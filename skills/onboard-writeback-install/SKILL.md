---
name: onboard-writeback-install
description: Phase 3 of Sage write-back onboarding — hands the customer's IT the SINGLE elevated-PowerShell command (from the provision step) plus the IT HTML quickstart, walks them through running the one-click installer (install-writeback.ps1) on their Sage server, and captures the box's NetBird mesh IP that the installer self-test prints at the end. Required arg `<slug>`; the customer command + token come from `/onboard-writeback-provision`.
---

# onboard-writeback-install

## Notation

`<angle brackets>` = placeholder. For `brekhus`, `<slug>` = `brekhus`. Non-bracket text is literal.

You are running **onboard-writeback-install** — Phase 3 of write-back onboarding. Goal: get the customer to run the one-click installer and report back their mesh IP. You do NOT run anything on the customer's box — they do, with one command. Normally invoked from `/onboard-writeback` Phase 3.

## Where each arg comes from

| Arg | Required? | Where it comes from |
|-----|-----------|---------------------|
| `<slug>` | Required | Same slug. `^[a-z0-9-]+$`. |
| `--customer-command "<block>"` | Optional | The exact PowerShell block printed by `/onboard-writeback-provision`. If omitted, re-read it from that phase's output / the operator pastes it. |

## Step 0 — pick which walkthrough to open

You'll run this step either WITH the customer's IT or solo on their box. Ask the operator which, and `open` the matching HTML (or both):

| Doing it… | Open |
|-----------|------|
| **With the customer / IT** | `Sage-API-Write-Back/docs/it-writeback-quickstart.html` (plain-language, send it to them too) |
| **Yourself / internal** | `Sage-API-Write-Back/docs/onboarding-playbook.html` (operator playbook) |

```
open Sage-API-Write-Back/docs/it-writeback-quickstart.html
open Sage-API-Write-Back/docs/onboarding-playbook.html
```

## Step 1 — hand over the command

Give whoever is running it (the customer's IT, or you) the single PowerShell block from Phase 2 (carries the setup key + agent token):
```
$p = @{ SetupKey='…'; AgentToken='…'; CompanyDatabase='…'; DataSource='…'; SageApiUser='…'; SageApiPassword='…' }
irm https://broker.xcel.report/updates/writeback.ps1 | iex; Install-Writeback @p
```
Run it in an **elevated PowerShell** (Run as Administrator) on the **Sage server**. PAUSE.

## Step 2 — what the installer does (so you can answer questions)

It is fully automated + idempotent ([`deploy/install-writeback.ps1`](../../../Sage-API-Write-Back/deploy/install-writeback.ps1)):

| # | Step |
|---|------|
| 1 | Installs + joins NetBird with the setup key |
| 2 | Downloads + installs the Write-Agent service (+ SageBridge) |
| 3 | Sets Sage company/datasource/API user + token — **diagnostics OFF** |
| 4 | Windows service + firewall inbound 9447 **scoped to the connector /32** |
| 5 | Self-test `/healthz` → prints company, Sage version, and the box's **mesh IP** |

## Step 3 — capture the mesh IP

On success the installer prints **"DONE. Write-back is installed and reachable"** and a `100.67.x.x` mesh IP. Have the operator paste it back.

**If it failed:** common causes — not elevated, NetBird didn't join (re-check the setup key), or the download host unreachable. Have them run `Get-Service SageWriteAgent` and check `C:\DataXcel\agent\*\logs`. Re-running the same command is safe (idempotent).

## Done

Report the captured **mesh IP** back to the operator / `/onboard-writeback`. It feeds **Phase 4** (`/onboard-writeback-register <slug> --mesh-ip <mesh-ip> --agent-token <token-from-phase-2>`). Do not record the lead here — that's the next skill.
