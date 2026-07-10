# QNAP Pilot Operator Checklist

Use this checklist before inviting early ylc.org testers to the hosted CCLD
tester pilot. It complements `.env.example`,
`scripts/verify-qnap-pilot-workflow.ps1`, `RUNBOOK.md`, and
`docs/developer/qnap-docker-runtime.md`. Start with the
[QNAP pilot readiness index](qnap-pilot-readiness-index.md). Use
[QNAP pilot seeded import evidence](qnap-pilot-seeded-import-evidence.md) when
capturing proof that PostgreSQL-backed source-derived CCLD records are loaded
before testers begin review. Use
[QNAP pilot auth readiness](qnap-pilot-auth-readiness.md) when capturing the
current production-mode auth readiness and deferred real-login work. Use
[QNAP pilot access-method decision](qnap-pilot-access-method-decision.md) before
sharing any external tester link, credential, network rule, VPN rule, or reverse
proxy route. Use
[QNAP seed data import runbook](qnap-seed-data-import-runbook.md) to load a
validated artifact into the QNAP PostgreSQL deployment before inviting testers.
Use
[Cloudflare Tunnel + Access setup](qnap-cloudflare-tunnel-access-setup.md) to
configure the Cloudflare access layer before sharing any tester-facing URL. Use
[QNAP pilot tester invitation decision](qnap-pilot-tester-invitation-decision.md)
before inviting testers. Use `scripts/build-qnap-pilot-evidence-packet.ps1` only
as optional local operator convenience after separate readiness evidence and
decisions are understood.

## Command Scope Quick Map

Use this map before copying any command:

| Lane | Who runs it | Examples | Command Scope |
|---|---|---|---|
| Local PowerShell | Developer or Codex when the current task allows local validation | `.\scripts\docs.ps1`, `git diff --check`, `python scripts\check_no_secrets.py`, placeholder-only verifier checks | Must not contact QNAP, print secrets, create generated evidence for commit, or change deployment state. |
| Human SSH session | Human operator only | `scp`, `tar`, `docker compose`, `docker compose cp`, `pg_dump`, `pg_restore`, QNAP `.env` editing, Cloudflare connector commands | Run outside Codex in a standalone terminal. Keep passwords, hostnames, `.env` values, and private paths out of repo docs and chat. |
| Not for Codex | Not run by Codex in normal repo work | SSH to QNAP, QNAP Docker commands, Cloudflare setup, tester invitations, retrieval enablement, imports, reset/reload, deployment host changes | Stop unless a later task explicitly authorizes that exact action. |

To avoid repeated password prompts, use operator-managed SSH keys or an
operator-controlled SSH agent configured outside the repository. Do not commit
private keys, SSH config containing private hosts, passwords, tokens, copied
`.env` values, or QNAP host aliases. Password prompts belong only in the
operator's standalone terminal, not in Codex chat, issues, docs, screenshots,
or generated evidence.

Before any human-operated QNAP step, run local readiness checks from the
repository checkout:

```powershell
.\scripts\docs.ps1
git diff --check
python scripts\check_no_secrets.py
```

When a real host `.env` is not available locally, start with the placeholder
verifier without Docker or QNAP contact:

```powershell
.\scripts\verify-qnap-pilot-workflow.ps1 -EnvFile .env.example -SkipComposeConfig -SkipDockerCheck
```

Stop before touching QNAP if these checks fail, if the working tree contains
secrets or generated evidence, if the operator has not assigned PostgreSQL and
raw artifact backup ownership, if the access-method decision is missing before
any tester-facing route, or if the next action would enable retrieval, run an
import, perform reset/reload, configure Cloudflare, invite testers, or expose
external services without explicit current-task approval.

## 1. Pilot Purpose And Scope

- Confirm this is a public-interest hobby project for early ylc.org tester
  validation, not a DSCC project.
- Confirm QNAP Docker is the first pilot runtime, not a permanent platform
  lock-in. Keep app runtime, PostgreSQL, raw files, processed files, logs,
  secrets, and backups separable for later AWS, Azure, DigitalOcean, Render,
  Fly.io, Railway, Supabase/Neon, or other host moves.
- Confirm source-completeness review uses dedicated source-review paths.
- Route legal, facility-wide, harm, abuse, neglect, liability, and related
  conclusions through dedicated review paths.

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
- Confirm the operator has a plan for collecting route-check evidence and
  review-guidance acknowledgements before inviting testers.

## 3. Environment Setup

- Copy `.env.example` to `.env` on the deployment host.
- Replace `CCLD_POSTGRES_PASSWORD` with a deployment-specific PostgreSQL
  password stored only in the untracked `.env` file or host secret store.
- Keep `CCLD_HOSTED_PAGE_DATA_MODE=postgres` for QNAP pilot mode.
- Keep `CCLD_HOSTED_TESTER_AUTH_MODE=production` for QNAP pilot mode.
- Keep `CCLD_HOSTED_TESTER_AUTH_PROVIDER_CLASS=cloudflare-access` for the QNAP
  pilot Cloudflare Access feedback bridge.
- Keep `CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH=disabled` for QNAP pilot mode.
- Configure `CCLD_CLOUDFLARE_ACCESS_TEAM_DOMAIN`,
  `CCLD_CLOUDFLARE_ACCESS_AUD`, and at least one of
  `CCLD_CLOUDFLARE_ACCESS_ALLOWED_EMAIL_DOMAINS` or
  `CCLD_CLOUDFLARE_ACCESS_ALLOWED_EMAILS` in the untracked host `.env`.
- Keep real Cloudflare Access team domains, AUD tags, JWTs, cookies, and tester
  allowlists out of committed files and evidence packets.
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

- Confirm verifier notices are expected. Placeholder notices are readiness
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
- Load a validated CCLD hosted seeded-corpus artifact into PostgreSQL using the
  [QNAP seed data import runbook](qnap-seed-data-import-runbook.md). The runbook
  covers: building the artifact on Windows, transferring it to QNAP, copying it
  into the container volume, running the import command, and verifying with
  read-only PostgreSQL queries.
- After import, confirm `hosted_import_batches` and `hosted_source_derived_records`
  contain validated rows (use the evidence queries in the runbook section 6 or
  `scripts/summarize-qnap-pilot-seeded-import-evidence.ps1`).
- Note: `/health` always reports `source_data_loaded: false` regardless of import
  state. Use PostgreSQL evidence queries to confirm the import, not the health
  endpoint.

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
  issuers, source-review conclusions, or legal conclusions.
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
  revocation method, feedback triage owner, backup/evidence confirmation,
  review-guidance acknowledgement, and explicit non-production-auth statement.
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
- Record that pilot review guidance was reviewed and acknowledged.

## 11. Cloudflare Tunnel and Access Setup

Complete this section before sharing any tester-facing URL. Use
[Cloudflare Tunnel + Access setup](qnap-cloudflare-tunnel-access-setup.md)
as the step-by-step runbook.

- Confirm the QNAP LAN smoke test passed before starting Cloudflare setup.
- Confirm Dream Machine Pro port forwarding is not configured for the app.
- Confirm the Cloudflare account and zone are ready.
- Confirm a pilot hostname placeholder has been chosen and recorded in local
  operator notes (not committed).
- Create the Cloudflare Tunnel. Record the tunnel name. Keep the tunnel token
  in local storage only.
- Start the `cloudflared` connector on the QNAP host (Docker container or
  native binary). Confirm the tunnel shows Healthy in the Cloudflare dashboard.
- Route only the app HTTP service (`CCLD_HOSTED_PORT`) through the tunnel.
  Confirm no QNAP admin UI, Container Station, SSH, SMB, NAS service, Docker
  socket, or database port has a public hostname route.
- Configure Cloudflare Access with the allowlisted tester email addresses and
  the selected identity method (one-time PIN, Google, Microsoft, or another
  approved provider). Record the identity method in the access-method decision
  doc. Record the session duration in local operator notes.
- Confirm Cloudflare Access blocks unauthenticated requests (private/incognito
  session should see an Access login page, not the app).
- Confirm Cloudflare Access denies a non-allowlisted email.
- Confirm an allowlisted test email can reach the app landing page and
  `/health` through the tunnel.
- Confirm `CCLD_HOSTED_TESTER_AUTH_MODE=production` and
  `CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH=disabled` remain set.
- Confirm no Cloudflare tokens, account IDs, private hostnames, or tester
  emails are committed to the repository.
- Record the evidence listed in the Cloudflare Tunnel + Access setup runbook
  section 10 in local operator notes or the evidence packet.

## 12. Backup And Rollback Checklist

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

## 13. Do-Not-Do List

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
- Do not commit the seeded corpus artifact
  (`data/processed/hosted_seeded_corpus/`).
- Do not treat non-zero import counts as proof of public-source completeness.
