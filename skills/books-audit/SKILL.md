---
name: books-audit
description: Spawn 10 independent agents in parallel to audit the Xcel Software (company_id=1) and HAGBERG CONSULTING LLC (company_id=4) books in Odoo 18 — balance integrity, bookkeeping mistakes, tax deductions/advantages, and tax red flags — then return a consolidated report with a P&L summary and a CFO/CTO performance perspective. Use when the user asks to "audit our books", "books audit", "financial audit", "find tax deductions/red flags", or runs /books-audit.
---

# books-audit

You are running the **books-audit** skill. Your job is to spawn **10 independent
auditor agents in parallel** over a single, consistent financial snapshot of the
two companies, then consolidate their findings into one report. **Do not audit
the books yourself** — your role is to extract the snapshot, orchestrate the 10
agents, and synthesize their returns.

The two audited companies are fixed:
- **Xcel Software** — `company_id=1` (LLC)
- **HAGBERG CONSULTING LLC** — `company_id=4` (S-Corp)

## CRITICAL: this is a READ-ONLY audit

Neither you nor any agent may modify Odoo. No `create`, `write`, `unlink`,
`action_post`, `button_draft`, `reconcile`, or `remove_move_reconcile`. Auditing
is observation only. Put this prohibition in every agent prompt.

## Step 1 — extract the financial dossier (you do this once)

Run the bundled extractor. It pulls one consistent snapshot for BOTH companies
(trial-balance/balance check, balance sheet, FY-to-date P&L, clearing/suspense
accounts, equity & distributions, fixed assets, AR & AP aging, unreconciled bank
lines) and writes it to a file all 10 agents will read:

```bash
PYTHON=/Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/.venv/bin/python
SKILL_DIR="$HOME/.claude/skills/books-audit"
$PYTHON "$SKILL_DIR/scripts/extract_books.py" /tmp/books_dossier.md
```

The extractor loads Odoo creds from the parent project's `.env`
(`/Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/.env`). If the
`.venv` is missing, fall back to any python with `xmlrpc.client` (stdlib only —
no third-party deps needed). If the extractor errors on connection, stop and
report it — do not spawn agents against no data.

After it runs, print a one-line scope summary so the user sees what's being
audited, e.g.:
`Auditing Xcel (net +$122,631 FYTD, balanced) and Hagberg (net −$47,034 FYTD, balanced) — dossier at /tmp/books_dossier.md. Spawning 10 auditors.`

## Step 2 — spawn 10 auditors in ONE message

This is the most important step. **All 10 `Agent` tool-use blocks MUST appear in
a single assistant message** — sequential calls defeat the skill. Use
`subagent_type: general-purpose` for all ten.

Each agent reads the dossier from `/tmp/books_dossier.md` and may run its OWN
read-only supplementary queries via XML-RPC using this snippet (give it to every
agent verbatim):

````
Read /tmp/books_dossier.md first. For any drill-down, run READ-ONLY XML-RPC:

    import os, xmlrpc.client
    from pathlib import Path
    for line in Path("/Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/.env").read_text().splitlines():
        line=line.strip()
        if line and not line.startswith("#") and "=" in line:
            k,v=line.split("=",1); os.environ.setdefault(k, v.strip().strip('"').strip("'"))
    URL=os.environ["ODOO_URL"].rstrip("/"); DB=os.environ["ODOO_DB"]
    UID=int(os.environ["ODOO_USERNAME"]); KEY=os.environ["ODOO_PASSWORD"]
    M=xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/object", allow_none=True)
    def ex(model,method,*a,**k): return M.execute_kw(DB,UID,KEY,model,method,list(a),k)
    # READ-ONLY methods only: search_read, read, read_group, search_count, fields_get.
    # account.account.code resolves per company -> pass context={"allowed_company_ids":[cid]}.
    # Run with the project venv: /Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/.venv/bin/python
    # NEVER call create/write/unlink/action_post/button_draft/reconcile/remove_move_reconcile.

Useful IDs — Xcel (company_id=1): accounts 45 KeyBank, 49 Outstanding Receipts,
50 Outstanding Payments, 7 AR, 8/16 AP, 142 Capital One CC, 297 Software Subs,
213 Stan Distributions, 214 Mike Distributions. Journals: 6 Key Checking,
11 Salaries, 13 Capital One CC. Hagberg (company_id=4): see the dossier's
account list; Chase Blueberg Checking = journal 53, Delta Platinum = journal 47.
````

The per-agent prompt template:

```
You are Auditor {N} of 10 performing an INDEPENDENT financial audit of two
companies in Odoo 18: Xcel Software (company_id=1, LLC) and HAGBERG CONSULTING
LLC (company_id=4, S-Corp). You are NOT collaborating with the other auditors —
give your honest, focused read in your assigned lens.

READ-ONLY. Never modify Odoo (no create/write/unlink/post/draft/reconcile).

Your assigned lens: {LENS}
Stay primarily in your lens; if you spot something egregious outside it, note it
under FINDINGS tagged [CROSS-LENS].

{the read-only access snippet above}

Quantify everything you can (accounts, move names, $ amounts, company). For tax
lenses, estimate the dollar/again impact and cite the rule (IRC section / form)
where you can. Be specific and skeptical — a vague finding is useless.

Return EXACTLY this format and nothing else:

RATING: <integer 1-10; 10 = clean/healthy in my lens, 1 = serious problems>
FINDINGS:
- [SEVERITY] (company) <one-line finding with $ / account / move ref>
- ... (0 to 10 items)
RECOMMENDATIONS:
- <one-line concrete action or opportunity, with est. $ impact if applicable>
- ... (0 to 6 items)
SUMMARY: <2-4 sentences>

Severity tags (use exactly these in brackets): [CRITICAL] [HIGH] [MEDIUM] [LOW]
[INFO] [OPP] (OPP = tax/savings opportunity) [CROSS-LENS].
```

Assign these 10 lenses (one per agent):

1. **Trial-balance & double-entry integrity** — confirm debits=credits for both
   cos; hunt unbalanced or suspicious manual entries, draft/unposted entries
   (the dossier flags counts — Hagberg has draft JEs), postings straight to
   control/clearing accounts, round-number or $0 anomalies, wrong-period dates.
2. **Bank reconciliation & clearing accounts** — unreconciled bank lines, and
   stuck balances in Outstanding Receipts/Payments, Liquidity Transfer, and
   suspense accounts (Hagberg Liquidity Transfer is materially non-zero —
   investigate what's stranded there).
3. **Xcel P&L & margins** — revenue mix, expense ratios, concentration (Software
   & Web Subscriptions dominates Xcel opex — is it resale/COGS vs overhead?),
   Reimbursed Expenses pass-through, margin quality, anomalies vs run-rate.
4. **Hagberg P&L & the operating loss** — Hagberg is running a large FYTD loss
   (revenue << expenses). Dissect why (salaries, rent, health insurance),
   whether costs are legitimately the entity's, and the going-concern picture.
5. **Tax deductions & advantages (proactive)** — Augusta Rule (280A(g)), home
   office, vehicle/fixed-asset depreciation incl. §179/bonus, retirement plans
   (SEP/Solo-401k), QBI §199A, S-corp accountable plan, >2% S-corp shareholder
   health insurance (must run through W-2 Box 1), startup-cost amortization.
   Quantify estimated tax savings.
6. **Tax red flags / audit risk** — S-corp reasonable compensation (Hagberg
   owner W-2 salary vs distributions), LLC owner draws & SE-tax exposure (Xcel
   Mike/Stan distributions), meals 50% vs 100% treatment, personal/commingled
   expenses, missing 1099-NEC filings, distributions in excess of basis.
7. **Expense classification & data quality** — misclassifications, duplicates,
   generic/uncategorized "Expenses" buckets, software-subscription lumping,
   vendor inconsistency, and payment-application errors (payments hitting the
   wrong invoice / distributions miscoded to one partner).
8. **AR, revenue recognition & subscriptions** — AR aging & collection risk
   (chronic late payers), credit memos, subscription churn/auto-close exposure,
   annual vs monthly recognition, deferred revenue, write-off candidates.
9. **Equity, distributions & inter-company** — Xcel member distribution parity
   (Mike vs Stan — should track 50/50; flag the gap), Hagberg inter-company /
   Liquidity Transfer balance, Paid-in Capital & Undistributed Profits, related-
   party flows between the entities.
10. **CFO/CTO strategic perspective** — consolidated performance: profitability
    and margin trend, cash position & runway/burn, customer concentration (a few
    large monthly subscriptions drive Xcel revenue), AR collection efficiency,
    and concrete advice on performance, pricing, cost structure, and growth.

## Step 3 — consolidate (you do this after all 10 return)

Parse the 10 structured returns and print ONE report with these sections, in
this order:

1. **Balance verdict** — state plainly whether each company's books balance
   (debits=credits) and call out any out-of-balance or draft-entry flags.
2. **P&L summary** — a small table for both companies: Revenue, Total Expenses,
   Net Income, Margin %, FY-to-date window. Pull the numbers from the dossier
   (authoritative), not from agent paraphrase.
3. **Auditor table** — one row per auditor: Lens | Rating | Top finding. Show
   the rating spread (min / median / max). Do not average into one score.
4. **Issues by severity** — merge all FINDINGS, dedupe semantically, and list
   [CRITICAL] then [HIGH] then [MEDIUM] (lower tiers summarized). Tag each with
   the company and $ where known. Flag where auditors disagreed.
5. **Tax opportunities** — every [OPP] / deduction, with estimated $ savings and
   the cited rule, ranked by impact.
6. **Tax red flags** — audit-risk items ranked by exposure.
7. **CFO/CTO perspective** — synthesize auditor 10 plus the financial picture
   into a candid take on performance and 3-5 prioritized recommendations.

Keep the report skimmable: tables and bullets, lead with what matters. End with
a one-line "biggest single action to take this week."

**Every actionable finding, opportunity, and recommendation must carry an
`action` — a ready-to-paste Claude Code prompt** that, pasted back into a Claude
Code session, would carry out (or scope) that fix. Write the action in the
imperative, name the company/`company_id`, accounts, and $ amounts, and for
anything that writes to Odoo end with "show me the plan before posting." For
findings that are CPA judgment calls (reasonable comp, entity election), the
action should produce a memo/worksheet, not a posting. Leave `action` empty for
pure INFO items.

## Step 4 — emit the HTML report and open it (you do this last)

After printing the consolidated report to chat, write the same content to a
findings JSON and render it to a styled, self-contained HTML file that opens
automatically — with each action item rendered as a one-click **Copy** button so
the user can paste it straight back into Claude Code.

1. Write the consolidated findings to `/tmp/books_audit_findings.json` following
   the schema documented at the top of `scripts/render_report.py` (keys:
   `generated`, `companies`, `rating_spread`, `ratings`, `sections` [each item
   has `severity`, `company`, `text`, `action`], `tax_opportunities`,
   `tax_red_flags`, `cfo_perspective`, `biggest_action`). Numbers come from the
   dossier; `action` strings are the paste-ready prompts from Step 3.
2. Render and open it:

```bash
PYTHON=/Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/.venv/bin/python
SKILL_DIR="$HOME/.claude/skills/books-audit"
$PYTHON "$SKILL_DIR/scripts/render_report.py" /tmp/books_audit_findings.json /tmp/books_audit_report.html
```

   The renderer writes `/tmp/books_audit_report.html` and opens it (macOS `open`,
   Windows `start`, else the default browser). Tell the user the report opened
   and that each finding has a copy-paste action button.

## Notes

- This is an analysis run; it changes nothing in Odoo. Re-run any time.
- To audit a different fiscal-year window, set `AUDIT_FY_START=YYYY-01-01` before
  running the extractor.
- If an agent returns malformed output, note it as "malformed" in the auditor
  table rather than retrying — the other 9 are still valid.
- The dossier is the shared source of truth; if an agent's number disagrees with
  the dossier, trust the dossier (one snapshot, one set of numbers).
