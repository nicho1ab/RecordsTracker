# Runbook

## First setup

```powershell
.\setup-project.ps1 -ProjectPath "<local-project-path>" -InitializeGit
```

## Run tests

```powershell
.\scripts\test.ps1
```

## Run linting

```powershell
.\scripts\lint.ps1
```

## Run documentation check

```powershell
.\scripts\docs.ps1
```

## Run sample ingestion

```powershell
.\scripts\run-ccld-sample.ps1
```

## Browse with Datasette

```powershell
.\.venv\Scripts\datasette.exe data\processed\ccld.sqlite
```

Then open the local URL shown in PowerShell.

## Add a fixture

1. Save raw source content under `tests/fixtures/<source>/raw/`.
2. Add expected output under `tests/fixtures/<source>/expected/`.
3. Run tests.
4. Commit raw fixture and expected JSON together.

## Recover from failed extraction

1. Check `data/raw/` for the source file.
2. Check logs under `data/logs/`.
3. Run the extractor against the raw file only.
4. Add or update a fixture reproducing the failure.
5. Fix extraction logic.
6. Run full regression tests.
