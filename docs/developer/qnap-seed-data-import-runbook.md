# QNAP Seed Data Import Runbook

Use this runbook to load a validated CCLD hosted seeded-corpus artifact into the
QNAP PostgreSQL-backed pilot deployment. Complete this step after Alembic
migrations are current and before inviting testers to review records.

This runbook is operator documentation only. It does not change app behavior,
routes, auth, schema, migrations, Docker configuration, or retrieval behavior.

Cross-references:

- [QNAP pilot deployment inventory](qnap-pilot-deployment-inventory.md) — what
  runs, what environment variables are required.
- [QNAP Docker runtime guide](qnap-docker-runtime.md) — file transfer, startup,
  log inspection.
- [QNAP pilot seeded import evidence](qnap-pilot-seeded-import-evidence.md) —
  read-only PostgreSQL evidence queries after import.
- [QNAP pilot operator checklist](qnap-pilot-operator-checklist.md) — ordered
  pre-invite checklist.

## 1. Preconditions

Complete every item before starting the import.

- The QNAP app container and PostgreSQL container are both healthy.
- Alembic migrations are current (`alembic upgrade head` has run successfully).
- `CCLD_HOSTED_PAGE_DATA_MODE=postgres` is set in the QNAP `.env`.
- `CCLD_HOSTED_TESTER_AUTH_MODE=production` and
  `CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH=disabled` remain set.
- A validated CCLD SQLite pipeline output file is available on the Windows
  workstation that built it.
- The QNAP deployment folder (`.env`, `docker-compose.qnap.yml`, `Dockerfile`)
  is present on the QNAP host.
- The operator has `scp` or an equivalent secure copy tool available on the
  Windows workstation.
- The operator has SSH access to the QNAP host.

Check that both containers are healthy before continuing:

```powershell
docker compose -f docker-compose.qnap.yml --env-file .env ps
```

Both `app` and `postgres` should show `healthy` or `running`. Do not import
into a partially started or unhealthy stack.

## 2. Step 1 — Build The Validated Artifact On Windows

Run this command from the repository root on the Windows workstation. Replace
`<db-path>` with the path to your validated CCLD SQLite file.

**Single-facility artifact** — use when the SQLite file contains exactly one
facility, or when you want to load only a specific facility:

```powershell
.\scripts\build-hosted-ccld-artifact.ps1 `
    -DbPath <db-path> `
    -FacilityNumber <facility-number> `
    -OutputPath data\processed\hosted_seeded_corpus\validated_ccld_seeded_corpus.json `
    -Overwrite
```

**Full-corpus artifact** — use when the SQLite file contains multiple facilities
and you want to load all of them into a single artifact. `-AllFacilities` is
opt-in and explicit. Do not use `-FacilityNumber` together with `-AllFacilities`
(they are mutually exclusive):

```powershell
.\scripts\build-hosted-ccld-artifact.ps1 `
    -DbPath <db-path> `
    -AllFacilities `
    -OutputPath data\processed\hosted_seeded_corpus\validated_ccld_seeded_corpus.json `
    -Overwrite
```

The artifact written for `-AllFacilities` includes `"corpus_scope": "full-corpus"`
in the JSON. The single-facility artifact includes `"corpus_scope": "single-facility"`.
Both distinguish the build scope, source artifact identity, import batch ID, and
generated timestamp. Both must be imported using the same `import_hosted_seeded_corpus`
command in step 5.

The script prints `Corpus scope: full-corpus` and the number of facilities included
when `-AllFacilities` is used. For single-facility, it prints the facility number.
Neither print reveals secrets or private paths.

If the SQLite contains multiple facilities and you pass neither `-FacilityNumber`
nor `-AllFacilities`, the command will fail with a clear message asking you to
choose. This failure is intentional.

The script writes the artifact to
`data\processed\hosted_seeded_corpus\validated_ccld_seeded_corpus.json` by
default. Verify the file exists and is non-empty before continuing:

```powershell
Get-Item data\processed\hosted_seeded_corpus\validated_ccld_seeded_corpus.json |
    Select-Object Name, Length, LastWriteTime
```

The `data\processed\hosted_seeded_corpus\` folder is in `.gitignore`. Do not
commit the artifact.

## 3. Step 2 — Transfer The Artifact To The QNAP Host

Copy the artifact to a staging location on the QNAP host. Use the same secure
copy approach used for the initial deployment file transfer (see the
[QNAP Docker runtime guide](qnap-docker-runtime.md) file-transfer section).

```powershell
scp data\processed\hosted_seeded_corpus\validated_ccld_seeded_corpus.json `
    <qnap-user>@<qnap-host>:<qnap-deployment-root>/import-staging/validated_ccld_seeded_corpus.json
```

On the QNAP host, confirm the file arrived before continuing:

```bash
ls -lh <qnap-deployment-root>/import-staging/validated_ccld_seeded_corpus.json
```

Do not store the artifact in the repository checkout or in a location that is
committed or publicly accessible.

## 4. Step 3 — Copy The Artifact Into The App Container Volume

Copy the artifact from the QNAP host staging location into the app container's
`/app/data/processed/hosted_seeded_corpus/` path. This path is backed by the
`ccld_processed_data` named Docker volume and persists across container restarts.

Run from the QNAP deployment folder (where `docker-compose.qnap.yml` lives):

```bash
mkdir -p <qnap-deployment-root>/import-staging
docker compose -f docker-compose.qnap.yml cp \
    <qnap-deployment-root>/import-staging/validated_ccld_seeded_corpus.json \
    app:/app/data/processed/hosted_seeded_corpus/validated_ccld_seeded_corpus.json
```

`docker compose cp` requires Docker Compose v2.x and a running app service.
Confirm the copy succeeded:

```bash
docker compose -f docker-compose.qnap.yml exec app \
    ls -lh /app/data/processed/hosted_seeded_corpus/validated_ccld_seeded_corpus.json
```

## 5. Step 4 — Run The Import

Run the import inside a one-off container using the existing Compose environment.
The `--env-file` flag passes the database URL and other required configuration
into the container without requiring the operator to paste the database URL on
the command line.

```bash
docker compose -f docker-compose.qnap.yml --env-file .env run --rm app \
    python -m ccld_complaints.cli.import_hosted_seeded_corpus \
    /app/data/processed/hosted_seeded_corpus/validated_ccld_seeded_corpus.json
```

Expected output on success:

```
Imported hosted seeded corpus batch: <import-batch-id>
Source-derived records staged: <count>
Reviewer-created state written: no
```

The import is idempotent for a given import batch ID. Running the same artifact
twice does not duplicate records, but it does create a new import batch row. If
you need to reload from a different artifact, prepare a new artifact with a
distinct import batch ID using `-ImportBatchId` in `build-hosted-ccld-artifact.ps1`.

If the command exits with an error, see section 9 (Troubleshoot And Rerun).

## 6. Step 5 — Verify The Import

Run the read-only evidence queries described in
[QNAP pilot seeded import evidence](qnap-pilot-seeded-import-evidence.md)
section 3. The key checks are:

Confirm the import batch is present and validated:

```bash
docker compose -f docker-compose.qnap.yml --env-file .env exec postgres \
    sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
    "SELECT validation_status, raw_hash_validation_status, count(*) AS import_batches \
     FROM hosted_import_batches \
     GROUP BY validation_status, raw_hash_validation_status \
     ORDER BY validation_status, raw_hash_validation_status;"'
```

Confirm source-derived records are present by entity type:

```bash
docker compose -f docker-compose.qnap.yml --env-file .env exec postgres \
    sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
    "SELECT entity_type, count(*) AS source_derived_rows \
     FROM hosted_source_derived_records \
     GROUP BY entity_type ORDER BY entity_type;"'
```

Counts greater than zero for `complaint`, `facility`, `source_document`, and
related entity types indicate a successful import. Counts of zero for all types
indicate the import did not complete or wrote to a different database. Recheck
`CCLD_HOSTED_TESTER_DATABASE_URL` in the `.env` file and rerun.

## 7. Health Endpoint Behavior After Import

**Known gap**: The `/health` endpoint always returns `source_data_loaded: false`
and `scaffold_only: true` regardless of whether records have been imported. This
is hardcoded in the current app implementation and does not reflect the actual
database state.

Do not use the `/health` response to determine whether the import succeeded. Use
the PostgreSQL evidence queries in section 6 instead.

```bash
curl -s http://<host-name-or-ip>:<CCLD_HOSTED_PORT>/health
```

The `/health` response showing `source_data_loaded: false` after a successful
import is expected and does not indicate a problem with the import.

## 8. Inspect Container Logs

To inspect recent app container logs after import:

```bash
docker compose -f docker-compose.qnap.yml logs --tail=60 app
```

To stream logs:

```bash
docker compose -f docker-compose.qnap.yml logs -f app
```

Look for Alembic migration lines, import-related log output, and any error
tracebacks. If you see database connection errors, confirm PostgreSQL is healthy
and that `CCLD_HOSTED_TESTER_DATABASE_URL` is set correctly in the `.env` file.

## 9. Troubleshoot And Rerun

If the import command fails:

1. Check the error output. Common causes:
   - `RuntimeError: Hosted tester database URL is required` — `CCLD_HOSTED_TESTER_DATABASE_URL` is not set or not reachable from the container. Confirm the `.env` file and that the `postgres` service is healthy.
   - `FileNotFoundError` or artifact path error — the artifact was not copied into the container correctly. Repeat step 4.
   - JSON decode error or schema validation error — the artifact file is malformed or truncated. Rebuild it in step 1.

2. Inspect logs:
   ```bash
   docker compose -f docker-compose.qnap.yml logs --tail=60 app
   ```

3. Confirm the database is reachable from a one-off app container:
   ```bash
   docker compose -f docker-compose.qnap.yml --env-file .env run --rm app \
       python -c "from ccld_complaints.hosted_app.persistence import load_hosted_database_config; \
                  from sqlalchemy import create_engine, text; \
                  cfg = load_hosted_database_config(require_url=True); \
                  e = create_engine(cfg.database_url); \
                  print(e.connect().execute(text('SELECT 1')).scalar())"
   ```
   A result of `1` confirms database connectivity.

4. Correct the problem and rerun step 4 (copy) and step 5 (import).

**To reload from a revised artifact** (safe non-destructive approach):

Build a new artifact with a distinct import batch ID on the Windows workstation,
transfer it (steps 2–3), and rerun the import (step 5). The importer stages
records by stable source identity and import batch. An existing import batch
is not overwritten; a new batch row is created.

**Note**: The current implementation does not include a one-command reset/reload
that clears previous import batches and source-derived records before reloading.
A reset/reload dry-run API seam and execution-plan seam exist in the codebase
(`/api/operations/seeded-corpus-reset-reload/dry-run` and `/execution-plan`) but
are local/test seams only and are not exposed as an operator CLI command. This is
a documented gap. Until a safe reset/reload CLI command is implemented, coordinate
with the development operator before removing import batches from PostgreSQL
manually.

## 10. Evidence To Capture

Capture the following without including secrets, private hostnames, tokens,
tester emails, raw artifact contents, raw server paths, or generated source data:

- Import command exit code and printed output (batch ID and record counts).
- Output of the `hosted_import_batches` count query (validation status, count).
- Output of the `hosted_source_derived_records` count query (entity type, count).
- Source traceability linkage counts (source URL, raw SHA-256, connector, source
  document linkage — see `qnap-pilot-seeded-import-evidence.md` section 3).
- Docker Compose health status of app and postgres services.
- Alembic `alembic current` output confirming migrations are applied.

Do not capture or commit database passwords, connection strings,
`CCLD_HOSTED_TESTER_DATABASE_URL`, raw artifact file contents, QNAP host paths,
or tester email addresses.

## 11. Readiness Gate

The QNAP pilot is not tester-ready until:

- Import evidence shows non-zero source-derived record counts in PostgreSQL.
- The QNAP verifier passes.
- Route evidence is captured.
- The Cloudflare Tunnel and Cloudflare Access access layer is configured and
  verified per [qnap-cloudflare-tunnel-access-setup.md](qnap-cloudflare-tunnel-access-setup.md).
- The access-method decision is recorded and open questions are resolved.
- The tester invitation decision is recorded.

Do not share any tester-facing URL, network path, or access credential before
all of the above are complete.

## 12. Do-Not-Do List

- Do not commit the artifact (`data/processed/hosted_seeded_corpus/`).
- Do not commit `.env` or paste its contents into issue comments or PRs.
- Do not paste the database URL or PostgreSQL password into the command line
  outside of the `--env-file` mechanism.
- Do not expose raw artifact file contents in screenshots, issue comments, or
  shared docs.
- Do not expose QNAP host-specific raw paths in shared docs or issues.
- Do not treat import evidence as proof of public-source completeness, legal
  findings, facility-wide conclusions, harm, abuse, neglect, or liability.
- Do not set `CCLD_RETRIEVAL_DEMO_MODE=mock-success` in QNAP pilot mode.
- Do not use fixture-demo mode as substitute QNAP pilot import evidence.
- Do not manually delete PostgreSQL rows to simulate a reset without coordinating
  with the development operator.
