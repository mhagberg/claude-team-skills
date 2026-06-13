---
name: onboard-writeback
description: End-to-end walkthrough to give an existing DataXcel customer Sage 100 Contractor WRITE-BACK (Claude creates change orders / AP invoices / journal entries through the native API). Drives the 4 write-back phases in order — Sage least-priv user → operator provisioning → customer one-click install → record + verify — confirming before each, piping captured values (setup key, agent token, mesh IP) forward. Only required arg is `<slug>`. Pass `--from-phase N` to resume. Runs AFTER the customer is already live on read-only DataXcel (`/onboard-customer`).
---

# onboard-writeback

## Notation

Anything in `<angle brackets>` is a **placeholder** — replace it with your actual value. For the customer `brekhus`, `<slug>` means `brekhus`, so `/onboard-writeback <slug>` becomes `/onboard-writeback brekhus`. Text NOT in angle brackets is literal.

You are running the **onboard-writeback** orchestrator. You are the conductor for turning on **write-back** for one already-onboarded DataXcel customer. The operator types `/onboard-writeback <slug>` once; you drive all four phases, one at a time, in order.

> **Prerequisite:** the customer is already live on read-only DataXcel (their `/onboard-customer` run is done — they have a NetBird `<slug>-sage` peer, a Metabase workspace, and a lead record). Write-back rides on top of that. If they are not yet onboarded, stop and tell the operator to run `/onboard-customer <slug>` first.

## Where each arg comes from

| Arg | Required? | Where it comes from |
|-----|-----------|---------------------|
| `<slug>` | Required | Same slug used in `/onboard-customer`. Lowercase alnum + dashes (`^[a-z0-9-]+$`). |
| `--from-phase <N>` | Optional | Resume at phase N (1-4). Default 1. |

Every later value — the Sage **API-security-group** username/password, the NetBird setup key, the minted agent token, the box's mesh IP — is captured by the phase that needs it and piped forward. None are required up front.

**Execution mode (harness note):** a skill body cannot invoke another slash command. At each "invoke sub-skill" point, **print the EXACT next command the operator should type**, with captured values pre-filled, then PAUSE. When the operator returns (`done` or pasted stdout), continue.

## Source of truth

- Onboarding doc: `Sage-API-Write-Back/docs/ONBOARDING.md`
- Operator script: `Sage-API-Write-Back/deploy/provision-customer.sh`
- Customer installer: `Sage-API-Write-Back/deploy/install-writeback.ps1`
- Security model: `Sage-API-Write-Back/docs/SECURITY-REVIEW-2026-06-12.md`

## Step 1 — validate + open the onboarding doc

Validate `<slug>` against `^[a-z0-9-]+$`; reject + stop on mismatch. Validate `--from-phase` (1-4) if given.

Open the onboarding reference for the operator:
```
open Sage-API-Write-Back/docs/ONBOARDING.md   # or the HTML on the Desktop
```
Confirm with the operator that the customer is already read-only-live (see Prerequisite). Get `continue`.

## Phase 1 — Sage least-privilege API user (security P1 #9)

Write-back must post under a Sage user in the **API security group**, NOT Company Administrator. This is the only manual Sage-side step and the customer's IT does it once in **Database Administration**.

Print, for the operator to relay to the customer:

> Create a Sage user (e.g. `DATAXCEL-API`) and assign it to the **API** security group on the live company. Do NOT make it Company Administrator. Send us the username + password over your secure channel.

PAUSE until the operator confirms they have the `<SageApiUser>` + `<SageApiPassword>` and the live `<CompanyDatabase>` + `<DataSource>` (from `XcelConnectAndUpdater/CLAUDE.md`, captured during read-only onboarding).

## Phase 2 — Operator provisions (NetBird + token)

Print the EXACT command and PAUSE:
```
/onboard-writeback-provision <slug> --company-db "<CompanyDatabase>" --datasource <DataSource> --sage-user <SageApiUser>
```
That sub-skill creates the customer's NetBird group + scoped **9447-only** policy + setup key, mints the agent token, and prints the **single PowerShell command** to send the customer. Capture from its output: the **customer one-liner** and the **minted agent token**.

## Phase 3 — Customer one-click install

Send the customer the one-liner from Phase 2. They run it in an **elevated PowerShell** on their Sage server:
```
$p = @{ SetupKey='…'; AgentToken='…'; CompanyDatabase='…'; DataSource='…'; SageApiUser='…'; SageApiPassword='…' }
irm https://get.xcel.report/writeback.ps1 | iex; Install-Writeback @p
```
The installer self-tests and prints the box's **mesh IP** (`100.67.x`). PAUSE until the operator pastes back that mesh IP (or `done` + the IP).

## Phase 4 — Record the agent + verify

Print the EXACT command and PAUSE:
```
/onboard-writeback-register <slug> --mesh-ip <mesh-ip> --agent-token <token-from-phase-2>
```
That sub-skill records `sage_agent_url` + `sage_agent_token` on the lead and verifies the connector reaches `/healthz`, pins the cert, and that a **dry-run** write previews correctly.

## Done

Report: customer `<slug>` now has write-back. The first real write should still be a human-approved dry-run → confirm together (the confirm gate enforces preview-before-write). Note any phase the operator skipped.
