param(
    [Parameter(Mandatory)]
    [string]$CaptureScriptPath,

    [Parameter(Mandatory)]
    [string]$EdgePath,

    [Parameter(Mandatory)]
    [string]$DiagnosticDirectory
)

$ErrorActionPreference = "Stop"
$tempRoot = [System.IO.Path]::GetFullPath("C:\Temp")
$resolvedDiagnosticDirectory = [System.IO.Path]::GetFullPath($DiagnosticDirectory)
if (-not $resolvedDiagnosticDirectory.StartsWith(($tempRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar), [System.StringComparison]::OrdinalIgnoreCase) -or (Split-Path $resolvedDiagnosticDirectory -Leaf) -notlike "RecordsTracker-issue-667-real-edge-*") {
    throw "DiagnosticDirectory must be a timestamped Issue #667 directory under the system temp root."
}
New-Item -ItemType Directory -Path $resolvedDiagnosticDirectory -Force | Out-Null
$resultPath = Join-Path $resolvedDiagnosticDirectory "result.json"
$metadataPath = Join-Path $resolvedDiagnosticDirectory "invocation.json"
$screenshotPath = Join-Path $resolvedDiagnosticDirectory "validation.png"
$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

[ordered]@{
    harness = Split-Path $PSCommandPath -Leaf
    captureScript = Split-Path $CaptureScriptPath -Leaf
    edgePath = $EdgePath
} | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $metadataPath -Encoding UTF8

$result = [ordered]@{
    success = $false
    failureClass = ""
    edgePath = $EdgePath
    edgeFileVersion = ""
    candidateAccepted = $false
    candidateStatus = ""
    screenshotCreated = $false
    screenshotBytes = 0
    screenshotWidth = 0
    screenshotHeight = 0
    sessionCreated = $false
    rootProcessId = 0
    rootExitedBeforeReadiness = $false
    taskOwnedProcessIds = @()
    taskOwnedProcessIdentities = @()
    devToolsActivePortExists = $false
    devToolsActivePortNonEmpty = $false
    parsedPort = 0
    browserIdentifierPresent = $false
    loopbackEndpointReachable = $false
    expectedPageTargetAvailable = $false
    startupElapsedMilliseconds = 0
    governedDeadlineSeconds = 0
    remainingTaskOwnedProcessIds = @()
    remainingTaskOwnedProcessIdentities = @()
    cleanupStopRequestedProcessIdentities = @()
    cleanupProfilePathValidated = $false
    cleanupAttemptCount = 0
    cleanupElapsedMilliseconds = 0
    cleanupInitialDeletionFailed = $false
    cleanupLastDeletionExceptionType = ""
    cleanupLastDeletionExceptionMessage = ""
    cleanupLastDeletionErrorId = ""
    cleanupClassification = ""
    productionCleanupSucceeded = $false
    profileRemoved = $false
    profileAbsentAfterHarness = $false
    screenshotRemoved = $false
}
$session = $null
$profileDir = ""
$taskOwnedProcessIds = @()
$taskOwnedProcessIdentities = @()

try {
    if (-not (Test-Path -LiteralPath $CaptureScriptPath -PathType Leaf)) { throw "Capture script is unavailable." }
    if (-not (Test-Path -LiteralPath $EdgePath -PathType Leaf)) { throw "Edge executable is unavailable." }
    . $CaptureScriptPath -LibraryOnly

    $result.edgeFileVersion = [string](Get-Item -LiteralPath $EdgePath).VersionInfo.FileVersion
    $tool = [pscustomobject]@{ Name = "issue-667-edge"; Kind = "edge"; Command = $EdgePath; FullPage = $false; InteractionAware = $true }
    $candidate = Test-ScreenshotToolCandidate -Candidate $tool
    $result.candidateAccepted = [bool]$candidate.Usable
    $result.candidateStatus = [string]$candidate.Status
    if (-not $candidate.Usable) { throw "Edge candidate was rejected: $($candidate.Status)" }

    $screenshotFailure = Invoke-RouteScreenshot -Tool $tool -Url "about:blank" -ScreenshotPath $screenshotPath -Width 1440 -Height 1200
    if ($screenshotFailure) { throw $screenshotFailure }
    $dimensions = Get-PngDimensions -Path $screenshotPath
    $result.screenshotCreated = Test-Path -LiteralPath $screenshotPath -PathType Leaf
    $result.screenshotBytes = if ($result.screenshotCreated) { [int](Get-Item -LiteralPath $screenshotPath).Length } else { 0 }
    $result.screenshotWidth = [int]$dimensions.width
    $result.screenshotHeight = [int]$dimensions.height
    if (-not $result.screenshotCreated -or $result.screenshotBytes -le 0 -or $result.screenshotWidth -le 0 -or $result.screenshotHeight -le 0) { throw "Required screenshot validation output was unavailable." }

    $session = Start-InteractionAwareBrowserSession -Tool $tool
    $result.sessionCreated = $null -ne $session
    $result.rootProcessId = [int]$session.Process.Id
    $result.rootExitedBeforeReadiness = [bool]$session.Process.HasExited
    $taskOwnedProcessIds = @($session.TaskProcessIds | ForEach-Object { [int]$_ } | Sort-Object -Unique)
    $result.taskOwnedProcessIds = @($taskOwnedProcessIds)
    $taskOwnedProcessIdentities = @($session.TaskProcessIdentities | Sort-Object { [int]$_.ProcessId })
    $result.taskOwnedProcessIdentities = @($taskOwnedProcessIdentities)
    $profileDir = [string]$session.ProfileDir
    $activePortFile = Join-Path $profileDir "DevToolsActivePort"
    $result.devToolsActivePortExists = Test-Path -LiteralPath $activePortFile -PathType Leaf
    $result.devToolsActivePortNonEmpty = $result.devToolsActivePortExists -and (Get-Item -LiteralPath $activePortFile).Length -gt 0
    if (-not $result.devToolsActivePortNonEmpty) { throw "DevToolsActivePort was missing or empty after session readiness." }
    $portLines = @([System.IO.File]::ReadAllText($activePortFile).TrimEnd([char[]]"`r`n") -split "`r?`n")
    $port = 0
    if ($portLines.Count -ne 2 -or -not [int]::TryParse($portLines[0], [ref]$port)) { throw "DevToolsActivePort was malformed after session readiness." }
    $result.parsedPort = $port
    $result.browserIdentifierPresent = $portLines[1] -match '^/devtools/browser/[A-Za-z0-9-]+$'
    $readiness = Get-TaskOwnedCdpReadiness -ActivePortFile $activePortFile -LaunchStartedAt (Get-Item -LiteralPath $profileDir).CreationTimeUtc -Tool $tool
    $result.loopbackEndpointReachable = $readiness.State -eq "ready"
    $result.expectedPageTargetAvailable = $null -ne $readiness.Target -and [bool]$readiness.Target.webSocketDebuggerUrl
    if (-not $result.browserIdentifierPresent -or -not $result.loopbackEndpointReachable -or -not $result.expectedPageTargetAvailable) { throw "Task-owned CDP readiness verification failed." }
}
catch {
    $result.failureClass = $_.Exception.Message.Split(":")[0]
}
finally {
    $result.startupElapsedMilliseconds = [int]$stopwatch.ElapsedMilliseconds
    $result.governedDeadlineSeconds = [Math]::Max(15, [int]$TimeoutSeconds)
    if ($null -ne $session) {
        try { Stop-InteractionAwareBrowserSession -Session $session } catch { if (-not $result.failureClass) { $result.failureClass = $_.Exception.Message.Split(":")[0] } }
    }
    $cleanup = if ($null -ne $session -and $null -ne $session.PSObject.Properties["CleanupResult"]) { $session.CleanupResult } else { $null }
    if ($null -ne $cleanup) {
        $result.cleanupStopRequestedProcessIdentities = @($cleanup.StopRequestedProcessIdentities)
        $result.remainingTaskOwnedProcessIdentities = @($cleanup.RemainingProcessIdentities)
        $result.remainingTaskOwnedProcessIds = @($cleanup.RemainingProcessIdentities | ForEach-Object { [int]$_.ProcessId })
        $result.cleanupProfilePathValidated = [bool]$cleanup.ProfilePathValidated
        $result.cleanupAttemptCount = [int]$cleanup.ProfileRemovalAttemptCount
        $result.cleanupElapsedMilliseconds = [int]$cleanup.ProfileRemovalElapsedMilliseconds
        $result.cleanupInitialDeletionFailed = [bool]$cleanup.InitialProfileRemovalFailed
        $result.cleanupLastDeletionExceptionType = [string]$cleanup.LastRemovalExceptionType
        $result.cleanupLastDeletionExceptionMessage = [string]$cleanup.LastRemovalExceptionMessage
        $result.cleanupLastDeletionErrorId = [string]$cleanup.LastRemovalErrorId
        $result.cleanupClassification = [string]$cleanup.Classification
        $result.productionCleanupSucceeded = [bool]$cleanup.Success
        $result.profileRemoved = [bool]$cleanup.ProfileRemoved
    }
    elseif (-not $result.sessionCreated) {
        $result.profileRemoved = [string]::IsNullOrWhiteSpace($profileDir) -or -not (Test-Path -LiteralPath $profileDir)
    }
    $result.profileAbsentAfterHarness = [string]::IsNullOrWhiteSpace($profileDir) -or -not (Test-Path -LiteralPath $profileDir)
    Remove-Item -LiteralPath $screenshotPath -Force -ErrorAction SilentlyContinue
    $result.screenshotRemoved = -not (Test-Path -LiteralPath $screenshotPath)
    if ($result.sessionCreated -and (-not $result.productionCleanupSucceeded -or $result.remainingTaskOwnedProcessIds.Count -gt 0 -or -not $result.profileRemoved -or -not $result.profileAbsentAfterHarness -or -not $result.screenshotRemoved) -and -not $result.failureClass) {
        $result.failureClass = "Task-owned cleanup verification failed."
    }
    $result.success = [bool]($result.candidateAccepted -and $result.screenshotCreated -and $result.screenshotBytes -gt 0 -and $result.screenshotWidth -gt 0 -and $result.screenshotHeight -gt 0 -and $result.sessionCreated -and $result.devToolsActivePortNonEmpty -and $result.browserIdentifierPresent -and $result.loopbackEndpointReachable -and $result.expectedPageTargetAvailable -and $result.productionCleanupSucceeded -and $result.remainingTaskOwnedProcessIds.Count -eq 0 -and $result.profileRemoved -and $result.profileAbsentAfterHarness -and $result.screenshotRemoved -and -not $result.failureClass)
    $result | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $resultPath -Encoding UTF8
}

if (-not $result.success) { exit 1 }
