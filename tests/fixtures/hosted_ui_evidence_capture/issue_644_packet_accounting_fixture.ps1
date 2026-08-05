param(
    [Parameter(Mandatory)]
    [string]$TempRoot,

    [Parameter(Mandatory)]
    [string]$CaptureScriptPath
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $CaptureScriptPath -PathType Leaf)) {
    throw "Capture script is missing: $CaptureScriptPath"
}

. $CaptureScriptPath -LibraryOnly

function Write-FixtureContent {
    param([string]$Path, [string]$Value)

    $parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    Set-Content -LiteralPath $Path -Value $Value -Encoding UTF8 -NoNewline
}

function New-FixturePacket {
    param(
        [string]$Name,
        [int]$ManifestFinalCountOffset = 0,
        [switch]$OmitSupplementalArtifact,
        [switch]$UseUnexpectedIndexExclusion
    )

    $packetDirectory = Join-Path $TempRoot $Name
    $zipPath = Join-Path $TempRoot "$Name.zip"
    New-Item -ItemType Directory -Path $packetDirectory -Force | Out-Null

    Write-FixtureContent -Path (Join-Path $packetDirectory 'route-status.csv') -Value 'route,status'
    Write-FixtureContent -Path (Join-Path $packetDirectory 'route-assertions.csv') -Value 'route,assertion,status'
    Write-FixtureContent -Path (Join-Path $packetDirectory 'route-text-markers.txt') -Value 'fixture marker'
    Write-FixtureContent -Path (Join-Path $packetDirectory 'README.txt') -Value 'fixture evidence packet'
    Write-FixtureContent -Path (Join-Path $packetDirectory 'reviews/independent-visual-review.json') -Value '{"decision":"PENDING"}'
    Write-FixtureContent -Path (Join-Path $packetDirectory 'reviews/owner-acceptance.json') -Value '{"decision":"PENDING"}'
    $png = [Convert]::FromBase64String('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL4WQAAAABJRU5ErkJggg==')
    New-Item -ItemType Directory -Path (Join-Path $packetDirectory 'screenshots') -Force | Out-Null
    [System.IO.File]::WriteAllBytes((Join-Path $packetDirectory 'screenshots/normal.png'), $png)
    if (-not $OmitSupplementalArtifact) {
        [System.IO.File]::WriteAllBytes((Join-Path $packetDirectory 'screenshots/supplemental.png'), $png)
    }

    $manifest = [ordered]@{
        routes = @(
            [ordered]@{
                name = 'fixture-route'
                screenshotPath = 'screenshots/normal.png'
                supplementalScreenshotPath = 'screenshots/supplemental.png'
            }
        )
    }
    Set-Content -LiteralPath (Join-Path $packetDirectory 'manifest.json') -Value ($manifest | ConvertTo-Json -Depth 5) -Encoding UTF8
    $accounting = New-EvidencePacketAccounting -PacketDirectory $packetDirectory
    $manifest.packetAccounting = $accounting
    Set-Content -LiteralPath (Join-Path $packetDirectory 'manifest.json') -Value ($manifest | ConvertTo-Json -Depth 5) -Encoding UTF8

    $sourceFiles = @(Test-EvidencePacketFiles -PacketDirectory $packetDirectory)
    $fileIndex = New-EvidenceFileIndex -SourceFiles $sourceFiles -Accounting $accounting
    if ($UseUnexpectedIndexExclusion) {
        $fileIndex.indexSelfExclusion = [ordered]@{ path = 'README.txt'; reason = 'fixture corruption' }
    }
    Set-Content -LiteralPath (Join-Path $packetDirectory 'file-index.json') -Value ($fileIndex | ConvertTo-Json -Depth 5) -Encoding UTF8
    if ($ManifestFinalCountOffset -ne 0) {
        $accounting.finalArtifactCount = [int]$accounting.finalArtifactCount + $ManifestFinalCountOffset
        $manifest.packetAccounting = $accounting
        Set-Content -LiteralPath (Join-Path $packetDirectory 'manifest.json') -Value ($manifest | ConvertTo-Json -Depth 5) -Encoding UTF8
    }
    Compress-Archive -LiteralPath $packetDirectory -DestinationPath $zipPath -Force

    return [ordered]@{ packetDirectory = $packetDirectory; zipPath = $zipPath; accounting = $accounting }
}

function Get-FailureMessage {
    param([scriptblock]$Action)

    try {
        & $Action
        return 'not rejected'
    }
    catch {
        return $_.Exception.Message
    }
}

$valid = New-FixturePacket -Name 'valid'
$validResult = Test-EvidencePacketAccounting -PacketDirectory $valid.packetDirectory -ZipPath $valid.zipPath -ReportedFinalArtifactCount ([int]$valid.accounting.finalArtifactCount)

$incorrectManifest = New-FixturePacket -Name 'incorrect-manifest' -ManifestFinalCountOffset 1
$incorrectManifestFailure = Get-FailureMessage { Test-EvidencePacketAccounting -PacketDirectory $incorrectManifest.packetDirectory -ZipPath $incorrectManifest.zipPath -ReportedFinalArtifactCount ([int]$incorrectManifest.accounting.finalArtifactCount) }

$incorrectReported = New-FixturePacket -Name 'incorrect-reported'
$incorrectReportedFailure = Get-FailureMessage { Test-EvidencePacketAccounting -PacketDirectory $incorrectReported.packetDirectory -ZipPath $incorrectReported.zipPath -ReportedFinalArtifactCount ([int]$incorrectReported.accounting.finalArtifactCount + 1) }

$omittedSupplementalFailure = Get-FailureMessage { New-FixturePacket -Name 'omitted-supplemental' -OmitSupplementalArtifact }

$unexpectedExclusion = New-FixturePacket -Name 'unexpected-exclusion' -UseUnexpectedIndexExclusion
$unexpectedExclusionFailure = Get-FailureMessage { Test-EvidencePacketAccounting -PacketDirectory $unexpectedExclusion.packetDirectory -ZipPath $unexpectedExclusion.zipPath -ReportedFinalArtifactCount ([int]$unexpectedExclusion.accounting.finalArtifactCount) }

$duplicatePathFailure = Get-FailureMessage {
    Assert-UniqueEvidencePaths -Files @(
        [pscustomobject]@{ path = 'screenshots/duplicate.png' },
        [pscustomobject]@{ path = 'screenshots/duplicate.png' }
    ) -Context 'Fixture duplicate inventory'
}

[ordered]@{
    valid = $validResult
    incorrectManifestFailure = $incorrectManifestFailure
    incorrectReportedFailure = $incorrectReportedFailure
    omittedSupplementalFailure = $omittedSupplementalFailure
    unexpectedExclusionFailure = $unexpectedExclusionFailure
    duplicatePathFailure = $duplicatePathFailure
} | ConvertTo-Json -Depth 8
