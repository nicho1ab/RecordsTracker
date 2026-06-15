# QNAP Pilot Operator Checklist

Use this checklist before inviting early external stakeholder organization testers to the hosted CCLD
tester pilot. It complements `.env.example`,
`scripts/verify-qnap-pilot-workflow.ps1`, `RUNBOOK.md`, and
`docs/developer/qnap-docker-runtime.md`. Start with the
[QNAP pilot readiness index](qnap-pilot-readiness-index.md). Use
[QNAP pilot seeded import evidence](qnap-pilot-seeded-import-evidence.md) when
capturing proof that PostgreSQL-backed source-derived CCLD records are loaded
before testers begin review. Use
[QNAP pilot auth readiness](qnap-pilot-auth-readiness.md) when capturing the
current production-mode auth boundary and deferred real-login work. Use
[QNAP pilot access-method decision](qnap-pilot-access-method-decision.md) before
sharing any external tester link, credential, network rule, VPN rule, or reverse
proxy route. Use
[QNAP pilot tester invitation decision](qnap-pilot-tester-invitation-decision.md)
before inviting testers. Use `scripts/build-qnap-pilot-evidence-packet.ps1` only
as optional local operator convenience after separate readiness evidence and
decisions are understood.

## 1. Pilot Purpose And Scope

- Confirm this is a public-interest hobby project for early external stakeholder organization tester
  validation, not a the user's employer project.
- Confirm QNAP Docker is the first pilot runtime, not a permanent platform
  lock-in. Keep app runtime, PostgreSQL, raw files, processed files, logs,
  secrets, and backups separable for later AWS, Azure, DigitalOcean, Render,
  Fly.io, Railway, Supabase/Neon, or other host moves.
- Confirm the pilot does not prove public-source completeness.
- Confirm the pilot does not make legal, facility-wide, harm, abuse, neglect,
  liability, or other unsupported conclusions.

## 2. Preflight

- Confirm the repository checkout is current and on the intended commit or
  release tag.
- Confirm Docker and Docker Compose are available on the QNAP host or selected
  Docker host.
- Confirm the expected app port is available and reachable by intended testers.
- Confirm PostgreSQL data volume backup responsibilities are assigned.
- Confirm raw artifact storage responsibilities are assigned.
- Confirm `.env` is not committed and remains untracked.
- Confirm no real database passwords, GitHub tokens, provider values, hosted
  callback URLs, private URLs, or account-specific settings are in committed
  files.
- Confirm the auth readiness notes are reviewed before inviting testers.
- Confirm the access-method decision is recorded before any external access path
  is shared.
- Confirm the tester invitation/access-control decision is recorded before
  inviting testers.
- Confirm the operator has a plan for collecting route-check evidence and known
  limitation acknowledgements before inviting testers.

## 3. Environment Setup

- Copy `.env.example` to `.env` on the deployment host.
- Replace `CCLD_POSTGRES_PASSWORD` with a deployment-specific PostgreSQL
  password stored only in the untracked `.env` file or host secret store.
- Keep `CCLD_HOSTED_PAGE_DATA_MODE=postgres` for QNAP pilot mode.
- Keep `CCLD_HOSTED_TESTER_AUTH_MODE=production` for QNAP pilot mode.
- Keep `CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH=disabled` for QNAP pilot mode.
- Keep `CCLD_RETRIEVAL_DEMO_MODE=` blank for QNAP pilot mode.
- Configure `CCLD_RETRIEVAL_RAW_DIR` to the container raw artifact path, for
  example `/app/data/raw/ccld/retrieval`.
- Decide whether controlled retrieval is intentionally disabled:
  `CCLD_RETRIEVAL_ENABLED=disabled`.
- If controlled retrieval is explicitly configured, keep it CCLD-only,
  complaint-only for now, server-side, bounded by facility/date/type, and backed
  by persistent raw artifact storage.
- Decide whether GitHub feedback is intentionally disabled by leaving both
  `GITHUB_FEEDBACK_REPO` and `GITHUB_FEEDBACK_TOKEN` blank.
- If GitHub feedback is explicitly configured, set both `GITHUB_FEEDBACK_REPO`
  and `GITHUB_FEEDBACK_TOKEN` in the untracked `.env` file or host secret store.
- Do not half-configure GitHub feedback. Repo without token or token without
  repo is a readiness error.

## 4. Verification Before Startup

- Run the QNAP pilot verifier:

```powershell
.\scripts\verify-qnap-pilot-workflow.ps1 -EnvFile .env
```

- Run Docker Compose config validation directly when needed:

```powershell
docker compose -f docker-compose.qnap.yml --env-file .env config
```

- Confirm verifier warnings are expected. Placeholder warnings are readiness
  prompts, not permission to commit real values.
- Resolve any failure for missing `.env`, unsafe local-dev auth, nonblank
  `CCLD_RETRIEVAL_DEMO_MODE` in QNAP pilot mode, retrieval enabled without raw
  storage, half-configured GitHub feedback, or committed-looking tokens.

## 5. Startup

- Start the Docker Compose stack:

```powershell
docker compose -f docker-compose.qnap.yml --env-file .env up --build -d
```

- Confirm the app and PostgreSQL containers are running.
- Confirm the app port is reachable from the intended tester network.
- Confirm the app health route responds before inviting testers.

## 6. Database And Migrations

- Confirm PostgreSQL is reachable from the app container.
- Run or verify Alembic migrations:

```powershell
docker compose -f docker-compose.qnap.yml --env-file .env run --rm app alembic upgrade head
```

- Confirm current Alembic state when containers are running:

```powershell
.\scripts\verify-qnap-pilot-workflow.ps1 -EnvFile .env -CheckContainers
```

- Confirm hosted pages are using PostgreSQL-backed page data mode, not
  `fixture-demo`.

## 7. Raw Artifact Storage

- Confirm `CCLD_RETRIEVAL_RAW_DIR` points to the intended container raw artifact
  path.
- Confirm the raw artifact path exists or can be created by the app container.
- Confirm the app container can write to the mounted raw artifact volume.
- Confirm raw artifact storage is included in backup planning.
- Do not expose raw artifact contents to testers.
- Do not expose server-specific raw paths to testers.

## 8. Route Verification

- Run the verifier with route checks after the stack is running:

```powershell
.\scripts\verify-qnap-pilot-workflow.ps1 -EnvFile .env -CheckContainers -BaseUrl http://<host-name-or-ip>:<CCLD_HOSTED_PORT>
```

- Verify `/` opens the hosted CCLD app shell.
- Verify `/auth/status` returns safe auth configuration status.
- Verify `/feedback` renders the feedback form or safe unconfigured state.
- Verify `/ccld/facilities` renders facility lookup or an expected protected or
  setup-required state.
- Verify `/ccld/records/request` renders request controls or an expected
  protected or setup-required state.
- Verify retrieval setup-required state when retrieval is disabled or not fully
  configured.
- Verify retrieval validation error state with an unsupported record type or
  invalid date range.
- Verify `/ccld/retrieval/jobs` renders safe history or an expected protected or
  setup-required state.
- Verify `/ccld/retrieval/jobs/detail?job_id=missing-job` renders safe not-found,
  protected, or setup-required state.
- Verify `/ccld/help` is readable.
- Verify `/reviewer` renders reviewer UI or an expected protected or
  setup-required state.
- Capture a GET-only route evidence summary with
  `scripts/summarize-qnap-pilot-route-evidence.ps1` after the app is running and
  the QNAP verifier passes. Expected protected, setup-required, safe-empty, and
  missing-job states are acceptable route evidence; route evidence must not show
  secrets, raw artifacts, raw server paths, cookies, provider subjects, provider
  issuers, source-completeness claims, or legal conclusions.
- Verify seeded reviewer detail routes only when fixture/demo data is explicitly
  being used for local workstation validation.
- Verify reviewer note/status paths only when the pilot mode intentionally
  enables the corresponding workflow context.

## 9. Optional Local-Dev-Only Mock-Success Verification

- Use `CCLD_RETRIEVAL_DEMO_MODE=mock-success` only in explicit local-dev
  scaffold validation, not QNAP pilot mode.
- Keep `CCLD_RETRIEVAL_DEMO_MODE=` blank in the QNAP pilot `.env` file.
- Use mock-success only to prove the local-dev request to retrieval job to import
  to history/detail to queue-link path works with committed fixtures.
- Do not treat mock-success output as production retrieval, live CCLD coverage,
  public-source completeness, or legal evidence.

## 10. Tester Readiness Evidence To Capture

- Capture verifier output summary.
- Capture Docker Compose config validation success.
- Capture container health/status.
- Capture Alembic current state or migration success.
- Capture route smoke results for the app shell, auth status, feedback, CCLD
  request, retrieval history/detail, help, and reviewer surfaces.
- Capture route evidence command output for the same route surface after the app
  is running and the QNAP verifier passes.
- Capture auth readiness evidence that production auth mode is active,
  local-dev auth is disabled, `/auth/status` is safe, and real login/session
  work remains deferred.
- Capture the access-method decision: selected method, named testers or approved
  group, role/scope, environment/host scope, start and expiration dates,
  revocation method, feedback triage owner, backup/evidence confirmation, known
  limitations acknowledgement, and explicit non-production-auth statement.
- Capture the tester invitation/access-control decision: who is invited, role,
  scope, approval, revocation plan, and feedback triage owner.
- Capture seeded import evidence that `hosted_import_batches` and
  `hosted_source_derived_records` contain validated PostgreSQL-backed CCLD rows
  before treating the pilot as tester-ready. The optional read-only
  `scripts/summarize-qnap-pilot-seeded-import-evidence.ps1` command can collect
  the safe count and configuration summary.
- Optionally assemble the local redacted Markdown packet with
  `scripts/build-qnap-pilot-evidence-packet.ps1`. The command writes under
  ignored `data/processed/qnap-pilot-evidence/`, is read-only, and is not an
  audit export, legal report, product export packet, public report, GitHub
  issue, or certification. Review generated packets before sharing and do not
  commit them.
- Record the GitHub feedback decision: intentionally disabled or fully
  configured.
- Record the controlled retrieval decision: intentionally disabled or fully
  configured with raw artifact storage.
- Record the PostgreSQL backup location and restore plan.
- Record the raw artifact backup location and restore plan.
- Record that known limitations were reviewed and acknowledged.

## 11. Backup And Rollback Checklist

- Back up the PostgreSQL volume or create a PostgreSQL dump before risky changes.
- Back up raw artifact storage separately from PostgreSQL.
- Store any `.env` backup outside the repository and restrict access.
- Stop the stack when needed:

```powershell
docker compose -f docker-compose.qnap.yml --env-file .env down
```

- Restart the stack after configuration changes:

```powershell
docker compose -f docker-compose.qnap.yml --env-file .env up --build -d
```

- Preserve logs before destructive host maintenance or rollback.
- Do not use destructive reset commands as a backup substitute.

## 12. Do-Not-Do List

- Do not commit `.env`.
- Do not commit database passwords, GitHub tokens, provider values, private URLs,
  hosted callback URLs, or account-specific settings.
- Do not enable local-dev auth for QNAP pilot mode.
- Do not set `CCLD_RETRIEVAL_DEMO_MODE=mock-success` in QNAP pilot mode.
- Do not half-configure GitHub feedback.
- Do not expose raw artifacts to testers.
- Do not expose server-specific raw paths to testers.
- Do not treat no records found as proof of public-source absence.
- Do not treat completed retrieval as proof of public-source completeness.
- Do not make legal, facility-wide, harm, abuse, neglect, liability, or
  completeness conclusions from the hosted pilot.
- Do not invite testers until the access method, role/scope, and revocation plan
  are deliberately approved.
- Do not share any access path until the access-method decision is recorded.