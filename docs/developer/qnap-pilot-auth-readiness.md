# QNAP Pilot Auth Readiness

Use this guide before inviting early external stakeholder organization testers to a QNAP-hosted pilot. It
explains the current hosted auth readiness path, what is intentionally not implemented
yet, which host-local settings must stay safe, and what auth evidence operators
should capture.

This guide complements the [QNAP pilot operator checklist](qnap-pilot-operator-checklist.md),
[QNAP Docker runtime guide](qnap-docker-runtime.md),
[QNAP pilot readiness index](qnap-pilot-readiness-index.md),
[QNAP pilot access-method decision](qnap-pilot-access-method-decision.md),
[QNAP pilot tester invitation decision](qnap-pilot-tester-invitation-decision.md),
ADR-0011, and ADR-0014.

## 1. Current Auth Readiness

- QNAP pilot mode should use `CCLD_HOSTED_TESTER_AUTH_MODE=production`.
- QNAP pilot mode should keep `CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH=disabled`.
- QNAP pilot feedback submission can use
  `CCLD_HOSTED_TESTER_AUTH_PROVIDER_CLASS=cloudflare-access`. Cloudflare Access
  protects the public hostname, and RecordsTracker validates the
  `Cf-Access-Jwt-Assertion` header before creating a minimal tester feedback
  actor.
- The Cloudflare Access bridge validates the Access JWT signature from the
  configured team domain JWKS, expected issuer, AUD tag, expiration/not-before,
  and email allowlist. It does not trust cookies, query string tokens,
  arbitrary email headers, or caller-provided actor fields.
- Production mode blocks anonymous workflow routes when no authenticated route
  context exists. Protected CCLD request, retrieval, import/reload, feedback
  submission, reviewer, and reviewer-created state actions should not be treated
  as anonymously available pilot workflows.
- Local-dev fixture auth exists only for local scaffold validation. It supplies a
  fixture tester actor for developer workstation checks; it is not production
  authentication.
- `/auth/status` is a safe status/debug route. It may summarize mode,
  provider-class placeholder state, Cloudflare Access configuration presence,
  OIDC placeholder presence, callback path, scopes, local-dev auth allowance,
  and whether real OIDC or sessions are implemented. It must not expose provider
  subjects, issuers, raw claims, tokens, cookies, private headers, client
  secrets, database connection strings, real team domains, AUD tags, email
  allowlists, or other secrets.

## 2. What Is Not Implemented Yet

- No real login flow.
- No real OIDC/OAuth2 callback handling.
- No session cookies.
- No user table.
- No self-service account creation.
- No production password login.
- No managed identity or provider token exchange. The Cloudflare Access bridge
  validates the Access JWT assertion only; it does not implement an app login
  UI or exchange tokens with Cloudflare.
- No tester invitation workflow.
- No production auth middleware beyond the current runtime path and existing
  local/test role/scope guard helpers.

Do not invite real testers until there is a deliberate access-control decision
for how they will authenticate and how their access will be provisioned,
limited, reviewed, and revoked. Record that decision in
[QNAP pilot access-method decision](qnap-pilot-access-method-decision.md) and
[QNAP pilot tester invitation decision](qnap-pilot-tester-invitation-decision.md).

## 3. Host-Local Placeholder Guidance

- Keep provider settings, client IDs, client secrets, callback URLs, issuer URLs,
  Cloudflare Access team domain, AUD tag, allowed tester configuration, and
  tenant/provider details in an untracked host-local `.env` file or host-managed
  secret store.
- Do not commit provider secrets, callback URLs, tenant-private values, hosted
  URLs, tokens, cookies, private headers, or raw provider claims.
- `.env.example` should contain blanks or neutral placeholders only.
- QNAP verifier remains the main local readiness check for auth mode and local-
  dev auth configuration. When `cloudflare-access` is selected, it also checks
  that the team domain, AUD tag, and at least one email allowlist setting are
  present without printing their values.
- Treat placeholder notices as readiness prompts, not permission to commit real
  values.

## 4. Evidence Before Inviting Testers

Capture a small auth readiness packet:

- QNAP verifier output showing production auth mode and local-dev auth disabled.
- QNAP verifier output showing the `cloudflare-access` provider, configured
  team/AUD presence, and configured email allowlist presence without printing
  real values.
- `/auth/status` output summary showing safe capability state without private
  values. Confirm it reports Cloudflare Access configuration presence and that
  real OIDC flow and sessions/cookies are not implemented.
- Route behavior showing protected workflow routes are blocked for anonymous
  production mode when applicable, such as `/ccld/records/request`,
  `/ccld/retrieval/jobs`, `/ccld/retrieval/jobs/detail?job_id=missing-job`, and
  `/reviewer`.
- Optional `scripts/summarize-qnap-pilot-route-evidence.ps1` output showing the
  same protected/setup-required/safe route states without printing response
  bodies, cookies, tokens, provider subjects, provider issuers, raw artifacts,
  raw server paths, or secrets.
- Feedback behavior showing configured feedback submission requires an allowed
  Cloudflare Access JWT-backed actor, while unconfigured feedback does not call
  GitHub.
- Decision record that real OIDC/login remains deferred or planned, including
  who owns the next access-control decision.
- Review guidance acknowledgement.
- Access-method decision record showing the temporary access method, scope,
  expiration, revocation method, and that it is not production auth unless real
  OIDC/session implementation exists.
- Review guidance acknowledgement that the scaffold does not implement real
  login, sessions, cookies, token validation, user tables, self-service signup,
  or tester invitations.

## 5. Do-Not-Do List

- Do not enable local-dev auth for QNAP pilot mode.
- Do not set `CCLD_RETRIEVAL_DEMO_MODE=mock-success` in QNAP pilot mode.
- Do not commit provider secrets.
- Do not paste tokens, callback secrets, provider claims, private headers,
  cookies, database connection strings, or hosted/private URLs into issues, PRs,
  docs, screenshots, or support notes.
- Do not paste real Cloudflare Access team domains, AUD tags, JWTs, cookies, or
  tester allowlists into committed files, screenshots, or issue bodies.
- Do not invite real testers until there is a deliberate access-control decision
  for how they will authenticate.
- Do not treat local-dev fixture auth as production authentication.
- Do not build custom password storage for the tester MVP.
- Do not use shared tester accounts for reviewer-created workflows.
