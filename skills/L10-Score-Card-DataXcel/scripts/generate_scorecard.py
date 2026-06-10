#!/usr/bin/env python3
"""L10 Score Card — DataXcel weekly scorecard generator.

Pulls weekly metrics from Odoo (XML-RPC), Google Analytics (GA4), PostHog,
and Linear, then renders a single self-contained HTML scorecard for Mike's
weekly L10 meeting.

Demos come from Google Calendar (the agent passes --demos N because GCal is an
MCP tool, not an HTTP API wired here).

Every metric is computed inside its own try/except — a dead source shows
"N/A — <reason>" rather than killing the whole report.

Run with the PARENT project's venv so GA4 / requests are importable:
    /Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/.venv/bin/python \
        generate_scorecard.py [--start YYYY-MM-DD --end YYYY-MM-DD] \
        [--demos N] [--pending-reports N] [--data-inaccuracies N] [--out PATH]

Default window = previous completed Mon–Sun.
"""
import os, sys, json, argparse, urllib.request, urllib.error
from pathlib import Path
from datetime import date, datetime, timedelta

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG  (confirm the ⚠️ items with Mike)
# ─────────────────────────────────────────────────────────────────────────────
ODOO_COMPANY_ID = 1                       # Xcel Software

# ⚠️ Referral CRM tags — best-match to ASG / RKL / Wright Office Solutions /
#    CBSL / SeverNova. Confirm IDs (CBS vs CBSL, ServerNoav vs SeverNova).
REFERRAL_TAG_IDS = [13, 27, 35, 80, 41]   # ASG, rkl, Wright Solutions, CBS, ServerNoav

# Qualified-or-beyond CRM stages (a "new qualified lead" = opp created in window)
QUALIFIED_STAGE_IDS = [2, 130, 117, 118, 119, 3, 4]   # Qualified, Qualified(email), Discovery.., Negotiation, Won..

GA_PROPERTY = "483003616"
GA_CREDS = str(Path.home() / ".secrets" / "ga4-reader.json")

POSTHOG_HOST = "https://us.posthog.com"
POSTHOG_PROJECT_ID = 425826
POSTHOG_KEY_PATH = Path.home() / ".secrets" / "posthog-personal-api-key"

LINEAR_KEY_PATH = Path.home() / ".secrets" / "linear-api-key"
LINEAR_PROJECT_MATCH = "sage"             # SageXcel project (containsIgnoreCase)
# ⚠️ label split: Data Inaccuracies = issues whose label matches one of these;
#    Pending Reports = the remaining not-done issues in the cycle.
LINEAR_INACCURACY_LABELS = ["inaccurac", "bug", "data"]

PARENT = Path("/Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting")

# ─────────────────────────────────────────────────────────────────────────────
# Env / Odoo
# ─────────────────────────────────────────────────────────────────────────────
def load_env():
    for p in [PARENT / ".env", PARENT / "odoo-bank-reconciliation" / ".env",
              Path.cwd() / ".env", Path.home() / ".env"]:
        if p.exists():
            for line in p.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k, v.strip().strip('"').strip("'"))
            return
load_env()

import xmlrpc.client
_OD = None
def odoo():
    global _OD
    if _OD is None:
        url = os.environ["ODOO_URL"].rstrip("/")
        _OD = (xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", allow_none=True),
               os.environ["ODOO_DB"], int(os.environ["ODOO_USERNAME"]), os.environ["ODOO_PASSWORD"])
    return _OD
def oex(model, method, *args, **kw):
    m, db, uid, key = odoo()
    return m.execute_kw(db, uid, key, model, method, list(args), kw)

# ─────────────────────────────────────────────────────────────────────────────
# Metric collectors  (each returns (value, source) or raises)
# ─────────────────────────────────────────────────────────────────────────────
def m_new_qualified_leads(s, e):
    n = oex("crm.lead", "search_count",
            [("company_id", "=", ODOO_COMPANY_ID), ("type", "=", "opportunity"),
             ("create_date", ">=", s), ("create_date", "<=", e + " 23:59:59"),
             ("stage_id", "in", QUALIFIED_STAGE_IDS)])
    return n, "Odoo CRM"

def m_referrals(s, e):
    n = oex("crm.lead", "search_count",
            [("company_id", "=", ODOO_COMPANY_ID),
             ("create_date", ">=", s), ("create_date", "<=", e + " 23:59:59"),
             ("tag_ids", "in", REFERRAL_TAG_IDS)])
    return n, "Odoo CRM (tags ASG/RKL/Wright/CBS/ServerNova)"

def m_odoo_page_views(s, e):
    for fld in ("visit_datetime", "create_date"):
        try:
            n = oex("website.track", "search_count",
                    [(fld, ">=", s), (fld, "<=", e + " 23:59:59")])
            return n, f"Odoo website.track ({fld})"
        except Exception:
            continue
    raise RuntimeError("website.track unavailable")

def m_quotations(s, e):
    so = oex("sale.order", "search_read",
             [("company_id", "=", ODOO_COMPANY_ID), ("state", "in", ["sent", "sale", "done"]),
              ("create_date", ">=", s), ("create_date", "<=", e + " 23:59:59")],
             ["amount_total"])
    return (len(so), round(sum(o["amount_total"] for o in so), 2)), "Odoo sale.order"

def m_hours_billed(s, e):
    # posted customer invoices in window; exclude subscription (recurring) product lines
    invs = oex("account.move", "search_read",
               [("company_id", "=", ODOO_COMPANY_ID), ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"), ("invoice_date", ">=", s), ("invoice_date", "<=", e)],
               ["id"])
    ids = [i["id"] for i in invs]
    if not ids:
        return (0, 0.0), "Odoo invoices (dev, excl. subscriptions)"
    lines = oex("account.move.line", "search_read",
                [("move_id", "in", ids), ("display_type", "=", False),
                 ("product_id", "!=", False)],
                ["quantity", "price_subtotal", "product_id"])
    prod_ids = list({l["product_id"][0] for l in lines})
    recurring = {p["id"] for p in oex("product.product", "search_read",
                 [("id", "in", prod_ids), ("recurring_invoice", "=", True)], ["id"])}
    hrs = sum(l["quantity"] for l in lines if l["product_id"][0] not in recurring)
    amt = sum(l["price_subtotal"] for l in lines if l["product_id"][0] not in recurring)
    return (round(hrs, 1), round(amt, 2)), "Odoo invoices (dev, excl. subscriptions)"

def _ga_client():
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.oauth2 import service_account
    creds = service_account.Credentials.from_service_account_file(GA_CREDS)
    return BetaAnalyticsDataClient(credentials=creds)

def m_ga(s, e):
    from google.analytics.data_v1beta.types import DateRange, Metric, RunReportRequest
    cli = _ga_client()
    req = RunReportRequest(property=f"properties/{GA_PROPERTY}",
        metrics=[Metric(name="screenPageViews"), Metric(name="userEngagementDuration"),
                 Metric(name="activeUsers")],
        date_ranges=[DateRange(start_date=s, end_date=e)])
    r = cli.run_report(req)
    if not r.rows:
        return (0, 0.0), "GA4"
    pv, eng, users = (float(r.rows[0].metric_values[i].value) for i in range(3))
    return (int(pv), round(eng / users, 1) if users else 0.0), "GA4"

def _posthog_query(hogql):
    key = POSTHOG_KEY_PATH.read_text().strip()
    req = urllib.request.Request(f"{POSTHOG_HOST}/api/projects/{POSTHOG_PROJECT_ID}/query/",
        data=json.dumps({"query": {"kind": "HogQLQuery", "query": hogql}}).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req)).get("results", [])

def m_posthog(s, e):
    # page views + avg engagement (avg session duration, seconds) over window
    end_excl = (datetime.strptime(e, "%Y-%m-%d").date() + timedelta(days=1)).isoformat()
    win = (f"timestamp >= toDateTime('{s} 00:00:00') "
           f"AND timestamp < toDateTime('{end_excl} 00:00:00')")
    pv = _posthog_query(f"SELECT count() FROM events WHERE event='$pageview' AND {win}")
    views = int(pv[0][0]) if pv and pv[0] else 0
    avg = 0.0
    try:
        eng = _posthog_query(
            f"SELECT round(avg(session.$session_duration)) FROM events "
            f"WHERE event='$pageview' AND {win}")
        if eng and eng[0] and eng[0][0] is not None:
            avg = round(float(eng[0][0]), 1)
    except Exception:
        pass
    return (views, avg), "PostHog"

def _linear(q):
    key = LINEAR_KEY_PATH.read_text().strip()
    req = urllib.request.Request("https://api.linear.app/graphql",
        data=json.dumps({"query": q}).encode(),
        headers={"Authorization": key, "Content-Type": "application/json"})
    try:
        r = json.load(urllib.request.urlopen(req))
    except urllib.error.HTTPError as ex:
        raise RuntimeError(f"Linear HTTP {ex.code}: {ex.read().decode()[:80]}")
    if r.get("errors"):
        raise RuntimeError("Linear: " + r["errors"][0].get("message", "error"))
    return r["data"]

def m_linear_dev():
    """Returns (pending_reports, data_inaccuracies) — not-done issues in the
    current cycle of the SageXcel project, split by label."""
    d = _linear('{ projects(filter:{name:{containsIgnoreCase:"%s"}}){ nodes { id name } } }'
                % LINEAR_PROJECT_MATCH)
    nodes = d["projects"]["nodes"]
    if not nodes:
        raise RuntimeError("SageXcel project not found")
    pid = nodes[0]["id"]
    d = _linear('{ project(id:"%s"){ issues(filter:{state:{type:{nin:["completed","canceled"]}},'
                'cycle:{isActive:{eq:true}}}, first:250){ nodes { id title labels{ nodes{ name } } } } } }'
                % pid)
    issues = d["project"]["issues"]["nodes"]
    inacc = [i for i in issues if any(any(t in l["name"].lower() for t in LINEAR_INACCURACY_LABELS)
                                      for l in i["labels"]["nodes"])]
    return (len(issues) - len(inacc), len(inacc)), "Linear (SageXcel active cycle, not done)"

def m_paid_users(s, e):
    """Weekly active customer users across paid Metabase instances."""
    utp = PARENT / "dataxcel-user-tracking"
    sys.path.insert(0, str(utp))
    import yaml  # noqa
    from collector.db import get_conn
    from collector.queries import get_weekly_active_users_customer
    cfg = yaml.safe_load((utp / "config" / "instances.yaml").read_text())
    host = cfg["rds_host"]; port = cfg.get("rds_port", 5432)
    total = 0
    for inst in cfg.get("instances", []):
        if "(Internal)" in str(inst.get("customer", "")):
            continue
        cm = get_conn(host, port, inst["db"], inst["user"], inst["password"])
        # get_conn is a @contextmanager -> use with-block
        with cm as conn:
            rows = get_weekly_active_users_customer(conn, 7)
            total += len(rows) if hasattr(rows, "__len__") else sum(1 for _ in rows)
    return total, "Metabase RDS (weekly-active customer users)"

# ─────────────────────────────────────────────────────────────────────────────
# Orchestration + HTML
# ─────────────────────────────────────────────────────────────────────────────
def safe(fn, *a):
    try:
        return fn(*a), None
    except Exception as ex:
        return None, f"{type(ex).__name__}: {ex}"[:120]

def fmt(v):
    if isinstance(v, float):
        return f"{v:,.1f}"
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)

def build_rows(s, e, demos, pending_override, inacc_override):
    R = []  # (category, metric, value_str, source, ok)
    def add(cat, metric, res, err, suffix=""):
        if err:
            R.append((cat, metric, f"N/A — {err}", "", False))
        else:
            val, src = res
            R.append((cat, metric, fmt(val) + suffix, src, True))

    add("Sales", "New Qualified Leads", *safe(m_new_qualified_leads, s, e))
    add("Sales", "# of Referrals", *safe(m_referrals, s, e))
    # demos from agent / GCal
    if demos is None:
        R.append(("Sales", "Number of Demos", "N/A — pass --demos from GCal", "", False))
    else:
        R.append(("Sales", "Number of Demos", fmt(demos), "Google Calendar", True))
    q, qe = safe(m_quotations, s, e)
    if qe:
        R.append(("Sales", "Quotations Sent (#)", f"N/A — {qe}", "", False))
        R.append(("Sales", "Quotations Sent ($)", f"N/A — {qe}", "", False))
    else:
        (cnt, dollars), src = q
        R.append(("Sales", "Quotations Sent (#)", fmt(cnt), src, True))
        R.append(("Sales", "Quotations Sent ($)", "$" + fmt(round(dollars, 2)), src, True))
    h, he = safe(m_hours_billed, s, e)
    if he:
        R.append(("Sales", "Hours Billed (#)", f"N/A — {he}", "", False))
        R.append(("Sales", "Hours Billed ($)", f"N/A — {he}", "", False))
    else:
        (hrs, amt), src = h
        R.append(("Sales", "Hours Billed (#)", fmt(hrs), src, True))
        R.append(("Sales", "Hours Billed ($)", "$" + fmt(round(amt, 2)), src, True))

    add("Marketing", "Odoo Page Views", *safe(m_odoo_page_views, s, e))
    ga, gae = safe(m_ga, s, e)
    if gae:
        R.append(("Marketing", "GA Page Views", f"N/A — {gae}", "", False))
        R.append(("Marketing", "GA Avg Engagement / user (s)", f"N/A — {gae}", "", False))
    else:
        (pv, avg), src = ga
        R.append(("Marketing", "GA Page Views", fmt(pv), src, True))
        R.append(("Marketing", "GA Avg Engagement / user (s)", fmt(avg) + "s", src, True))
    ph, phe = safe(m_posthog, s, e)
    if phe:
        R.append(("Marketing", "PostHog Page Views", f"N/A — {phe}", "", False))
        R.append(("Marketing", "PostHog Avg Engagement (s)", f"N/A — {phe}", "", False))
    else:
        (pv, avg), src = ph
        R.append(("Marketing", "PostHog Page Views", fmt(pv), src, True))
        R.append(("Marketing", "PostHog Avg Engagement (s)", fmt(avg) + "s", src, True))

    dev, deve = safe(m_linear_dev)
    if pending_override is not None or inacc_override is not None:
        R.append(("Development", "Pending Reports",
                  fmt(pending_override) if pending_override is not None else "N/A", "manual", pending_override is not None))
        R.append(("Development", "Data Inaccuracies Reported",
                  fmt(inacc_override) if inacc_override is not None else "N/A", "manual", inacc_override is not None))
    elif deve:
        R.append(("Development", "Pending Reports", f"N/A — {deve}", "", False))
        R.append(("Development", "Data Inaccuracies Reported", f"N/A — {deve}", "", False))
    else:
        (pend, inacc), src = dev
        R.append(("Development", "Pending Reports", fmt(pend), src, True))
        R.append(("Development", "Data Inaccuracies Reported", fmt(inacc), src, True))

    add("Usage", "Paid Logged-in Users / Week", *safe(m_paid_users, s, e))
    return R

CAT_COLOR = {"Sales": "#0b5fff", "Marketing": "#7c3aed", "Development": "#0891b2", "Usage": "#16a34a"}

def render_html(rows, s, e):
    cats = {}
    for cat, metric, val, src, ok in rows:
        cats.setdefault(cat, []).append((metric, val, src, ok))
    blocks = []
    for cat, items in cats.items():
        c = CAT_COLOR.get(cat, "#334155")
        trs = "".join(
            f'<tr><td style="padding:11px 14px;border-bottom:1px solid #eef2f6;">{m}</td>'
            f'<td align="right" style="padding:11px 14px;border-bottom:1px solid #eef2f6;font-weight:700;'
            f'{"color:#b91c1c;font-weight:500;font-size:12px;" if not ok else f"color:{c};"}">{v}</td>'
            f'<td style="padding:11px 14px;border-bottom:1px solid #eef2f6;color:#8a94a6;font-size:11px;">{src}</td></tr>'
            for m, v, src, ok in items)
        blocks.append(
            f'<div style="margin:0 0 22px;"><div style="background:{c};color:#fff;padding:9px 14px;'
            f'border-radius:8px 8px 0 0;font-weight:700;font-size:14px;">{cat}</div>'
            f'<table width="100%" cellspacing="0" cellpadding="0" style="border:1px solid #e6ebf2;'
            f'border-top:none;border-radius:0 0 8px 8px;font-size:14px;">{trs}</table></div>')
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>DataXcel L10 Scorecard — {s} to {e}</title></head>
<body style="margin:0;background:#f4f6f8;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#1f2933;">
<div style="max-width:720px;margin:0 auto;padding:24px;">
  <div style="background:#0b1f44;color:#fff;border-radius:12px;padding:24px 28px;margin-bottom:22px;">
    <div style="font-size:22px;font-weight:800;">DataXcel — L10 Scorecard</div>
    <div style="color:#9db8ff;font-size:14px;margin-top:4px;">Week of {s} → {e}</div>
  </div>
  {''.join(blocks)}
  <div style="text-align:center;color:#9aa5b1;font-size:11px;margin-top:18px;">
    Generated by the L10-Score-Card-DataXcel skill</div>
</div></body></html>"""

def prev_week():
    today = date.today()
    last_sun = today - timedelta(days=(today.weekday() + 1))  # most recent Sunday
    return (last_sun - timedelta(days=6)).isoformat(), last_sun.isoformat()

def main():
    ds, de = prev_week()
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=ds); ap.add_argument("--end", default=de)
    ap.add_argument("--demos", type=int, default=None)
    ap.add_argument("--pending-reports", type=int, default=None)
    ap.add_argument("--data-inaccuracies", type=int, default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    rows = build_rows(a.start, a.end, a.demos, a.pending_reports, a.data_inaccuracies)
    out = a.out or str(Path.home() / "Downloads" / f"l10_scorecard_{a.start}_{a.end}.html")
    Path(out).write_text(render_html(rows, a.start, a.end))
    summary = {"start": a.start, "end": a.end, "out": out,
               "rows": [{"category": c, "metric": m, "value": v, "source": s, "ok": ok}
                        for c, m, v, s, ok in rows]}
    print(json.dumps(summary, indent=2) if a.json else f"Wrote {out}")
    miss = [r["metric"] for r in summary["rows"] if not r["ok"]]
    if miss:
        print("NEEDS ATTENTION: " + ", ".join(miss), file=sys.stderr)

if __name__ == "__main__":
    main()
