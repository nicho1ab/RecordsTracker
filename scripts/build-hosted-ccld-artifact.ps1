<#
.SYNOPSIS
Builds a local/test CCLD hosted seeded-corpus JSON artifact.
.DESCRIPTION
Converts validated CCLD SQLite pipeline output into hosted seeded-corpus JSON that the local/test /ccld/records/request page can load through the existing validated import/reload path. This script does not run live public web requests or browser-triggered connector execution.
.PARAMETER DbPath
Validated CCLD SQLite pipeline output path.
.PARAMETER OutputPath
Hosted seeded-corpus JSON artifact path to write.
.PARAMETER FacilityNumber
CCLD facility/license number. Required when SQLite contains multiple facilities.
.PARAMETER StartDate
Optional inclusive YYYY-MM-DD start date filter.
.PARAMETER EndDate
Optional inclusive YYYY-MM-DD end date filter.
.PARAMETER ImportBatchId
Hosted seeded corpus import batch ID. Defaults to the local/test reviewer scope used by /ccld/records/request.
.PARAMETER ImportedAt
Optional ISO datetime for deterministic local/test artifact generation.
.PARAMETER SourceArtifactIdentity
Optional non-secret artifact identity. Defaults to a SQLite file hash identity.
.PARAMETER Overwrite
Replace the output artifact if it already exists.
.EXAMPLE
.\scripts\build-hosted-ccld-artifact.ps1 -DbPath data\processed\ccld.sqlite -FacilityNumber 157806098 -Overwrite
.NOTES
Run from the repository root after validating the CCLD SQLite output.
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$DbPath,
    [string]$OutputPath = "data\processed\hosted_seeded_corpus\validated_ccld_seeded_corpus.json",
    [string]$FacilityNumber,
    [string]$StartDate,
    [string]$EndDate,
    [string]$ImportBatchId = "seeded-ccld-fixture-2026-06-13",
    [string]$ImportedAt,
    [string]$SourceArtifactIdentity,
    [switch]$Overwrite
)

$ErrorActionPreference = "Stop"
$python = Join-Path $PWD ".venv\Scripts\python.exe"
$srcPath = Join-Path $PWD "src"
$previousPythonPath = $env:PYTHONPATH

try {
    if ([string]::IsNullOrWhiteSpace($previousPythonPath)) {
        $env:PYTHONPATH = $srcPath
    }
    else {
        $env:PYTHONPATH = "$srcPath;$previousPythonPath"
    }

    $arguments = @(
        "-m",
        "ccld_complaints.cli.build_hosted_ccld_artifact",
        "--db-path",
        $DbPath,
        "--output-path",
        $OutputPath,
        "--import-batch-id",
        $ImportBatchId
    )

    if (-not [string]::IsNullOrWhiteSpace($FacilityNumber)) {
        $arguments += @("--facility-number", $FacilityNumber)
    }
    if (-not [string]::IsNullOrWhiteSpace($StartDate)) {
        $arguments += @("--start-date", $StartDate)
    }
    if (-not [string]::IsNullOrWhiteSpace($EndDate)) {
        $arguments += @("--end-date", $EndDate)
    }
    if (-not [string]::IsNullOrWhiteSpace($ImportedAt)) {
        $arguments += @("--imported-at", $ImportedAt)
    }
    if (-not [string]::IsNullOrWhiteSpace($SourceArtifactIdentity)) {
        $arguments += @("--source-artifact-identity", $SourceArtifactIdentity)
    }
    if ($Overwrite) {
        $arguments += "--overwrite"
    }

    if (Test-Path $python) {
        & $python @arguments
    }
    else {
        python @arguments
    }
}
finally {
    $env:PYTHONPATH = $previousPythonPath
}