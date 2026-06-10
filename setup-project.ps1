<#
.SYNOPSIS
Scaffolds the CCLD complaints proof-of-concept project.
.DESCRIPTION
Copies the governance pack into a target project folder, creates a Python virtual environment, installs dependencies, creates local data folders, initializes SQLite, optionally initializes Git, and runs initial validation checks.
.PARAMETER ProjectPath
The folder where the project should be created or updated.
.PARAMETER InitializeGit
Initializes a local Git repository if one does not already exist.
.PARAMETER SkipInstall
Skips Python virtual environment creation and dependency installation.
.PARAMETER Force
Allows setup to continue when the target folder already contains files.
.EXAMPLE
.\setup-project.ps1 -ProjectPath "C:\Users\andre\Desktop\ccld-complaints-poc" -InitializeGit
.EXAMPLE
.\setup-project.ps1 -ProjectPath "C:\Users\andre\Desktop\ccld-complaints-poc" -InitializeGit -SkipInstall
.NOTES
Run this from the extracted governance pack folder. It is designed for Windows PowerShell and VS Code local development.
#>
param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectPath,

    [switch]$InitializeGit,

    [switch]$SkipInstall,

    [switch]$Force
)

$ErrorActionPreference = "Stop"

$sourceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$targetRoot = $ProjectPath

Write-Host "Source governance pack: $sourceRoot"
Write-Host "Target project path: $targetRoot"

if ((Test-Path $targetRoot) -and -not $Force) {
    $existing = Get-ChildItem -Path $targetRoot -Force -ErrorAction SilentlyContinue
    if ($existing.Count -gt 0) {
        throw "Target folder already contains files. Re-run with -Force or choose an empty folder."
    }
}

New-Item -ItemType Directory -Path $targetRoot -Force | Out-Null

$exclude = @(".venv", ".git", "data\raw", "data\processed", "data\logs")
robocopy $sourceRoot $targetRoot /E /XD "$sourceRoot\.venv" "$sourceRoot\.git" /XF "CCLD-Governance-Pack.zip" | Out-Null
if ($LASTEXITCODE -gt 7) {
    throw "robocopy failed with exit code $LASTEXITCODE"
}

Set-Location $targetRoot

New-Item -ItemType Directory -Path "data\raw" -Force | Out-Null
New-Item -ItemType Directory -Path "data\processed" -Force | Out-Null
New-Item -ItemType Directory -Path "data\logs" -Force | Out-Null
New-Item -ItemType File -Path "data\raw\.gitkeep" -Force | Out-Null
New-Item -ItemType File -Path "data\processed\.gitkeep" -Force | Out-Null
New-Item -ItemType File -Path "data\logs\.gitkeep" -Force | Out-Null

if (-not $SkipInstall) {
    Write-Host "Creating Python virtual environment..."
    python -m venv .venv
    $python = Join-Path $targetRoot ".venv\Scripts\python.exe"
    & $python -m pip install --upgrade pip
    & $python -m pip install -r requirements-dev.txt
    & $python -m ccld_complaints.cli.init_db
} else {
    Write-Host "Skipping Python install."
}

if ($InitializeGit) {
    if (-not (Test-Path ".git")) {
        git init
        git add .
        git commit -m "Initial governed project scaffold"
    } else {
        Write-Host "Git repository already exists."
    }
}

if (-not $SkipInstall) {
    Write-Host "Running validation..."
    .\scripts\lint.ps1
    .\scripts\test.ps1
    .\scripts\docs.ps1
}

Write-Host "Setup complete."
Write-Host "Open the project with: code `"$targetRoot`""
Write-Host "SQLite database path: $targetRoot\data\processed\ccld.sqlite"
