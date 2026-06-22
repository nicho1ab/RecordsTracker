# QNAP Pilot Readiness Index

Use this index as the ordered pre-invite path for the QNAP hosted CCLD pilot.
It ties together the operator checklist, runtime guide, auth readiness notes,
tester invitation decision, seeded import evidence, route evidence, and known
limitations.

This is a documentation index only. It does not change app behavior, scripts,
routes, auth, retrieval, imports, database schema, or deployment.

## 1. Confirm Pilot Scope

- QNAP Docker is the first pilot runtime, not a permanent platform lock-in.
- Early tester scope is ylc.org-oriented pilot validation for this public-interest
  hobby project, not a DSCC project.
- The pilot is CCLD-only and uses a seeded or imported test corpus with
  PostgreSQL-backed hosted page data.
- The pilot does not prove public-source completeness, public-source absence,
  legal findings, facility-wide conclusions, harm, abuse, neglect, liability, or
  rights-deprivation conclusions.

Start with the [QNAP pilot operator checklist](qnap-pilot-operator-checklist.md)
and keep [known limitations](../user/known-limitations.md) visible throughout
the readiness review.

## 2. Prepare Environment

Use these documents and files:

- [QNAP Docker runtime guide](qnap-docker-runtime.md).
- `.env.example` as the placeholder-only template.
- [QNAP pilot operator checklist](qnap-pilot-operator-checklist.md).
- `scripts/verify-qnap-pilot-workflow.ps1`.

Copy `.env.example` to an untracked `.env` on the deployment host, replace
host-local values there, and keep QNAP-specific paths and secrets out of
committed files.

Run:

```powershell
.\scripts\verify-qnap-pilot-workflow.ps1 -EnvFile .env
```

Do not continue toward invitations until the verifier passes or only reports
expected placeholder warnings that are resolved before external tester use.

## 3. Confirm Data Readiness

Use:

- [QNAP pilot seeded import evidence](qnap-pilot-seeded-import-evidence.md).
- `scripts/summarize-qnap-pilot-seeded-import-evidence.ps1`.

After a validated CCLD hosted artifact or seeded corpus is imported, run:

```powershell
.\scripts\summarize-qnap-pilot-seeded-import-evidence.ps1 -EnvFile .env
```

For placeholder or template validation without Docker/PostgreSQL checks, run:

```powershell
.\scripts\summarize-qnap-pilot-seeded-import-evidence.ps1 -EnvFile .env.example -SkipDatabaseCheck
```

The evidence should show PostgreSQL-backed page-data expectations, migrated
database readiness, imported source-derived row counts, safe source traceability
linkage, raw artifact backup acknowledgement, and no source-completeness or
legal conclusions.

## 4. Confirm Route Readiness

Use:

- `scripts/summarize-qnap-pilot-route-evidence.ps1`.
- [Hosted scaffold guide](hosted-scaffold.md).
- [QNAP Docker runtime guide](qnap-docker-runtime.md) route guidance.

After the app is running and the QNAP verifier passes, run:

```powershell
.\scripts\summarize-qnap-pilot-route-evidence.ps1 -BaseUrl http://<host-name-or-ip>:<CCLD_HOSTED_PORT> -TimeoutSeconds 10
```

For safe local placeholder validation without a running server, run:

```powershell
.\scripts\summarize-qnap-pilot-route-evidence.ps1 -BaseUrl http://127.0.0.1:9 -TimeoutSeconds 1 -AllowUnavailable
```

Expected protected, setup-required, safe-empty, and missing-job states are
acceptable route evidence. Route evidence does not run imports, retrieval,
feedback submission, live CCLD calls, GitHub calls, reviewer-created writes, or
database mutations. Route evidence must not print response bodies, secrets, raw
artifacts, raw server paths, cookies, provider subjects, provider issuers, or
connection strings.

## 5. Confirm Auth Readiness

Use:

- [QNAP pilot auth readiness](qnap-pilot-auth-readiness.md).
- [QNAP pilot access-method decision](qnap-pilot-access-method-decision.md).
- [ADR-0011](../decisions/ADR-0011-hosted-tester-mvp-auth-access-roles.md).
- [ADR-0014](../decisions/ADR-0014-hosted-tester-mvp-auth-provider-and-role-implementation.md).

QNAP pilot mode uses `CCLD_HOSTED_TESTER_AUTH_MODE=production` and keeps
`CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH=disabled`.

Real login, OIDC/OAuth2 callback handling, sessions, cookies, user tables,
self-service signup, and invitation workflow remain deferred. `/auth/status`
evidence is a safe capability summary only and must not expose private provider
values, provider subjects, provider issuers, raw claims, tokens, cookies,
private headers, callback secrets, or connection strings.

Do not share any external tester link, credential, network rule, VPN rule, or
reverse proxy route until the access-method decision is recorded. The decision
must state the selected temporary access method, named testers or approved group,
role/scope, environment/host scope, start and expiration dates, revocation
method, feedback triage owner, backup/evidence confirmation, known-limitations
acknowledgement, and that the method is not production auth unless real OIDC and
session implementation exists.

## 6. Confirm Tester Invitation Decision

Use [QNAP pilot tester invitation decision](qnap-pilot-tester-invitation-decision.md).

Before invitations, the operator must decide and record:

- Who may be invited.
- Which role and scope each tester receives.
- Who approved the access.
- How access can be revoked.
- Who can perform revocation.
- How tester feedback and GitHub Issues will be triaged.
- Whether the evidence packet is complete.
- That known limitations have been acknowledged.

Do not invite testers until there is a deliberate access-control decision for
how they will authenticate, what they can access, and how access can be revoked.

## 7. Capture Evidence Packet

Optional local command:

```powershell
.\scripts\build-qnap-pilot-evidence-packet.ps1 -EnvFile .env -BaseUrl http://<host-name-or-ip>:<CCLD_HOSTED_PORT> -KnownLimitationsAcknowledged
```

For placeholder/template validation without Docker/PostgreSQL checks or a
running server:

```powershell
.\scripts\build-qnap-pilot-evidence-packet.ps1 -EnvFile .env.example -SkipDatabaseCheck -AllowRouteUnavailable -BaseUrl http://127.0.0.1:9
```

The packet command is optional, local, read-only operator convenience. It uses
the existing verifier, seeded import evidence, and route evidence scripts, then
writes redacted Markdown under ignored `data/processed/qnap-pilot-evidence/`.
It is not an audit export, legal report, product export packet, public report,
GitHub issue, or official certification. Operators must review generated packets
before sharing them, and generated evidence files must not be committed.

The evidence packet should include:

- QNAP verifier output summary.
- Seeded import evidence command output.
- Route evidence command output.
- Auth readiness decision.
- Access-method decision.
- Tester invitation/access-control decision.
- Feedback configuration decision: intentionally disabled or fully configured.
- Retrieval configuration decision: intentionally disabled or fully configured
  with persistent raw artifact storage.
- PostgreSQL backup plan.
- Raw artifact backup plan.
- Known limitations acknowledged.
- A statement that no public-source completeness, legal, facility-wide, harm,
  abuse, neglect, liability, or rights-deprivation conclusions are made from the
  evidence.

Keep the evidence packet free of `.env` values, secrets, tokens, callback URLs,
tenant IDs, private URLs, hosted URLs, raw artifact contents, raw source
narrative, raw server paths, cookies, provider subjects, provider issuers, raw
provider claims, private headers, and connection strings.

## 8. Do Not Invite Until

Do not invite early testers until all of these are true:

- `.env` is configured on the host and remains untracked.
- QNAP verifier passes.
- PostgreSQL migrations and data readiness are confirmed.
- Route evidence is captured.
- Auth readiness has been reviewed.
- Access method, role/scope, approval, and revocation are deliberately decided.
- Feedback and retrieval configuration decisions are documented.
- PostgreSQL and raw artifact backup plans are documented.
- Known limitations are acknowledged.
- No public-source completeness, legal, facility-wide, harm, abuse, neglect,
  liability, or rights-deprivation conclusions are made from pilot evidence.

## 9. Completion Marker

After the access-method decision is recorded and the evidence packet is
generated from real pilot inputs, the QNAP pilot pre-invite readiness path is
complete.

Complete means the repository has the documented operator path and local commands
needed to prepare the pilot. It does not mean production OIDC, production
deployment, anonymous public access, or broader product functionality is
implemented.

Do not add more readiness-only branches after this unless a concrete validation,
security, privacy, data-integrity, or tester-blocking defect is found.

### LAN Smoke Test Status

The first LAN smoke test passed. Docker Engine (`27.1.2-qnap8`) and Docker
Compose (`v2.29.1-qnap2`) were confirmed available via Container Station. The
app and PostgreSQL containers started, Alembic migrations ran, and both the
health route (`/health`) and landing page (`/`) responded `200` on the LAN.

The app is LAN-only at this stage. No Cloudflare Tunnel, Cloudflare Access,
DNS, reverse proxy, TLS certificate, or public internet exposure has been
configured.

### Next Access-Layer Milestone

The next milestone is **Cloudflare Tunnel + Cloudflare Access**. Until that is
configured, the app is accessible only on the QNAP host's local network. Do
not share external tester links, credentials, network rules, VPN rules, or
reverse proxy routes until the access-method decision is recorded and either a
managed access layer or an approved alternative is in place.

The Cloudflare Access identity approach has been recorded in
[qnap-pilot-access-method-decision.md](qnap-pilot-access-method-decision.md)
section 9. The selected method is Cloudflare Tunnel + Cloudflare Access with
individually allowlisted testers. Open questions (tester email list, pilot
hostname, identity provider choice, and Access policy owner) must be resolved
before any tester-facing URL is shared.

The operator runbook for creating the tunnel and configuring Access is in
[qnap-cloudflare-tunnel-access-setup.md](qnap-cloudflare-tunnel-access-setup.md).
The next live operator step is to follow that runbook, complete the Access
verification smoke tests in section 9, and capture the evidence in section 10.

## 10. Deferred Items

These remain deferred and must not be implied by readiness evidence:

- **Cloudflare Tunnel** (next access-layer milestone — not yet configured).
- **Cloudflare Access** (next access-layer milestone — not yet configured).
- Real OIDC/login.
- OIDC/OAuth2 callback handling.
- Sessions or cookies.
- User tables.
- Self-service signup.
- Invitation workflow implementation.
- Account management UI.
- Identity provider integration.
- Deployment hardening.
- New retrieval record types.
- Non-CCLD sources.
- Export UI or audit UI.
- Raw artifact viewer.
- Broader UI redesign.