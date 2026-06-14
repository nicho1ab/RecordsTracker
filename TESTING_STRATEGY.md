# Testing Strategy

## Test categories

### Unit tests

Validate small deterministic functions such as date parsing, URL parsing, hash generation, and field extraction.

### Fixture-based extraction tests

Validate complete extraction from known raw source files into expected JSON.

### Regression tests

Every extraction bug fix must add a failing fixture or test before the fix is accepted.

Every bug fix, CI failure fix, or repeated review correction must include a root-cause review. If the root cause reveals a missing, unclear, or too-weak project rule, add or update the relevant governance, testing, fixture, connector, or workflow documentation in the same change. If no governance change is needed, state why in the PR or handoff.

### Contract tests

Validate connector output against JSON schemas and the source connector contract.

### Data quality tests

Validate internal consistency, including required fields, valid date order, allowed finding values, duplicate source URLs, and hash presence.

### Documentation tests

Validate that required documentation files exist and that data dictionary/schema updates are present when schema files change.

Production-discovery requirements changes must run documentation validation and
affected documentation-check tests. Hosted tester MVP implementation must add
validation for review-state separation, annotation and correction traceability,
source-traceable export packet behavior, accessibility expectations,
authentication and access governance, audit event attribution and no-secret
metadata where audit persistence is implemented, feedback collection, and
reset/reload behavior at the level of the implemented change. Reset/reload
operational metadata tests must prove any persisted planning record remains
separate, permissioned, non-secret, and non-executing. Reset/reload planning
metadata read route tests must prove authorized readback remains scoped,
non-secret, and non-mutating.
Reviewer-created state read route tests must prove authorized readback remains
scoped, non-secret, separated from source-derived reads, and non-mutating across
source-derived rows, reviewer-created rows, audit rows, and operational metadata.
Reviewer workflow shell state-read integration tests must prove selected detail
payloads compose associated reviewer-created state read route output only
through authenticated, role/scope-allowed local/test contexts and remain
non-secret and non-mutating across source-derived rows, reviewer-created rows,
audit rows, and operational metadata.

### Fixture hash and line-ending tests

Raw fixtures with expected SHA-256 hashes must use the line endings required by `.gitattributes`. Expected fixture hashes must match Git-normalized bytes, not platform-specific working-tree bytes. When adding or changing raw fixtures that appear in expected JSON, verify line endings and hashes before committing.

### Public-source planning fixtures

Tiny public-source planning fixtures may be committed only when they are small,
documented, safe to publish, and clearly separated from ignored raw source files
and generated profiling outputs. Tests for those fixtures should verify that the
files are present, tiny, traceability-shaped, synthetic or minimized, and not
usable as full raw-source dumps or production imports.

### Accessibility tests

Validate documentation structure and run manual or automated checks for user-facing pages before release.

## Minimum pull request requirements

- Existing tests pass.
- New or changed extraction behavior includes fixture tests.
- Bug fixes include regression tests.
- Bug and CI-failure fixes include a root-cause governance review and update the relevant governance rule when a missing rule contributed to the failure.
- Data contract changes include schema and documentation updates.
- User-visible behavior changes include user documentation updates.
- Implementation work uses focused validation first, then standard PR validation before opening a PR.
- PR bodies include focused validation, why those focused checks matched the change, full local validation results, required remote check results, and any tests intentionally not run with the reason.

## Validation tiers

### Focused validation

Run the smallest relevant tests for the changed area before broader validation.
Focused validation should catch likely failures quickly and should be explained in
the PR body or task handoff.

Use focused validation such as:

- Extraction changes: targeted extractor tests and related fixture regression tests.
- Connector changes: targeted connector discovery, fetch, and raw storage tests using fixtures or mocks.
- Data contract or schema changes: schema validation, init or migration SQL tests, persistence tests, and affected data dictionary checks.
- Datasette, view, or export changes: affected SQL, view, export, metadata, and documentation checks.
- Documentation-only changes: documentation validation and link or reference checks.
- Production-discovery requirements changes: documentation validation and affected documentation-check tests.
- Security or privacy changes: security checks and any affected tests.
- Accessibility-facing changes: documentation, export, view, or presentation accessibility checks.

### Standard PR validation

Run standard PR validation before every PR unless the change is analysis-only and
no files were edited:

```powershell
.\scripts\lint.ps1
```

```powershell
.\scripts\test.ps1
```

```powershell
.\scripts\docs.ps1
```

```powershell
git diff --check
```

### Required remote validation

Before merge, verify the required GitHub status-check contexts pass:

- `validate`
- `docs-check`
- `fixtures`
- `security`

### Full release validation

Run or verify the full test suite before any release, production-readiness
milestone, schema change, connector expansion, export-contract change, or
production architecture transition.

## Commands

```powershell
.\scripts\lint.ps1
.\scripts\test.ps1
.\scripts\docs.ps1
git diff --check
```

For CI failures, also run the exact failing workflow command locally when it can
be run without secrets or live external requests. If local and CI results differ,
check cross-platform behavior such as line endings, path separators, filesystem
glob ordering, locale-sensitive output, and Git-normalized fixture bytes. For
fixture hash failures, verify Git-normalized bytes with commands such as:

```powershell
git ls-files --eol tests\fixtures\ccld\raw\<fixture-name>.html
```

```powershell
git show HEAD:tests/fixtures/ccld/raw/<fixture-name>.html
```
