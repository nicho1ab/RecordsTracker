# QNAP Pilot Access-Method Decision

Use this guide before any external tester link, credential, network rule, VPN
rule, reverse proxy route, temporary access route, or screen-share tester session
is shared for the QNAP-hosted CCLD pilot.

This is a decision scaffold only. It does not implement authentication,
networking, deployment, sessions, users, invitations, account management,
reverse proxy configuration, VPN configuration, routes, schemas, or app
behavior.

## 1. Purpose

- Record the access method before any external tester access path is shared.
- Make the selected temporary access method, limits, owner, scope, expiration,
  and revocation path explicit.
- Keep the pilot aligned with ADR-0011, ADR-0014, the QNAP auth readiness guide,
  the tester invitation decision, and the QNAP evidence packet.
- Confirm that this record does not make the selected access method production
  authentication.

## 2. Current Auth Reality

The current QNAP pilot readiness state is:

- Real login is not implemented.
- OIDC/OAuth2 callback handling is not implemented.
- Sessions and cookies are not implemented.
- User tables are not implemented.
- Invitation workflow implementation is not implemented.
- Local-dev fixture auth is not production authentication.
- QNAP pilot mode must keep `CCLD_HOSTED_TESTER_AUTH_MODE=production`.
- QNAP pilot mode must keep `CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH=disabled`.

Protected workflow routes may show sign-in-required or setup-required states
until a later approved authentication implementation exists. Do not interpret a
temporary access method as real OIDC, sessions, cookies, user tables, invitation
workflow, or production auth middleware.

## 3. Allowed Temporary Access-Method Categories

Choose one category and record why it fits the current pilot stage:

- No external tester access yet: allows operator-only readiness work and evidence
  capture. Does not allow external tester links, credentials, network access,
  review work, feedback submission, or reviewer-created state by testers.
- Operator-only local network validation: allows a trusted operator to validate
  the app on a private local network. Does not allow unsupervised external
  tester access or sharing a public anonymous URL.
- Temporary supervised screen-share walkthrough: allows an operator to show the
  running pilot to a named tester while the operator controls access. Does not
  give the tester independent credentials, persistent access, broad admin access,
  or production authentication.
- Temporary restricted network/VPN access, if separately approved outside the
  repo: allows access only for named testers or an approved small group within a
  separately managed restricted network boundary. Does not implement app auth,
  OIDC, sessions, user tables, invitations, reverse proxy configuration, VPN
  configuration, or deployment in this repository.
- Future managed OIDC/OAuth2 access after implementation: allows authenticated,
  scoped tester access only after a later approved implementation adds real
  provider integration, callback handling, sessions or equivalent state, user or
  role persistence as needed, tests, and deployment guidance. It is not available
  in the current scaffold.
- Cloudflare Tunnel + Cloudflare Access with individually allowlisted testers:
  exposes only the app HTTP service through a Cloudflare Tunnel (no router port
  forwarding). Cloudflare Access enforces email-based identity checks before any
  tester-facing URL can be reached. Does not replace the app's own hosted auth
  boundary. Does not expose QNAP admin UI, Container Station UI, SSH, SMB, or
  NAS management services through the tunnel. Does not configure Dream Machine
  Pro port forwarding. Requires recording the selected identity provider approach,
  the named testers or approved group, and who owns ongoing Access policy
  updates. Secrets, tunnel credentials, account IDs, and private hostnames must
  not be committed to the repository.

Do not invent another access method without recording the same owner, scope,
expiration, revocation, no-secret, and no-conclusion boundaries.

## 4. Required Decision Fields

Record these fields in the local operator decision notes and reference the
decision from the evidence packet:

- Decision date.
- Decision owner or approver.
- Selected access method.
- Named testers or approved group.
- Role and scope per tester.
- Environment or host scope.
- Start date.
- End or expiration date.
- Revocation method.
- Feedback triage owner.
- Backup and evidence packet confirmation.
- Known limitations acknowledgement.
- Reason the selected method is acceptable for this pilot stage.
- Explicit statement that this is not production auth unless real OIDC/session
  implementation exists.

Keep decision notes free of credentials, provider values, private URLs, hosted
URLs, callback URLs, tenant IDs, connection strings, raw provider claims, raw
artifact contents, raw server paths, and `.env` values.

## 5. Temporary Access Guardrails

- No anonymous public URL.
- No shared broad admin account by default.
- No local-dev fixture auth for external testers.
- No committed credentials.
- No provider secrets, callback URLs, private URLs, hosted URLs, tokens, tenant
  IDs, connection strings, or client secrets in docs, issues, PRs, screenshots,
  support notes, or evidence packets.
- No broad future-data, all-project, statewide, private-source, destructive,
  import/reload, reset, raw-artifact, audit-export, user-admin, role-admin, or
  administrative access unless that specific access is explicitly approved and
  documented.
- Revocation must be possible before testers are invited.
- Access must be limited to the QNAP pilot environment, the approved seeded or
  imported corpus, CCLD-only workflows, approved pilot routes, and the minimum
  role needed for the tester's task.

## 6. Evidence Packet Relationship

Reference the access-method decision in the QNAP pilot evidence packet after:

- QNAP verifier output.
- Seeded import evidence.
- Route evidence.
- Auth readiness notes.
- Tester invitation decision.
- Feedback decision.
- Retrieval decision.
- PostgreSQL backup plan.
- Raw artifact backup plan.
- Known limitations acknowledgement.

The access-method decision is evidence that the operator deliberately chose how
access will be limited and revoked. It is not evidence of production auth,
public-source completeness, legal findings, facility-wide conclusions, harm,
abuse, neglect, liability, or rights-deprivation.

## 7. Deferred Items

These remain deferred and must not be implied by an access-method decision:

- Real OIDC/login implementation.
- OAuth2 callback handling.
- Sessions or cookies.
- User tables.
- Self-service signup.
- Invitation workflow implementation.
- Account management UI.
- Identity provider integration.
- Deployment hardening.
- Public URL production readiness.

## 8. Do-Not-Do List

- Do not share any access path until the decision is recorded.
- Do not use local-dev fixture auth as production authentication.
- Do not publish a public anonymous tester URL.
- Do not commit or paste secrets.
- Do not treat a temporary network or access workaround as production auth.
- Do not invite testers without a revocation plan.
- Do not make public-source completeness, legal, facility-wide, harm, abuse,
  neglect, liability, or rights-deprivation conclusions.

## 9. Cloudflare Access Identity Decision

This section records the selected access-layer approach for the QNAP pilot
before any Cloudflare Tunnel or tester-facing URL is created.

This is a pilot access-control decision, not a production security
certification. It does not implement Cloudflare Tunnel, Cloudflare Access,
DNS, TLS certificates, firewall rules, Dream Machine Pro configuration,
or internet exposure.

### 9.1 Selected Approach

The selected access method for the QNAP pilot is:
**Cloudflare Tunnel + Cloudflare Access with individually allowlisted testers.**

- Cloudflare Tunnel will be used to make the app reachable from outside the
  QNAP LAN without router port forwarding or Dream Machine Pro firewall changes.
- Cloudflare Access will sit in front of the app URL and enforce identity checks
  before any tester can reach the app.
- Initial tester access will use individually allowlisted email addresses or a
  small named tester group managed in Cloudflare Access.
- No public unauthenticated route will be created.

### 9.2 What This Decision Is Not

- This is not production OIDC login. The app's `CCLD_HOSTED_TESTER_AUTH_MODE`
  must stay `production` and `CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH` must stay
  `disabled`. Cloudflare Access is a network-layer access control that sits in
  front of the app; it is not the app's authentication layer.
- Cloudflare Access does not replace the app's hosted auth boundary, session
  handling, user tables, OIDC callback, or role enforcement. Those remain
  deferred.
- This is not a permanent deployment decision. The pilot remains portable and
  QNAP is not a permanent platform lock-in.

### 9.3 Guardrails

- Only the app HTTP service (`CCLD_HOSTED_PORT`, container port 8000) may be
  exposed through the tunnel.
- QNAP admin UI, Container Station UI, SSH, SMB, AFP, NAS management services,
  and any non-app QNAP service must not be exposed through the tunnel.
- Dream Machine Pro port forwarding must not be configured for the app.
- No broad anonymous public route may be created.
- Access must be limited to the named tester group, the approved seeded corpus,
  CCLD-only workflows, and the minimum role for each tester's task.
- Revocation must be possible before testers are invited. Access can be revoked
  by removing the email allowlist entry or disabling the Cloudflare Access
  policy.
- The Cloudflare Tunnel and Access configuration is operator-managed outside
  the repository. It must not be committed.

### 9.4 Secrets and Credentials

Keep all of the following outside the repository and outside committed files:

- Cloudflare tunnel token and tunnel credential files.
- Cloudflare account ID and zone ID.
- Cloudflare Access application client ID and client secret.
- Private pilot hostname or subdomain.
- Tester email addresses.
- Any `cloudflared` configuration that references private values.

### 9.5 Open Questions

These must be resolved before sharing a tester-facing URL:

| Question | Status |
|---|---|
| Final tester email list | Not yet finalized. Record in local operator notes before enabling Access policy. |
| Final pilot hostname or subdomain | Not yet assigned. Keep out of repo when chosen. |
| Identity provider for Cloudflare Access | Not yet decided. Options include one-time PIN (email OTP), Google identity, Microsoft identity, or another managed provider supported by Cloudflare Access. |
| Who owns ongoing Access policy updates | Not yet assigned. Must be decided before inviting testers. |

### 9.6 Next Step

Once this decision is recorded, the next operator step is to create the
Cloudflare Tunnel, configure Cloudflare Access, and verify that:

- Only the app port is reachable through the tunnel.
- The Access policy blocks unauthenticated requests.
- At least one named tester can authenticate and reach the app landing page.
- The app health route responds through the tunnel.
- No QNAP admin or management service is reachable through the tunnel.

Do not invite testers or share the pilot URL until those verifications pass
and the open questions in section 9.5 are resolved.