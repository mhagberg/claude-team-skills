---
name: customer-snapshots
description: Toggle dbt snapshots on or off for a single customer in single_customers.py (or rollup_customers.py). New customers default to snapshots=True via the onboarding flow; use this to flip an existing customer.
---

# customer-snapshots

You are running the **customer-snapshots** skill. Goal: flip a single
customer's `snapshots=` flag in the dbt customer registry. Default action is
ON; pass `--off` to disable.

The Mon–Fri + last-day-of-month gate is enforced centrally by the
`should_run()` helper in
`etl_pipeline/airflow/dags/utils/data_classes.py` (Deliverable 4 of the
onboarding plan) — you do NOT change schedules here, only the per-customer
opt-in flag.

**Execution mode:** local edit + read-only checks unprompted. The Git push at
the end is RISKY and requires `yes`.

## Step 1 — validate args

Required:
- `<slug>` — customer slug.

Optional:
- `--off` — set `snapshots=False` instead of the default `True`.

Print a one-line plan: `Setting snapshots=<True|False> for <slug>.`

## Step 2 — locate the registry entry

Search both files for an existing `DBTConfig(customer="<slug>"...)` or
`RollupConfig(customer="<slug>"...)` line:

```bash
grep -nE 'customer="<slug>"' \
  /Users/mike/dev/projects/etl_pipeline/airflow/dags/utils/single_customers.py \
  /Users/mike/dev/projects/etl_pipeline/airflow/dags/utils/rollup_customers.py
```

- If found in `single_customers.py` → edit that file.
- If found in `rollup_customers.py` → edit that file.
- If found in BOTH → stop and tell the user (this should never happen; flag it).
- If found in NEITHER → stop with error:
  `Customer <slug> not registered. Run /onboard-customer-postcall first.`

## Step 3 — edit (LOCAL — no confirm)

Use the Edit tool. Change `snapshots=True` ↔ `snapshots=False` on the matched
line. If the line doesn't have an explicit `snapshots=` kwarg (older style),
add it. Preserve formatting and trailing comma.

Show the diff back to the user.

## Step 4 — commit + push (RISKY — confirm push)

Confirm:

> Commit the snapshots flip on `etl_pipeline` with message
> `chore(snapshots): set <slug> snapshots=<True|False>`? Push to origin?
> Type `yes`.

On `yes`:

```bash
git -C /Users/mike/dev/projects/etl_pipeline add airflow/dags/utils/single_customers.py airflow/dags/utils/rollup_customers.py
git -C /Users/mike/dev/projects/etl_pipeline commit -m "chore(snapshots): set <slug> snapshots=<True|False>"
git -C /Users/mike/dev/projects/etl_pipeline push
```

(`git add` both files even if only one changed — the other is a no-op.)

## Step 5 — summary

```
Customer: <slug>
snapshots: <True|False>
File: single_customers.py | rollup_customers.py
Schedule gate: Mon-Fri + last day of month (enforced centrally by should_run()).

The snapshot DAG `<slug>_dataxcel_analytics_dbt_dag_snapshot` will appear
(or disappear) in the Airflow UI on the next scheduler tick.
```

Stop.
