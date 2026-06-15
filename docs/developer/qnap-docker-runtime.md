# QNAP Docker Runtime

## Purpose

This guide describes the first production-like runtime envelope for the hosted
CCLD app: a Python app container plus PostgreSQL in Docker Compose. QNAP Docker
is the first practical deployment target. The Compose file uses portable
container settings, named volumes, and environment variables so the same model
can move later to AWS, Azure, DigitalOcean, Render, Fly.io, or another host
without hard-coding QNAP paths into application code.

This runtime includes the first provider-agnostic auth boundary for the external stakeholder organization pilot
direction: production mode blocks anonymous workflow routes unless an
authenticated route context exists, and explicit local-dev mode is available only
for local scaffold validation. It does not add a real OIDC login flow, token
handling, sessions, cookies, custom password storage, production import
automation, public URL behavior, or a hosted deployment in this repository
branch. The first ADR-0016 controlled browser-triggered, server-executed CCLD
retrieval-job slice can run in this runtime when explicitly configured with
server-side raw storage and PostgreSQL.

## Files

- `Dockerfile` builds the Python standard-library hosted scaffold image.
- `docker-compose.qnap.yml` runs the app and PostgreSQL with named volumes.
- `.env.example` documents placeholder environment values only.

The committed examples must not contain real passwords, tokens, hosted URLs,
cloud credentials, account-specific paths, or personal machine details.

## Environment Configuration

Copy `.env.example` to `.env` on the deployment host and replace placeholder
values there. The `.env` file is ignored by Git and must stay server-side.

Required values:

- `CCLD_POSTGRES_DB`: PostgreSQL database name for the hosted runtime.
- `CCLD_POSTGRES_USER`: PostgreSQL app user.
- `CCLD_POSTGRES_PASSWORD`: deployment-specific PostgreSQL password, stored only
  in the untracked host `.env` file.
- `CCLD_HOSTED_PORT`: host port mapped to container port `8000`.
- `CCLD_HOSTED_PAGE_DATA_MODE`: use `postgres` for QNAP and future hosted
  deployments. Use `fixture-demo` only for explicit local demos and tests.

Provider-agnostic hosted tester auth values:

- `CCLD_HOSTED_TESTER_AUTH_MODE`: use `production` for QNAP/pilot-like runtime;
  use `local-dev` only for local scaffold validation.
- `CCLD_HOSTED_TESTER_AUTH_PROVIDER_CLASS`: must be `managed-oidc-oauth2`.
- `CCLD_HOSTED_TESTER_OIDC_ISSUER`: provider issuer placeholder kept in the
  untracked deployment `.env` file.
- `CCLD_HOSTED_TESTER_OIDC_CLIENT_ID`: provider client ID placeholder kept in
  the untracked deployment `.env` file.
- `CCLD_HOSTED_TESTER_OIDC_CALLBACK_PATH`: path placeholder such as
  `/auth/callback`; do not commit real hosted callback URLs.
- `CCLD_HOSTED_TESTER_OIDC_SCOPES`: space-separated OIDC scopes such as
  `openid profile`.
- `CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH`: keep `disabled` for production mode; set
  to `enabled` only with `local-dev` mode for local scaffold validation.

Optional server-side GitHub Issues feedback values:

- `GITHUB_FEEDBACK_REPO`: target repository in `owner/repo` format.
- `GITHUB_FEEDBACK_TOKEN`: server-side token used only by the app process.
- `GITHUB_FEEDBACK_DEFAULT_LABELS`: optional comma-separated extra labels.

Optional value:

- `CCLD_FACILITY_REFERENCE_CSV`: container path for a local/test facility
  reference CSV, such as `/app/data/raw/ccld/facility-reference.csv`.

Optional controlled CCLD retrieval job values:

- `CCLD_RETRIEVAL_ENABLED`: set to `enabled` only when server-side raw storage,
  PostgreSQL, and access boundaries are ready.
- `CCLD_RETRIEVAL_RAW_DIR`: container path for preserved raw CCLD retrieval
  artifacts, such as `/app/data/raw/ccld/retrieval`.
- `CCLD_RETRIEVAL_MAX_DATE_RANGE_DAYS`: maximum request date span.
- `CCLD_RETRIEVAL_PER_JOB_LIMIT`: maximum selected report requests per job.
- `CCLD_RETRIEVAL_RATE_LIMIT_PER_ACTOR`: active queued/running jobs allowed per
  actor.
- `CCLD_RETRIEVAL_TIMEOUT_SECONDS`: per-request retrieval timeout.
- `CCLD_RETRIEVAL_RETRY_LIMIT`: bounded retry count.

The app receives `CCLD_HOSTED_TESTER_DATABASE_URL` from Compose. Do not commit a
database connection string. Do not print the connection string in logs, docs,
tests, screenshots, or support notes.

In PostgreSQL page-data mode, core workflow pages use the hosted source-derived,
import, and reviewer-created state services. If the database is not migrated,
not reachable, or empty, pages show setup-required guidance instead of falling
back silently to fixture data. Before a QNAP pilot, run migrations and import a
validated CCLD artifact so facility lookup, request queue, and reviewer detail
have source-derived rows to read.

Do not commit provider secrets, tenant-specific private values, hosted callback
URLs, tokens, cookies, or raw provider claims. This branch documents the auth
configuration seam and safe route placeholders only. Do not expose
`GITHUB_FEEDBACK_TOKEN` in browser HTML, JavaScript, logs, issue bodies, tests,
screenshots, or docs.

## Start Locally or on QNAP

From the repository root on any Docker host:

```powershell
docker compose -f docker-compose.qnap.yml --env-file .env up --build -d
```

Then open:

```text
http://<host-name-or-ip>:<CCLD_HOSTED_PORT>/
```

Health route:

```text
http://<host-name-or-ip>:<CCLD_HOSTED_PORT>/health
```

QNAP Container Station users can import or run the Compose file from the repo
working copy. Keep QNAP-specific host paths, share names, snapshots, and backup
locations in QNAP configuration or local operations notes, not in application
code.

## Migrations

The app service runs Alembic migrations before starting the scaffold:

```text
alembic upgrade head
```

To run migrations manually inside the app container:

```powershell
docker compose -f docker-compose.qnap.yml --env-file .env run --rm app alembic upgrade head
```

Migrations must remain reviewable repository files under `migrations/versions/`
and must preserve the source-derived, reviewer-created, audit, import, feedback,
auth/access, export, and operational data boundaries defined by the ADRs.

## Volumes

The Compose file defines portable named volumes:

- `ccld_postgres_data`: PostgreSQL data directory.
- `ccld_processed_data`: local/test processed artifacts available to the app.
- `ccld_raw_data`: local/test raw/reference files available to the app.
- `ccld_logs`: runtime log files if future code writes them.

On QNAP, map or back up those named volumes using QNAP tools. On cloud hosts,
map the same responsibilities to managed disks, persistent volumes, or a managed
database. The app should still receive configuration through environment
variables and should not depend on QNAP-specific filesystem paths.

For controlled retrieval jobs, `ccld_raw_data` or an approved server-side raw
artifact mount preserves fetched CCLD source files before extraction, and
backups must cover both PostgreSQL and raw artifacts. Retrieval job workers must
use configured server-side storage paths or volumes, not browser-provided paths.

## Backup and Restore

Preferred PostgreSQL backup from a running Compose deployment:

```powershell
docker compose -f docker-compose.qnap.yml --env-file .env exec postgres pg_dump -U $env:CCLD_POSTGRES_USER -d $env:CCLD_POSTGRES_DB -Fc -f /tmp/ccld-postgres.dump
```

Copy the dump out of the container using a host-specific Docker or QNAP method
and store it outside the repository.

Restore into an empty compatible PostgreSQL database:

```powershell
docker compose -f docker-compose.qnap.yml --env-file .env exec postgres pg_restore -U $env:CCLD_POSTGRES_USER -d $env:CCLD_POSTGRES_DB --clean --if-exists /tmp/ccld-postgres.dump
```

Before any restore, stop the app container or place the deployment in a
maintenance window so application writes cannot race with restore steps. Do not
use destructive reset commands as a backup substitute.

## Smoke Validation

After starting the runtime, check the health route and core local/test pages:

- `/`
- `/health`
- `/auth/status`
- `/auth/login`
- `/feedback`
- `/ccld/facilities`
- `/ccld/records/request`
- `/ccld/help`
- `/reviewer`

The scaffold should continue to identify itself as local/test. It should not
claim real OIDC login, token handling, sessions, cookies, public launch, or
source completeness. Retrieval job pages should show safe setup-required state
unless retrieval is explicitly enabled with server-side storage.

In production auth mode, protected workflow routes such as `/ccld/records/request`
and `/reviewer` return a sign-in-required page until a real provider-backed
actor context is supplied by a later OIDC implementation. Public help remains
available at `/ccld/help`.

## Portability Notes

The first QNAP deployment should prove the app, database, migrations, volumes,
and no-secret environment model. Later cloud moves should preserve the same
contract:

- App image receives configuration from environment variables.
- PostgreSQL remains the runtime database unless a later ADR changes it.
- Persistent data lives in a database volume or managed PostgreSQL service.
- Raw and processed local/test artifacts use mounted storage, not application
  code paths tied to one host.
- Secrets stay outside Git and outside rendered HTML or browser JavaScript.
- Future controlled CCLD retrieval jobs stay server-side, use mounted raw
  artifact storage, and can move to a separate worker/container/task without
  QNAP-specific application code.

GitHub Projects are not required for this runtime. Optional paid platform
features are not required.

For migration planning beyond QNAP, see
[cloud-portability-deployment.md](cloud-portability-deployment.md). That guide
compares low-cost host options and keeps PostgreSQL, raw file storage, secrets,
backups, and future retrieval jobs separated from provider-specific app code.
