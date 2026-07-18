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
- Preserve the active `.env` and `docker-compose.qnap.yml`.
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
9. Copy only `.env` and `docker-compose.qnap.yml` into the new release.
10. Do not copy the old `.deployed-commit` into the new release.
11. Validate the new release with `docker compose config` before activation.
12. Stop only the `app` service; leave PostgreSQL running.
13. Rename the active directory to a timestamped previous-release directory.
14. Rename the validated versioned release directory to `/share/Public/RecordsTracker`.
15. Rebuild and recreate only the `app` service with `--no-deps`.
16. Verify the app is running, healthy, and has zero restarts after recreation.
17. Verify PostgreSQL remains running and healthy; report its restart count without assuming it began at zero.
18. Verify Alembic current is at head, logs contain no deployment-blocking errors, the health route returns 200, and required routes return no 5xx responses.
19. Write the new full commit to `.deployed-commit` only after all verification succeeds.
20. Retain the prior release directory and backups until hosted acceptance and stakeholder confirmation are complete.

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

Rollback restores the preserved previous application directory only:

1. Stop the `app` service.
2. Rename the failed active directory to a timestamped failed-release path.
3. Rename the preserved previous-release directory back to `/share/Public/RecordsTracker`.
4. Rebuild and recreate only the `app` service with `--no-deps`.
5. Verify app and PostgreSQL health and the health route.
6. Do not restore PostgreSQL unless a separately reviewed database rollback is required.

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

## Operator command standards

- QNAP commands must be BusyBox-compatible unless a required utility was explicitly verified.
- Use one complete copy/pasteable one-line command per numbered operator step.
- Commands must fail nonzero on verification failure.
- Print PASS only after the operation and its verification succeed.
- Keep Windows PowerShell commands separate from standalone QNAP SSH commands.

## Maintenance

Update this runbook whenever a deployment reveals a new prerequisite, storage path, Compose behavior, rollback requirement, or verification requirement. Record the reason and supporting evidence in the pull request.
