---
name: configure-customer-metabase
description: Configure a newly-cloned customer Metabase tenant to the canonical DataXcel settings — site name, HTTPS site URL, IANA timezone, email From Name + Reply-To, email address for help requests (admin-email), iframe allowlist, custom-homepage-dashboard — and archive non-team users left over from the demo clone. Runs AFTER `/onboard-customer-hub` and BEFORE `/validate-hub-dashboards`. **The AI agent does all of this automatically using the shared `single.xcel.report` Metabase API key.**
---

# configure-customer-metabase

## Notation

In this doc and everywhere else (README, playbook, other SKILL.md files), anything in `<angle brackets>` is a **placeholder** — replace it with your actual value. Example: for the customer named `lunstrum`, `<slug>` means `lunstrum`, so `/configure-customer-metabase <slug>` becomes `/configure-customer-metabase lunstrum`. Anything NOT in angle brackets is literal text to type as-is.

You are running the **configure-customer-metabase** skill. Goal: take a
freshly-cloned customer Metabase tenant and snap it to the canonical
DataXcel configuration in one go — settings, email metadata, iframe
allowlist, custom homepage, and leftover-demo-user purge — so every
customer's instance is configured identically and the validation +
finalize steps can rely on those values.

> **The AI agent uses the single.xcel.report API key for all of this.**
> Every customer Metabase tenant cloned from the `single` template carries
> over the same `mb_OtooFk7pInjCBF9EzZb4sT/9wsXCXWIJOCAdCbA2blw=` API key.
> That key has admin scope on the cloned tenant. You do NOT need to look up
> a per-customer key for this step — that's only required when a customer
> later gets a dedicated instance.

**Position in the canonical sequence:**

```
… → /onboard-customer-hub → /configure-customer-metabase (you are here)
   → /validate-hub-dashboards → /validate-customer-metabase
   → /onboard-customer-briefing → /finalize-customer-metabase
```

**Execution mode:** read-only GETs run unprompted. Every PUT to
`/api/setting/*`, every `DELETE /api/user/<id>`, and every change to the
custom-homepage-dashboard requires an explicit `yes` confirmation that
shows the exact URL and request body that will go out. Read-only first,
writes second.

## Step 1 — validate args

Required:
- `<slug>` — customer short name. Must match the slug used everywhere
  else in the canonical onboarding sequence (`lunstrum`, `ais`,
  `dietrich`, …). Lowercase, no spaces.

Optional:
- `--site-name "<Display Name>"` — Metabase Settings → General → Site Name.
  Default if missing: `<Slug> Reporting` with the slug title-cased
  (`lunstrum` → `Lunstrum Reporting`). **Note for the user before
  applying:** "This is Mike's preferred convention — override per customer
  with `--site-name` if the customer wants something else (e.g.
  `Acme Construction Analytics`)."
- `--timezone <IANA>` — Metabase Settings → Localization → Report Timezone.
  Default if missing: `America/Boise` (Mountain). **IANA only** — reject
  shorthand like `MST`, `Mountain`, `PT`. If `--timezone` does not contain
  a `/`, stop and tell the user the IANA list lives at
  `https://en.wikipedia.org/wiki/List_of_tz_database_time_zones`.
- `--archive-allowlist email1,email2,...` — additional emails (beyond the
  hard-coded Xcel team list) that should NOT be archived. These users are
  KEPT in place. Comma-separated, case-insensitive.
- `--metabase-url <url>` — override the default `https://<slug>.xcel.report`.
  Almost never needed.
- `--api-key <key>` — override the shared key. Only use this for the
  occasional dedicated-instance customer.

Print a one-line plan summary before any API call:

```
Plan: configure <slug> @ <metabase-url> | site=<resolved-name> | tz=<resolved-tz>
```

## Step 2 — resolve API key

Default API key resolution:

1. If `--api-key` was passed, use it.
2. Otherwise, default to the shared single.xcel.report key:
   `mb_OtooFk7pInjCBF9EzZb4sT/9wsXCXWIJOCAdCbA2blw=`.
3. If `<slug>` is on a dedicated instance (`dd`, `brekhus`, `jolma`,
   `vertex`, `4x`, `burbach`, `ipwlc`, `nvision`, `pcg`), read the row for
   `<slug>` in the **Metabase Instances & API Keys** table of
   `/Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/XcelConnectAndUpdater/CLAUDE.md`
   and use that key instead. Print: `<slug> is on a dedicated instance —
   using the per-customer API key from XcelConnectAndUpdater/CLAUDE.md.`

Header on every call: `x-api-key: <api-key>` and `Content-Type:
application/json` for writes.

If any GET returns 401: stop and tell the user the API key is wrong —
remind them about `--api-key`.

## Step 0 — point the cloned data source at the actual customer warehouse (REQUIRED, NEVER SKIP)

**CRITICAL.** When a customer's Metabase tenant is cloned via
`duplicate_single.sh`, the Postgres metadata that holds the data-source
connection (database id=2 in the cloned Metabase app DB) carries over
verbatim from the demo. The cloned tenant's "Metabase database #2" still
has the demo's `host` / `port` / `db` / `user` / `password` — for clones
of `single.xcel.report` that's Vertex Coatings' anonymized SQL Server at
`100.67.89.249:50285`, user `jobxcel`, db `Vertex Coatings Anonymize
Reporting`. **Renaming the connection in the Metabase admin UI does NOT
fix this** — the display name is cosmetic. Until the actual connection
keys are updated via the REST API, every dashboard, every validation,
every "Sage vs Metabase" comparison runs against the demo's warehouse,
not the customer's.

**Order matters:** this step runs BEFORE everything else in this skill
(site name, site URL, timezone, iframe allowlist, custom homepage,
demo-user purge). None of those matter if Metabase is querying the wrong
warehouse.

### 0.1 Resolve the four customer values

Pull these from the **SQL Credentials** + **NetBird Customers** tables
in
`/Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/XcelConnectAndUpdater/CLAUDE.md`
(the `/onboard-customer-oncall` skill wrote them there). If a row for
`<slug>` is missing, stop and tell the user: "Run
`/onboard-customer-oncall <slug>` first — the customer's NetBird IP,
SQL port, and `dataxcel` password aren't on file yet."

| Field | Value source |
|-------|--------------|
| `<netbird-ip>` | NetBird Customers table → NetBird IP (e.g. `100.67.139.127`) |
| `<sql-port>` | NetBird Customers table → SQL Port (e.g. `49816`) |
| `<dataxcel-pw>` | SQL Credentials table → SQL Password for `<slug>` |
| `<customer-name>` | Slug title-cased, or the Company column if present |

### 0.2 Read the current connection (read-only — surfaces the drift)

```
GET <metabase-url>/api/database/2
```

Print a one-line summary:

```
Current MB DB id=2: host=<current-host> port=<current-port> db=<current-db> user=<current-user>
Target           : host=<netbird-ip>    port=<sql-port>     db=dataxcel_analytics user=dataxcel
```

If they already match (the customer was re-onboarded, or this skill
already ran), skip 0.3 + 0.4 and move on to Step 1.

### 0.3 Apply the connection (RISKY — confirm)

Show the exact body and ask `yes`:

```
PUT <metabase-url>/api/database/2
Headers:
  x-api-key: <api-key>
  Content-Type: application/json
Body:
{
  "name": "<customer-name> Analytics",
  "engine": "sqlserver",
  "details": {
    "host": "<netbird-ip>",
    "port": <sql-port>,
    "db": "dataxcel_analytics",
    "user": "dataxcel",
    "password": "<dataxcel-pw>",
    "ssl": true,
    "trust-server-certificate": true,
    "additional-options": "trustServerCertificate=true"
  }
}
```

On `yes`, run the PUT. Then trigger a schema sync:

```
POST <metabase-url>/api/database/2/sync_schema
```

If DB id=2 does NOT exist on the cloned tenant (rare — the seed clone
should always have it; happens only if Mike manually deleted it), fall
back to `POST <metabase-url>/api/database` with the same body shape and
capture the returned id for the smoke query in 0.4.

> **Why BOTH `ssl: true` AND `additional-options:
> "trustServerCertificate=true"` are required.** `ssl: true` is
> Metabase's API model for the GUI "Use a secure connection (SSL)"
> toggle — without it the connection is unencrypted, which fails
> customer security review and may not work at all against SQL Servers
> that require encryption (and is the same setting Mike turns on by
> hand in the admin UI). `additional-options:
> "trustServerCertificate=true"` is the literal JDBC connection-string
> option that gets appended to the SQL Server JDBC URL, and is shown
> in the Metabase GUI as "Additional JDBC connection string options".
> The top-level `trust-server-certificate: true` field is Metabase's
> own API model for the GUI toggle of the same name; the
> `additional-options` field is the literal JDBC string the driver
> consumes. They are NOT redundant — some Metabase versions only
> respect one, and some SQL Server JDBC driver versions ignore one
> without the other. Including both is the safe canonical shape;
> customer Sage servers behind NetBird present self-signed certs, so
> without trust-server-certificate the encrypted handshake fails.

### 0.4 Verify — GET, not the PUT echo (REQUIRED)

Metabase echoes back the PUT body even in edge cases where the change
didn't persist. The ONLY honest check is a fresh GET:

```
GET <metabase-url>/api/database/2
→ assert details.host == <netbird-ip>
→ assert details.port == <sql-port>
→ assert details.db == "dataxcel_analytics"
→ assert details.user == "dataxcel"
→ assert details.ssl == True
→ assert details["additional-options"] == "trustServerCertificate=true"
→ assert details["trust-server-certificate"] == True
```

Then a smoke query that hits a table that only exists in the customer's
real warehouse:

```
POST <metabase-url>/api/dataset
{"database":2,"type":"native","native":{"query":"SELECT TOP 1 ledger_account_id FROM dbo.Ledger_Accounts_by_Month"}}
```

Must return rows. If it errors with `Cannot open database 'Vertex
Coatings Anonymize Reporting' requested by the login. The login failed.`
(or any reference to the demo's DB name), the PUT didn't persist — stop
and tell the user. Do NOT continue to Step 1 until this smoke query
succeeds against the customer's warehouse.

Print:

```
MB DB id=2 now points at <netbird-ip>:<sql-port>/dataxcel_analytics — smoke query returned <N> row(s). OK.
```

## Step 3 — read-only baseline check

Pull the current values for everything we're about to touch. Single table
out so the user can eyeball drift before any writes happen.

| # | Setting | Endpoint |
|---|---------|----------|
| 1 | site-name | `GET <metabase-url>/api/setting/site-name` |
| 2 | site-url | `GET <metabase-url>/api/setting/site-url` |
| 3 | report-timezone | `GET <metabase-url>/api/setting/report-timezone` |
| 4 | email-from-name | `GET <metabase-url>/api/setting/email-from-name` |
| 5 | email-reply-to | `GET <metabase-url>/api/setting/email-reply-to` |
| 6 | admin-email | `GET <metabase-url>/api/setting/admin-email` |
| 7 | allowed-iframe-hosts | `GET <metabase-url>/api/setting/allowed-iframe-hosts` |
| 8 | custom-homepage-dashboard | `GET <metabase-url>/api/setting/custom-homepage-dashboard` |

Also `GET <metabase-url>/api/user?include_deactivated=false` (paginate by
`limit`/`offset` if the envelope reports `total > 100`) — needed for the
user purge in step 5.

Print a single status table:

```
Setting                         Current                          Target                          Status
site-name                       <current>                        <target>                        OK / WRONG
site-url                        <current>                        <target>                        OK / WRONG
report-timezone                 <current>                        <target>                        OK / WRONG
email-from-name                 <current>                        DataXcel Support                OK / WRONG
email-reply-to                  <current>                        ["support@xcel.software"]       OK / WRONG
admin-email                     <current>                        scline@xcel.software            OK / WRONG
allowed-iframe-hosts            <current, truncated>             <merged>                        OK / NEEDS-MERGE
custom-homepage-dashboard       <current id> (<name>)            <Dashboard Report Menu id>      OK / WRONG / MISSING
Users found                     <N total>                        (inventory only)                —
```

## Step 4 — apply settings (RISKY — one confirm per write)

For each of settings 1–8, if Status is OK skip silently. For each one that
needs a change, ask `yes` per write, showing the exact URL + body. Apply
them in the table order.

### 4.1 site-name

Target = `--site-name` if provided, else `<Slug> Reporting` (slug
title-cased). Reminder to user before showing the confirm: "This is
Mike's preferred convention — override per customer with `--site-name`."

```
PUT <metabase-url>/api/setting/site-name
{"value": "<target>"}
```

### 4.2 site-url

Target = `<metabase-url>` — i.e. `https://<slug>.xcel.report` unless
overridden. **Always HTTPS.** Reject `http://` or any domain that is not
`<slug>.xcel.report` (or the override). Exact string match including
scheme and no trailing slash.

```
PUT <metabase-url>/api/setting/site-url
{"value": "https://<slug>.xcel.report"}
```

If current is `http://...` or the wrong host, call it out explicitly in
the confirm prompt — that's why this exists.

### 4.3 report-timezone

Target = resolved `--timezone` (default `America/Boise`). IANA only.

```
PUT <metabase-url>/api/setting/report-timezone
{"value": "America/Boise"}
```

### 4.4 email-from-name

Target = literal string `DataXcel Support`. Hard-coded — not a flag.

```
PUT <metabase-url>/api/setting/email-from-name
{"value": "DataXcel Support"}
```

### 4.5 email-reply-to

Target = JSON array `["support@xcel.software"]`. **Must be an array, not a
plain string** — Metabase rejects a string here with 400. Hard-coded — not
a flag.

```
PUT <metabase-url>/api/setting/email-reply-to
{"value": ["support@xcel.software"]}
```

### 4.6 admin-email

Target = literal string `scline@xcel.software`. Hard-coded — not a flag.
This is the Metabase admin → Settings → General → Email → "Email address
for help requests" field. It's the address Metabase shows users in error
pages and "contact your admin" links. Stan Cline is the canonical admin —
same human whose email is in the team allowlist below (the demo-user
purge protects this address from deactivation).

```
PUT <metabase-url>/api/setting/admin-email
{"value": "scline@xcel.software"}
```

Verify with a GET:

```
GET <metabase-url>/api/setting/admin-email
→ assert response == "scline@xcel.software"
```

### 4.7 allowed-iframe-hosts

Read the current value. Ensure these four hosts are present (add any that
are missing, preserve everything else):

- `board.xcel.report`
- `home.xcel.report`
- `ai.xcel.report`
- `metagent.app`

Metabase stores this as a string with each host on its own line (the
admin UI uses a newline separator on every instance we run). Preserve
the existing separator format and existing entries — only append missing
ones. Do NOT replace or de-duplicate aggressively; if the customer (or
the seed clone) added a host, leave it.

If all four are already present, skip with a one-line "iframe allowlist
already has board/home/ai/metagent — no change."

```
PUT <metabase-url>/api/setting/allowed-iframe-hosts
{"value": "<existing>\nboard.xcel.report\nhome.xcel.report\nai.xcel.report\nmetagent.app"}
```

(Build the body off the actual current value — do not hard-code the
example above.)

### 4.8 custom-homepage-dashboard

The canonical homepage on every customer instance is a dashboard literally
named `Dashboard Report Menu`. If `custom-homepage-dashboard` is unset, or
points at a dashboard whose name is NOT `Dashboard Report Menu`, look up
the right id and PUT it.

Lookup:

```
GET <metabase-url>/api/search?q=Dashboard%20Report%20Menu&models=dashboard
```

Filter results to where `name == "Dashboard Report Menu"` (exact, case
sensitive). Expected: exactly one hit. If zero hits, stop with an error
— the seed-set clone is broken; do not silently pick a substitute.
If multiple hits, prefer the one in the root collection (smallest
`collection_id` / null collection).

```
PUT <metabase-url>/api/setting/custom-homepage-dashboard
{"value": <dashboard-id>}
```

Also ensure `enable-custom-homepage` is true if Metabase exposes it as a
separate setting on this version (newer Metabase auto-enables when
`custom-homepage-dashboard` is set; older does not). If you see an
`enable-custom-homepage` row in `GET /api/setting`, PUT it to `true` the
same way.

## Step 5 — archive non-team users (RISKY — single batch confirm)

Use the user list from Step 3.

**Keep allowlist (do NOT archive):**

Hard-coded Xcel team — case-insensitive match:

- `mhagberg@xcel.software`
- `scline@xcel.software`
- `tburningham@xcel.software`

Plus the `.jobxcel.ai` aliases for the same humans (treat the two domains
as interchangeable):

- `mhagberg@jobxcel.ai`
- `scline@jobxcel.ai`
- `tburningham@jobxcel.ai`

Plus everything in `--archive-allowlist` (additive — those users are
KEPT, not archived). Trim whitespace, lowercase, dedup.

**System allowlist (never archive):**

- Any email starting with `noreply@`
- `metabase@metabase.localhost`
- Anything where the user record's `is_installer` flag is true on the
  `/api/user` response

**Common leftover demo users to flag explicitly.** When you build the
deletion queue, mark each of these by name if you see them so the user
recognises them — they're the usual suspects carried over from cloning
the `single.xcel.report` demo template:

- `Corbin Taylor`
- `DataXcel PlayGround User`
- `Julie Allen`
- `Randy Fullmer`
- `playground@xcel.software`

(Anything matching by name OR email triggers the flag; the deletion
itself is still keyed on the resolved Metabase user id.)

Build the deletion queue (everything in the active user list that is NOT
in any allowlist). Print it as a numbered table:

```
Pending archive (N):
  1. Corbin Taylor              <corbin@example.com>          id=42  (known demo user)
  2. DataXcel PlayGround User   <playground@xcel.software>    id=43  (known demo user)
  3. Joe Customer               <joe@oldcustomer.com>         id=51
  ...
```

If the queue is empty, print "No non-team users — nothing to archive" and
move on.

Confirm the whole queue at once — single prompt, not per-user. There can
be a dozen leftover demo users on a freshly-cloned instance and per-user
confirms are friction.

> Archive **N users** listed above from `<metabase-url>`? Each will be
> deactivated via `DELETE <metabase-url>/api/user/<id>` (Metabase soft-
> deactivates — preserves the user's authored questions/dashboards so
> migration authorship stays intact, just blocks login).
>
> Type `yes` to proceed, `skip` to leave them in place, anything else aborts.

On `yes`, loop the queue and call `DELETE /api/user/<id>` for each. Print
one line per user (`archived` or `error: <body>`). On the first non-2xx,
stop the loop and print the error — do not blast through.

On `skip`, print "Non-team users left in place" and move on.

## Step 6 — final summary

Print a single green-on-success table:

```
Customer: <slug>
Metabase: <metabase-url>

Setting                         Status
site-name                       OK ("Lunstrum Reporting")
site-url                        OK (https://lunstrum.xcel.report)
report-timezone                 OK (America/Boise)
email-from-name                 OK (DataXcel Support)
email-reply-to                  OK (["support@xcel.software"])
admin-email                     OK (scline@xcel.software)
allowed-iframe-hosts            OK (board, home, ai, metagent present)
custom-homepage-dashboard       OK (id=42 "Dashboard Report Menu")

Users archived: <n>
Users kept:     <n>   (team + --archive-allowlist + system)
```

Final lines:

```
Configuration complete for <slug>.

Next: /validate-hub-dashboards <slug>
```

Stop.

## Why this exists

Before this skill, every onboarding involved a human clicking around
Metabase Settings and (worse) eyeballing the iframe allowlist and the
custom homepage dashboard. That's an unreliable last mile right before
go-live. `configure-customer-metabase` makes the canonical settings
declarative: every customer gets the same configuration, applied the
same way, with the same shared API key, with the same audit trail in
the confirm prompts.

It also stripes the "destructive but routine" work — deactivating leftover
demo users — out of `/finalize-customer-metabase` so that finalize is now
purely about adding the customer's real users at the very end.

## What this skill does NOT do

- Does NOT add new customer users — that's `/finalize-customer-metabase`,
  which runs LAST, after both validation skills are green.
- Does touch the Metabase database connection — **Step 0** updates the
  cloned tenant's `db id=2` to point at the customer's actual warehouse.
  This is a belt-and-suspenders re-application of the same update
  `/onboard-customer-postcall` Step 6 makes. Both skills do it so that
  whichever one runs second still verifies the connection is right
  before anything downstream queries it. NEVER skip — see the "Why"
  in Step 0.
- Does NOT install iframes (briefing iframe is the briefing skill's job;
  Hub iframe is the hub skill's job). This skill only adds the iframe
  hosts to the allowlist so those iframes can render.
- Does NOT verify the customer's data is correct vs Sage — that's
  `/validate-customer-metabase`.
- Does NOT verify all dashboards' cards render — that's
  `/validate-hub-dashboards`.

## Notes / gotchas

- **`email-reply-to` MUST be a JSON array.** Putting a plain string
  there returns 400 with `should be a sequence`. Same shape as the
  Metabase admin UI sends from Settings → Email.
- **`allowed-iframe-hosts` is a newline-separated string, not an array.**
  This is Metabase-version-dependent — on some versions it is an array;
  on the v0.61.x cluster we run, it's a string with each host on its
  own line. Read the current value type and preserve it. If you ever
  see an array, append; if a string, append with the same separator
  already in use.
- **`DELETE /api/user/<id>` is soft-deactivate, not hard delete.**
  Deactivated users disappear from login screens but their authored
  questions/dashboards remain attributed to them — exactly what we want
  for a cloned-from-demo cleanup.
- **Why the shared API key works.** Every customer instance on the
  shared EKS Metabase cluster is cloned from the `single` template DB,
  which carries the same API key over. That's why Lunstrum / Hallowell /
  Roth / Dietrich / Bookout / West / AIS / Valley Glass all authenticate
  with the same `mb_OtooFk7pInjCBF9EzZb4sT/...` key. Dedicated-instance
  customers (`dd`, `brekhus`, `jolma`, etc.) have their own keys
  recorded in `XcelConnectAndUpdater/CLAUDE.md`.
- **Default timezone `America/Boise`** matches the Xcel Software /
  Idaho-based customer baseline. Override per customer (`--timezone
  America/Denver` for Mountain Time but in CO/WY, `--timezone
  America/Chicago` for CT, etc.).
- **Default site name `<Slug> Reporting`** is Mike's preferred
  convention. Customers regularly want their full company name (e.g.
  `Acme Construction Analytics`) — pass `--site-name` to override.
