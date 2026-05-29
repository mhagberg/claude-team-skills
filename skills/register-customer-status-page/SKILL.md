---
name: register-customer-status-page
description: Register a customer on the daily customers.xcel.report status page — appends the slug to INSTANCES in dataxcel-customer-report/customer_report/registry.py (AST-validated), commits + pushes a feature branch in the submodule, and triggers a one-off Airflow customer_report_dag run so the customer appears in tonight's report. Only required arg is <slug>.
---

# register-customer-status-page

You are running the **register-customer-status-page** skill. Goal: add a
brand-new customer to the daily internal status page at
`https://customers.xcel.report` so Mike + the team can see the customer's
Metabase users / dashboards / refresh-DAG state / MRR alongside every
other customer the next morning.

This is **phase 10** of the canonical onboarding sequence — the final
write that flips a customer from "live but invisible to ops" to "tracked
on the daily report."

**Position in the canonical sequence:**

```
… → /onboard-customer-briefing → /finalize-customer-metabase
   → /register-customer-status-page (you are here)
```

## Where each arg comes from

| Arg | Required? | Where it comes from |
|-----|-----------|---------------------|
| `<slug>` | Required | Same slug used in every prior onboarding skill. The `mb_key` in the customer-report registry is this slug. |
| `--company "<Display Name>"` | Optional | Display name on the status page. Defaults to title-cased slug (`lunstrum` → `Lunstrum`). Override if the customer has a real legal name you want shown (e.g. `4X Construction`, `American Integrated Services (AIS)`). |
| `--multi` | Optional | Set when the customer is multi-company (served by a rollup DAG, not a single-DAG). Defaults to `False`. If you ran `/onboard-customer-postcall` with a `RollupConfig` instead of `DBTConfig`, pass `--multi`. |
| `--refresh-dag <dag_id>` | Optional | Exact Airflow `dag_id` to surface as the refresh DAG on the report. Default: `<slug>_dataxcel_analytics_dbt_dag` (the single-customer convention). For multi-company customers the convention is `<slug>_dataxcel_rollup_dbt_rollup_dag`. Pass explicitly if your customer is on a non-standard DAG name (`rothlandscape_dataxcel_analytics_dbt_dag`, `brekhus_brekhus_dataxcel_rollup_dbt_rollup_dag`, etc.). |
| `--odoo-sub <S-number,…>` | Optional | Comma-separated Odoo `sale.order` S-numbers (the customer's active subscription quote IDs — e.g. `S00150`). The report joins on these to pull MRR + contact + email + phone from Odoo. Skip or pass empty if no subscription exists yet. |
| `--internal` | Optional | Marks the row as internal — suppresses MRR display, sorts after customer rows, adds an "internal" badge. Use only for internal demo / playground instances. |

That is the full surface. Every other field in the INSTANCES entry shape
is computed from the slug (`url` is `https://<slug>.xcel.report`,
`mb_key` is `<slug>`).

**Execution mode:** the local file edit is unprompted (it's just a Python
list-literal append, AST-validated). The Git commit + push and the
Airflow DAG trigger are RISKY and each require an explicit `yes`.

## Step 1 — validate args + resolve defaults

Required:

- `<slug>` — regex `^[a-z0-9-]+$`. Reject and stop on mismatch.

Resolve defaults:

- `--company` → title-cased slug (`my-customer` → `My Customer`).
- `--multi` → `False` unless flag was given.
- `--refresh-dag` → `<slug>_dataxcel_analytics_dbt_dag` if `--multi` is
  False, else `<slug>_dataxcel_rollup_dbt_rollup_dag` (matches the
  `rollup_customers.py` factory convention). Explicit `--refresh-dag`
  overrides.
- `--odoo-sub` → empty list `[]` if not given. Parse comma-separated into
  a list of strings (strip whitespace, reject anything not matching
  `^S\d{5}$` — the Odoo S-number format).
- `--internal` → `False` unless flag was given.

Refuse if the registry path doesn't exist on disk:

```
/Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/dataxcel-customer-report/customer_report/registry.py
```

Print a one-line plan summary that shows every resolved value:

> Plan: append `<slug>` (company=<Display>, multi=<True|False>,
> refresh_dag=<dag>, odoo_sub=<list>, internal=<True|False>) to
> dataxcel-customer-report/customer_report/registry.py.

Refuse to proceed if a row for `mb_key == <slug>` is already in
`INSTANCES`. Print: "Already registered — see existing row." and stop.

## Step 2 — read the canonical schema (READ-ONLY)

Read these two files to confirm the entry shape and the add-procedure has
not drifted since this skill was written:

1. `/Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/dataxcel-customer-report/CLAUDE.md`
   — submodule router. Confirms the project's hard rules ("no secrets in
   source", "per-instance failures must not abort the run", etc.).
2. `/Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/dataxcel-customer-report/docs/customer-registry.md`
   — INSTANCES schema + add/remove playbook.

If `customer-registry.md` documents a field this skill does not handle
(`url`, `mb_key`, `company`, `refresh_dag`, `multi`, `odoo_sub`,
`internal`), stop and tell the operator the schema drifted — this skill
needs updating. Do NOT silently write an incomplete row.

## Step 3 — edit INSTANCES in registry.py (LOCAL — AST-validated, no confirm)

The submodule's `register_tenant.py` in `dataxcel-dashboard-hub` is the
reference pattern for this kind of edit: textual insert, then re-parse
with `ast.parse` to confirm the file still compiles. Use the same
approach here.

Algorithm:

1. Read `customer_report/registry.py` as text.
2. Walk its AST to locate the `INSTANCES` assignment node (must be an
   `ast.List` literal at module scope). If it isn't a plain list literal,
   stop with `RuntimeError("INSTANCES is not a list literal — schema drift")`.
3. Find the source span of the list (open `[` ... close `]`) using
   `node.lineno`/`col_offset` and `node.end_lineno`/`end_col_offset`
   converted to character offsets. Same helper code as
   `dataxcel-dashboard-hub/scripts/register_tenant.py`
   `_find_iframe_tenants_list_span`.
4. Format the new entry to match the existing style — two-line dict
   literal, one `{...}` per row, 4-space indent matching the surrounding
   entries. Read the file to see the existing convention before
   formatting. Example shape:

   ```python
       {"mb_key": "<slug>", "company": "<Display>", "url": "https://<slug>.xcel.report",
        "refresh_dag": "<refresh_dag>", "multi": <True|False>, "odoo_sub": <odoo_sub_list>},
   ```

   - Omit `"internal": True` unless `--internal` was passed (matches the
     existing convention — internal flag is opt-in, not default).
   - `refresh_dag` MUST be the literal Python `None` (not `"None"`) when
     the user has no DAG at all (e.g. `west`, `stratfc`, `playground`).
     The default resolver in step 1 produces a string; only emit `None`
     if the operator passed `--refresh-dag none` (lowercase).
   - `odoo_sub` is always a list, even if empty.

5. Insert the new line just BEFORE the closing `]` of `INSTANCES`,
   preserving the previous line's terminating comma + newline. Same
   "rfind the last newline before the close bracket" approach as the
   reference script.
6. `ast.parse` the modified source. If it raises `SyntaxError`, restore
   the original file and stop with the error.
7. Run the registry unit tests to confirm:

   ```bash
   cd /Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/dataxcel-customer-report
   PYTHONPATH=. python -m pytest tests/test_registry.py -v
   ```

   If any test fails, restore the original file and stop with the test
   output. (The tests check no-duplicate-keys, URL shape, DAG-name shape
   — exactly the invariants this skill is supposed to preserve.)

8. Show the operator the diff (the one new line) before moving to step 4.

## Step 4 — commit + push on a feature branch (RISKY — confirm)

Use a feature branch — never push directly to `main` on the customer-report
submodule. Branch name: `feat/register-status-page-<slug>`.

Confirm:

> Commit and push the registry change on a new branch in
> `dataxcel-customer-report`?
>
>   Branch:  feat/register-status-page-<slug>
>   Message: feat(registry): add <slug> to customer status page
>
> This pushes the branch to GitHub. The operator should open a PR + merge
> separately if they want the change to ride the next Airflow image
> rebuild — but the live DAG already bind-mounts the submodule from
> Mike's machine, so the *running* DAG will pick up the change on its
> next run regardless (see docs/deploy.md §5b).
>
> Type `yes` to proceed.

On `yes`:

```bash
SUBMODULE=/Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/dataxcel-customer-report
git -C "$SUBMODULE" checkout -b feat/register-status-page-<slug>
git -C "$SUBMODULE" add customer_report/registry.py
git -C "$SUBMODULE" commit -m "feat(registry): add <slug> to customer status page"
git -C "$SUBMODULE" push -u origin feat/register-status-page-<slug>
```

If the branch already exists (re-run), check out + amend isn't safe per
parent-repo policy — just commit a NEW commit on the existing branch.

After push, print the commit SHA + the branch URL so the operator can
open a PR if they want one. Do NOT auto-open a PR — this skill does not
ship PRs.

## Step 5 — trigger a one-off customer_report_dag run (RISKY — confirm)

The DAG runs daily at 13:30 UTC anyway, so a one-off trigger is optional
— but Mike usually wants to see the new customer the same day, not wait
until tomorrow.

Confirm:

> Trigger Airflow `customer_report_dag` now via SSH to
> `mike@100.67.235.51` so `<slug>` shows up on customers.xcel.report
> within ~5 minutes?
>
> If you say `no`, the next scheduled run at 13:30 UTC will pick it up
> automatically.
>
> Type `yes` to trigger now, or `skip` to wait for the scheduled run.

On `yes`, prompt for the sudo password (do NOT hardcode), then:

```bash
ssh mike@100.67.235.51 "echo '<password>' | sudo -S docker exec \
  airflow-airflow-scheduler-1 airflow dags trigger customer_report_dag"
```

If SSH fails (no key, broker unreachable), fall back to printing the
EXACT manual command for the operator to run themselves:

```
ssh mike@100.67.235.51
sudo docker exec airflow-airflow-scheduler-1 airflow dags trigger customer_report_dag
```

Wait ~30s, then print the Airflow UI link (`http://100.67.235.51:8080/dags/customer_report_dag/runs`)
so the operator can watch it.

## Step 6 — confirm the row appears (read-only, optional)

After the DAG run completes (or the operator says they'll check later),
optionally fetch `https://customers.xcel.report` and grep for the slug.
This is best-effort — the page is Firebase-Auth gated and may require
the operator's session cookie. Skip if `curl -s` returns the auth wall
HTML. Do NOT block the skill on this.

## Step 7 — summary + final wrap-up

```
Customer: <slug>
Company:  <Display>
URL:      https://<slug>.xcel.report
Refresh DAG: <refresh_dag>
Multi-company: <True|False>
Odoo subscriptions: <odoo_sub_list>
Internal: <True|False>

Registry: appended to dataxcel-customer-report/customer_report/registry.py
Branch:   feat/register-status-page-<slug> (pushed to origin; open a PR
          when ready)
DAG run:  <triggered | scheduled for 13:30 UTC>

Customer <slug> will appear at https://customers.xcel.report after the
next customer_report_dag run (daily 13:30 UTC or the manual trigger above).
```

Stop. This is the LAST phase of the canonical onboarding sequence — the
orchestrator `/onboard-customer <slug>` ends here too.

## Notes for the AI agent

- **Schema drift guard.** Always re-read `docs/customer-registry.md`
  before editing. If a new field appears there (e.g. a future
  `region` or `tier` field), STOP and ask the operator — do not silently
  write a row missing the new field.
- **Skill-over-manual rule.** This skill is the ONLY supported way to
  add a customer to the status page. The README's "Add a new instance"
  procedure in `dataxcel-customer-report/docs/customer-registry.md`
  is a manual fallback for the operator who insists on doing it by hand
  — that section should be collapsed under a `<details>` block per
  `feedback_skill_over_manual_steps.md`. If the docs disagree, update
  the docs (separate PR) — do not invent a different add procedure here.
- **No deploy step.** Adding an INSTANCES entry is a code change, not a
  deploy change (per `docs/customer-registry.md`). The DAG bind-mounts
  the live submodule, so the next run picks up the new entry. We do NOT
  redeploy the Firebase Hosting site as part of this — that only changes
  if `hosting/public/index.html` changes.
- **Confirmation discipline.** File edit is unprompted (AST-validated +
  unit-tested before any external visibility). Git push and Airflow
  trigger each get their own confirmation.
