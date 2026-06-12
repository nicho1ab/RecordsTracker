# Runbook

## Validate changes

Run the full local validation set before completing a task:

```powershell
.\scripts\lint.ps1
.\scripts\test.ps1
.\scripts\docs.ps1
```

## Run fixture-backed sample ingestion

Use committed fixtures to populate the local sample database without making live
web requests:

```powershell
.\scripts\run-ccld-sample.ps1
```

The script prints the SQLite database path, generated Datasette metadata path,
and the Datasette command to open.

## Run controlled live fetch

Live fetch is explicitly user-invoked and must be scoped to provided facility
numbers. Use conservative limits while testing:

```powershell
.\scripts\run-ccld-live-fetch.ps1 -FacilityNumber 157806098 -Limit 5 -MaxRequests 10
```

## Run multi-facility live fetch

Provide multiple explicit facility numbers when you need a multi-facility local
review database:

```powershell
.\scripts\run-ccld-live-fetch.ps1 -FacilityNumber 157806098,157806097 -Limit 5 -MaxRequests 20
```

This workflow does not perform statewide crawling or automatic search expansion.

## Browse with Datasette

Prefer the Datasette command printed by the sample or live fetch script because
it includes the generated metadata file.

Manual command:

```powershell
.\.venv\Scripts\datasette.exe data\processed\ccld.sqlite --metadata data\processed\ccld.datasette-metadata.json
```

Open the local URL shown in PowerShell and start with these views:

1. `complaint_review_summary`
2. `facility_complaint_summary`
3. `delay_review_flags`
4. `source_traceability_review`

## Export review bundle

After populating the database, export standard source-traceable CSV review outputs:

```powershell
.\scripts\export-review-bundle.ps1
```

For a custom database or output folder:

```powershell
.\scripts\export-review-bundle.ps1 -DbPath data\processed\live-ccld.sqlite -OutputDir data\processed\live-review-bundle
```

The bundle includes complaint review, delay triage, and source traceability CSVs plus a README with caution language. Delay review flags are screening aids only; verify important details against source documents.

## Add a fixture

1. Save raw source content under `tests/fixtures/<source>/raw/`.
2. Add expected output under `tests/fixtures/<source>/expected/`.
3. Verify the raw fixture uses the line endings required by `.gitattributes`.
4. If expected output includes `raw_sha256`, compute it from the Git-normalized
	fixture bytes that CI will read, not from a platform-specific working-tree
	copy.
5. Run tests.
6. Commit raw fixture and expected JSON together.

## Recover from failed extraction

1. Check `data/raw/` for the source file.
2. Check logs under `data/logs/`.
3. Run the extractor against the raw file only.
4. Add or update a fixture reproducing the failure.
5. Fix the smallest amount of extraction logic needed.
6. Review the root cause for a missing or unclear governance rule. Add or update
	governance, testing, fixture, connector, or workflow documentation when a new
	rule would prevent recurrence.
7. Run full regression tests and documentation checks.

## Recover from a CI failure

1. Identify the exact workflow step and command that failed.
2. Run the same command locally when it does not require secrets or live external
	requests.
3. If local results differ from CI, check cross-platform behavior such as line
	endings, path separators, locale-sensitive output, and Git-normalized fixture
	bytes.
4. If the failure involved expected raw hashes, verify fixture line endings with:

```powershell
git ls-files --eol tests\fixtures\ccld\raw\<fixture-name>.html
```

5. Fix the smallest root cause, rerun the exact failing command, then run the
	standard validation set.
6. Add or update a governance rule if the root cause exposed a missing rule.

## PR and merge cleanup

Before opening a PR, include the validation results, a concise PR title, and a PR
body that states whether user-facing or documentation-impacting behavior changed.

After the PR merges, clean up the local branch:

```powershell
git switch main
git pull --ff-only
git branch --delete <merged-branch-name>
git remote prune origin
```

Start follow-up work from an updated `main` branch:

```powershell
git switch main
git pull --ff-only
git switch -c <next-branch-name>
```
