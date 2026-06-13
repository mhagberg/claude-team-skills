---
name: onboard-writeback-sage-user
description: Phase 1 of Sage write-back onboarding — guides the customer's IT to create the least-privilege Sage 100 Contractor API user (in the API security group, NOT Company Administrator; security P1 #9) that DataXcel posts writes under, and captures the username/password + the live company database + SQL data source for the later phases. Required arg `<slug>`.
---

# onboard-writeback-sage-user

## Notation

`<angle brackets>` = placeholder. For `brekhus`, `<slug>` = `brekhus`. Non-bracket text is literal.

You are running **onboard-writeback-sage-user** — Phase 1 of write-back onboarding. Goal: get a least-privilege Sage login created on the customer side and capture the four values the rest of the flow needs. Normally invoked from `/onboard-writeback` Phase 1.

## Where each arg comes from

| Arg | Required? | Where it comes from |
|-----|-----------|---------------------|
| `<slug>` | Required | Same slug as `/onboard-customer`. `^[a-z0-9-]+$`. |

No other args — everything else is captured FROM the customer during this phase.

## Why least-privilege (P1 #9)

Writes are posted under this Sage user and recorded in Sage's audit trail. It must be in the **API** security group only — **never** Company Administrator — so a compromised connector can't do more than the create-only write surface allows.

## Step 1 — send the customer the instruction

Print this for the operator to relay to the customer's IT (also point them at the IT HTML quickstart `Sage-API-Write-Back/docs/it-writeback-quickstart.html`, Step 1):

> In Sage **Database Administration**, create a user (suggested name `DATAXCEL-API`) and add it to the **API** security group on your live company. Do NOT make it Company Administrator. Send us the username + password over your secure channel.

PAUSE for the customer to do it.

## Step 2 — capture the four values

When the customer responds, capture and confirm back (mask the password):

| Value | Example | Source |
|-------|---------|--------|
| `<SageApiUser>` | `DATAXCEL-API` | customer just created it |
| `<SageApiPassword>` | `••••` | customer's secure channel |
| `<CompanyDatabase>` | `Brekhus Tile & Stone` | the live company file — cross-check `XcelConnectAndUpdater/CLAUDE.md` (captured at read-only onboarding) |
| `<DataSource>` | `BTSSRV` | the Sage SQL data source — same CLAUDE.md customer table |

If the company DB / data source are already in `XcelConnectAndUpdater/CLAUDE.md` for `<slug>`, read them from there instead of asking again.

## Done

Report the four captured values (password masked) back to the operator / `/onboard-writeback`. They feed straight into **Phase 2** (`/onboard-writeback-provision <slug> --company-db "<CompanyDatabase>" --datasource <DataSource> --sage-user <SageApiUser>`). Do not proceed to provisioning here — that's the next skill.
