# Testing

## Run all tests

```powershell
.\scripts\test.ps1
```

## Run linting and type checks

```powershell
.\scripts\lint.ps1
```

## Test the review bundle exporter

The export bundle workflow is covered by integration tests. To manually check it after sample ingestion:

```powershell
.\scripts\run-ccld-sample.ps1
```

```powershell
.\scripts\export-review-bundle.ps1
```

Confirm the generated CSV files keep clear headers and source traceability columns, and that the generated README describes delay flags, timeline rows, facility pattern counts, multi-facility traceability rows, and facility comparison rows as screening aids.

The integration tests also build a small fixture-backed multi-facility corpus with `populate_multi_facility_sample_database`. That corpus uses tracked fixtures only and exercises facility identifier intake diagnostics, controlled fetch summary output, multi-facility source traceability, facility comparison, and review-bundle exports without live public requests. Keep it small and deterministic; do not treat fixture counts as public-source completeness or facility conclusions.

## Test design

Prefer fixture-based tests over ad hoc manual verification. Every important source report should have:

- Raw fixture
- Expected JSON
- Parser test
- Data quality test

Data quality tests should include source traceability checks for derived records.
At minimum, complaints, allegations, events, and extraction audit rows should
trace back to a source document with source URL, raw SHA-256 hash, connector
metadata, and retrieval timestamp.

## Regression rule

When fixing extraction behavior, add the failing case as a fixture before changing parser code.

## CI failure rule

When fixing a CI failure, identify the exact failing workflow command and run it locally when it does not require secrets or live external requests. If local and CI results differ, check cross-platform behavior such as line endings, path separators, locale-sensitive output, and Git-normalized fixture bytes.

Every bug or CI-failure fix must include a root-cause governance review. If a missing or unclear rule contributed to the failure, update the relevant governance, testing, fixture, connector, or workflow documentation in the same change. If no governance rule is needed, state why in the PR or handoff.

## Fixture hash rule

Raw fixtures with expected SHA-256 hashes must use the line endings required by `.gitattributes`. Compute expected hashes from Git-normalized bytes, not from platform-specific working-tree bytes.

Use this check when changing raw fixtures:

```powershell
git ls-files --eol tests\fixtures\ccld\raw\<fixture-name>.html
```
