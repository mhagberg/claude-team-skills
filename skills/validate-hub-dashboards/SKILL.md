---
name: validate-hub-dashboards
description: Health-check EVERY dashboard the DataXcel Dashboard Hub will surface for a customer — execute every card on every non-excluded dashboard against their Metabase REST API and report pass / empty / failing. Gate BEFORE inviting users. Mirrors the daily check_dashboard_health Cloud Function so on-demand validation runs the same logic as the scheduled job.
---

# validate-hub-dashboards

## Notation

In this doc and everywhere else (README, playbook, other SKILL.md files), anything in `<angle brackets>` is a **placeholder** — replace it with your actual value. Example: for the customer named `lunstrum`, `<slug>` means `lunstrum`, so `/validate-hub-dashboards <slug>` becomes `/validate-hub-dashboards lunstrum`. Anything NOT in angle brackets is literal text to type as-is.

You are running the **validate-hub-dashboards** skill. This is a
**health-check gate** that sits between hub provisioning and final user
invites in the canonical onboarding sequence:

```
precall  ->  customer IT runs scripts  ->  postcall  ->  validate-customer-metabase
  ->  onboard-customer-hub  ->  >>> validate-hub-dashboards (you are here) <<<
  ->  finalize-customer-metabase  ->  customer goes live
```

Mike's instruction (2026-05-29, Lunstrum onboarding):

> "We also need to run the dashboard hub validation on every dashboard to
> ensure they are all running."

`/validate-customer-metabase` already proves the *numbers* reconcile to
Sage. THIS skill proves that **every dashboard the Hub will actually
surface to the customer** loads without broken cards, unresolved
field-ids, or query errors — the failure mode we hit with Hallowell where
the pMBQL migrator left stale field-ids pointing at columns that no
longer existed in the customer's schema.

**Execution mode:** every action in this skill is **read-only** against
Metabase (we `GET /api/dashboard`, `GET /api/dashboard/<id>`, and
`POST /api/card/<id>/query` — the POST is a query execution, not a write).
Run the validation loop unprompted. The only optional write is caching
results into Firestore at `tenants/<slug>/health/latest`; ask before
doing that.

## Step 1 — parse args + resolve config

CLI shape:

```
/validate-hub-dashboards <slug>
    [--reports all | --exclude <dashboard-ids,...>]
    [--timeout 60]
    [--exclude-collections "Automatically Generated Dashboards,Examples (Metabase Sample Data)"]
    [--metabase-url https://<slug>.xcel.report]
    [--api-key mb_...]
    [--cache-to-firestore]
```

Required:

- `<slug>` — customer slug (e.g. `lunstrum`, `west`, `ais`). Fail loudly
  if missing: "Missing <slug>. Usage: `/validate-hub-dashboards <slug>`."

Defaults:

- `--reports` defaults to `all` (every non-excluded dashboard on the
  instance, matching the Hub's surfaced set). If the user passes
  `--exclude 12,47,103`, those dashboard IDs are dropped on top of the
  collection-level exclusions.
- `--timeout` defaults to `60` seconds per card (matches the production
  `check_dashboard_health` value at `dataxcel-dashboard-hub/functions/main.py`
  ~line 1024 — Mike dropped it from 300s to 60s because "anything longer is
  broken for users"). Allow `--timeout 300` for slow instances like IPWLC
  if the user explicitly opts in.
- `--exclude-collections` defaults to the EXACT Hub exclusion set from
  `dataxcel-dashboard-hub/functions/main.py`:
  - Collection name `"Automatically Generated Dashboards"` and all its
    descendants
  - Collection name `"Examples (Metabase Sample Data)"` and all its
    descendants
  - Any dashboard whose name contains `"menu"` (case-insensitive)
  - The legacy navigation dashboard id `94`
  - Any personal collection (Metabase collections with
    `personal_owner_id` set)
  Mirror this list exactly — do NOT invent a new one. If the user passes
  `--exclude-collections "X,Y"`, treat it as a REPLACEMENT for the
  defaults (so they can broaden), but always still exclude the personal
  collections + dashboard id 94 + `menu`-named dashboards (those are
  structural, not just convention).
- `--metabase-url` defaults to `https://<slug>.xcel.report`.
- `--api-key` defaults to the shared `single.xcel.report` Metabase API
  key:
  `mb_OtooFk7pInjCBF9EzZb4sT/9wsXCXWIJOCAdCbA2blw=`
  (source of truth: `XcelConnectAndUpdater/CLAUDE.md`, "Metabase Instances
  & API Keys" table; same shared key Hallowell, Roth, Dietrich, Bookout,
  West, and AIS all use. If the customer is on a dedicated Metabase
  instance, the user must pass `--api-key` explicitly.)
- `--cache-to-firestore` is off by default. When set, write the result
  document to `tenants/<slug>/health/latest` in Firestore (matching the
  shape the scheduled Cloud Function writes). Requires confirmation.

Print a one-line plan summary BEFORE running anything:

```
Validating hub dashboards for <slug> against <metabase-url>
Timeout: <timeout>s per card
Excluded collections: <list>
Mode: <A: invoke deployed Cloud Function | B: local replication>
```

## Step 2 — choose execution path

There are two possible paths. **Default to path B (local replication)**
unless the user explicitly asks to invoke the deployed Cloud Function.

### Path A — invoke the deployed `check_dashboard_health`

The function `check_dashboard_health` in
`dataxcel-dashboard-hub/functions/main.py` is decorated
`@scheduler_fn.on_schedule(...)` — it has **no HTTPS trigger**, so it
cannot be called directly via `curl`. To invoke it on demand, you'd need
one of:

1. The Google Cloud Scheduler "Force run" button in the Firebase console
   (manual UI step, not scriptable from the skill).
2. `gcloud scheduler jobs run firebase-schedule-check_dashboard_health-us-central1
   --location=us-central1 --project=dataxcel-hub` — requires
   `gcloud auth login` and the right IAM role.

Path A runs against **all 16 tenants** in `TENANT_INSTANCES`, not just
`<slug>` — there's no per-tenant trigger. So even if you invoke it,
you'd still need to wait for the run to complete and then read
`tenants/<slug>/health/latest` from Firestore.

Only use path A when the user explicitly types `--use-deployed-function`
AND has `gcloud` set up. Otherwise default to path B.

### Path B — local replication (default)

Replicate `_check_tenant_health` from
`dataxcel-dashboard-hub/functions/main.py` exactly, in-process. This
means we are running the SAME logic that runs daily at 05:00 MT, just
on demand and scoped to one tenant. Steps 3–5 implement this.

State the chosen path in the plan summary so the user knows what's
about to happen.

## Step 3 — fetch dashboard + collection inventory

Using the resolved `--metabase-url` and `--api-key`:

```
GET <metabase-url>/api/dashboard       (timeout 30s)
GET <metabase-url>/api/collection      (timeout 30s)
```

From `/api/collection`:

- Build `collections = {id: name}`.
- Build `personal_ids = {c.id for c in collections if c.personal_owner_id}`.
- Build the descendant-id set for each excluded collection name (an
  excluded collection's children are also excluded). The Hub's
  `_descendant_ids` helper walks the collection tree by `location` /
  `parent_id`; replicate that.

Filter the dashboard list. **Skip any dashboard where:**

- `archived` is true, OR
- `id == 94` (legacy navigation), OR
- `"menu" in name.lower()`, OR
- `collection_id` is in the excluded descendant set, OR
- `collection_id` is in `personal_ids`, OR
- `id` is in the user's `--exclude` list

This MUST match the filter logic at
`dataxcel-dashboard-hub/functions/main.py` (lines ~1068–1075). If you
drift from it, validation passes here but the Hub will still surface
dashboards you didn't test — defeating the gate.

Print the kept-dashboard count and the dropped count side by side:

```
Inventory: 47 dashboards on instance; 38 will be surfaced by the Hub (9 excluded).
```

## Step 4 — execute every card on every kept dashboard

For each kept dashboard:

1. `GET <metabase-url>/api/dashboard/<dashboard-id>` (timeout 30s) →
   collect `dashcards`. Each dashcard has a nested `card.id` and
   `card.name`.
2. For each `(card_id, card_name)`:
   - `POST <metabase-url>/api/card/<card_id>/query` with empty JSON body
     and `--timeout` seconds.
   - Classify the result:
     - **failed** — HTTP error, timeout, or response JSON has a
       non-null `error` field.
     - **empty** — response succeeded but `data.rows` is empty
       (this is a WARN, not a hard fail — some dashboards legitimately
       show zero rows for a fresh customer).
     - **success** — response has rows.
   - Track `running_time` from the response for the avg/max per-dashboard
     query time.

Parallelise per dashboard (up to 5 concurrent card executions matching
the production function's `ThreadPoolExecutor(max_workers=5)`). Across
dashboards, run sequentially within this skill — single-tenant on-demand
runs don't need the cross-dashboard concurrency the production batch
uses.

Stream progress as you go. For a 38-dashboard / ~400-card instance this
takes 2–8 minutes; the user needs to see liveness:

```
[12/38] Income Statement — 14 cards — 14 pass, 0 empty, 0 fail (avg 1.2s, max 3.4s)
[13/38] Job Cost Detail   — 22 cards — 19 pass, 2 empty, 1 FAIL  (avg 2.1s, max 8.7s)
        Card 4711 "Cost-to-date by phase": Field 21034 does not exist.
```

**Watch specifically for the Hallowell stale-field-id failure mode.** When
a card fails with an error body containing `Field <id> does not exist`,
`does not exist`, `not found`, or `Column .* could not be resolved`,
flag it as `[STALE-FIELD-ID]` in the per-card detail line. The fix for
that class is documented in `metabase-migration/CLAUDE.md` — the pMBQL
migrator leaves stale field-ids pointing at columns the customer's schema
doesn't have. Re-running `metabase-migration/pmbql_migrate.py` against
the customer instance, or pruning the broken card, is the resolution.

## Step 5 — pass / fail decision + output

### Sticky summary table

After every dashboard has been checked, print a sticky table:

```
========================================
  Hub dashboard health for <slug>
========================================

| Dashboard                       | Cards | Pass | Empty | Fail |
|---------------------------------|-------|------|-------|------|
| Income Statement                |    14 |   14 |     0 |    0 |
| Balance Sheet                   |     8 |    8 |     0 |    0 |
| Job Cost Detail                 |    22 |   19 |     2 |    1 |
| WIP / Over-Under Billings       |     6 |    6 |     0 |    0 |
| ...                             |   ... |  ... |   ... |  ... |
|---------------------------------|-------|------|-------|------|
| TOTAL                           |   412 |  408 |     3 |    1 |

Excluded by Hub rules: 9 dashboards
  Automatically Generated Dashboards (collection)
  Examples (Metabase Sample Data) (collection)
  "Menu" (id 94)
  Personal collections: 3 dashboards
```

### Per-failure detail

For every failing card, print:

```
[FAIL] Dashboard "Job Cost Detail" (id 215)
       Card "Cost-to-date by phase" (id 4711)
       HTTP 200  body[0:200]: {"error":"Field 21034 does not exist."}
       [STALE-FIELD-ID] — see metabase-migration/CLAUDE.md Hallowell gotcha
```

If the failure is NOT a recognised stale-field-id pattern, just print
the first 200 chars of the error body without the tag.

### Status classification

- `0 failing` → **PASS** (warn-only on empties)
  - If empties > 0, surface them in a section:
    ```
    [WARN] 3 cards returned 0 rows. Eyeball before user invites:
      - Dashboard "AR Aging" card "Past Due > 90 days" (id 4823)
      - ...
    Empty rows can be legitimate (fresh customer, no data yet) or can
    indicate a wrong filter — Mike's call.
    ```
- `>= 1 failing` → **FAIL** (BLOCK).

### On PASS

Print (ANSI green if the terminal supports it; otherwise plain text):

```
========================================
  hub dashboard health: PASS for <slug>
========================================

  Dashboards surfaced: <kept>
  Cards executed:      <total>
  Pass:                <pass>
  Empty (warn):        <empty>
  Fail:                0

  Timeout:             <timeout>s per card
  Metabase URL:        <metabase-url>
```

If `--cache-to-firestore` was passed, ask: "Write this result to
`tenants/<slug>/health/latest` in Firestore (matches the schema
`check_dashboard_health` writes)? (yes / no)". On `yes`, write the
document with the same shape as the production function:

```json
{
  "tenantId": "<slug>",
  "checkedAt": "<iso8601>",
  "totalDashboards": <kept>,
  "healthyDashboards": <kept - dashboards_with_any_failure>,
  "unhealthyDashboards": <dashboards_with_any_failure>,
  "dashboards": [ ... per-dashboard objects matching the production shape ... ]
}
```

End the message with EXACTLY:

```
Next: /finalize-customer-metabase <slug> --users <email1,email2,...> [--admin-users <email,...>]
```

### On FAIL

Print (ANSI red if supported; otherwise plain text):

```
========================================
  hub dashboard health: FAIL for <slug>
========================================

  Dashboards surfaced: <kept>
  Cards executed:      <total>
  Pass:                <pass>
  Empty (warn):        <empty>
  Fail:                <fail>      <-- BLOCK

  Failing dashboards:
    - "Job Cost Detail" (id 215)   1 / 22 cards
    - "..."                        ...

  Do NOT proceed to finalize. Failed cards need fixing first.

  Resolution paths:
    1. /clone-dashboard <slug> <dashboard-id>     <-- TODO: skill not yet built
    2. (Fallback for now) Re-run metabase-migration/pmbql_migrate.py
       against the customer instance to refresh field-ids, then re-run
       /validate-hub-dashboards <slug>. See metabase-migration/CLAUDE.md
       "Hallowell stale-field-id gotcha".
    3. If a dashboard is genuinely unwanted, archive it in Metabase so
       the Hub's sync drops it on the next 06:00 MT tick, then re-run.
```

<details>
<summary>Why no automatic Next: pointer on FAIL</summary>

Per `feedback_skill_over_manual_steps.md` and the
`validate-customer-metabase` precedent: this skill refuses to print a
`Next:` pointer when validation fails. A green `Next:` pointer is a
promise that the customer is ready for users; we will not make that
promise while any card is failing. The user must fix the failures and
re-run `/validate-hub-dashboards <slug>`.
</details>

Exit non-zero.

## Step 6 — read-only against Metabase, confirm on Firestore write

To be explicit per the design principle in
`claude-team-skills/CLAUDE.md` ("execute with confirmation on risky
steps"):

- `GET /api/dashboard`, `GET /api/dashboard/<id>`, `GET /api/collection`,
  `POST /api/card/<id>/query` — all run unprompted. The `POST` to
  `/query` executes the card's existing query against the customer's
  data warehouse; it does not mutate Metabase.
- Firestore write to `tenants/<slug>/health/latest` — requires `yes`
  confirmation, only when `--cache-to-firestore` was passed.
- No edits to Metabase settings, no user adds, no dashboard mutations.

## Step 7 — skill-over-manual rule

Every concrete command in this skill body is something **you** (the host
Claude) run. The user should not be typing `curl` or `python` to drive
this — that's what the skill is for. The only manual step the user owns
is deciding what to do with failures (re-clone, archive, etc.), and even
there the `Next:` pointer surfaces a slash command (`/clone-dashboard
<slug> <dashboard-id>` — flagged as TODO since that skill doesn't exist
yet; until it does, fall back to the `pmbql_migrate.py` mention).

## Outstanding TODOs

These are deferred work this skill assumes will exist later:

- **`/clone-dashboard <slug> <dashboard-id>`** — does not exist yet. The
  FAIL block points at it for the canonical resolution; until built, the
  fallback path in the FAIL output (`pmbql_migrate.py` re-run) is what
  the user will actually do. Wire this skill once
  `skills/clone-dashboard/SKILL.md` lands.
- **Batch fix workflow** — when N dashboards fail for the same root cause
  (e.g. a schema column got renamed), there is no `/fix-stale-field-ids
  <slug>` skill yet. For now, the user re-runs `pmbql_migrate.py` and
  then re-runs this skill. A future skill should detect the cluster and
  offer a one-shot fix.
- **Path A wiring** — if a future iteration of
  `dataxcel-dashboard-hub/functions/main.py` exposes
  `check_dashboard_health` as an HTTPS-callable, replace path A's manual
  `gcloud scheduler jobs run` with a direct invocation and the Firestore
  read.

## Quick recap of the gate

This skill enforces ONE thing: every dashboard the Dashboard Hub will
surface to the customer actually runs end-to-end. If you walk away from
a `/validate-hub-dashboards` run without seeing the green "PASS" block,
the next step is NOT `/finalize-customer-metabase` — it's fixing
whatever cards are failing and re-running this skill.
