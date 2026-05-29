---
name: finalize-customer-metabase
description: FINAL step before a DataXcel customer goes live — adds customer users (regular + admin), verifies Metabase Base URL + timezone are correct, and deletes any non-team users left over from cloning the demo instance. Uses the shared single.xcel.report API key by default. Only run AFTER /validate-customer-metabase passes.
---

# finalize-customer-metabase

You are running the **finalize-customer-metabase** skill. This is the LAST
gate before a customer's Metabase instance is handed to them. Goal: add the
customer's users, verify Base URL + report timezone match the canonical
values, and prune any non-team users that were carried over when the
instance was cloned from `single.xcel.report`.

**Execution mode:** every read-only check (GET requests, listing users)
runs unprompted. Every Metabase write — PUT setting, POST user, PUT
user/deactivate, POST group membership — requires an explicit `yes`
confirmation showing the exact URL + body that will go out. Read-only
checks first, writes second.

**Hard precondition:** `/validate-customer-metabase <slug>` must have been
run and passed. If the user runs this skill without that, stop and tell
them to run `/validate-customer-metabase <slug>` first. Validation failures
mean the instance isn't ready — running finalize blindly will hand a
broken instance to the customer.

## Step 1 — validate args

Required:
- `<slug>` — customer short name (must match the slug used in the rest of
  the onboarding sequence: `lunstrum`, `ais`, `dietrich`, etc.).
- `--users <email1,email2,...>` — comma-separated list of regular customer
  user emails. **Fail loudly** if this is missing — finalize is meaningless
  without users to add. Print: "No --users supplied; nothing to add. Re-run
  with --users <email1,email2>." and stop.

Optional:
- `--admin-users <email1,...>` — comma-separated list of customer admin
  emails. These get added AND put in the Metabase Administrators group.
- `--timezone <IANA>` — default `America/Boise`. IANA only (e.g.
  `America/Denver`, `America/Chicago`, `America/New_York`). Do NOT accept
  shorthand here — finalize is a verification step, be strict.
- `--metabase-url <url>` — override the default `https://<slug>.xcel.report`.
- `--api-key <key>` — override the looked-up API key.

Dedup `--admin-users` against `--users`: if the same email appears in both,
treat it as admin-only (don't double-add). Print a one-line note when you
do this.

Print a one-line plan summary before any API call:
```
Plan: finalize <slug> @ <metabase-url> | TZ=<tz> | users=<n> | admins=<n>
```

## Step 2 — resolve API key

Default API key resolution:

1. If `--api-key` was passed, use it (no lookup).
2. Otherwise, read
   `/Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/XcelConnectAndUpdater/CLAUDE.md`
   and find the row for `<slug>` in the **"Metabase Instances & API Keys"**
   table.
3. If the row's key column literally says `(shared)` or matches the shared
   single.xcel.report value, use the shared key:
   `mb_OtooFk7pInjCBF9EzZb4sT/9wsXCXWIJOCAdCbA2blw=`
4. If the row has its own key (e.g. `dd`, `brekhus`, `jolma`, `vertex`,
   `4x`, `burbach`, `ipwlc`, `nvision`, `pcg`), use that one.
5. If `<slug>` isn't in the table at all, default to the shared key and
   print a warning: `<slug> not in API key table — defaulting to shared
   single.xcel.report key. If finalize fails with 401, pass --api-key
   explicitly.`

The shared key works for any instance cloned from `single` — that's most
new customers.

## Step 3 — read-only baseline check

Hit these three GETs and print the results in a table before any writes.
Use header `x-api-key: <api-key>`.

| Check | Endpoint | Expected |
|-------|----------|----------|
| Base URL | `GET <metabase-url>/api/setting/site-url` | `<metabase-url>` exactly |
| Timezone | `GET <metabase-url>/api/setting/report-timezone` | resolved `--timezone` value |
| User list | `GET <metabase-url>/api/user?include_deactivated=false` (paginate via `limit`/`offset` if total > 100) | inventory only |

If the user-list endpoint returns a paginated envelope (`{data: [...],
total: N, limit, offset}`), follow `offset` until you've pulled them all.

If any GET returns 401: stop and tell the user the API key is wrong —
remind them about `--api-key`.

Print a single status table:
```
Setting        Current                      Target                       Status
site-url       <current>                    <target>                     OK / WRONG
report-tz      <current>                    <target>                     OK / WRONG
Users found    <N total>                    (inventory)                  —
```

## Step 4 — fix Base URL if wrong (RISKY — confirm)

Target = `<metabase-url>` (i.e. `https://<slug>.xcel.report` unless
overridden). Compare to current `site-url` — exact string match, including
scheme and no trailing slash.

If wrong, confirm:

> Metabase `site-url` is currently `<current>` — should be `<target>`.
>
> PUT `<metabase-url>/api/setting/site-url` with body
> `{"value": "<target>"}`?
> Type `yes`.

On `yes`, run the PUT. Re-GET to verify. If still wrong, stop with an
error — don't continue with users on a misconfigured instance.

If correct, skip.

## Step 5 — fix timezone if wrong (RISKY — confirm)

Target = the resolved `--timezone` (default `America/Boise`). Compare to
current `report-timezone`.

If wrong, confirm:

> Metabase `report-timezone` is currently `<current>` — should be `<target>`.
>
> PUT `<metabase-url>/api/setting/report-timezone` with body
> `{"value": "<target>"}`?
> Type `yes`.

On `yes`, run the PUT. Re-GET to verify.

If correct, skip.

## Step 6 — build the user allowlist + deletion queue

Construct the allowlist:

**Team allowlist (hardcoded — accept both domains):**
- `mhagberg@xcel.software`, `mhagberg@jobxcel.ai`
- `tsutton@xcel.software`, `tsutton@jobxcel.ai`
- `sgammon@xcel.software`, `sgammon@jobxcel.ai`

(If the actual team aliases differ, the customer-onboarding-postcall skill
log will show them. Treat the .software/.jobxcel.ai pair as interchangeable.)

**Customer allowlist:** everything from `--users` + `--admin-users`.

**System allowlist:** any account with email starting with `noreply@`,
`metabase@metabase.localhost`, or whose `is_qbnewb`/`is_installer` flag is
true on the API response. These are Metabase's own scaffolding accounts
— do NOT delete them.

Anything in the user list that is NOT in any allowlist goes into the
**deletion queue**. Print the queue as a numbered table:

```
Pending deletion (N):
  1. Old Demo User <demo@xcel.report>           id=42  last_login=2026-03-01
  2. Vertex Coatings Owner <jane@vertex.com>    id=51  last_login=2026-04-12
  ...
```

If the queue is empty, print "No stale users — skipping deletion" and go
to Step 8.

## Step 7 — purge stale users (RISKY — confirm batch)

Confirm the whole queue at once (single prompt, not per-user — there can be
a dozen leftover demo users on a freshly-cloned instance and per-user
confirms are pure friction):

> Deactivate **N users** listed above from `<metabase-url>`? Each will be
> deactivated via `DELETE <metabase-url>/api/user/<id>` (Metabase soft-deletes
> — they can be reactivated by an admin if needed).
>
> Type `yes` to proceed, `skip` to leave them in place, anything else aborts.

On `yes`, loop the queue and call `DELETE /api/user/<id>` for each.
Metabase's `DELETE /api/user/<id>` is a soft-deactivate (the user record
stays in the DB but is hidden from logins) — that's the safe choice here
vs. hard delete. Print one line per user with status (deactivated /
error). If ANY return non-2xx, stop the loop and print the error — do not
continue blindly.

On `skip`, print "Stale users left in place" and move on.

## Step 8 — fetch the Administrators group id (read-only)

If `--admin-users` was supplied OR you have any users to add at all, fetch
`GET <metabase-url>/api/permissions/group`. Find the entry where
`name == "Administrators"`. Save that id as `<admin-group-id>`. The
default "All Users" group is auto-assigned by Metabase on user create —
no separate POST needed.

If the Administrators group isn't returned, stop with an error — that
means the API key doesn't have admin privileges and you can't proceed.

## Step 9 — add users (RISKY — confirm per batch)

For each email in `--users` and `--admin-users`:

1. **Derive name** from the local-part of the email. Replace `.`, `_`, `-`
   with spaces. Title-case each word. Examples:
   - `john.smith@acme.com` → first=`John`, last=`Smith`
   - `jdoe@acme.com` → first=`Jdoe`, last=`` (single token; that's OK)
   - `mary-jane_williams@acme.com` → first=`Mary`, last=`Jane Williams`
   Print the derived name for each before posting.

2. **Check existing.** Walk the user list from Step 3 — if the email is
   already there (case-insensitive), mark it `already-existed`, do NOT
   POST again, and (if they're in `--admin-users`) continue to step 3 to
   ensure admin membership.

Confirm the whole batch in one prompt:

> Create **N new users** on `<metabase-url>` (M regular, K admin)? Each
> will receive Metabase's standard invitation email.
>
> Regular:
>   - John Smith <john.smith@acme.com>
>   - ...
> Admin:
>   - Jane Doe <jane.doe@acme.com>
>   - ...
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
  "user_group_memberships": [{"id": 1}]   # "All Users" is group id 1 in Metabase
}
```

Metabase will send the invitation automatically.

For admin users, after the POST (or for users marked `already-existed`),
also POST membership:

```
POST <metabase-url>/api/permissions/group/<admin-group-id>/membership
Body: {"user_id": <new-or-existing-user-id>, "group_id": <admin-group-id>}
```

If a POST returns 4xx with a body indicating "email already in use",
treat as `already-existed` and recover their `id` via a fresh
`GET /api/user?query=<email>` so admin membership can still be applied
without aborting the batch.

If anything else fails (5xx, 401), stop the loop and print the response
body.

## Step 10 — final summary

Print a single table:

```
Customer: <slug>
Metabase: <metabase-url>
Base URL:  OK (or 'fixed')
Timezone:  <tz>  (OK or 'fixed')
Users purged:   <n>
Users created:  <n>   (M regular, K admin)
Users skipped:  <n>   (already-existed)
```

Then the per-user detail table:

```
Email                          Role     Status
john.smith@acme.com            user     created
jane.doe@acme.com              admin    created
mike.boss@acme.com             admin    already-existed (admin membership added)
demo@xcel.report               —        deactivated
```

Final lines:

```
Customer <slug> is LIVE. Metabase URL: https://<slug>.xcel.report

Next: send the customer their welcome email — run
/onboard-customer-welcome <slug> (template: "Welcome Email — Full
Reporting Package" in XcelConnectAndUpdater/CLAUDE.md).
```

If `/onboard-customer-welcome` doesn't exist yet (it's queued), say so
plainly: `(/onboard-customer-welcome not yet shipped — for now, copy the
"Welcome Email — Full Reporting Package" template from
XcelConnectAndUpdater/CLAUDE.md into Gmail.)` That keeps the
skill-over-manual rule honest while the welcome skill is still being
built.

Stop.

## Notes / gotchas

- **Metabase user delete semantics.** `DELETE /api/user/<id>` is
  **deactivate**, not hard delete. Deactivated users disappear from login
  screens but their authored questions/dashboards remain attributed to
  them. That's exactly what we want for a cloned-from-demo cleanup: the
  demo-content authorship history stays intact, the demo users just can't
  log in. If you ever need hard delete, you have to do it in the
  application database directly — out of scope here.
- **Why `single.xcel.report` shares an API key.** Every customer instance
  on the shared EKS Metabase cluster is cloned from the single template
  DB, which carries the same API key over. That's why Hallowell / Roth /
  Dietrich / Bookout / West / AIS / Valley Glass all authenticate with
  the same `mb_OtooFk7pInjCBF9EzZb4sT/...` key. Dedicated-instance
  customers (`dd`, `brekhus`, `jolma`, etc.) have their own keys recorded
  in `XcelConnectAndUpdater/CLAUDE.md`.
- **Why this skill exists after `/validate-customer-metabase`.** Validation
  is a non-destructive check that the instance is ready (URL reachable,
  DB connected, dashboards present, schema synced). Finalize is the
  *destructive* step (deactivates demo users, adds real users). Splitting
  them keeps the dangerous writes behind a green-light gate.
- **Default timezone.** `America/Boise` matches the Xcel Software /
  Idaho-based customer baseline. Override per customer (`--timezone
  America/Denver` for Hagberg-on-MT-time, etc.).
