# Testing

## Run all tests

```powershell
.\scripts\test.ps1
```

## Run linting and type checks

```powershell
.\scripts\lint.ps1
```

## Test design

Prefer fixture-based tests over ad hoc manual verification. Every important source report should have:

- Raw fixture
- Expected JSON
- Parser test
- Data quality test

## Regression rule

When fixing extraction behavior, add the failing case as a fixture before changing parser code.
