param(
    [Parameter(Mandatory)]
    [string]$TempRoot,

    [Parameter(Mandatory)]
    [string]$CaptureScriptPath
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $CaptureScriptPath -PathType Leaf)) { throw "Capture script is unavailable." }
. $CaptureScriptPath -LibraryOnly

function Get-FixtureStartupFailure {
    param([string]$OutputStatus)
    $prefix = if ($OutputStatus -in @("missing", "empty")) { "BROWSER_AUTOMATION_NO_REQUIRED_OUTPUT" } else { "BROWSER_AUTOMATION_INVALID_REQUIRED_OUTPUT" }
    return "${prefix}: operation=interaction-aware-startup; exitCode=0; requiredOutput=DevTools endpoint; browserExecutableCategory=edge; outputStatus=$OutputStatus"
}

function Get-FixtureCdpReadiness {
    param(
        [string]$ActivePortFile,
        [DateTime]$LaunchStartedAt,
        [ValidateSet("valid", "unreachable", "missing-target", "mismatched")]
        [string]$EndpointState = "valid"
    )
    if (-not (Test-Path -LiteralPath $ActivePortFile -PathType Leaf)) {
        return [pscustomobject]@{ State = "pending"; Failure = ""; Target = $null }
    }
    $portFile = Get-Item -LiteralPath $ActivePortFile -ErrorAction Stop
    if ($portFile.Length -le 0) {
        return [pscustomobject]@{ State = "terminal"; Failure = (Get-FixtureStartupFailure -OutputStatus "empty"); Target = $null }
    }
    if ($portFile.LastWriteTimeUtc -lt $LaunchStartedAt) {
        return [pscustomobject]@{ State = "terminal"; Failure = (Get-FixtureStartupFailure -OutputStatus "stale"); Target = $null }
    }
    $content = [System.IO.File]::ReadAllText($ActivePortFile).TrimEnd([char[]]"`r`n")
    $portLines = @($content -split "`r?`n")
    $port = 0
    if ($portLines.Count -ne 2 -or [string]::IsNullOrWhiteSpace($portLines[0]) -or [string]::IsNullOrWhiteSpace($portLines[1]) -or -not [int]::TryParse($portLines[0], [ref]$port) -or $port -lt 1 -or $port -gt 65535 -or $portLines[1] -notmatch '^/devtools/browser/[A-Za-z0-9-]+$') {
        return [pscustomobject]@{ State = "terminal"; Failure = (Get-FixtureStartupFailure -OutputStatus "malformed"); Target = $null }
    }
    if ($EndpointState -eq "unreachable") {
        return [pscustomobject]@{ State = "pending"; Failure = (Get-FixtureStartupFailure -OutputStatus "unreachable"); Target = $null }
    }
    if ($EndpointState -eq "missing-target") {
        return [pscustomobject]@{ State = "pending"; Failure = (Get-FixtureStartupFailure -OutputStatus "missing-page-target"); Target = $null }
    }
    if ($EndpointState -eq "mismatched") {
        return [pscustomobject]@{ State = "terminal"; Failure = (Get-FixtureStartupFailure -OutputStatus "mismatched-endpoint"); Target = $null }
    }
    return [pscustomobject]@{ State = "ready"; Failure = ""; Target = [pscustomobject]@{ webSocketDebuggerUrl = "ws://127.0.0.1:$port/devtools/page/test" } }
}

function Wait-FixtureCdpReadiness {
    param(
        [DateTime]$Deadline,
        [ValidateSet("ready", "handoff", "missing", "late-ready")]
        [string]$Mode,
        [bool]$RootExited
    )
    $clock = [DateTime]::UtcNow
    $polls = 0
    while ($clock -lt $Deadline) {
        $polls += 1
        $state = if ($Mode -eq "ready" -or ($Mode -eq "handoff" -and $polls -gt 1) -or ($Mode -eq "late-ready" -and $polls -gt 1)) { "ready" } else { "pending" }
        if ($state -eq "ready") {
            return [pscustomobject]@{ State = "ready"; Polls = $polls; RootExited = $RootExited }
        }
        $clock = $clock.AddMilliseconds(50)
    }
    throw (Get-FixtureStartupFailure -OutputStatus "missing")
}

function Get-FixtureOwnedProcessIds {
    param([int[]]$RootProcessIds, [hashtable]$ChildrenByParent)
    $owned = [System.Collections.Generic.HashSet[int]]::new()
    $pending = [System.Collections.Generic.Queue[int]]::new()
    foreach ($processId in $RootProcessIds) { if ($owned.Add($processId)) { $pending.Enqueue($processId) } }
    while ($pending.Count -gt 0) {
        $parentId = $pending.Dequeue()
        $children = $ChildrenByParent[$parentId]
        if ($null -eq $children) { continue }
        foreach ($childId in @($children)) {
            if ([int]$childId -gt 0 -and $owned.Add([int]$childId)) { $pending.Enqueue([int]$childId) }
        }
    }
    return @($owned | Sort-Object)
}

function Invoke-FixtureCleanupScenario {
    param(
        [string]$ProfileDir,
        [string]$GovernedRoot,
        [object[]]$ProcessIdentities = @(),
        [int]$ProcessPollsBeforeExit = 0,
        [int]$RemovalFailuresBeforeSuccess = 0,
        [switch]$PermanentProcess,
        [switch]$PermanentRemoval,
        [int]$ReusedProcessId = 0
    )
    $script:CleanupFixtureState = [pscustomobject]@{
        Clock = [DateTime]::new(2026, 8, 4, 12, 0, 0, [DateTimeKind]::Utc)
        ProcessPollsBeforeExit = $ProcessPollsBeforeExit
        RemovalFailuresBeforeSuccess = $RemovalFailuresBeforeSuccess
        PermanentProcess = [bool]$PermanentProcess
        PermanentRemoval = [bool]$PermanentRemoval
        ReusedProcessId = $ReusedProcessId
        StopRequestedIds = [System.Collections.Generic.List[int]]::new()
        ProcessProviderIds = [System.Collections.Generic.List[int]]::new()
        RemovalAttemptCount = 0
    }
    $currentProcessProvider = {
        param($processId)
        $script:CleanupFixtureState.ProcessProviderIds.Add([int]$processId)
        $expected = $ProcessIdentities | Where-Object { [int]$_.ProcessId -eq [int]$processId } | Select-Object -First 1
        if ($null -eq $expected) { return $null }
        if ([int]$processId -eq $script:CleanupFixtureState.ReusedProcessId) {
            return [pscustomobject]@{ ProcessId = [int]$processId; CreationTimeUtcTicks = [long]$expected.CreationTimeUtcTicks + 1 }
        }
        if ($script:CleanupFixtureState.StopRequestedIds.Contains([int]$processId) -and -not $script:CleanupFixtureState.PermanentProcess -and $script:CleanupFixtureState.ProcessPollsBeforeExit -le 0) {
            return $null
        }
        return $expected
    }
    $stopProcessAction = {
        param($processId)
        $script:CleanupFixtureState.StopRequestedIds.Add([int]$processId)
    }
    $removeProfileAction = {
        param($path)
        $script:CleanupFixtureState.RemovalAttemptCount += 1
        if ($script:CleanupFixtureState.PermanentRemoval) {
            throw [System.IO.IOException]::new("synthetic directory is not empty")
        }
        if ($script:CleanupFixtureState.RemovalFailuresBeforeSuccess -gt 0) {
            $script:CleanupFixtureState.RemovalFailuresBeforeSuccess -= 1
            throw [System.IO.IOException]::new("synthetic profile is in use")
        }
        Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction Stop
    }
    $nowProvider = { $script:CleanupFixtureState.Clock }
    $sleepAction = {
        param($milliseconds)
        $script:CleanupFixtureState.Clock = $script:CleanupFixtureState.Clock.AddMilliseconds($milliseconds)
        if ($script:CleanupFixtureState.StopRequestedIds.Count -gt 0 -and $script:CleanupFixtureState.ProcessPollsBeforeExit -gt 0) {
            $script:CleanupFixtureState.ProcessPollsBeforeExit -= 1
        }
    }
    $outcome = Invoke-TaskOwnedBrowserCleanup `
        -ProfileDir $ProfileDir `
        -ProcessIdentities $ProcessIdentities `
        -GovernedTempRoot $GovernedRoot `
        -CleanupTimeoutMilliseconds 150 `
        -PollMilliseconds 50 `
        -CurrentProcessProvider $currentProcessProvider `
        -StopProcessAction $stopProcessAction `
        -RemoveProfileAction $removeProfileAction `
        -NowProvider $nowProvider `
        -SleepAction $sleepAction
    return [pscustomobject]@{
        Outcome = $outcome
        StopRequestedIds = @($script:CleanupFixtureState.StopRequestedIds)
        ProcessProviderIds = @($script:CleanupFixtureState.ProcessProviderIds)
        RemovalAttemptCount = $script:CleanupFixtureState.RemovalAttemptCount
    }
}

function Get-FixtureCleanupSummary {
    param([object]$Scenario)
    return [ordered]@{
        Success = [bool]$Scenario.Outcome.Success
        Classification = [string]$Scenario.Outcome.Classification
        ProfilePathValidated = [bool]$Scenario.Outcome.ProfilePathValidated
        StopRequestedIds = @($Scenario.StopRequestedIds)
        ProcessProviderIds = @($Scenario.ProcessProviderIds)
        RemainingProcessIds = @($Scenario.Outcome.RemainingProcessIdentities | ForEach-Object { [int]$_.ProcessId })
        ProfileRemovalAttemptCount = [int]$Scenario.Outcome.ProfileRemovalAttemptCount
        ProfileRemovalElapsedMilliseconds = [int]$Scenario.Outcome.ProfileRemovalElapsedMilliseconds
        InitialProfileRemovalFailed = [bool]$Scenario.Outcome.InitialProfileRemovalFailed
        ProfileRemoved = [bool]$Scenario.Outcome.ProfileRemoved
        LastRemovalExceptionType = [string]$Scenario.Outcome.LastRemovalExceptionType
        LastRemovalExceptionMessage = [string]$Scenario.Outcome.LastRemovalExceptionMessage
        LastRemovalErrorId = [string]$Scenario.Outcome.LastRemovalErrorId
        FixtureRemovalAttemptCount = [int]$Scenario.RemovalAttemptCount
        Failure = [string]$Scenario.Outcome.Failure
    }
}

$profile = Join-Path $TempRoot "ccld-ui-evidence-readiness"
$externalProfile = Join-Path $TempRoot "outside-task-profile"
New-Item -ItemType Directory -Path $profile, $externalProfile -Force | Out-Null
$activePortFile = Join-Path $profile "DevToolsActivePort"
$outsidePortFile = Join-Path $externalProfile "DevToolsActivePort"
$validPort = "9222`n/devtools/browser/abcdef-123"
$startedAt = [DateTime]::UtcNow.AddSeconds(-1)

Set-Content -LiteralPath $activePortFile -Value $validPort -NoNewline
$valid = Get-FixtureCdpReadiness -ActivePortFile $activePortFile -LaunchStartedAt $startedAt
Set-Content -LiteralPath $activePortFile -Value "" -NoNewline
$empty = Get-FixtureCdpReadiness -ActivePortFile $activePortFile -LaunchStartedAt $startedAt
$malformed = @()
foreach ($content in @("bad`n/devtools/browser/abcdef-123", "9222", "9222`n/devtools/browser/abcdef-123`nextra")) {
    Set-Content -LiteralPath $activePortFile -Value $content -NoNewline
    $malformed += Get-FixtureCdpReadiness -ActivePortFile $activePortFile -LaunchStartedAt $startedAt
}
Set-Content -LiteralPath $activePortFile -Value $validPort -NoNewline
$unreachable = Get-FixtureCdpReadiness -ActivePortFile $activePortFile -LaunchStartedAt $startedAt -EndpointState unreachable
$missingTarget = Get-FixtureCdpReadiness -ActivePortFile $activePortFile -LaunchStartedAt $startedAt -EndpointState missing-target
(Get-Item -LiteralPath $activePortFile).LastWriteTimeUtc = [DateTime]::UtcNow.AddMinutes(-1)
$stale = Get-FixtureCdpReadiness -ActivePortFile $activePortFile -LaunchStartedAt ([DateTime]::UtcNow)
Remove-Item -LiteralPath $activePortFile -Force
Set-Content -LiteralPath $outsidePortFile -Value $validPort -NoNewline
$outsideProfile = Get-FixtureCdpReadiness -ActivePortFile $activePortFile -LaunchStartedAt $startedAt

$normal = Wait-FixtureCdpReadiness -Deadline ([DateTime]::UtcNow.AddMilliseconds(100)) -Mode ready -RootExited $false
$handoff = Wait-FixtureCdpReadiness -Deadline ([DateTime]::UtcNow.AddMilliseconds(100)) -Mode handoff -RootExited $true
try { Wait-FixtureCdpReadiness -Deadline ([DateTime]::UtcNow.AddMilliseconds(50)) -Mode missing -RootExited $true | Out-Null; $missingOutput = "NO_ERROR" } catch { $missingOutput = $_.Exception.Message }
try { Wait-FixtureCdpReadiness -Deadline ([DateTime]::UtcNow.AddMilliseconds(50)) -Mode late-ready -RootExited $true | Out-Null; $lateOutput = "NO_ERROR" } catch { $lateOutput = $_.Exception.Message }

$ownedProcessIds = Get-FixtureOwnedProcessIds -RootProcessIds @(41) -ChildrenByParent @{ 41 = @(51); 51 = @(52); 99 = @(100) }
$governedRoot = Join-Path $TempRoot "governed-temp"
$outsideRoot = Join-Path $TempRoot "outside-governed-temp"
New-Item -ItemType Directory -Path $governedRoot, $outsideRoot -Force | Out-Null
$identity = [pscustomobject]@{ ProcessId = 401; CreationTimeUtcTicks = 638898192000000000 }

$immediateProfile = Join-Path $governedRoot "ccld-ui-evidence-00000000000000000000000000000001"
$delayedProcessProfile = Join-Path $governedRoot "ccld-ui-evidence-00000000000000000000000000000002"
$delayedRemovalProfile = Join-Path $governedRoot "ccld-ui-evidence-00000000000000000000000000000003"
$permanentRemovalProfile = Join-Path $governedRoot "ccld-ui-evidence-00000000000000000000000000000004"
$processTimeoutProfile = Join-Path $governedRoot "ccld-ui-evidence-00000000000000000000000000000005"
$siblingProfile = Join-Path $governedRoot "ccld-ui-evidence-00000000000000000000000000000006"
$exactSiblingTarget = Join-Path $governedRoot "ccld-ui-evidence-00000000000000000000000000000007"
$malformedProfile = Join-Path $governedRoot "ccld-ui-evidence-not-a-task-guid"
$outsideProfilePath = Join-Path $outsideRoot "ccld-ui-evidence-00000000000000000000000000000008"
New-Item -ItemType Directory -Path $immediateProfile, $delayedProcessProfile, $delayedRemovalProfile, $permanentRemovalProfile, $processTimeoutProfile, $siblingProfile, $exactSiblingTarget, $malformedProfile, $outsideProfilePath -Force | Out-Null

$immediate = Invoke-FixtureCleanupScenario -ProfileDir $immediateProfile -GovernedRoot $governedRoot
$delayedProcess = Invoke-FixtureCleanupScenario -ProfileDir $delayedProcessProfile -GovernedRoot $governedRoot -ProcessIdentities @($identity) -ProcessPollsBeforeExit 2
$delayedRemoval = Invoke-FixtureCleanupScenario -ProfileDir $delayedRemovalProfile -GovernedRoot $governedRoot -RemovalFailuresBeforeSuccess 1
$permanentRemoval = Invoke-FixtureCleanupScenario -ProfileDir $permanentRemovalProfile -GovernedRoot $governedRoot -PermanentRemoval
$processTimeout = Invoke-FixtureCleanupScenario -ProfileDir $processTimeoutProfile -GovernedRoot $governedRoot -ProcessIdentities @($identity) -PermanentProcess

$invalidCases = [ordered]@{}
foreach ($entry in @(
    [pscustomobject]@{ Name = "Empty"; Path = "" },
    [pscustomobject]@{ Name = "Relative"; Path = "ccld-ui-evidence-00000000000000000000000000000009" },
    [pscustomobject]@{ Name = "TempRoot"; Path = $governedRoot },
    [pscustomobject]@{ Name = "Parent"; Path = $TempRoot },
    [pscustomobject]@{ Name = "OutsideRoot"; Path = $outsideProfilePath },
    [pscustomobject]@{ Name = "MalformedName"; Path = $malformedProfile }
)) {
    $invalidCases[$entry.Name] = Get-FixtureCleanupSummary -Scenario (Invoke-FixtureCleanupScenario -ProfileDir $entry.Path -GovernedRoot $governedRoot)
}

$reparseTarget = Join-Path $TempRoot "reparse-target"
$reparseProfile = Join-Path $governedRoot "ccld-ui-evidence-0000000000000000000000000000000a"
New-Item -ItemType Directory -Path $reparseTarget -Force | Out-Null
New-Item -ItemType Junction -Path $reparseProfile -Target $reparseTarget | Out-Null
$reparse = Invoke-FixtureCleanupScenario -ProfileDir $reparseProfile -GovernedRoot $governedRoot

$siblingCleanup = Invoke-FixtureCleanupScenario -ProfileDir $exactSiblingTarget -GovernedRoot $governedRoot
$reusedIdentity = [pscustomobject]@{ ProcessId = 404; CreationTimeUtcTicks = 638898192000000100 }
$reuseProfile = Join-Path $governedRoot "ccld-ui-evidence-0000000000000000000000000000000b"
New-Item -ItemType Directory -Path $reuseProfile -Force | Out-Null
$pidReuse = Invoke-FixtureCleanupScenario -ProfileDir $reuseProfile -GovernedRoot $governedRoot -ProcessIdentities @($reusedIdentity) -ReusedProcessId 404

[ordered]@{
    Valid = $valid.State
    Empty = $empty.Failure
    Malformed = @($malformed | ForEach-Object { $_.Failure })
    Unreachable = $unreachable.Failure
    MissingTarget = $missingTarget.Failure
    Stale = $stale.Failure
    OutsideProfile = $outsideProfile.State
    Normal = $normal.State
    Handoff = $handoff.State
    HandoffPolls = $handoff.Polls
    HandoffRootExited = $handoff.RootExited
    MissingOutput = $missingOutput
    LateOutput = $lateOutput
    OwnedProcessIds = @($ownedProcessIds)
    UnrelatedProcessSelected = @($ownedProcessIds) -contains 99
    SuccessCleanupRemoved = -not (Test-Path -LiteralPath $immediateProfile)
    FailureCleanupRemoved = -not (Test-Path -LiteralPath $delayedRemovalProfile)
    ExternalProfilePreserved = Test-Path -LiteralPath $externalProfile
    Cleanup = [ordered]@{
        Immediate = Get-FixtureCleanupSummary -Scenario $immediate
        DelayedProcess = Get-FixtureCleanupSummary -Scenario $delayedProcess
        DelayedRemoval = Get-FixtureCleanupSummary -Scenario $delayedRemoval
        PermanentRemoval = Get-FixtureCleanupSummary -Scenario $permanentRemoval
        ProcessTimeout = Get-FixtureCleanupSummary -Scenario $processTimeout
        InvalidPaths = $invalidCases
        Reparse = Get-FixtureCleanupSummary -Scenario $reparse
        ReparseTargetPreserved = Test-Path -LiteralPath $reparseTarget -PathType Container
        Sibling = Get-FixtureCleanupSummary -Scenario $siblingCleanup
        SiblingPreserved = Test-Path -LiteralPath $siblingProfile -PathType Container
        PidReuse = Get-FixtureCleanupSummary -Scenario $pidReuse
    }
} | ConvertTo-Json -Depth 6
