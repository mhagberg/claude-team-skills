---
name: finalize-customer-metabase
description: FINAL step before a DataXcel customer goes live — invites the customer's users (regular + admin) on their Metabase instance, using the shared `single.xcel.report` Metabase API key by default. HARD prerequisite — must run AFTER `/configure-customer-metabase`, `/validate-hub-dashboards`, AND `/validate-customer-metabase` have all passed. This skill only adds users; site name / timezone / site URL / iframe allowlist / demo-user archive all live in `/configure-customer-metabase`.
---

# finalize-customer-metabase

## Notation

In this doc and everywhere else (README, playbook, other SKILL.md files), anything in `<angle brackets>` is a **placeholder** — replace it with your actual value. Example: for the customer named `lunstrum`, `<slug>` means `lunstrum`, so `/finalize-customer-metabase <slug>` becomes `/finalize-customer-metabase lunstrum`. Anything NOT in angle brackets is literal text to type as-is.

You are running the **finalize-customer-metabase** skill. This is the
LAST gate before a customer's Metabase instance is handed to them. Goal:
add the customer's users (regular + admin), nothing else.

> **The AI agent uses the single.xcel.report API key by default.** Same
> shared key every other onboarding skill uses on shared-cluster
> customers:
> `mb_OtooFk7pInjCBF9EzZb4sT/9wsXCXWIJOCAdCbA2blw=`. Pass `--api-key`
> only for dedicated-instance customers (`dd`, `brekhus`, `jolma`,
> `vertex`, `4x`, `burbach`, `ipwlc`, `nvision`, `pcg`).

**Position in the canonical sequence:**

```
… → /configure-customer-metabase → /validate-hub-dashboards
   → /validate-customer-metabase → /onboard-customer-briefing
   → /finalize-customer-metabase  (you are here)
```

**Execution mode:** read-only GETs run unprompted. Every `POST /api/user`
and every admin-group membership write requires explicit `yes`
confirmation in a single batch prompt that shows the exact URL + body
that will go out.

## Hard precondition — three skills must have already passed

This skill REFUSES to do anything unless all three of these have run
recently and passed:

1. `/configure-customer-metabase <slug>` — site name, site URL, timezone,
   email, iframe allowlist, demo-user archive.
2. `/validate-hub-dashboards <slug>` — every Hub dashboard's cards render.
3. `/validate-customer-metabase <slug>` — Metabase numbers match Sage
   inside `--tolerance`.

**How to detect "recently".** This is currently a soft check — see the
OPEN TODO below. For now: ask the user "Have `/configure-customer-metabase
<slug>`, `/validate-hub-dashboards <slug>`, and `/validate-customer-metabase
<slug>` all been run and passed in the last hour?" If the user says no
(or anything other than `yes`), stop and tell them to run the missing
ones first. Print the canonical sequence so they see where they are.

> **OPEN TODO — detect prerequisites automatically.** The other three
> skills should drop a marker (Firestore doc `tenants/<slug>/onboarding_state`
> with `configure_passed_at` / `hub_validated_at` / `sage_validated_at`
> ISO timestamps, OR a `/tmp/<slug>-<step>.ok` flag file the skill checks
> mtime on, OR both — Firestore for cross-machine, /tmp for the local
> session) so this skill can hard-fail without asking. Until that lands,
> we rely on the user telling the truth in the confirmation prompt.

## Step 1 — validate args

Required:
- `<slug>` — customer short name. Must match the slug used everywhere
  else in the canonical onboarding sequence.
- `--users <email1,email2,...>` — comma-separated list of regular customer
  user emails. **Fail loudly** if this is missing — finalize is meaningless
  without users to add. Print: "No --users supplied; nothing to add. Re-run
  with --users <email1,email2>." and stop.

Optional:
- `--admin-users <email1,...>` — comma-separated list of customer admin
  emails. These get added AND put in the Metabase Administrators group.
- `--metabase-url <url>` — override the default `https://<slug>.xcel.report`.
- `--api-key <key>` — override the default shared key. Only use this for
  dedicated-instance customers.

Dedup `--admin-users` against `--users`: if the same email appears in
both, treat it as admin-only (don't double-add). Print a one-line note
when you do this.

Print a one-line plan summary before any API call:

```
Plan: finalize <slug> @ <metabase-url> | users=<n> | admins=<n>
```

## Step 2 — resolve API key

Default API key resolution:

1. If `--api-key` was passed, use it.
2. Otherwise, default to the shared single.xcel.report key:
   `mb_OtooFk7pInjCBF9EzZb4sT/9wsXCXWIJOCAdCbA2blw=`.
3. If `<slug>` is on a dedicated instance (`dd`, `brekhus`, `jolma`,
   `vertex`, `4x`, `burbach`, `ipwlc`, `nvision`, `pcg`), read the row
   for `<slug>` in the **Metabase Instances & API Keys** table of
   `/Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/XcelConnectAndUpdater/CLAUDE.md`
   and use that key instead.

Header on every call: `x-api-key: <api-key>` and `Content-Type:
application/json` for writes.

If any GET returns 401: stop and tell the user the API key is wrong —
remind them about `--api-key`.

## Step 3 — confirm the three prerequisites passed

Ask the user explicitly:

> Has `/configure-customer-metabase <slug>` been run and reported
> success? (Sets site name, site URL, timezone, email, iframe allowlist,
> archives demo users.)
>
> Has `/validate-hub-dashboards <slug>` been run and reported every
> dashboard healthy?
>
> Has `/validate-customer-metabase <slug>` been run and reported all
> Sage-vs-Metabase reports within tolerance?
>
> Type `yes` only if all three are green. Anything else aborts.

If anything other than `yes`, print:

```
Refusing to finalize. Run the missing prerequisites first:
  /configure-customer-metabase <slug>
  /validate-hub-dashboards <slug>
  /validate-customer-metabase <slug>
Then re-run /finalize-customer-metabase <slug> --users ...
```

and stop.

## Step 4 — read-only baseline

`GET <metabase-url>/api/user?include_deactivated=false` (paginate by
`limit`/`offset` if total > 100). Build a lowercase-email -> id map of
existing active users. Needed for dedup in Step 6.

`GET <metabase-url>/api/permissions/group` — find the entry where
`name == "Administrators"`. Save that id as `<admin-group-id>`. The
default "All Users" group (id 1) is auto-assigned by Metabase on user
create — no separate POST needed for regular users.

If the Administrators group isn't returned, stop with an error — that
means the API key doesn't have admin privileges and you can't proceed.

## Step 5 — derive names + dedup against existing

For each email in `--users` and `--admin-users`:

1. **Derive name** from the local-part of the email. Replace `.`, `_`,
   `-` with spaces. Title-case each word. Examples:
   - `john.smith@acme.com` → first=`John`, last=`Smith`
   - `jdoe@acme.com` → first=`Jdoe`, last=`` (single token; that's OK)
   - `mary-jane_williams@acme.com` → first=`Mary`, last=`Jane Williams`
2. **Check existing.** If the email is already in the active user list
   (case-insensitive), mark it `already-existed`. Do NOT POST again. If
   they're in `--admin-users`, still queue an admin-group-membership POST
   so we can add admin rights to a pre-existing user.

Print the derived names + dedup state in a small table before the confirm.

## Step 6 — add users (RISKY — single batch confirm)

Confirm the whole batch in one prompt:

> Create **N new users** on `<metabase-url>` (M regular, K admin)? Each
> will receive Metabase's standard invitation email.
>
> Regular:
>   - John Smith <john.smith@acme.com>
>   - …
> Admin:
>   - Jane Doe <jane.doe@acme.com>
>   - …
> Already-existed (admin membership only):
>   - Mike Boss <mike@acme.com>
>   - …
>
> Type `yes`.

On `yes`, for each new user POST:

```
POST <metabase-url>/api/user
Headers: x-api-key, Content-Type: application/json
Body: {
  "first_name": "<derived>",
  "last_name":  "<derived>",
  "email":      "<email>",
  "user_group_memberships": [{"id": 1}]   # "All Users" is group id 1
}
```

Metabase sends the invitation automatically.

For admin users (new OR `already-existed`), after the POST (or after
resolving their id), POST membership:

```
POST <metabase-url>/api/permissions/group/<admin-group-id>/membership
Body: {"user_id": <user-id>, "group_id": <admin-group-id>}
```

If a POST returns 4xx with a body indicating "email already in use",
treat as `already-existed` and recover their `id` via a fresh
`GET /api/user?query=<email>` so admin membership can still be applied
without aborting the batch.

If anything else fails (5xx, 401), stop the loop and print the response
body.

## Step 7 — final summary

Print a single table:

```
Customer: <slug>
Metabase: <metabase-url>

Users created:   <n>   (M regular, K admin)
Admin promotions: <n>  (already-existed users moved into Administrators)
Users skipped:   <n>   (already-existed, no admin change)
```

Then the per-user detail table:

```
Email                          Role     Status
john.smith@acme.com            user     created
jane.doe@acme.com              admin    created
mike.boss@acme.com             admin    already-existed (admin membership added)
```

Final lines:

```
Customer <slug> is LIVE. Metabase URL: https://<slug>.xcel.report.

Send the customer their welcome email — template "Welcome Email — Full
Reporting Package" in
/Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/XcelConnectAndUpdater/CLAUDE.md.
```

Stop.

## What this skill does NOT do (it used to — read this if you remember the old behaviour)

This skill used to set the site URL, the report timezone, AND archive
non-team users from the demo clone. All of that moved to
`/configure-customer-metabase` so the writes that set the canonical
configuration happen BEFORE the two validation gates, not after them.

If you find yourself wanting to fix a timezone or a base URL or archive
a stray demo user from inside this skill, the correct move is: stop,
re-run `/configure-customer-metabase <slug>` (which is idempotent), and
then come back here.

## Notes / gotchas

- **Why the prerequisite confirmation is currently a soft check.** We
  don't yet have a cross-machine source of truth that says "configure
  passed at T, hub-validation passed at T+ε, sage-validation passed at
  T+ε'." The OPEN TODO at the top of this file describes the planned
  fix (Firestore doc + `/tmp` flag file). Until then, the skill trusts
  the user's `yes` — but it prints the three commands explicitly so
  it's obvious what was supposed to happen.
- **Metabase user delete is deactivate, not hard delete.** That was
  relevant when this skill did archives. It now lives in
  `/configure-customer-metabase` — same semantics, just earlier in
  the sequence.
- **Why finalize runs last.** Users get login emails the moment they're
  created. We do NOT want a customer to log in to a Metabase instance
  whose dashboards haven't been validated against Sage yet — Mike's
  hard rule (2026-05-29): "we need to make sure the numbers validate
  against the Sage reports before we add the users and give them
  access."
