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

Confirm the generated CSV files keep clear headers and source traceability columns, and that the generated README describes delay flags as screening aids.

## Test design

Prefer fixture-based tests over ad hoc manual verification. Every important source report should have:

- Raw fixture
- Expected JSON
- Parser test
- Data quality test

## Regression rule

When fixing extraction behavior, add the failing case as a fixture before changing parser code.
