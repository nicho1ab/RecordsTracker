# QNAP Pilot Seeded Import Evidence

Use this evidence guide after the QNAP pilot stack is configured and before
inviting early external stakeholder organization testers. It helps an operator prove that PostgreSQL-backed
hosted CCLD source-derived records are available to the app, rather than relying
only on fixture-demo or scaffold assumptions.

This guide complements the [QNAP pilot operator checklist](qnap-pilot-operator-checklist.md),
[QNAP Docker runtime guide](qnap-docker-runtime.md), and `RUNBOOK.md`.

## 1. Purpose

- Capture early QNAP hosted tester readiness evidence.
- Prove the hosted app can see imported PostgreSQL-backed CCLD source-derived
  records from a validated hosted seeded-corpus artifact or controlled seeded
  import path.
- Preserve source traceability by checking import batch metadata, source-derived
  row counts, source URL presence, raw SHA-256 presence, connector metadata, and
  source document linkage.
- This evidence does not prove public-source completeness.
- Do not treat this evidence as public-source completeness, public-source
  absence, legal findings, facility-wide conclusions, harm conclusions, abuse
  conclusions, neglect conclusions, liability conclusions, or official CCLD
  coverage.

## 2. Preconditions

- `.env` exists on the deployment host and remains untracked.
- PostgreSQL container is running.
- Alembic migrations are current.
- `CCLD_HOSTED_PAGE_DATA_MODE=postgres` is set for QNAP pilot mode.
- The QNAP verifier passes, or reports only expected placeholder warnings from
  `.env.example`-style values that will be replaced before inviting testers.
- `CCLD_RETRIEVAL_RAW_DIR` is configured as a container raw artifact path and is
  included in backup planning.
- `CCLD_RETRIEVAL_DEMO_MODE=` remains blank for QNAP pilot mode.
- GitHub feedback is either intentionally disabled with both feedback values
  blank, or fully configured server-side with both repo and token values in the
  untracked host configuration.

Run the QNAP verifier first:

```powershell
.\scripts\verify-qnap-pilot-workflow.ps1 -EnvFile .env
```

When containers are running, include container and route checks:

```powershell
.\scripts\verify-qnap-pilot-workflow.ps1 -EnvFile .env -CheckContainers -BaseUrl http://<host-name-or-ip>:<CCLD_HOSTED_PORT>
```

## 3. Import Evidence

Use these commands from the repository root on the Docker host. They use the
existing Compose services and container environment so database secrets do not
need to be pasted into command lines, issue comments, PRs, or evidence notes.

Confirm migrations are current:

```powershell
docker compose -f docker-compose.qnap.yml --env-file .env run --rm app alembic current
```

Confirm the hosted import tables exist:

```powershell
docker compose -f docker-compose.qnap.yml --env-file .env exec postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT table_name FROM information_schema.tables WHERE table_schema = ''public'' AND table_name IN (''hosted_import_batches'', ''hosted_source_derived_records'', ''hosted_ccld_retrieval_jobs'') ORDER BY table_name;"'
```

Capture validated import batch counts:

```powershell
docker compose -f docker-compose.qnap.yml --env-file .env exec postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT validation_status, raw_hash_validation_status, count(*) AS import_batches FROM hosted_import_batches GROUP BY validation_status, raw_hash_validation_status ORDER BY validation_status, raw_hash_validation_status;"'
```

Capture source-derived record counts by entity type:

```powershell
docker compose -f docker-compose.qnap.yml --env-file .env exec postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT entity_type, count(*) AS source_derived_rows FROM hosted_source_derived_records GROUP BY entity_type ORDER BY entity_type;"'
```

Capture safe traceability linkage counts without printing raw artifact contents
or server-specific raw paths:

```powershell
docker compose -f docker-compose.qnap.yml --env-file .env exec postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT entity_type, count(*) AS rows, count(source_url) AS rows_with_source_url, count(raw_sha256) AS rows_with_raw_sha256, count(source_document_id) AS rows_with_source_document_id FROM hosted_source_derived_records GROUP BY entity_type ORDER BY entity_type;"'
```

Capture a bounded source document and complaint linkage sample. Do not include
`raw_path` if it contains a host-specific path or reveals server layout:

```powershell
docker compose -f docker-compose.qnap.yml --env-file .env exec postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT entity_type, stable_source_id, source_document_id, connector_name, left(raw_sha256, 12) || ''...'' AS raw_sha256_prefix FROM hosted_source_derived_records WHERE entity_type IN (''source_document'', ''complaint'') ORDER BY entity_type, stable_source_id LIMIT 10;"'
```

If counts are zero, treat the deployment as not ready for tester review. Build or
prepare a validated CCLD hosted seeded-corpus artifact through the existing
outside-browser workflow, import it through the existing hosted import path, then
repeat this evidence capture. Do not use fixture-demo mode or local-dev
mock-success mode to stand in for QNAP pilot evidence.

## 4. Route Evidence

Capture the route-check summary from the QNAP verifier first. It verifies the
landing page, health, auth status, feedback, CCLD facility/request/retrieval
history/help surfaces, retrieval detail safe not-found behavior, and reviewer
route status without making live CCLD or GitHub calls.

For `/ccld/records/request`, capture the expected state for the configured
pilot mode:

- If no authenticated tester context is available yet, protected workflow pages
  may show sign-in-required guidance. Record that as an auth readiness state,
  not as a data absence state.
- If PostgreSQL is unavailable, not migrated, or empty, pages should show
  setup-required guidance rather than silently falling back to fixture data.
- If PostgreSQL-backed records are available and an authorized workflow context
  is available, submit the known facility/date request and capture the loaded
  queue state, including matching source-derived row counts and reviewer links.
- If the queue returns no match, confirm the facility/date criteria, import
  counts, and local validated load state before assuming anything. A no-match
  result is not proof that the public CCLD portal has no matching records.

For retrieval routes:

- `/ccld/retrieval/jobs` should show safe empty-history or recent-job history
  over existing operational metadata.
- `/ccld/retrieval/jobs/detail?job_id=missing-job` should show safe not-found,
  protected, or setup-required state without raw stack traces, raw artifact
  contents, raw server paths, or private values.
- Retrieval setup-required state is expected when `CCLD_RETRIEVAL_ENABLED` is
  disabled or retrieval is not fully configured with server-side raw storage.

For `/feedback`, record whether GitHub feedback is intentionally disabled or
fully configured. If disabled, the page should say feedback is not configured
and should not call GitHub. If configured, only safe issue metadata should be
sent server-side.

## 5. Evidence Packet

Keep the packet small and safe:

- QNAP verifier output summary.
- Docker Compose config validation success.
- Alembic current output or migration success.
- Validated `hosted_import_batches` count.
- `hosted_source_derived_records` counts by entity type.
- Source URL, raw SHA-256, connector, and source document linkage counts.
- No raw artifact file contents displayed.
- Bounded route check results for `/ccld/records/request`, retrieval history,
  retrieval missing-job detail, `/feedback`, `/ccld/help`, and `/reviewer`.
- GitHub feedback decision: intentionally disabled or fully configured.
- Controlled retrieval decision: intentionally disabled or fully configured with
  persistent raw artifact storage.
- PostgreSQL backup location or plan confirmation.
- Raw artifact storage backup location or plan confirmation.
- Known limitations acknowledged.

Do not include real secrets, provider values, tokens, private URLs, raw artifact
contents, raw narrative source content, server-specific raw paths, or host-local
backup locations in public PRs, issues, screenshots, or committed docs.

## 6. Backup Notes

- Back up the PostgreSQL volume or create a PostgreSQL dump before inviting
  testers and before risky changes.
- Back up raw artifact storage separately from PostgreSQL.
- Store any `.env` backup outside the repository and restrict access.
- Preserve logs when setup fails, but redact secrets, private URLs, raw provider
  values, and connection details before sharing.
- A database backup alone is not enough when source-derived rows reference raw
  artifact hashes or artifact storage.

## 7. Do-Not-Do List

- Do not commit `.env`.
- Do not paste secrets into issue comments, PRs, screenshots, docs, or support
  notes.
- Do not expose raw artifacts to testers.
- Do not expose raw server-specific paths to testers.
- Do not treat no records found as proof of public-source absence.
- Do not treat imported PostgreSQL rows as proof of public-source completeness.
- Do not make legal, facility-wide, harm, abuse, neglect, liability, or
  completeness conclusions from this evidence.
- Do not enable `CCLD_RETRIEVAL_DEMO_MODE=mock-success` for QNAP pilot mode.
- Do not use fixture-demo mode as QNAP pilot seeded import evidence.