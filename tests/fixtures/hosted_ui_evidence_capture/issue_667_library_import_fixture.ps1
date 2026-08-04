param(
    [Parameter(Mandatory)]
    [string]$CaptureScript,

    [Parameter(Mandatory)]
    [string]$ResultPath
)

$ErrorActionPreference = "Stop"
$resultDirectory = Split-Path -Parent $ResultPath
$environmentNames = @(
    "CCLD_HOSTED_PAGE_DATA_MODE",
    "CCLD_HOSTED_TESTER_AUTH_MODE",
    "CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH"
)
$beforeEnvironment = @{}
foreach ($name in $environmentNames) {
    $beforeEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
}
$beforeLocation = (Get-Location).Path
$beforeArtifacts = @(Get-ChildItem -LiteralPath $resultDirectory -Force)

. $CaptureScript -LibraryOnly

$afterImportStatement = "continued"
$afterEnvironment = @{}
foreach ($name in $environmentNames) {
    $afterEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
}
$afterArtifacts = @(Get-ChildItem -LiteralPath $resultDirectory -Force | Where-Object { $_.FullName -ne (Get-Item -LiteralPath $ResultPath -ErrorAction SilentlyContinue).FullName })

[ordered]@{
    ContinuedAfterImport = $afterImportStatement -eq "continued"
    CurrentDirectoryUnchanged = (Get-Location).Path -eq $beforeLocation
    EnvironmentUnchanged = ($beforeEnvironment | ConvertTo-Json -Compress) -eq ($afterEnvironment | ConvertTo-Json -Compress)
    NoArtifactsCreated = $beforeArtifacts.Count -eq $afterArtifacts.Count
    Functions = @(
        "Start-InteractionAwareBrowserSession",
        "Stop-InteractionAwareBrowserSession",
        "Wait-TaskOwnedCdpReadiness",
        "Get-TaskOwnedCdpReadiness",
        "Invoke-TaskOwnedBrowserCleanup"
    ) | ForEach-Object { Test-Path -LiteralPath ("Function:{0}" -f $_) }
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ResultPath -Encoding UTF8
