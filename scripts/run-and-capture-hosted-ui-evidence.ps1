<#
.SYNOPSIS
Starts a local hosted CCLD mode and captures a UI evidence packet.
.DESCRIPTION
Convenience wrapper for local review only. It starts one existing hosted app script
in live, fixture, or scaffold mode, waits for the root route, then calls
scripts/capture-hosted-ui-evidence.ps1. It does not submit forms, trigger
retrieval, import data, mutate reviewer-created state, or call GitHub.
.PARAMETER Mode
Mode to run: live, fixture, or scaffold.
.PARAMETER Port
Local port to bind. Defaults to 8003 for live, 8010 for fixture, and 8000 for scaffold.
.PARAMETER OutputDir
Evidence output root. Defaults to data/processed/ui-evidence.
.PARAMETER KillExistingPortProcess
Stop any process listening on the chosen local port before launch.
.PARAMETER PythonExecutable
Verified Python executable to pass to the fixture/demo launcher. Required for a
secondary worktree that has no local virtual environment.
.PARAMETER Issue502
Capture the focused Issue #502 Home and Find a Facility evidence packet.
.PARAMETER Issue420
Capture the focused Issue #420 Facility Overview evidence packet.
.PARAMETER Issue642
Capture the focused Issue #642 Compare Facilities interaction evidence packet.
.PARAMETER Issue642LicensingSourceUnavailable
Launch the separate Issue #642 fixture state with the Licensing source absent.
.EXAMPLE
.\scripts\run-and-capture-hosted-ui-evidence.ps1 -Mode fixture -Port 8010 -KillExistingPortProcess
.EXAMPLE
.\scripts\run-and-capture-hosted-ui-evidence.ps1 -Mode fixture -Port 8010 -Issue502
.EXAMPLE
.\scripts\run-and-capture-hosted-ui-evidence.ps1 -Mode fixture -Port 8010 -Issue420
#>
param(
    [ValidateSet("live", "fixture", "scaffold")]
    [string]$Mode = "fixture",

    [int]$Port = 0,

    [string]$OutputDir = "data/processed/ui-evidence",

    [switch]$KillExistingPortProcess,

    [string]$PythonExecutable = "",

    [switch]$Issue502,

    [switch]$Issue420,

    [switch]$Issue642,

    [switch]$Issue643,

    [switch]$Issue644,

    [switch]$Issue655,

    [switch]$Issue655Rehearsal,

    [string]$RehearsalRunName = 'run',

    [switch]$Issue642LicensingSourceUnavailable
)

$ErrorActionPreference = "Stop"

function Get-PortListenerObservation {
    param(
        [int]$LocalPort,
        [scriptblock]$PrimaryEnumerator = $null,
        [scriptblock]$FallbackEnumerator = $null
    )
    $primaryError = ''
    try {
        $primaryListeners = if ($PrimaryEnumerator) { @(& $PrimaryEnumerator $LocalPort) } else { @(Get-NetTCPConnection -LocalPort $LocalPort -State Listen -ErrorAction Stop) }
        $listeners = @($primaryListeners | ForEach-Object {
            $name = ''
            try { $name = (Get-Process -Id $_.OwningProcess -ErrorAction Stop).ProcessName } catch { }
            [pscustomobject]@{ timestamp=(Get-Date).ToString('o'); localAddress=[string]$_.LocalAddress; localPort=[int]$_.LocalPort; state=[string]$_.State; owningPid=[int]$_.OwningProcess; processName=$name }
        })
        return [pscustomobject]@{ timestamp=(Get-Date).ToString('o'); state=if ($listeners.Count -eq 0) {'FREE'} else {'LISTENER_PRESENT'}; primaryEnumeration='succeeded'; fallbackEnumeration='not-required'; listeners=$listeners; enumerationError='' }
    }
    catch { $primaryError = $_.Exception.Message }

    try {
        $fallbackLines = if ($FallbackEnumerator) { @(& $FallbackEnumerator $LocalPort) } else {
            $output = @(& netstat -ano -p tcp 2>&1)
            if ($LASTEXITCODE -ne 0) { throw "netstat exited with code $LASTEXITCODE." }
            $output
        }
        $listeners = [System.Collections.ArrayList]::new(); $sawTcpRow = $false
        foreach ($line in @($fallbackLines)) {
            $text = [string]$line
            if ($text -notmatch '^\s*TCP\s+') { continue }
            $sawTcpRow = $true
            if ($text -notmatch '^\s*TCP\s+(?<local>\S+)\s+\S+\s+LISTENING\s+(?<pid>\d+)\s*$') {
                if ($text -match '\s+LISTENING\s+') { throw "Unable to safely parse netstat listener row: $text" }
                continue
            }
            $local = [string]$Matches.local
            $listenerPid = [int]$Matches.pid
            if ($local -notmatch ':(?<port>\d+)$') { throw "Unable to safely parse netstat local endpoint: $local" }
            if ([int]$Matches.port -ne $LocalPort) { continue }
            $name = ''
            try { $name = (Get-Process -Id $listenerPid -ErrorAction Stop).ProcessName } catch { }
            [void]$listeners.Add([pscustomobject]@{ timestamp=(Get-Date).ToString('o'); localAddress=$local; localPort=$LocalPort; state='Listen'; owningPid=$listenerPid; processName=$name })
        }
        if (-not $sawTcpRow -and @($fallbackLines).Count -eq 0) { throw 'netstat produced no parseable output.' }
        return [pscustomobject]@{ timestamp=(Get-Date).ToString('o'); state=if ($listeners.Count -eq 0) {'FREE'} else {'LISTENER_PRESENT'}; primaryEnumeration='failed'; fallbackEnumeration='succeeded'; listeners=@($listeners); enumerationError="Primary Get-NetTCPConnection failed: $primaryError" }
    }
    catch {
        return [pscustomobject]@{ timestamp=(Get-Date).ToString('o'); state='ENUMERATION_FAILED'; primaryEnumeration='failed'; fallbackEnumeration='failed'; listeners=@(); enumerationError="Primary Get-NetTCPConnection failed: $primaryError Fallback netstat failed: $($_.Exception.Message)" }
    }
}

function Test-StableFreePort {
    param(
        [int]$LocalPort,
        [int]$RequiredConsecutiveFree = 3,
        [int]$IntervalMilliseconds = 250,
        [int]$MaximumObservations = 20,
        [scriptblock]$ObservationProvider = $null,
        [scriptblock]$PrimaryEnumerator = $null,
        [scriptblock]$FallbackEnumerator = $null
    )
    $observations = [System.Collections.ArrayList]::new(); $freeStreak = 0; $transient = $false
    for ($index = 0; $index -lt $MaximumObservations; $index++) {
        $observation = if ($ObservationProvider) { & $ObservationProvider $index } else { Get-PortListenerObservation -LocalPort $LocalPort -PrimaryEnumerator $PrimaryEnumerator -FallbackEnumerator $FallbackEnumerator }
        [void]$observations.Add($observation)
        if ($observation.state -eq 'ENUMERATION_FAILED') { return [pscustomobject]@{ free=$false; state='ENUMERATION_FAILED'; transientListener=$transient; observations=@($observations) } }
        if (@($observation.listeners).Count -eq 0) { $freeStreak++ } else { if ($freeStreak -gt 0) { $transient = $true }; $freeStreak = 0 }
        if ($freeStreak -ge $RequiredConsecutiveFree) { return [pscustomobject]@{ free=$true; state='FREE'; transientListener=$transient; observations=@($observations) } }
        if ($index -lt ($MaximumObservations - 1)) { Start-Sleep -Milliseconds $IntervalMilliseconds }
    }
    [pscustomobject]@{ free=$false; state='LISTENER_PRESENT'; transientListener=$transient; observations=@($observations) }
}

function Write-PortObservations {
    param([object[]]$Observations)
    foreach ($observation in $Observations) {
        if ($observation.state -eq 'ENUMERATION_FAILED') { Write-Host "$($observation.timestamp) listener=unresolved primary=$($observation.primaryEnumeration) fallback=$($observation.fallbackEnumeration) error=$($observation.enumerationError)" }
        elseif (@($observation.listeners).Count -eq 0) { Write-Host "$($observation.timestamp) listener=none primary=$($observation.primaryEnumeration) fallback=$($observation.fallbackEnumeration)" }
        else { foreach ($listener in $observation.listeners) { Write-Host "$($listener.timestamp) listener=$($listener.localAddress):$($listener.localPort) state=$($listener.state) pid=$($listener.owningPid) process=$($listener.processName) primary=$($observation.primaryEnumeration) fallback=$($observation.fallbackEnumeration)" } }
    }
}

function Get-TaskOwnedProcessIds {
    param([int]$RootProcessId)
    $ids = [System.Collections.Generic.List[int]]::new()
    $pending = [System.Collections.Generic.Queue[int]]::new()
    $pending.Enqueue($RootProcessId)
    while ($pending.Count -gt 0) {
        $id = $pending.Dequeue()
        if ($ids.Contains($id)) { continue }
        $ids.Add($id)
        foreach ($child in @(Get-CimInstance Win32_Process -Filter "ParentProcessId = $id" -ErrorAction SilentlyContinue)) {
            $pending.Enqueue([int]$child.ProcessId)
        }
    }
    return @($ids)
}

function Stop-TaskOwnedFixture {
    param([System.Diagnostics.Process]$RootProcess)
    foreach ($id in @(Get-TaskOwnedProcessIds -RootProcessId $RootProcess.Id | Sort-Object -Descending)) {
        Stop-Process -Id $id -ErrorAction SilentlyContinue
        Write-Host "Stopped verified task-owned fixture PID: $id"
    }
}

function Test-TaskOwnedFixtureReadiness {
    param([System.Diagnostics.Process]$RootProcess, [int]$LocalPort, [string]$BaseUrl, [int]$TimeoutSeconds = 30)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $RootProcess.Refresh()
        if ($RootProcess.HasExited) { return [pscustomobject]@{ ready=$false; reason="launcher exited with code $($RootProcess.ExitCode)"; listener=$null; ownerIds=@() } }
        $ownerIds = @(Get-TaskOwnedProcessIds -RootProcessId $RootProcess.Id)
        $listener = @(Get-NetTCPConnection -LocalPort $LocalPort -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1)
        $ownedListener = @($listener | Where-Object { $ownerIds -contains [int]$_.OwningProcess })
        if ($ownedListener.Count -eq 1) {
            try {
                $response = Invoke-WebRequest -Uri "$BaseUrl/" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
                if ([int]$response.StatusCode -eq 200) { return [pscustomobject]@{ ready=$true; reason='ready'; listener=$ownedListener[0]; ownerIds=$ownerIds } }
            }
            catch { }
        }
        Start-Sleep -Milliseconds 250
    }
    return [pscustomobject]@{ ready=$false; reason='readiness timeout or listener ownership mismatch'; listener=$null; ownerIds=@(Get-TaskOwnedProcessIds -RootProcessId $RootProcess.Id) }
}

function Get-Issue655CandidatePorts {
    # The fixture and capture scripts take -Port and build BaseUrl from it.  This
    # bounded high, unprivileged loopback set avoids a preferred fixed port.
    return @(20000..20009)
}

function New-Issue655ScenarioUri {
    param([string]$BaseUrl, [string]$Query, [string]$Fragment = '')
    $base = [System.Uri]$BaseUrl
    $builder = [System.UriBuilder]::new($base.Scheme, $base.Host, $base.Port, '/ccld/facilities/intelligence')
    $builder.Query = $Query.TrimStart('?')
    $builder.Fragment = $Fragment.TrimStart('#')
    return $builder.Uri.AbsoluteUri
}

$scriptPath = switch ($Mode) {
    "live" { ".\scripts\run-hosted-complaint-retrieval-live.ps1" }
    "fixture" { ".\scripts\run-hosted-complaint-retrieval-demo.ps1" }
    default { ".\scripts\run-hosted-scaffold.ps1" }
}

if ($Mode -eq "fixture" -and [string]::IsNullOrWhiteSpace($PythonExecutable)) {
    $worktreePython = Join-Path $PWD ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $worktreePython -PathType Leaf) {
        $PythonExecutable = $worktreePython
    }
    else {
        throw "Fixture mode requires -PythonExecutable when the current worktree has no local virtual environment."
    }
}

$shell = (Get-Command pwsh -ErrorAction SilentlyContinue)
if (-not $shell) { $shell = Get-Command powershell -ErrorAction Stop }

$candidatePorts = if ($Issue655) { @(Get-Issue655CandidatePorts) } else { @($Port) }
if (-not $Issue655 -and $Port -eq 0) {
    if ($Mode -eq "live") { $candidatePorts = @(8003) }
    elseif ($Mode -eq "fixture") { $candidatePorts = @(8010) }
    else { $candidatePorts = @(8000) }
}
if ($Issue655 -and $KillExistingPortProcess) { throw 'Issue #655 fixture acquisition never terminates an existing listener.' }
$candidateResults = [System.Collections.ArrayList]::new()
$process = $null; $baseUrl = ''; $Port = 0
foreach ($candidate in $candidatePorts | Select-Object -Unique) {
    $portCheck = Test-StableFreePort -LocalPort $candidate
    Write-PortObservations -Observations $portCheck.observations
    $candidateResult = [ordered]@{ port=$candidate; selectionMethod=if ($Issue655) {'bounded-high-unprivileged-loopback'} else {'requested-port'}; observations=@($portCheck.observations); launched=$false; taskOwnedPid=$null; readiness='not-attempted'; rejectionReason='' }
    if (-not $portCheck.free) { $candidateResult.rejectionReason='stable-free guard failed'; [void]$candidateResults.Add($candidateResult); continue }
    if ($portCheck.transientListener) { Write-Host "Transient listener observation cleared before launch." }
    $candidateBaseUrl = "http://127.0.0.1:$candidate"
    $launcherArguments = @('-NoProfile','-ExecutionPolicy','Bypass','-File',$scriptPath,'-Port',[string]$candidate)
    if ($Mode -eq 'fixture') {
        $launcherArguments += @('-PythonExecutable',$PythonExecutable)
        if ($Issue642 -or $Issue644) { $launcherArguments += '-Issue642Evidence' }
        if ($Issue642LicensingSourceUnavailable) { $launcherArguments += '-Issue642LicensingSourceUnavailable' }
    }
    # Failed fixture launches leave only temporary diagnostics, never an evidence packet directory.
    $launcherLogPrefix = "recordstracker-$Mode-$candidate-$((Get-Date).ToUniversalTime().ToString('yyyyMMdd-HHmmssZ'))"
    $launcherStdout = Join-Path ([System.IO.Path]::GetTempPath()) "$launcherLogPrefix.stdout.log"
    $launcherStderr = Join-Path ([System.IO.Path]::GetTempPath()) "$launcherLogPrefix.stderr.log"
    $candidateProcess = Start-Process -FilePath $shell.Source -ArgumentList $launcherArguments -WorkingDirectory $PWD -RedirectStandardOutput $launcherStdout -RedirectStandardError $launcherStderr -WindowStyle Hidden -PassThru
    $candidateResult.launched=$true; $candidateResult.taskOwnedPid=$candidateProcess.Id; $candidateResult.launchCommand=($launcherArguments -join ' '); $candidateResult.launcherStdout=$launcherStdout; $candidateResult.launcherStderr=$launcherStderr
    $readiness = Test-TaskOwnedFixtureReadiness -RootProcess $candidateProcess -LocalPort $candidate -BaseUrl $candidateBaseUrl
    $candidateResult.readiness=$readiness.reason
    if ($readiness.ready) { $process=$candidateProcess; $Port=$candidate; $baseUrl=$candidateBaseUrl; $candidateResult.listenerPid=$readiness.listener.OwningProcess; [void]$candidateResults.Add($candidateResult); break }
    Stop-TaskOwnedFixture -RootProcess $candidateProcess
    $candidateResult.rejectionReason='launch collision or fixture-start failure'; [void]$candidateResults.Add($candidateResult)
}
Write-Host ('ISSUE655_PORT_ACQUISITION=' + ($candidateResults | ConvertTo-Json -Depth 8 -Compress))
if ($null -eq $process) { throw "Issue #655 fixture acquisition exhausted $($candidatePorts.Count) candidate ports without verified readiness." }

Write-Host "URL to open: $baseUrl/"
Write-Host "Started process ID: $($process.Id)"
Write-Host "Stop command: Stop-Process -Id $($process.Id)"

$captureArguments = @{
    BaseUrl = $baseUrl
    Mode = $Mode
    OutputDir = $OutputDir
}
if ($Issue502) { $captureArguments.Issue502 = $true }
if ($Issue420) { $captureArguments.Issue420 = $true }
if ($Issue642) { $captureArguments.Issue642 = $true }
if ($Issue643) { $captureArguments.Issue643 = $true }
if ($Issue644) { $captureArguments.Issue644 = $true }
if ($Issue655) { $captureArguments.Issue655 = $true }
if ($Issue655Rehearsal) {
    if (-not $Issue655) { throw 'Issue655Rehearsal requires Issue655.' }
    $captureArguments.Issue655Rehearsal = $true
    $captureArguments.RehearsalRunName = $RehearsalRunName
}
if ($Issue642LicensingSourceUnavailable) {
    $captureArguments.Issue642 = $true
    $captureArguments.Issue642LicensingSourceUnavailable = $true
}
try {
    & .\scripts\capture-hosted-ui-evidence.ps1 @captureArguments
    if ($LASTEXITCODE -ne 0) { throw "Evidence capture exited with code $LASTEXITCODE." }
    Write-Host "Evidence capture complete for $Mode mode at $baseUrl/."
}
finally {
    Stop-TaskOwnedFixture -RootProcess $process
    $postShutdown = Test-StableFreePort -LocalPort $Port
    Write-PortObservations -Observations $postShutdown.observations
    if (-not $postShutdown.free) { throw "Port $Port did not reach three consecutive listener-free observations after task-owned fixture shutdown." }
    Write-Host "Fixture port $Port is stably free after shutdown."
}
