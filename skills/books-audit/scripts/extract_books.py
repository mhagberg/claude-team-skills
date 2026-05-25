#!/usr/bin/env python3
"""Extract a read-only financial dossier for the books-audit skill.

Pulls a consistent snapshot from Odoo 18 (XML-RPC) for both audited companies
— Xcel Software (company_id=1) and HAGBERG CONSULTING LLC (company_id=4) — and
writes a single markdown dossier the 10 reviewer agents all read from. Querying
Odoo once (here) keeps every agent on the SAME numbers and avoids 10 agents
hammering the API with divergent queries.

READ-ONLY. This script never writes to Odoo.

Usage:
    python extract_books.py [OUTPUT_PATH]      # default: /tmp/books_dossier.md

Env (loaded from the parent project's .env, or cwd/.env, or ~/.env):
    ODOO_URL, ODOO_DB, ODOO_USERNAME (uid int), ODOO_PASSWORD (api key)
    AUDIT_FY_START   optional, default 2026-01-01 (P&L is fiscal-year-to-date)
"""
import os
import sys
import xmlrpc.client
from pathlib import Path
from datetime import date, datetime


def load_env():
    for p in [
        Path("/Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/.env"),
        Path.cwd() / ".env",
        Path.home() / ".env",
    ]:
        if p.exists():
            for line in p.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k, v.strip().strip('"').strip("'"))
            return str(p)
    return None


ENV_USED = load_env()
URL = os.environ["ODOO_URL"].rstrip("/")
DB = os.environ["ODOO_DB"]
UID = int(os.environ["ODOO_USERNAME"])
KEY = os.environ["ODOO_PASSWORD"]
M = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/object", allow_none=True)


def ex(model, method, *args, **kw):
    return M.execute_kw(DB, UID, KEY, model, method, list(args), kw)


COMPANIES = [(1, "Xcel Software"), (4, "HAGBERG CONSULTING LLC")]
FY_START = os.environ.get("AUDIT_FY_START", "2026-01-01")
TODAY = date.today()

INCOME_TYPES = {"income", "income_other"}
EXPENSE_TYPES = {"expense", "expense_depreciation", "expense_direct_cost"}
PL_TYPES = INCOME_TYPES | EXPENSE_TYPES
ASSET_TYPES = {"asset_receivable", "asset_cash", "asset_current",
               "asset_non_current", "asset_prepayments", "asset_fixed"}
LIAB_TYPES = {"liability_payable", "liability_credit_card",
              "liability_current", "liability_non_current"}
EQUITY_TYPES = {"equity", "equity_unaffected"}

CLEARING_HINTS = ("suspense", "outstanding", "liquidity", "transfer", "undeposited")


def m(x):
    return f"{(x or 0.0):>15,.2f}"


def age_bucket(d):
    if not d:
        return "no date"
    try:
        dd = datetime.strptime(d, "%Y-%m-%d").date()
    except Exception:
        return "no date"
    days = (TODAY - dd).days
    if days <= 30:
        return "0-30"
    if days <= 60:
        return "31-60"
    if days <= 90:
        return "61-90"
    return ">90"


def section(cid, name, out):
    out.append(f"\n\n{'=' * 92}")
    out.append(f"# {name}  (company_id={cid})")
    out.append(f"{'=' * 92}")

    # Odoo 18: account.account.code is computed per the active company, so we
    # must read it with that company in context or every code comes back "0".
    accs = ex("account.account", "search_read", [("company_ids", "in", [cid])],
              fields=["id", "code", "name", "account_type"],
              context={"allowed_company_ids": [cid]})
    meta = {a["id"]: a for a in accs}

    # ---- 1. Balance check (authoritative: total debit == total credit) ----
    g = ex("account.move.line", "read_group",
           [("company_id", "=", cid), ("parent_state", "=", "posted")],
           ["debit:sum", "credit:sum"], [])
    td = g[0]["debit"] or 0.0
    tc = g[0]["credit"] or 0.0
    out.append("\n## 1. Balance check — all posted journal entries")
    out.append(f"    Total debits : {m(td)}")
    out.append(f"    Total credits: {m(tc)}")
    flag = "BALANCED ✅" if abs(td - tc) < 0.01 else "*** OUT OF BALANCE — INVESTIGATE ***"
    out.append(f"    Difference   : {m(td - tc)}   {flag}")

    # draft (unposted) entries are a data-quality red flag for an audit
    n_draft = ex("account.move", "search_count",
                 [("company_id", "=", cid), ("state", "=", "draft"),
                  ("move_type", "!=", "entry")])
    n_draft_je = ex("account.move", "search_count",
                    [("company_id", "=", cid), ("state", "=", "draft"),
                     ("move_type", "=", "entry")])
    out.append(f"    Draft invoices/bills (unposted): {n_draft}")
    out.append(f"    Draft journal entries (unposted): {n_draft_je}")

    # ---- 2. Balance sheet rollup (all-time, posted) ----
    pa = ex("account.move.line", "read_group",
            [("company_id", "=", cid), ("parent_state", "=", "posted")],
            ["balance:sum"], ["account_id"], lazy=False)
    bal = {}
    for r in pa:
        if r.get("account_id"):
            bal[r["account_id"][0]] = r["balance"] or 0.0
    assets = sum(b for a, b in bal.items() if meta.get(a, {}).get("account_type") in ASSET_TYPES)
    liabs = sum(b for a, b in bal.items() if meta.get(a, {}).get("account_type") in LIAB_TYPES)
    equity = sum(b for a, b in bal.items() if meta.get(a, {}).get("account_type") in EQUITY_TYPES)
    out.append("\n## 2. Balance sheet (cumulative, posted) — display signs normalized")
    out.append(f"    Assets            : {m(assets)}")
    out.append(f"    Liabilities       : {m(-liabs)}")
    out.append(f"    Equity (excl. CY) : {m(-equity)}")
    out.append(f"    Assets − Liab − Equity = {m(assets + liabs + equity)}  "
               f"(should equal current-year net income below)")

    # ---- 3. P&L fiscal-year-to-date ----
    pl = ex("account.move.line", "read_group",
            [("company_id", "=", cid), ("parent_state", "=", "posted"),
             ("date", ">=", FY_START)],
            ["balance:sum"], ["account_id"], lazy=False)
    income = expense = 0.0
    pl_rows = []
    for r in pl:
        if not r.get("account_id"):
            continue
        aid = r["account_id"][0]
        t = meta.get(aid, {}).get("account_type")
        b = r["balance"] or 0.0
        if t in PL_TYPES:
            disp = -b if t in INCOME_TYPES else b
            pl_rows.append((meta[aid]["code"], meta[aid]["name"], t, disp))
            if t in INCOME_TYPES:
                income += -b
            else:
                expense += b
    net = income - expense
    out.append(f"\n## 3. Profit & Loss — FY-to-date (since {FY_START}, through {TODAY})")
    out.append(f"    Revenue        : {m(income)}")
    out.append(f"    Total expenses : {m(expense)}")
    out.append(f"    NET INCOME     : {m(net)}   "
               f"({'profit' if net >= 0 else 'LOSS'}; margin "
               f"{(net / income * 100) if income else 0:.1f}%)")
    out.append("\n    Top P&L accounts by magnitude:")
    out.append(f"    {'code':<8} {'type':<22} {'FYTD amount':>15}  name")
    for code, nm, t, disp in sorted(pl_rows, key=lambda x: -abs(x[3]))[:20]:
        out.append(f"    {code:<8} {t:<22} {m(disp)}  {nm[:42]}")

    # ---- 4. Clearing / suspense accounts (should be ~0 or in-transit) ----
    out.append("\n## 4. Clearing / suspense / transfer accounts (watch for stuck balances)")
    found = False
    for aid, b in sorted(bal.items(), key=lambda kv: -abs(kv[1])):
        info = meta.get(aid, {})
        nm = (info.get("name") or "").lower()
        if any(h in nm for h in CLEARING_HINTS):
            found = True
            out.append(f"    {info.get('code',''):<8} {m(b)}  {info.get('name','')[:50]}")
    if not found:
        out.append("    (none matched by name)")

    # ---- 5. Equity / distribution accounts ----
    out.append("\n## 5. Equity & distribution accounts (cumulative)")
    for aid, b in sorted(bal.items(), key=lambda kv: -abs(kv[1])):
        info = meta.get(aid, {})
        if info.get("account_type") in EQUITY_TYPES or "distribution" in (info.get("name") or "").lower():
            out.append(f"    {info.get('code',''):<8} {m(b)}  {info.get('name','')[:50]}")

    # ---- 6. Fixed assets ----
    fa = [(meta[a]["code"], meta[a]["name"], bal[a]) for a in bal
          if meta.get(a, {}).get("account_type") == "asset_fixed"]
    if fa:
        out.append("\n## 6. Fixed asset accounts")
        for code, nm, b in sorted(fa, key=lambda x: -abs(x[2])):
            out.append(f"    {code:<8} {m(b)}  {nm[:50]}")

    # ---- 7. AR aging ----
    def aging(account_type, label, sign):
        rows = ex("account.move.line", "search_read",
                  [("company_id", "=", cid),
                   ("account_id.account_type", "=", account_type),
                   ("parent_state", "=", "posted"),
                   ("amount_residual", "!=", 0),
                   ("reconciled", "=", False)],
                  fields=["move_name", "partner_id", "date_maturity", "date",
                          "amount_residual"], limit=500)
        buckets = {"0-30": 0.0, "31-60": 0.0, "61-90": 0.0, ">90": 0.0, "no date": 0.0}
        oldest = []
        for r in rows:
            amt = (r["amount_residual"] or 0.0) * sign
            buckets[age_bucket(r.get("date_maturity") or r.get("date"))] += amt
            oldest.append((r.get("date_maturity") or r.get("date"), amt,
                           (r["partner_id"][1] if r.get("partner_id") else "?"),
                           r.get("move_name")))
        out.append(f"\n## {label} aging  ({len(rows)} open line(s))")
        out.append(f"    0-30: {m(buckets['0-30'])}   31-60: {m(buckets['31-60'])}   "
                   f"61-90: {m(buckets['61-90'])}   >90: {m(buckets['>90'])}   "
                   f"no-date: {m(buckets['no date'])}")
        out.append(f"    TOTAL outstanding: {m(sum(buckets.values()))}")
        out.append("    Oldest 10:")
        for d, amt, p, mv in sorted(oldest, key=lambda x: (x[0] or "9999"))[:10]:
            out.append(f"      {str(d):<12} {m(amt)}  {str(p)[:34]:<34} {mv}")

    aging("asset_receivable", "7. Accounts Receivable", 1)
    aging("liability_payable", "8. Accounts Payable", -1)

    # ---- 9. Unreconciled bank statement lines ----
    bl = ex("account.bank.statement.line", "search_read",
            [("company_id", "=", cid), ("is_reconciled", "=", False)],
            fields=["date", "payment_ref", "amount", "journal_id"],
            order="date asc", limit=200)
    out.append(f"\n## 9. Unreconciled bank statement lines: {len(bl)}")
    for r in bl[:40]:
        j = r["journal_id"][1] if r.get("journal_id") else "?"
        out.append(f"    {r['date']} {m(r['amount'])}  {j[:20]:<20} {(r.get('payment_ref') or '')[:48]}")


def main():
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/books_dossier.md")
    out = []
    out.append("# FINANCIAL DOSSIER — books-audit snapshot")
    out.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")
    out.append(f"Odoo: {URL}  DB: {DB}  (env: {ENV_USED})")
    out.append(f"Fiscal-year-to-date P&L since: {FY_START}")
    for cid, name in COMPANIES:
        try:
            section(cid, name, out)
        except Exception as e:
            out.append(f"\n\n*** ERROR extracting {name} (company_id={cid}): {e!r}")
    text = "\n".join(out)
    out_path.write_text(text)
    print(text)
    print(f"\n\n[dossier written to {out_path}]")


if __name__ == "__main__":
    main()
