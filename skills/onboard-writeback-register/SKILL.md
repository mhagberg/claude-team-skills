---
name: onboard-writeback-register
description: Final step of Sage write-back onboarding — after the customer ran the one-click installer and reported their NetBird mesh IP, records `sage_agent_url` + `sage_agent_token` on the customer's lead, then verifies the connector reaches the agent `/healthz`, captures + PINS the agent's TLS cert (P1 #10), and runs a dry-run write that previews cleanly (nothing committed). Required arg `<slug>` + `--mesh-ip` + `--agent-token`.
---

# onboard-writeback-register

## Notation

`<angle brackets>` = placeholder. For `brekhus`, `<slug>` = `brekhus`. Non-bracket text is literal.

You are running **onboard-writeback-register** — the close-out step that wires the just-installed agent into the customer's lead and proves write-back works end-to-end (preview only). Normally invoked from `/onboard-writeback` Phase 4.

## Where each arg comes from

| Arg | Required? | Where it comes from |
|-----|-----------|---------------------|
| `<slug>` | Required | Same slug. `^[a-z0-9-]+$`. |
| `--mesh-ip <100.67.x.x>` | Required | Printed by the installer (`install-writeback.ps1`) on the customer's box at the end of its self-test. The operator pastes it back. |
| `--agent-token <swa_…>` | Required | The token minted in `/onboard-writeback-provision`. |

## Step 1 — confirm

Echo: `sage_agent_url = https://<mesh-ip>:9447`, token `swa_…` (mask all but the last 4). Confirm with the operator. Get `yes`.

## Step 2 — record the agent on the lead

Set on the customer's lead record (Firestore `mcp_leads/<lead_uuid>`, or via the connector's admin path):
```
sage_agent_url   = https://<mesh-ip>:9447
sage_agent_token = <agent-token>
```
> The connector encrypts the token at rest (KMS, P1 #6). On the next OAuth connect / re-probe it verifies the URL is a **mesh address** + `/healthz` (P1 #8) and **pins the cert** (P1 #10). Confirm the customer's lead is a BYO-workspace lead (write-back requires a connected Metabase workspace — a demo lead is rejected).

## Step 3 — verify reachability + pin

From the connector pod (or any mesh-joined box), confirm the agent answers and the cert is pinnable:
```
curl -sk https://<mesh-ip>:9447/healthz          # expect {"status":"ok","company":"…"}
```
Confirm `status=ok` and the `company` matches the customer. If unreachable: check the customer's firewall allows the connector /32 on 9447, and that their NetBird peer is in `customer-<slug>` with the `mcp-connector-to-<slug>` policy enabled.

## Step 4 — dry-run proof (nothing written)

Have the operator ask Claude (in the customer's connector session) to **preview** a trivial change order or AP invoice with `confirm=false`. Confirm the response is a **preview** (status `validated`) that:
- resolves a real job/vendor and **echoes its name** (P0 #4 wrong-record guard),
- returns a **`confirm_token`** (P0 #1 confirm gate).

Do NOT commit during onboarding. The first real write is a human-approved preview → confirm the operator + customer do together.

## Done

Report: customer `<slug>` write-back is live and verified (reachable, pinned, dry-run previews cleanly). Hand the customer the sample prompts from `Sage-API-Write-Back/docs/ONBOARDING.md`. Remind them every write previews first and waits for their `yes`.
