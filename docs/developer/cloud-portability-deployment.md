# Cloud Portability Deployment Plan

## Purpose

QNAP Docker is the first practical deployment target for the hosted CCLD app,
but the runtime should stay portable enough to move later to AWS, Azure,
DigitalOcean, Render, Fly.io, Railway, or another host without rewriting
application code. This document describes the portable deployment model and the
tradeoffs between low-cost hosting options.

This is planning and configuration guidance only. It does not deploy the app,
create cloud resources, configure DNS, add credentials, claim production launch,
or require paid services as the only path.

## Portable Runtime Contract

Keep these concerns separated across every host:

- App runtime: the Python container built from `Dockerfile`.
- Database: PostgreSQL, reached through `CCLD_HOSTED_TESTER_DATABASE_URL` or the
  Compose-derived equivalent.
- Raw and processed files: persistent storage mounted for `data/raw`,
  `data/processed`, and `data/logs`, or a later approved object-storage adapter.
- Secrets: host-managed environment variables or secret stores, never committed
  to the repository.
- Backups: PostgreSQL dumps or managed database backups plus raw file storage
  snapshots/copies.
- Auth configuration: managed OIDC/OAuth2 provider settings supplied outside the
  repository.
- Feedback configuration: GitHub Issues repo and token supplied as server-side
  secrets only.
- Page data mode: `CCLD_HOSTED_PAGE_DATA_MODE=postgres` for production-style
  runtime; `fixture-demo` only for explicit local demos/tests.

Application code must not hard-code QNAP paths, cloud regions, bucket names,
private URLs, hosted callback URLs, database credentials, or provider-specific
secrets.

## Environment Variables

Use `.env.example` only as a placeholder map. Real values belong in an untracked
`.env` file on QNAP or in the selected host's secret/environment configuration.

Portable groups:

- Database: `CCLD_POSTGRES_DB`, `CCLD_POSTGRES_USER`, `CCLD_POSTGRES_PASSWORD`,
  and the generated `CCLD_HOSTED_TESTER_DATABASE_URL`.
- App mode: `CCLD_HOSTED_PAGE_DATA_MODE=postgres`,
  `CCLD_HOSTED_TESTER_AUTH_MODE=production`, and
  `CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH=disabled`.
- Auth placeholders: `CCLD_HOSTED_TESTER_AUTH_PROVIDER_CLASS`,
  `CCLD_HOSTED_TESTER_OIDC_ISSUER`, `CCLD_HOSTED_TESTER_OIDC_CLIENT_ID`,
  `CCLD_HOSTED_TESTER_OIDC_CALLBACK_PATH`, and
  `CCLD_HOSTED_TESTER_OIDC_SCOPES`.
- Feedback placeholders: `GITHUB_FEEDBACK_REPO`, `GITHUB_FEEDBACK_TOKEN`, and
  optional `GITHUB_FEEDBACK_DEFAULT_LABELS`.
- Optional local reference data: `CCLD_FACILITY_REFERENCE_CSV`, only when a
  local or mounted facility reference CSV is intentionally used.
- Optional controlled retrieval settings: `CCLD_RETRIEVAL_ENABLED`,
  `CCLD_RETRIEVAL_RAW_DIR`, `CCLD_RETRIEVAL_MAX_DATE_RANGE_DAYS`,
  `CCLD_RETRIEVAL_PER_JOB_LIMIT`, `CCLD_RETRIEVAL_RATE_LIMIT_PER_ACTOR`,
  `CCLD_RETRIEVAL_TIMEOUT_SECONDS`, and `CCLD_RETRIEVAL_RETRY_LIMIT`.
- Local-dev retrieval demo: `CCLD_RETRIEVAL_DEMO_MODE=mock-success` only for
  explicit local-dev fixture/demo validation. Leave it blank for QNAP,
  production-like, and future cloud hosts.

Do not commit real issuer URLs, callback URLs, tenant identifiers, client
secrets, tokens, cookies, private headers, database URLs, cloud credentials, or
machine-specific paths.

## Hosting Option Comparison

| Option | Python app | PostgreSQL | Persistent raw file storage | Server-side retrieval jobs | Secrets | Scheduled backups | Custom domain/HTTPS | Notes |
|---|---|---|---|---|---|---|---|---|
| QNAP Docker | Yes, via Compose app container | Yes, PostgreSQL container or external PostgreSQL | Yes, Docker named volumes or QNAP-backed host storage | Future worker/container job can run beside app after ADR approval | Untracked `.env` or QNAP-managed settings | QNAP snapshots plus `pg_dump` | Depends on router/reverse proxy setup | First practical target. Lowest rewrite risk because current Compose model already matches it. |
| AWS low-cost path | Yes, ECS/Fargate, App Runner, or EC2 container | RDS PostgreSQL, Aurora Serverless, or PostgreSQL on EC2 | EFS or S3-style object storage after adapter approval | ECS task, EventBridge, Lambda wrapper, or worker container after ADR approval | AWS Secrets Manager, SSM Parameter Store, or task env | RDS snapshots or scheduled `pg_dump`; S3/EFS lifecycle backups | ALB/App Runner/CloudFront with ACM | Likely long-term target, but avoid AWS-specific app code. Free-tier details change and should not be assumed permanent. |
| Azure | Yes, Container Apps, App Service for Containers, or VM/container | Azure Database for PostgreSQL or PostgreSQL in container | Azure Files, managed disk, or Blob Storage after adapter approval | Container Apps jobs, Functions wrapper, or worker container after ADR approval | Key Vault or app settings | Managed PostgreSQL backups plus storage snapshots | App Service/Container Apps ingress with certificates | Good managed identity story; avoid Azure SDK dependency until needed. |
| DigitalOcean | Yes, App Platform or Droplet/container | Managed PostgreSQL or PostgreSQL on Droplet | Volumes, Spaces after adapter approval, or Droplet disk | Worker component, cron, or Droplet service after ADR approval | App Platform env/secrets or Droplet secrets management | Managed DB backups/snapshots; volume snapshots | App Platform/Droplet reverse proxy | Simple operational model; managed services may exceed hobby/free budgets. |
| Render | Yes, web service container | Render PostgreSQL or external PostgreSQL | Persistent disks on paid tiers, or external object storage after adapter approval | Background worker or cron job after ADR approval | Environment/secret settings | Managed PostgreSQL backups depend on plan | Built-in custom domain/HTTPS | Convenient app hosting; check current free-tier database and persistent disk limits before choosing. |
| Fly.io | Yes, app container | Fly Postgres or external PostgreSQL | Volumes; object storage requires separate service/adapter | Machines/worker process or scheduled machine after ADR approval | Secrets | Volume snapshots and database backup workflow need explicit setup | Built-in TLS and custom domains | Portable container model, but volumes are region/instance-specific and need careful backup planning. |
| Railway | Yes, service container | Railway PostgreSQL or external PostgreSQL | Persistent volumes/support depends on current plan; external object storage may be needed | Service/cron pattern after ADR approval | Variables/secrets | Backup support depends on current plan | Custom domains/HTTPS | Fast prototype path; verify pricing and persistence before relying on it. |
| Supabase or Neon with separate app host | No app host by itself for this app | Yes, managed PostgreSQL | Not enough for raw files unless paired with object storage | Requires separate app/worker host | Database/provider secrets plus app host secrets | Managed database backups depend on plan | App custom domain handled by separate host | Useful as a PostgreSQL provider, not a complete app deployment by itself. |

## Recommended Migration Shape

Start with QNAP Docker and keep the same boundaries when moving cloudward:

1. Build the same app container from `Dockerfile`.
2. Point the app at PostgreSQL through environment variables.
3. Run `alembic upgrade head` before app startup or as a one-time release step.
4. Mount durable raw/processed/log storage or use a later approved object-storage
   adapter.
5. Keep auth provider configuration in the host secret store.
6. Keep server-side retrieval jobs separate from request-time browser code when
  ADR-0016 retrieval implementation is added.
7. Use `scripts/verify-qnap-pilot-workflow.ps1` for the QNAP pilot as a concrete
   example of env, Compose, container, and route verification. Later hosts should
   keep equivalent checks for database, raw storage, secrets, migrations, health,
   auth status, feedback, CCLD request, retrieval history/detail, and reviewer
   routes.
8. Validate `/health`, `/auth/status`, `/ccld/help`, `/feedback`, and protected
  workflow behavior before inviting testers.
9. Validate `/feedback` in unconfigured mode and with a mocked or non-production
  GitHub Issues configuration before accepting tester feedback.

## Raw File Storage Migration

Current Docker storage uses named volumes for:

- `ccld_raw_data` mounted at `/app/data/raw`.
- `ccld_processed_data` mounted at `/app/data/processed`.
- `ccld_logs` mounted at `/app/data/logs`.

For migration:

1. Stop app writes or enter a maintenance window.
2. Export/copy raw, processed, and log volume contents with host-specific tools.
3. Preserve relative paths and file names referenced by source traceability.
4. Verify raw SHA-256 hashes after copy where raw files are referenced by hosted
   rows or import artifacts.
5. Restore volumes or map them to equivalent cloud persistent storage.
6. Keep public narrative content access-limited even when source files are public.

Do not migrate raw files by committing them to the repository.

## PostgreSQL Backup and Restore

Portable backup baseline:

```powershell
pg_dump -Fc -f ccld-postgres.dump <database-url-or-connection-options>
```

Portable restore baseline into a prepared compatible database:

```powershell
pg_restore --clean --if-exists -d <database-url-or-connection-options> ccld-postgres.dump
```

For QNAP Compose, use the concrete commands in
[qnap-docker-runtime.md](qnap-docker-runtime.md). For managed cloud PostgreSQL,
prefer managed snapshots/backups when available, and periodically test a restore
into a non-production database before relying on backups.

Backups must cover both PostgreSQL and raw/source files. A database backup alone
is not enough if hosted rows reference raw paths or raw hashes.

## Server-Side Retrieval Jobs

ADR-0016 controlled browser-triggered, server-executed CCLD retrieval jobs now
have a first implementation slice for complaint records. Keep job execution
host-portable:

- Browser submits bounded CCLD facility/license, record-type, and date-range
  inputs only.
- Server or worker performs retrieval.
- Raw source evidence is preserved in configured raw storage.
- Source-derived records are validated before PostgreSQL import.
- Rate limits, job status, audit/status metadata, and safe error messages are
  enforced by application services.
- Job workers should run as a separate process/container/task where possible.
- Tests must mock network retrieval; CI must not make live CCLD calls.

Do not build retrieval jobs around provider-specific queues until the project
chooses that host or adds a portable abstraction.

## Production-Readiness Checklist

Before any public or pilot launch claim:

- `main` is protected by a ruleset requiring PRs and `validate`, `docs-check`,
  `fixtures`, and `security` checks.
- Runtime uses `CCLD_HOSTED_PAGE_DATA_MODE=postgres`.
- Runtime uses `CCLD_HOSTED_TESTER_AUTH_MODE=production` and local-dev auth is
  disabled.
- Managed OIDC/OAuth2 provider is configured outside the repo.
- No secrets, hosted URLs, callback URLs, tokens, cookies, or private account
  values are committed.
- PostgreSQL migrations have run successfully.
- A validated CCLD artifact has been imported.
- Facility lookup, request queue, reviewer detail, and auth status routes are
  verified against PostgreSQL-backed data.
- Raw and processed storage is persistent and backed up.
- PostgreSQL backup and restore have been tested.
- Raw file copy/restore preserves source traceability and hashes.
- HTTPS/custom domain is configured by the host or reverse proxy.
- Logs do not expose secrets, raw provider claims, cookies, tokens, private
  headers, or unnecessary narrative source text.
- Retrieval jobs remain disabled unless configuration enables the controlled
  server-side job path and raw artifact storage is available.
- Known limitations and support/incident notes are current.

## Non-Goals

This guide does not implement cloud deployment, provision resources, choose a
final cloud provider, create DNS, configure TLS, create app registrations, add
provider SDKs, or replace the QNAP-first path. It is a
portable checklist so a later move does not require rethinking app, database,
storage, secrets, and backup boundaries from scratch.