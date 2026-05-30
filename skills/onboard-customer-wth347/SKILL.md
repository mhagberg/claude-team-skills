---
name: onboard-customer-wth347
description: Install the WTH-347 Davis-Bacon certified-payroll iframe with a per-customer signed URL on a customer's Metabase WH-347 dashboard. CURRENTLY BLOCKED — per-customer signed-URL infra is wth-347 Phase 6 work and has not shipped yet; skill leaves the dashboard on the shared demo URL and logs the BLOCKED status.
---

# onboard-customer-wth347

## Notation

In this doc and everywhere else (README, playbook, other SKILL.md files), anything in `<angle brackets>` is a **placeholder** — replace it with your actual value. Example: for the customer named `lunstrum`, `<slug>` means `lunstrum`, so `/onboard-customer-wth347 <slug>` becomes `/onboard-customer-wth347 lunstrum`. Anything NOT in angle brackets is literal text to type as-is.

You are running the **onboard-customer-wth347** skill. Goal: install the
per-customer signed-URL iframe for the WTH-347 Davis-Bacon certified-payroll
app on the customer's Metabase **WH-347 Davis-Bacon Certified Payroll**
dashboard — same pattern as `board.xcel.report` (CEO Briefing) and
`home.xcel.report` (Dashboard Hub) use.

> **🛑 BLOCKED — read this first.**
>
> As of 2026-05-29, **the per-customer signed-URL infrastructure for the
> WTH-347 app does not exist yet**. The `wth-347-davis-bacon` submodule is
> pre-Phase-1, scaffold-only (see its `PROJECT-PLAN.md` status banner). The
> existing `mintIframeJwt` Cloud Function is a 5-minute TTL Phase-2
> placeholder that requires a Firebase Auth magic-link handshake — it is
> **NOT** a static long-lived per-customer HMAC token in the URL like
> `home.xcel.report/hub/<slug>?token=…` or
> `board.xcel.report/report/<slug>/<month>?…`.
>
> There is no `install_wth347_iframe.py`, no per-customer hosting domain
> (the planned `wth347.xcel.report` per `wth-347-davis-bacon` PLAN D2 has
> not been deployed), and no per-customer `customers/<slug>.yaml` in the
> submodule.
>
> **What this skill does TODAY:**
>
> 1. Verifies a "WH-347 Davis-Bacon Certified Payroll" dashboard exists on
>    `https://<slug>.xcel.report`. If not, prints "no WH-347 dashboard on
>    this tenant — nothing to install" and stops.
> 2. Reports the current iframe URL on the dashboard. If it is
>    `https://wth347-demo.web.app` (the shared demo), prints a BLOCKED
>    banner explaining the customer is on the demo URL until per-customer
>    signed-URL infra ships.
> 3. **Does NOT mint a token. Does NOT mutate the dashboard. Does NOT
>    change `allowed-iframe-hosts`.** Writing the demo URL again would be
>    a no-op; writing a fake "future" URL would break the iframe.
> 4. Prints the exact provisioning command that WILL be wired up once
>    Phase 6 of `wth-347-davis-bacon` ships, so the operator knows what
>    to re-run after the infra lands:
>    ```
>    python scripts/install_wth347_iframe.py --customer <slug>
>    ```
>
> Re-running this skill after Phase 6 ships will swap the demo iframe URL
> for the per-customer signed URL on the WH-347 dashboard and add the
> production host (likely `wth347.xcel.report`) to
> `allowed-iframe-hosts`. Until then, every real customer continues to
> share the demo URL.

**Execution mode:** read-only Metabase API checks (`GET`) run unprompted.
The dashboard + allowlist mutations that will be added when Phase 6 ships
must require explicit `yes` confirmation.

## Step 1 — validate args

Required:
- `<slug>` — must match the customer slug from earlier onboarding skills.

Optional:
- `--metabase-url <url>` — override the default `https://<slug>.xcel.report`.
- `--api-key <key>` — override the default shared `single.xcel.report`
  Metabase API key (read from `XcelConnectAndUpdater/CLAUDE.md` Metabase
  Instances table).

Print a one-line plan:

> Plan: install/refresh WTH-347 iframe for `<slug>` on
> `https://<slug>.xcel.report`. (Currently BLOCKED — see banner.)

## Step 2 — locate the WH-347 dashboard (READ-ONLY)

```bash
curl -s -H "x-api-key: <api-key>" \
  "https://<slug>.xcel.report/api/search?q=WH-347&models=dashboard"
```

Parse the response. Expect at most one dashboard whose `name` starts with
"WH-347 Davis-Bacon" (id varies per tenant; on Lunstrum it is `215`).

- If no result → print "WH-347 dashboard not provisioned on this tenant.
  Skip this skill — the customer doesn't use the certified-payroll iframe
  yet" and exit clean.
- If multiple results → list them and ask the user which is the correct
  one (should never happen — Metabase deduplicates dashboard names).

Save the dashboard id as `<dash_id>`.

## Step 3 — inspect the current iframe (READ-ONLY)

```bash
curl -s -H "x-api-key: <api-key>" \
  "https://<slug>.xcel.report/api/dashboard/<dash_id>"
```

Walk `dashcards` looking for an iframe-type virtual card. Match on
`visualization_settings.virtual_card.display == "iframe"` and pull
`visualization_settings.iframe` for the URL.

Compare the iframe URL against three states:

1. **`https://wth347-demo.web.app`** (or any `*.web.app` host that
   matches `wth347-demo`) → customer is on the shared demo URL.
   This is the current state for every real customer as of 2026-05-29.
2. **`https://wth347.xcel.report/<slug>?token=…`** (post-Phase-6 shape
   — exact path TBD) → per-customer signed URL is already installed.
   Print "WTH-347 already on per-customer signed URL — nothing to do"
   and exit clean.
3. **Any other URL** → unexpected; print the URL and ask the user how
   to proceed.

## Step 4 — print BLOCKED status and exit

Print a clearly-formatted block:

```
🛑 BLOCKED — WTH-347 per-customer signed URL is not yet available.

Customer:           <slug>
Dashboard:          <dash_id> on https://<slug>.xcel.report
Current iframe URL: https://wth347-demo.web.app (shared demo)

The wth-347-davis-bacon submodule is pre-Phase-1. Per-customer signed-URL
infra is Phase 6 work (see wth-347-davis-bacon/PROJECT-PLAN.md). Until
that ships:

  - Every real customer's WH-347 dashboard iframes the SHARED demo URL.
  - The demo URL is for testing only — there is no per-customer auth
    boundary on it today.
  - Do NOT pretend this is fixed. Do NOT mint a fake token. The skill
    intentionally leaves the dashboard untouched.

Once Phase 6 ships and install_wth347_iframe.py exists, re-run:

  python scripts/install_wth347_iframe.py --customer <slug>

That script will mint a fresh signed URL, add the production host to
Metabase's allowed-iframe-hosts, and swap the demo URL for the
per-customer signed URL on dashboard <dash_id>.

Until then: NEXT step is the rest of the onboarding sequence (this
skill is a no-op for the current build).
```

Exit 0 — the skill ran successfully even though the install was blocked.
That distinction matters for the parent `/onboard-customer` wrapper:
"blocked because the infra isn't built yet" must not look like
"errored". Print the BLOCKED banner unambiguously so a future operator
can grep the run log for it.

## Step 5 — manual fallback (BLOCKED — will become the real install path)

<details>
<summary><strong>Manual fallback — once per-customer signed-URL infra ships</strong></summary>

When the wth-347-davis-bacon Phase 6 work lands, this skill will start
calling the installer below. Today this command DOES NOT EXIST — the
script has not been written, the host has not been deployed, and the
per-customer YAML has not been created. The block is here so operators
know exactly what shape the eventual command will take.

```bash
cd /Users/mike/dev/projects/odoo_bank_metabase_payroll_reporting/wth-347-davis-bacon
python scripts/install_wth347_iframe.py --customer <slug>
```

The installer (modelled after
`dataxcel-board-reports-pipeline/scripts/install_briefing_iframe.py`) will:

1. Mint a signed JWT URL with the customer slug as a claim. URL shape
   (per `wth-347-davis-bacon/docs/architecture/security.md`): the SPA
   strips the JWT from the URL bar via `history.replaceState` and lives
   it in memory only. 5-min TTL refresh via `mintIframeJwt`. The static
   long-lived shape used by board/home is NOT in scope for the
   wth-347 design; the installer will mint whatever shape lands in
   Phase 6 (likely a longer-lived "iframe bootstrap token" with a
   shorter session JWT minted on viewer load).
2. Add `wth347.xcel.report` (or whatever D2 resolves to) to
   `allowed-iframe-hosts` on the customer's Metabase. Same
   read-append-write pattern as `install_briefing_iframe.py` and
   `install_hub_iframe.py`.
3. Locate the WH-347 dashboard via `GET /api/search?q=WH-347&models=dashboard`.
4. Snapshot the dashboard to
   `/tmp/wth347_iframe_rollback_<slug>_<dash>_<ts>.json` before any
   mutation.
5. Find the existing iframe dashcard (currently pointing at
   `wth347-demo.web.app`) and update its `visualization_settings.iframe`
   to the new per-customer signed URL in place. Same idempotency rules
   as the briefing installer — re-running just refreshes the URL.
6. PUT the updated dashboard with `dashcards`, `tabs`, and `parameters`
   preserved (Metabase 0.58+ requirement).

The fallback above is intentionally documented in detail so the
implementer of Phase 6 can ship it without having to re-derive the
shape — the briefing installer is the canonical reference.

</details>

## Step 6 — summary + next step

```
Customer: <slug>
Dashboard: <dash_id> on https://<slug>.xcel.report
Status: BLOCKED — per-customer signed-URL infra not yet built.
Customer remains on the shared demo URL until wth-347-davis-bacon
Phase 6 ships.

Next: continue the onboarding sequence — this skill is a no-op for
the current build. See README "Onboarding a new DataXcel customer".
```

Stop.
