# Hosted Corpus Verification and Evidence Packaging

This repository-owned post-deployment workflow provides the acceptance evidence
for Issue #419. It replaces ad hoc SQL, inline container Python, and unverified
paths. It is read-only: it does not retrieve sources, deploy, recreate
containers, mutate production data, or mutate reviewer-created state.

The supported command is `python -m ccld_complaints.cli.verify_hosted_corpus`.
It is shipped in the image through `COPY src ./src` and emits
`recordstracker.hosted-corpus-verification.v1`, validated by
`schemas/hosted-corpus-verification-v1.schema.json`.

## Audit contract

The audit uses the existing PostgreSQL configuration and the existing Compare
Facilities read model (`list_facility_intelligence_page`) for its facility count.
It reports page-data and retrieval/demo modes; persisted, unique, and displayed
counts; duplicate and repeated identities; source-document links; synthetic and
fallback markers; corpus size; deterministic representatives; source URL, hash,
retrieval, connector, and import metadata; and reviewer-state separation.

`blocking_failures` produces a nonzero command status. Missing
operator-captured displayed counts are warnings rather than invented values. The
result never contains database URLs, credentials, cookies, tokens, private
headers, raw paths, or personal local paths.

## QNAP operator boundary

Use a standalone SSH session with the exact operator-supplied
`<operator-username>@<qnap-host>` value. This placeholder must not be replaced
in committed documentation. Run one line at a time. Each line prints PASS or
FAIL and returns a nonzero status on failure; do not use `set -e`, `set -u`,
`exit`, heredocs, aliases, Bash-only syntax, or host `/tmp`.

The stable remote evidence location is
`/share/Public/RecordsTracker-staging/issue-419/`. Preflight space and the
destination. Inspect the app container only; do not recreate it or deploy it.

```sh
ssh <operator-username>@<qnap-host>
df -k /share/Public/RecordsTracker-staging/issue-419/ && echo PASS || echo FAIL
test -d /share/Public/RecordsTracker-staging/issue-419/ && echo PASS || echo FAIL
sudo docker compose exec -T app python -m ccld_complaints.cli.verify_hosted_corpus --deployed-sha <deployed-sha> --output /app/data/processed/issue-419/hosted-corpus-verification.json; status=$?; test $status -eq 0 && echo PASS || echo FAIL
sudo docker compose cp app:/app/data/processed/issue-419/hosted-corpus-verification.json /share/Public/RecordsTracker-staging/issue-419/hosted-corpus-verification.json && echo PASS || echo FAIL
test -s /share/Public/RecordsTracker-staging/issue-419/hosted-corpus-verification.json && echo PASS || echo FAIL
python -m json.tool /share/Public/RecordsTracker-staging/issue-419/hosted-corpus-verification.json >/dev/null && echo PASS || echo FAIL
sha256sum /share/Public/RecordsTracker-staging/issue-419/hosted-corpus-verification.json && echo PASS || echo FAIL
```

Before SCP, verify the file exists, is nonempty, parses as JSON, passes the
portable-content scan, and has the recorded SHA-256. The repository-owned copy
step explicitly transfers the result from the running app container to the
stable staging location; do not assume a mount or use host `/tmp`. A blocking
result is failure evidence and not acceptance.

## Windows finalization

Transfer to an actual user-accessible destination. The finalizer rejects
placeholders, nonexistent paths, directories, empty files, malformed ZIPs, and
internal `.codex/visualizations` references. Verify a transferred file is a
leaf, nonempty, valid JSON, and matches the remote SHA-256.

`scripts/finalize_hosted_corpus_evidence.py` preserves the historical package
byte-for-byte, creates a distinct timestamped ZIP, adds the current audit and
manifest inventory, and reports one of `created`, `updated`, `copied unchanged`,
or `reused unchanged`. Its report includes source path when applicable,
delivered path, timestamp, size, SHA-256, action, and whether content materially
changed. A copied or reused file is not newly generated.

```powershell
Test-Path -LiteralPath <User-Accessible-Output-Path> -PathType Leaf
Get-Content -Raw -LiteralPath <User-Accessible-Output-Path> | ConvertFrom-Json | Out-Null
python scripts/finalize_hosted_corpus_evidence.py --audit-json <User-Accessible-Output-Path> --historical-package <Historical-Package-Path> --output-directory <User-Accessible-Package-Directory>
```

The final ZIP must enumerate `current/<audit filename>` and `manifest.json`.
When new evidence is added its hash must differ from the historical package. Do
not overwrite the historical ZIP.

## Boundary and ownership

This workflow supplies corpus-gate evidence only. It does not establish
stakeholder acceptance, source completeness, deployment completion, or closure
of Issue #419. General interactive-shell safeguards remain independently owned
by Issue #635.
