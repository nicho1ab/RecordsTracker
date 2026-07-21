# QNAP Release Deployment Runbook

## Authority

This is the authoritative RecordsTracker procedure for QNAP release deployment, verification, hosted acceptance, and application rollback. Do not invent an alternate deployment process. Stop and update this runbook through a reviewed pull request when an observed runtime condition conflicts with it.

HQ is permanently human-only. The user alone performs archive transfer and
every QNAP, deployment, rollback, database, restore, and Cloudflare operation
through the approved local transfer workflow and standalone SSH client.

Agents may verify a release SHA locally, prepare and inspect a clean local
archive, calculate its hash, generate local archive-transfer command text,
generate QNAP command text from this runbook, prepare hosted-acceptance
checklists, and interpret safe output pasted by the user.

Agents may never invoke SSH through PowerShell, Git Bash, WSL, Python,
libraries, MCP, browser terminals, or an indirect mechanism; run remote shell
commands; run QNAP Docker or Compose; inspect or modify QNAP `.env`; connect to
QNAP PostgreSQL; transfer or deploy autonomously; deploy; roll back; restore
PostgreSQL; or administer Cloudflare.

## Fixed environment

- Local repository: `<repo-root>\`
- QNAP host: `<qnap-host>` (private operator-supplied value).
- QNAP username: `<qnap-user>` (private operator-supplied value).
- Active application directory: `/share/Public/RecordsTracker`
- Staging directory: `/share/Public/RecordsTracker-staging`
- Backup paths: timestamped application-tree, configuration, deployed-commit,
  and PostgreSQL-dump paths created by this procedure; no private host or
  account value is committed as part of those paths.
- Compose filename: `docker-compose.qnap.yml`
- Compose service identities: `app` and `postgres`; Compose assigns container
  names because the file does not declare fixed `container_name` values.
- QNAP does not use Git for deployment.
- The user uses Windows PowerShell only for local Git verification, archive
  creation, and archive transfer.
- The user runs all QNAP commands directly in the standalone SSH client.
- Preserve the active host-local `.env`. Back up the active
  `docker-compose.qnap.yml`, but retain the release's tracked Compose file when
  it contains reviewed release changes.
- Application and PostgreSQL runtime data use Docker named volumes unless inspection proves otherwise.
- Never restore PostgreSQL during an application rollback unless separately authorized.

The host and username values remain in a user-controlled location outside the
repository. The user may use a private PSD1 file, password manager, operator
notes, or manual substitution. No agent may read, create, display, upload, or
depend on that private store, and no agent may create a private PSD1 file.

## Required deployment model

1. Verify clean local `main` and `origin/main` at the exact approved merged commit.
2. Create a clean tar archive with `git archive` and verify that it is readable and non-empty.
3. The user transfers the archive with `scp` using
   `<qnap-user>@<qnap-host>`.
4. Move the archive into a versioned staging directory under `/share/Public/RecordsTracker-staging`.
5. Inspect active Compose services and container mounts before changing the runtime.
6. Confirm that runtime data is stored in named volumes or explicitly preserve every runtime bind mount.
7. Create and verify:
   - a complete active-application-tree backup;
   - copies of `.env`, `docker-compose.qnap.yml`, and the prior `.deployed-commit`;
   - a non-empty PostgreSQL dump.
8. Extract the archive into a new versioned release directory.
9. Copy the active host-local `.env` into the new release. Do not replace the
   release's tracked `docker-compose.qnap.yml` with the previously deployed
   file.
10. Compare the backed-up active Compose file with the release's tracked Compose
    file. Accept only reviewed, expected release changes. If the old file has an
    unexpected host-specific difference, stop deployment and resolve it through
    review; do not copy or merge it into the release ad hoc.
11. Do not copy the old `.deployed-commit` into the new release.
12. Run `sudo docker compose -f docker-compose.qnap.yml --env-file .env config`
    from the new release and require it to pass before activation.
13. Stop only the `app` service; leave PostgreSQL running. Never recreate the
    `postgres` service or its volume for this application-only release.
14. Rename the active directory to a timestamped previous-release directory;
    its prior tracked Compose file remains with that prior application release.
15. Rename the validated versioned release directory to `/share/Public/RecordsTracker`.
16. Rebuild and recreate only the `app` service with `--no-deps`.
17. Verify the app is running, healthy, and has zero restarts after recreation.
18. Verify PostgreSQL remains running and healthy; report its restart count without assuming it began at zero.
19. Verify Alembic current is at head, logs contain no deployment-blocking errors, the health route returns 200, and required routes return no 5xx responses.
20. Write the new full commit to `.deployed-commit` only after all verification succeeds.
21. Retain the prior release directory and backups until hosted acceptance and stakeholder confirmation are complete.

## Prohibited deployment approaches

- Do not deploy with Git on QNAP.
- Do not blindly overlay the new archive onto the active tree.
- Do not use `rsync --delete` unless this runbook is deliberately revised after compatibility testing.
- Do not preserve unexplained historical clutter inside the active application directory.
- Do not stop, recreate, delete, or replace the PostgreSQL service or volume during an application-only release.
- Do not induce live errors or mutate production-style data merely to reproduce controlled evidence states.

## Verification routes

Verify at minimum:

- `/`
- `/ccld/facilities`
- `/ccld/records/request`
- `/ccld/facilities/intelligence`
- `/reviewer`
- `/feedback`
- `/ccld/help`

Direct unauthenticated checks may return an expected authentication response, but they must not return transport failures or HTTP 5xx responses.

## Application rollback

Rollback restores the preserved previous application directory together with
its prior tracked Compose file:

1. Stop the `app` service.
2. Rename the failed active directory to a timestamped failed-release path.
3. Rename the preserved previous-release directory back to `/share/Public/RecordsTracker`.
4. Restore the preserved host-local `.env`, require
   `sudo docker compose -f docker-compose.qnap.yml --env-file .env config` to
   pass, and rebuild and recreate only the `app` service with `--no-deps`.
5. Verify app and PostgreSQL health and the health route.
6. Do not recreate the `postgres` service or volume. Do not restore PostgreSQL
   unless a separately reviewed database rollback is required.

## Hosted acceptance

After deployment:

- review the authenticated intelligence route at desktop, narrow, mobile, keyboard-focus, copy-feedback, and print states;
- reconcile at least three representative real facilities to PostgreSQL and original source records;
- confirm displayed complaint counts equal unique contributing complaint records;
- confirm recommended-next complaint and source actions resolve to the displayed complaint;
- confirm source-derived and reviewer-created state remain separate;
- confirm no duplicate Facility IDs, duplicate complaint records, or synthetic fallback facilities appear;
- record evidence locations, limitations, scenarios, and stakeholder confirmation in the governing issue.

Controlled fixture evidence remains authoritative for loading, forced error, no-data, partial-source, unavailable-source, and other states that should not be induced by damaging the hosted runtime.

### Operator coverage runtime acceptance

Before generating coverage, the human operator configures
`CCLD_OPERATOR_COVERAGE_ALLOWED_EMAILS` with exact operator email addresses and
keeps `CCLD_OPERATOR_COVERAGE_PACKAGE_DIR` at its deployed default
`/app/data/processed/source-to-screen-audit/runtime-current` unless a reviewed
deployment requires another persistent processed-data path. A configured tester
domain does not grant operator access.

The user runs each command below directly in the standalone QNAP SSH client
from `/share/Public/RecordsTracker`. Agents must not run or proxy these commands.

1. Generate the read-only structural audit and atomically publish the validated
   contract package:

   ```sh
   sudo docker compose -f docker-compose.qnap.yml exec -T app python -m ccld_complaints.source_to_screen_audit --mode runtime --output-dir /app/data/processed/source-to-screen-audit/runtime-audit --coverage-output-dir /app/data/processed/source-to-screen-audit/runtime-current
   ```

2. Revalidate package hashes and reconcile its Facility ID totals with a safe
   deployed-database aggregate query:

   ```sh
   sudo docker compose -f docker-compose.qnap.yml exec -T app python -m ccld_complaints.operator_coverage_runtime_verify --package-dir /app/data/processed/source-to-screen-audit/runtime-current
   ```

Both commands are read-only with respect to PostgreSQL. The producer publishes
files only after complete stable-consumer validation and preserves the prior
accepted package on failure. The verifier prints safe aggregate JSON only and
exits nonzero when validation or reconciliation fails. Neither command retrieves
public sources, imports data, changes jobs or checkpoints, or mutates reviewer
state.

After both commands pass, run the automated Hosted acceptance procedure in
`docs/developer/operator-source-coverage-dashboard.md` from the authorized local
workstation. It requires an approved in-memory Cloudflare header-provider
command; do not copy browser cookies or profiles and do not persist assertions.
The unavailable-package state remains a local controlled acceptance scenario and
must not be induced against the deployed runtime.

This coverage is diagnostic for the deployed rows and available governed read
boundaries. It is not proof of statewide completeness, freshness, absence of
complaints, legal conclusions, or correct rendering without the automated UI
evidence.

### TransparencyAPI snapshot lifecycle operator commands

These commands operate only on a complete TransparencyAPI package that the human
operator has already preserved under the app's mounted raw-data volume. The recommended
container path is
`/app/data/raw/ccld/transparencyapi-operator/<snapshot-id>/manifest.json`. The CLI does
not retrieve or copy source data.

When no retained package exists, capture a new package from a clean local RecordsTracker
checkout with the local-only command below. Do not run capture on QNAP, and do not reuse a
missing package's snapshot ID or expected hashes:

```powershell
python -m ccld_complaints.cli.transparencyapi_snapshot_capture capture --output-dir <repo-root>
```

The command writes under the repository's ignored
`data/raw/ccld/transparencyapi-facility-reference` directory, validates the new manifest
locally, and prints aggregate-safe JSON. It does not access a database. The operator must
review that output, run the lifecycle CLI's local `inspect-package` command against the
new manifest, and transfer the complete package separately through the approved human
workflow. A partial or rejected package must not be transferred or reconstructed.

After human transfer, confirm the mounted package directory contains the governed
manifest and every referenced raw artifact before using the QNAP lifecycle commands.

Run read-only checks first from `/share/Public/RecordsTracker` in the standalone QNAP
SSH client. Substitute only the governed container manifest path:

```sh
sudo docker compose -f docker-compose.qnap.yml exec -T app python -m ccld_complaints.cli.transparencyapi_snapshot_lifecycle --help
```

```sh
sudo docker compose -f docker-compose.qnap.yml exec -T app python -m ccld_complaints.cli.transparencyapi_snapshot_lifecycle status
```

```sh
sudo docker compose -f docker-compose.qnap.yml exec -T app python -m ccld_complaints.cli.transparencyapi_snapshot_lifecycle inspect-package /app/data/raw/ccld/transparencyapi-operator/<snapshot-id>/manifest.json
```

```sh
sudo docker compose -f docker-compose.qnap.yml exec -T app python -m ccld_complaints.cli.transparencyapi_snapshot_lifecycle dry-run /app/data/raw/ccld/transparencyapi-operator/<snapshot-id>/manifest.json
```

Stop if any command exits nonzero, reports a rejection, shows an unexpected pointer,
or fails an approved Facility ID/name check. Save only the aggregate JSON. Do not retain
database connection values, source bodies, headers, contact details, or reviewer data in
operator evidence.

Before the first mutation, verify the current PostgreSQL backup still exists and remains
usable. Create a new backup only when the database changed since the verified backup or
that backup is no longer available. Run each lifecycle transition separately:

```sh
sudo docker compose -f docker-compose.qnap.yml exec -T app python -m ccld_complaints.cli.transparencyapi_snapshot_lifecycle stage /app/data/raw/ccld/transparencyapi-operator/<snapshot-id>/manifest.json
```

```sh
sudo docker compose -f docker-compose.qnap.yml exec -T app python -m ccld_complaints.cli.transparencyapi_snapshot_lifecycle validate <snapshot-id>
```

```sh
sudo docker compose -f docker-compose.qnap.yml exec -T app python -m ccld_complaints.cli.transparencyapi_snapshot_lifecycle accept <snapshot-id>
```

For the first promotion, explicitly prove both pointers are absent:

```sh
sudo docker compose -f docker-compose.qnap.yml exec -T app python -m ccld_complaints.cli.transparencyapi_snapshot_lifecycle promote <snapshot-id> --expected-active none --expected-prior none
```

For a later promotion, copy the exact active and prior identities from the immediately
preceding `status` result:

```sh
sudo docker compose -f docker-compose.qnap.yml exec -T app python -m ccld_complaints.cli.transparencyapi_snapshot_lifecycle promote <snapshot-id> --expected-active <active-snapshot-id> --expected-prior <prior-snapshot-id-or-none>
```

Rollback swaps the active and prior accepted pointers without deleting history. Use the
exact immediately preceding values; then run `status` again:

```sh
sudo docker compose -f docker-compose.qnap.yml exec -T app python -m ccld_complaints.cli.transparencyapi_snapshot_lifecycle rollback --expected-active <active-snapshot-id> --expected-prior <prior-snapshot-id>
```

Re-promotion is the ordinary guarded `promote` command with the post-rollback active and
prior values. The CLI performs no source retrieval, scheduling, canonical backfill,
reviewer-state mutation, snapshot deletion, deployment, or Cloudflare operation.

## Operator command standards

- QNAP commands must be BusyBox-compatible unless a required utility was explicitly verified.
- Use one complete copy/pasteable one-line command per numbered operator step.
- Commands must fail nonzero on verification failure.
- Print PASS only after the operation and its verification succeed.
- Keep Windows PowerShell commands separate from standalone QNAP SSH commands.

## Maintenance

Update this runbook whenever a deployment reveals a new prerequisite, storage path, Compose behavior, rollback requirement, or verification requirement. Record the reason and supporting evidence in the pull request.
