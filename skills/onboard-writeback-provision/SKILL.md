---
name: onboard-writeback-provision
description: Operator side of Sage write-back onboarding — creates the customer's NetBird group + auto-join setup key + a SCOPED TCP-9447-only policy (MCPConnector → customer-<slug>), mints the agent bearer token via Google Secret Manager creds, and prints the SINGLE elevated-PowerShell command to send the customer's IT (no copy-paste of secrets by the operator). Required arg `<slug>`; Sage params via flags. Wraps `Sage-API-Write-Back/deploy/provision-customer.sh`.
---

# onboard-writeback-provision

## Notation

Anything in `<angle brackets>` is a **placeholder**. For `brekhus`, `<slug>` = `brekhus`. Text not in brackets is literal.

You are running **onboard-writeback-provision** — the operator step that stages a customer's write-back infrastructure on the DataXcel side and hands the customer ONE command to run. Normally invoked from `/onboard-writeback` Phase 2.

## Where each arg comes from

| Arg | Required? | Where it comes from |
|-----|-----------|---------------------|
| `<slug>` | Required | Same slug as `/onboard-customer`. `^[a-z0-9-]+$`. |
| `--company-db "<Company Database>"` | Required | The live Sage company-file name (e.g. `Brekhus Tile & Stone`) — from `XcelConnectAndUpdater/CLAUDE.md`, captured at read-only onboarding. |
| `--datasource <DataSource>` | Required | The Sage SQL data source (e.g. `BTSSRV`). |
| `--sage-user <SageApiUser>` | Required | The Sage **API-security-group** username (P1 #9) the customer's IT created. |

The Sage password is NOT passed here — the operator types it into the printed command privately, or the customer's IT keeps it on their side. The NetBird API token comes from **Google Secret Manager** (`netbird-api-token`), never typed.

## Prerequisites

- The `MCPConnector` NetBird group + the connector pod on the `mcp-connector-key` already exist (one-time mesh hardening — `Sage-API-Write-Back/docs/netbird-hardening-plan.md`).
- `gcloud` is authenticated as an account with Secret Manager access (`mhagberg@xcel.software`). If a reauth is needed, tell the operator to run `! gcloud auth login mhagberg@xcel.software` and re-run.

## Step 1 — confirm args

Echo back the slug, company DB, datasource, and Sage user. Confirm with the operator. Get `yes`.

## Step 2 — run the provisioning script

Print the EXACT command and run it (the operator supplies the Sage password at the prompt / inline):
```
cd Sage-API-Write-Back/deploy
./provision-customer.sh <slug> "<Company Database>" <DataSource> <SageApiUser> '<SageApiPassword>'
```

This creates (idempotent):
- NetBird group `customer-<slug>`,
- a reusable auto-join **setup key** (assigns ONLY that group),
- policy `mcp-connector-to-<slug>` — `MCPConnector → customer-<slug>`, **TCP 9447 only**,
- a freshly **minted agent token** (`swa_…`),

and prints the single PowerShell block to send the customer.

## Step 3 — hand off

Capture from the script output and report back to the operator (and to `/onboard-writeback`):
- the **customer one-liner** (the `irm …/writeback.ps1 | iex; Install-Writeback @p` block),
- the **minted agent token** (needed again in `/onboard-writeback-register`).

Remind the operator: send the one-liner to the customer's IT via a secure channel (it carries the setup key + agent token). The IT-facing **HTML quickstart** (`Sage-API-Write-Back/docs/it-writeback-quickstart.html`) can be sent alongside for the non-technical walkthrough.

Do NOT proceed to record the lead yet — that happens in `/onboard-writeback-register` after the customer runs the installer and reports their mesh IP.
