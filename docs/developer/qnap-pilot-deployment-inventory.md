# QNAP Pilot Deployment Inventory

Use this inventory to answer "what exactly would we deploy on QNAP Docker?"
before adding Cloudflare Tunnel or any reverse proxy, public URL, or external
access layer. It consolidates facts from `docker-compose.qnap.yml`, `Dockerfile`,
`.env.example`, and the companion runtime and checklist docs into a single
reference. It does not replace those docs; it is a compact cross-reference.

This document does not implement Cloudflare Tunnel, Cloudflare Access, a public
URL, DNS, certificates, reverse proxy, or firewall configuration. It does not
change app behavior, routes, schemas, migrations, auth, retrieval behavior,
extraction behavior, source connectors, workbook exports, or generated data.

## 1. What Gets Built And Run

| Component | Image / Source | Role |
|---|---|---|
| `app` | Built from `Dockerfile` using `python:3.12-slim` | Hosts the CCLD reviewer web app on port 8000 inside the container. Runs Alembic migrations on startup then starts `ccld_complaints.hosted_app`. |
| `postgres` | `postgres:16-alpine` | Provides the PostgreSQL database for hosted page data and reviewer state. Holds the named volume `ccld_postgres_data`. |

No other services, workers, tunnels, reverse proxies, or cloud connectors are
declared in `docker-compose.qnap.yml`.

## 2. Port Mapping

| Container port | Host port variable | Default | Notes |
|---|---|---|---|
| `8000/tcp` (app) | `CCLD_HOSTED_PORT` | `8000` | Map to any available QNAP host port. Only this port is exposed. The app is reachable on the local network at `http://<qnap-ip>:<CCLD_HOSTED_PORT>/`. |
| PostgreSQL | Not exposed to host | Internal only | The `postgres` service has no published ports. The app container reaches it at `postgres:5432` over the Compose internal network. |

The `/health` route at `http://<qnap-ip>:<CCLD_HOSTED_PORT>/health` is the
container health endpoint. Both services define health checks in the Compose
file.

## 3. Named Volumes

| Volume | Mounted at (in app container) | What it stores |
|---|---|---|
| `ccld_postgres_data` | PostgreSQL internal (`/var/lib/postgresql/data`) | All PostgreSQL database data: hosted page data, reviewer state, Alembic version table, imported source-derived records. Back this up with `pg_dump`. |
| `ccld_processed_data` | `/app/data/processed` | Processed outputs such as export bundles. Not a source-of-truth; can be regenerated. |
| `ccld_raw_data` | `/app/data/raw` | Raw CCLD retrieval artifacts when live retrieval is enabled. Source-of-truth for raw preserved inputs. Back this up. |
| `ccld_logs` | `/app/data/logs` | App runtime logs. Not a source-of-truth. |

QNAP Container Station maps named volumes to QNAP-managed storage. Keep
QNAP-specific share names, snapshot schedules, and backup locations in QNAP
configuration or local operations notes, not in application code.

## 4. Environment Variables

Copy `.env.example` to `.env` on the QNAP host, then replace placeholder values.
Keep `.env` untracked. Do not commit real passwords, tokens, callback URLs, or
account-specific values.

### 4a. Required — PostgreSQL And Port

| Variable | QNAP pilot value | Notes |
|---|---|---|
| `CCLD_POSTGRES_DB` | `ccld_records` | PostgreSQL database name. |
| `CCLD_POSTGRES_USER` | `ccld_app` | PostgreSQL app user. |
| `CCLD_POSTGRES_PASSWORD` | _(replace with strong local password)_ | Never commit. Keep in untracked `.env` or QNAP secret store. |
| `CCLD_HOSTED_PORT` | `8000` | Host port. Change if 8000 is occupied. |

### 4b. Required — Runtime Mode

| Variable | QNAP pilot value | Why |
|---|---|---|
| `CCLD_HOSTED_PAGE_DATA_MODE` | `postgres` | Enables PostgreSQL-backed hosted pages. `fixture-demo` is local-dev only. |
| `CCLD_HOSTED_TESTER_AUTH_MODE` | `production` | Blocks anonymous workflow routes. `local-dev` is for local scaffold validation only. |
| `CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH` | `disabled` | Must be `disabled` in QNAP pilot mode. |
| `CCLD_RETRIEVAL_DEMO_MODE` | _(blank)_ | Must remain blank in QNAP pilot mode. `mock-success` is local-dev only. |

### 4c. Auth Placeholders (Host-Local Only)

These values are supplied by the operator in the untracked `.env` file. The
`docker-compose.qnap.yml` passes them to the app container. Real provider
secrets must not be committed.

| Variable | Notes |
|---|---|
| `CCLD_HOSTED_TESTER_AUTH_PROVIDER_CLASS` | `managed-oidc-oauth2` |
| `CCLD_HOSTED_TESTER_OIDC_ISSUER` | Provider issuer placeholder. Not a committed value. |
| `CCLD_HOSTED_TESTER_OIDC_CLIENT_ID` | Provider client ID placeholder. Not a committed value. |
| `CCLD_HOSTED_TESTER_OIDC_CALLBACK_PATH` | `/auth/callback` |
| `CCLD_HOSTED_TESTER_OIDC_SCOPES` | `openid profile` |

Real OIDC login, callback handling, sessions, and user tables are not
implemented yet. Auth placeholder values are readiness configuration for when
a production OIDC flow is later added. See
[qnap-pilot-auth-readiness.md](qnap-pilot-auth-readiness.md).

### 4d. Optional — GitHub Feedback

| Variable | Notes |
|---|---|
| `GITHUB_FEEDBACK_REPO` | Leave blank to intentionally disable GitHub feedback. Set to `owner/repo` to enable it. |
| `GITHUB_FEEDBACK_TOKEN` | Leave blank when feedback is disabled. Keep server-side only; never commit. |
| `GITHUB_FEEDBACK_DEFAULT_LABELS` | Optional. |

Either both `GITHUB_FEEDBACK_REPO` and `GITHUB_FEEDBACK_TOKEN` are blank
(intentionally disabled), or both are set. Half-configured feedback is a pilot
readiness error.

### 4e. Optional — Controlled Retrieval

| Variable | Default | Notes |
|---|---|---|
| `CCLD_RETRIEVAL_ENABLED` | `disabled` | Keep `disabled` until persistent raw artifact storage, PostgreSQL, and access boundaries are confirmed. Set `enabled` only to explicitly enable live retrieval. |
| `CCLD_RETRIEVAL_RAW_DIR` | `/app/data/raw/ccld/retrieval` | Container path for raw artifact preservation. Backed by `ccld_raw_data` volume. |
| `CCLD_RETRIEVAL_MAX_DATE_RANGE_DAYS` | `366` | Maximum request date span. |
| `CCLD_RETRIEVAL_PER_JOB_LIMIT` | `5` | Maximum selected report requests per job. |
| `CCLD_RETRIEVAL_RATE_LIMIT_PER_ACTOR` | `3` | Active queued/running jobs per actor. |
| `CCLD_RETRIEVAL_TIMEOUT_SECONDS` | `30` | Per-request retrieval timeout. |
| `CCLD_RETRIEVAL_RETRY_LIMIT` | `1` | Bounded retry count. |

### 4f. Optional — Facility Reference

| Variable | Notes |
|---|---|
| `CCLD_FACILITY_REFERENCE_CSV` | Container path to a local/test facility reference CSV. Leave blank when not using a local reference CSV. |

### 4g. Injected By Compose (Do Not Set Manually)

| Variable | Source |
|---|---|
| `CCLD_HOSTED_TESTER_DATABASE_URL` | Constructed by `docker-compose.qnap.yml` from `CCLD_POSTGRES_USER`, `CCLD_POSTGRES_PASSWORD`, and `CCLD_POSTGRES_DB`. Do not commit a database connection string. Do not print it in logs or docs. |

## 5. Startup Sequence

The Compose `app` service command runs Alembic migrations before starting the
web server:

```
alembic upgrade head && python -m ccld_complaints.hosted_app --host 0.0.0.0 --port 8000
```

The `app` service depends on `postgres` reaching a healthy state before
starting. The full startup order is:

1. `postgres` container starts and passes its health check.
2. `app` container starts, runs `alembic upgrade head`, then starts the web server.
3. App health check (`/health`) passes within 20 seconds.

Start the stack from the repository root on the Docker host:

```powershell
docker compose -f docker-compose.qnap.yml --env-file .env up --build -d
```

### First LAN Smoke Test Results

Docker Engine (`27.1.2-qnap8`) and Docker Compose (`v2.29.1-qnap2`) were
confirmed available via Container Station. The deployment folder used in the
first LAN smoke test was `/share/Container/RecordsTracker/app`. Git is not
available on QNAP; the archive was created on Windows with `git archive` and
transferred with `scp`. Both the health route and the landing page responded
`200` on the LAN after startup. The app is LAN-only at this stage — no
Cloudflare Tunnel, Cloudflare Access, DNS, reverse proxy, TLS certificate, or
public internet exposure has been configured. The next access-layer milestone
is Cloudflare Tunnel and Cloudflare Access.

See [qnap-docker-runtime.md](qnap-docker-runtime.md) for the generic
`git archive` + `scp` transfer commands and the Container Station home
directory permission fix.

Run migrations manually when needed without restarting the stack:

```powershell
docker compose -f docker-compose.qnap.yml --env-file .env run --rm app alembic upgrade head
```

Validate environment and Compose configuration before first startup:

```powershell
.\scripts\verify-qnap-pilot-workflow.ps1 -EnvFile .env
```

Run a full local smoke check (starts stack, waits for health, probes routes,
then stops the stack cleanly):

```powershell
.\scripts\verify-qnap-pilot-workflow.ps1 -EnvFile .env -SmokeStart
```

The `-SmokeStart` flag is opt-in and starts real containers. Use it only on the
QNAP Docker host or a local Docker host, not in shared CI. If the health
endpoint does not respond within the wait timeout (default 120 s, adjustable
with `-SmokeWaitSeconds`), the script collects recent container logs and
stops the stack. The default config-check mode (no `-SmokeStart`) does not
start or stop any containers.

After a smoke check passes, verify container state and routes against an
already-running stack:

```powershell
.\scripts\verify-qnap-pilot-workflow.ps1 -EnvFile .env -CheckContainers -BaseUrl http://<qnap-ip>:<CCLD_HOSTED_PORT>
```

## 6. Database Bootstrap And Seed Data

Before testers can review records, the PostgreSQL database must have:

- Alembic migrations applied (`alembic upgrade head`).
- At least one validated hosted import batch in `hosted_import_batches`.
- Source-derived CCLD complaint records in `hosted_source_derived_records`.
- No direct modification of source-derived records by the import process.

Seed data comes from a validated CCLD hosted artifact or a seeded test corpus,
imported after migrations are applied. Raw artifact files used as import sources
must be preserved and backed up; they must not be exposed to testers.

Use the seeded import evidence guide after importing:

- [qnap-pilot-seeded-import-evidence.md](qnap-pilot-seeded-import-evidence.md)
- `scripts/summarize-qnap-pilot-seeded-import-evidence.ps1 -EnvFile .env`

The import summary command is read-only. It does not run imports, retrieval, or
live CCLD calls. It does not print secrets, raw artifact contents, or
server-specific paths.

## 7. Export And Output Paths

| Path | Volume | Notes |
|---|---|---|
| `/app/data/raw/ccld/retrieval` | `ccld_raw_data` | Raw CCLD retrieval artifacts preserved by the app when live retrieval is enabled. Do not expose contents to testers. |
| `/app/data/processed` | `ccld_processed_data` | Export bundles and processed outputs. Not a source-of-truth. |
| `/app/data/logs` | `ccld_logs` | Runtime logs. Not a source-of-truth. |

Generated outputs under `data/processed/` and `data/logs/` on the host must not
be committed to the repository.

## 8. What Is Not Deployed In This Stage

This inventory describes the pre-Cloudflare Tunnel deployment. The following are
not deployed and not required at this stage:

- **Cloudflare Tunnel**: not configured. App is LAN-accessible only.
- **Cloudflare Access**: not configured. No zero-trust identity layer.
- **Reverse proxy**: not configured in the Compose file or in this stage.
- **Public DNS or custom domain**: not required. Access uses `http://<qnap-ip>:<port>`.
- **TLS/HTTPS certificates**: not configured at this stage.
- **Real OIDC login flow**: not implemented. Auth mode is `production` (blocks anonymous workflow routes), but no real provider callback, session, or user table exists yet.
- **Tester invitation workflow**: not implemented.
- **Production retrieval automation**: off by default (`CCLD_RETRIEVAL_ENABLED=disabled`). Enable explicitly only after persistent raw artifact storage and access boundaries are confirmed.
- **GitHub feedback**: off by default. Enable explicitly by configuring both `GITHUB_FEEDBACK_REPO` and `GITHUB_FEEDBACK_TOKEN`.
- **Datasette**: not part of the Docker Compose stack. Datasette is the local CSV review layer; it is not deployed to QNAP in this stage.

## 9. Pre-Cloudflare Access State

Without Cloudflare Tunnel the app is reachable only on the QNAP host's local
network. The intended access model at this stage is:

- Operator validates on the local LAN using `http://<qnap-lan-ip>:<CCLD_HOSTED_PORT>`.
- No external tester link, VPN rule, or reverse proxy route is shared before the
  access-method decision is recorded.

Use [qnap-pilot-access-method-decision.md](qnap-pilot-access-method-decision.md)
to record the selected temporary access method before sharing any access path.

## 10. Gaps Before Pilot Is Tester-Ready

These gaps are tracked in existing ADRs and readiness docs. They are listed here
for operator awareness only.

| Gap | Current state | Blocking for testers? |
|---|---|---|
| Real OIDC login flow | Not implemented. Production auth mode blocks anonymous workflow routes. | Yes — testers cannot authenticate to workflow routes without a real login or an approved temporary access method. |
| Session/cookie handling | Not implemented. | Follows OIDC implementation. |
| User table | Not implemented. | Follows OIDC implementation. |
| Tester invitation workflow | Not implemented. Decision scaffold documented. | Required before external testers are given independent access. |
| External access path | Not configured. LAN-only at this stage. | Required before remote tester access. Decision scaffold in [qnap-pilot-access-method-decision.md](qnap-pilot-access-method-decision.md). |
| Seed data import | Not done automatically. Operator must import after first startup. | Yes — testers need imported CCLD source-derived records to review. |
| PostgreSQL backup plan | Must be assigned to an operator. | Required before treating the pilot as tester-ready. |
| Raw artifact backup plan | Must be assigned to an operator when retrieval is enabled. | Required when live retrieval is enabled. |

## 11. Reference Docs

- [qnap-docker-runtime.md](qnap-docker-runtime.md) — full runtime reference and environment variable guide.
- [qnap-pilot-operator-checklist.md](qnap-pilot-operator-checklist.md) — ordered pre-invite checklist.
- [qnap-pilot-readiness-index.md](qnap-pilot-readiness-index.md) — ordered pre-invite path.
- [qnap-pilot-auth-readiness.md](qnap-pilot-auth-readiness.md) — auth boundary and deferred login work.
- [qnap-pilot-access-method-decision.md](qnap-pilot-access-method-decision.md) — access method decision scaffold.
- [qnap-pilot-tester-invitation-decision.md](qnap-pilot-tester-invitation-decision.md) — tester invitation decision scaffold.
- [qnap-pilot-seeded-import-evidence.md](qnap-pilot-seeded-import-evidence.md) — seed data import evidence guide.
- [cloud-portability-deployment.md](cloud-portability-deployment.md) — portability plan for future hosts.
- `docker-compose.qnap.yml` — Compose configuration.
- `Dockerfile` — app image definition.
- `.env.example` — placeholder environment template.
- `scripts/verify-qnap-pilot-workflow.ps1` — pre-startup and post-startup verifier.
