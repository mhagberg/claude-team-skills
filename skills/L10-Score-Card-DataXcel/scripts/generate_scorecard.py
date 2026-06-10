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
GA_WINDOW_DAYS = 28   # GA page-views/engagement use a trailing 28-day window
                      # (matches Mike's GA "Pages and screens" report Total),
                      # NOT the weekly window the other metrics use.

POSTHOG_HOST = "https://us.posthog.com"
POSTHOG_PROJECT_ID = 425826
POSTHOG_KEY_PATH = Path.home() / ".secrets" / "posthog-personal-api-key"

LINEAR_KEY_PATH = Path.home() / ".secrets" / "linear-api-key"  # fallback; env LINEAR_API_KEY wins
LINEAR_TEAM_KEY = "SAG"                    # SageXcel team (NOT a project)
# Data Inaccuracies = not-done issues labeled with any of these; Pending Reports
# = the remaining not-done issues in the active cycle.
LINEAR_INACCURACY_LABELS = ["bug", "inaccurac"]

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
    # DataXcel quotes created in the window (any non-cancelled state). A quote is
    # "DataXcel" when at least one line carries a DataXcel-named product
    # (excludes generic dev/bidding quotes like Custom Software Development Hours).
    src = "Odoo sale.order (DataXcel quotes)"
    cand = oex("sale.order", "search_read",
               [("company_id", "=", ODOO_COMPANY_ID), ("state", "!=", "cancel"),
                ("create_date", ">=", s), ("create_date", "<=", e + " 23:59:59")],
               ["id", "amount_total"])
    if not cand:
        return (0, 0.0), src
    ids = [c["id"] for c in cand]
    dx = oex("sale.order.line", "search_read",
             [("order_id", "in", ids), ("product_id.name", "ilike", "DataXcel")],
             ["order_id"])
    dx_ids = {l["order_id"][0] for l in dx}
    dollars = sum(c["amount_total"] for c in cand if c["id"] in dx_ids)
    return (len(dx_ids), round(dollars, 2)), src

def m_hours_billed(s, e):
    # posted customer invoices in window; exclude subscription (recurring) product lines
    invs = oex("account.move", "search_read",
               [("company_id", "=", ODOO_COMPANY_ID), ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"), ("invoice_date", ">=", s), ("invoice_date", "<=", e)],
               ["id"])
    ids = [i["id"] for i in invs]
    src = "Odoo invoices (hourly dev work)"
    if not ids:
        return (0, 0.0), src
    # hourly dev lines = product whose name contains "Hour" (Custom Software
    # Development Hours, Odoo Development Hours). Excludes subscriptions/setup/hosting.
    # NOTE Odoo 18 product lines have display_type='product' (NOT False).
    lines = oex("account.move.line", "search_read",
                [("move_id", "in", ids), ("display_type", "=", "product"),
                 ("product_id.name", "ilike", "Hour")],
                ["quantity", "price_subtotal"])
    hrs = sum(l["quantity"] for l in lines)
    amt = sum(l["price_subtotal"] for l in lines)
    return (round(hrs, 1), round(amt, 2)), src

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
    src = f"GA4 (trailing {GA_WINDOW_DAYS}d)"
    if not r.rows:
        return (0, 0.0), src
    pv, eng, users = (float(r.rows[0].metric_values[i].value) for i in range(3))
    return (int(pv), round(eng / users, 1) if users else 0.0), src

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
    key = os.environ.get("LINEAR_API_KEY") or LINEAR_KEY_PATH.read_text().strip()
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
    SageXcel TEAM's active cycle. Data Inaccuracies = Bug-labeled; Pending
    Reports = the rest."""
    d = _linear('{ teams(filter:{key:{eq:"%s"}}){ nodes { id } } }' % LINEAR_TEAM_KEY)
    nodes = d["teams"]["nodes"]
    if not nodes:
        raise RuntimeError("SageXcel team not found")
    tid = nodes[0]["id"]
    d = _linear('{ team(id:"%s"){ issues(filter:{state:{type:{nin:["completed","canceled"]}},'
                'cycle:{isActive:{eq:true}}}, first:250){ nodes { id labels{ nodes{ name } } } } } }'
                % tid)
    issues = d["team"]["issues"]["nodes"]
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

def _num(v):
    """(raw, pretty) for a count/number — raw is paste-clean (no commas)."""
    if isinstance(v, float):
        if v == int(v):
            return str(int(v)), f"{int(v):,}"
        return f"{v:.1f}", f"{v:,.1f}"
    return str(int(v)), f"{int(v):,}"

def _money(v):
    raw = str(int(v)) if v == int(v) else f"{v:.2f}"
    return raw, f"${v:,.2f}"

def build_rows(s, e, demos, pending_override, inacc_override):
    """Returns (rows, extras). rows = the 13 scorecard rows in Mike's EXACT order
    and labels: (category, metric, raw_value, pretty_value, source, ok).
    extras = supplementary PostHog figures (not in the canonical 13)."""
    nql, e1 = safe(m_new_qualified_leads, s, e)
    ref, e2 = safe(m_referrals, s, e)
    # GA uses a trailing 28-day window (matches Mike's GA report), not the week
    ga_s = (datetime.strptime(e, "%Y-%m-%d").date() - timedelta(days=GA_WINDOW_DAYS - 1)).isoformat()
    ga, e4 = safe(m_ga, ga_s, e)         # ((pv, eng), src)
    ph, e5 = safe(m_posthog, s, e)       # ((pv, eng), src)
    hb, e6 = safe(m_hours_billed, s, e)  # ((hrs, $), src)
    quo, e7 = safe(m_quotations, s, e)   # ((cnt, $), src)
    lin, e8 = safe(m_linear_dev)         # ((pending, inacc), src)
    paid, e9 = safe(m_paid_users, s, e)

    NA = ("N/A", "N/A")
    def n(res, err, idx=None, fn=_num):
        if err:
            return NA + ("", False)
        val, src = res
        if idx is not None:
            val = val[idx]
        raw, pretty = fn(val)
        return raw, pretty, src, False if err else True

    rows = []
    rows.append(("DataXcel Sales", "New Qualified Leads", *n(nql, e1)))
    rows.append(("DataXcel Sales", "# of referrals", *n(ref, e2)))
    rows.append(("DataXcel GA Page Views", "GA Number of Page Views", *n(ga, e4, 0)))
    rows.append(("DataXcel GA", "Avg Engagement time per active user in Seconds", *n(ga, e4, 1)))
    if demos is None:
        rows.append(("DataXcel Sales", "Number of Demos", "N/A", "N/A", "", False))
    else:
        r, p = _num(demos)
        rows.append(("DataXcel Sales", "Number of Demos", r, p, "Google Calendar", True))
    rows.append(("DataXcel Sales", "Hours Billed (#)", *n(hb, e6, 0)))
    rows.append(("DataXcel Sales", "Hours Billed ($)", *n(hb, e6, 1, _money)))
    # Pending Reports (Linear, or manual override)
    if pending_override is not None:
        r, p = _num(pending_override)
        rows.append(("DataXcel Development", "Pending Reports", r, p, "manual", True))
    else:
        rows.append(("DataXcel Development", "Pending Reports", *n(lin, e8, 0)))
    rows.append(("DataXcel Sales", "Quotations Sent (#)", *n(quo, e7, 0)))
    rows.append(("DataXcel Sales", "Quotations Sent ($)", *n(quo, e7, 1, _money)))
    if inacc_override is not None:
        r, p = _num(inacc_override)
        rows.append(("DataXcel Development", "Data inaccuracies Reported", r, p, "manual", True))
    else:
        rows.append(("DataXcel Development", "Data inaccuracies Reported", *n(lin, e8, 1)))
    rows.append(("DataXcel", "Paid Logged in Users/Week", *n(paid, e9)))

    extras = []
    if e5:
        extras.append(("PostHog Page Views", "N/A", "", False))
        extras.append(("PostHog Avg Engagement (s)", "N/A", "", False))
    else:
        (pv, avg), src = ph
        extras.append(("PostHog Page Views", _num(pv)[1], src, True))
        extras.append(("PostHog Avg Engagement (s)", _num(avg)[1], src, True))
    return rows, extras

def render_html(rows, extras, s, e):
    # 1) Copy/paste table — Category | Metric | Value, in exact order, plain.
    cp = "".join(
        f'<tr><td style="border:1px solid #d6dde6;padding:6px 10px;">{cat}</td>'
        f'<td style="border:1px solid #d6dde6;padding:6px 10px;">{metric}</td>'
        f'<td style="border:1px solid #d6dde6;padding:6px 10px;">{raw}</td></tr>'
        for cat, metric, raw, pretty, src, ok in rows)
    # 2) Pretty table
    pretty_rows = "".join(
        f'<tr><td style="padding:11px 14px;border-bottom:1px solid #eef2f6;color:#52606d;font-size:12px;">{cat}</td>'
        f'<td style="padding:11px 14px;border-bottom:1px solid #eef2f6;">{metric}</td>'
        f'<td align="right" style="padding:11px 14px;border-bottom:1px solid #eef2f6;font-weight:700;'
        f'{"color:#b91c1c;font-weight:500;" if not ok else "color:#0b5fff;"}">{pretty}</td></tr>'
        for cat, metric, raw, pretty, src, ok in rows)
    extra_rows = "".join(
        f'<tr><td style="padding:9px 14px;border-bottom:1px solid #eef2f6;color:#7c3aed;font-size:12px;">PostHog (extra)</td>'
        f'<td style="padding:9px 14px;border-bottom:1px solid #eef2f6;">{m}</td>'
        f'<td align="right" style="padding:9px 14px;border-bottom:1px solid #eef2f6;font-weight:700;'
        f'{"color:#b91c1c;font-weight:500;" if not ok else "color:#7c3aed;"}">{v}</td></tr>'
        for m, v, src, ok in extras)
    notes = "".join(
        f"<li><b>{metric}</b>: {src}</li>"
        for cat, metric, raw, pretty, src, ok in rows if ok and src)
    na = [metric for cat, metric, raw, pretty, src, ok in rows if not ok]
    na_html = ("<div style='background:#fef2f2;border:1px solid #f5c2c2;border-radius:8px;"
               "padding:12px 16px;margin:18px 0;color:#9b1c1c;font-size:13px;'>"
               "<b>Needs attention (N/A):</b> " + ", ".join(na) + "</div>") if na else ""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>DataXcel L10 Scorecard — {s} to {e}</title></head>
<body style="margin:0;background:#f4f6f8;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#1f2933;">
<div style="max-width:760px;margin:0 auto;padding:24px;">
  <div style="background:#0b1f44;color:#fff;border-radius:12px;padding:22px 28px;margin-bottom:20px;">
    <div style="font-size:22px;font-weight:800;">DataXcel — L10 Scorecard</div>
    <div style="color:#9db8ff;font-size:14px;margin-top:4px;">Week of {s} → {e}</div>
  </div>

  <div style="font-size:13px;font-weight:700;color:#52606d;margin:0 0 6px;">📋 COPY / PASTE (select the table)</div>
  <table cellspacing="0" cellpadding="0" style="border-collapse:collapse;font-size:13px;width:100%;background:#fff;margin-bottom:28px;">
    <tr style="background:#eef2f7;font-weight:700;">
      <td style="border:1px solid #d6dde6;padding:6px 10px;">Category</td>
      <td style="border:1px solid #d6dde6;padding:6px 10px;">Metric</td>
      <td style="border:1px solid #d6dde6;padding:6px 10px;">Value</td>
    </tr>
    {cp}
  </table>

  {na_html}

  <div style="font-size:13px;font-weight:700;color:#52606d;margin:0 0 6px;">✨ SCORECARD</div>
  <table width="100%" cellspacing="0" cellpadding="0" style="border:1px solid #e6ebf2;border-radius:8px;font-size:14px;background:#fff;">
    {pretty_rows}{extra_rows}
  </table>

  <details style="margin-top:16px;font-size:12px;color:#52606d;">
    <summary style="cursor:pointer;font-weight:600;">Sources</summary>
    <ul style="margin:8px 0 0;padding-left:20px;">{notes}</ul>
  </details>
  <div style="text-align:center;color:#9aa5b1;font-size:11px;margin-top:18px;">
    Generated by the L10-Score-Card-DataXcel skill</div>
</div></body></html>"""

def default_window():
    # CURRENT week (Mon–Sun containing today) — the live L10 week. Future days in
    # the week simply have no data yet. Use --start/--end for any other week.
    today = date.today()
    mon = today - timedelta(days=today.weekday())
    return mon.isoformat(), (mon + timedelta(days=6)).isoformat()

def main():
    ds, de = default_window()
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=ds); ap.add_argument("--end", default=de)
    ap.add_argument("--demos", type=int, default=None)
    ap.add_argument("--pending-reports", type=int, default=None)
    ap.add_argument("--data-inaccuracies", type=int, default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-open", action="store_true", help="do NOT auto-open the HTML")
    a = ap.parse_args()
    rows, extras = build_rows(a.start, a.end, a.demos, a.pending_reports, a.data_inaccuracies)
    out = a.out or str(Path.home() / "Downloads" / f"l10_scorecard_{a.start}_{a.end}.html")
    Path(out).write_text(render_html(rows, extras, a.start, a.end))
    if not a.no_open:
        import subprocess
        try:
            subprocess.run(["open", out], check=False)
        except Exception:
            pass
    summary = {"start": a.start, "end": a.end, "out": out,
               "rows": [{"category": c, "metric": m, "value": raw, "source": src, "ok": ok}
                        for c, m, raw, pretty, src, ok in rows]}
    print(json.dumps(summary, indent=2) if a.json else f"Wrote {out}")
    miss = [r["metric"] for r in summary["rows"] if not r["ok"]]
    if miss:
        print("NEEDS ATTENTION: " + ", ".join(miss), file=sys.stderr)

if __name__ == "__main__":
    main()
