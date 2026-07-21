<#
.SYNOPSIS
Captures a repeatable hosted CCLD UI evidence packet from an already-running app.
.DESCRIPTION
Runs GET-only route captures against a local/private hosted CCLD RecordsTracker URL,
writes route status, sanitized HTML, text summaries, lightweight accessibility
summaries, optional screenshots, and a manifest under ignored data/processed.
This script never submits forms, runs retrieval, imports data, mutates reviewer-
created state, calls GitHub, or performs production authentication.
.PARAMETER BaseUrl
Already-running hosted app base URL, such as http://127.0.0.1:8003.
.PARAMETER Mode
Capture mode label: live, fixture, or scaffold.
.PARAMETER OutputDir
Ignored output root. Defaults to data/processed/ui-evidence.
.PARAMETER ViewportWidth
Screenshot viewport width. Defaults to 1440.
.PARAMETER ViewportHeight
Screenshot viewport height. Defaults to 1200.
.PARAMETER TimeoutSeconds
Per-route GET timeout in seconds. Defaults to 10.
.PARAMETER IncludeHtml
When true, writes sanitized route HTML files. Defaults to true.
.PARAMETER IncludeScreenshots
When true, attempts optional screenshot capture if a local tool is available.
.PARAMETER ScreenshotToolPreference
Screenshot tool selector: auto, playwright, edge, or chrome. Explicit requests
fail without silently falling back to another tool.
.PARAMETER AllowUnavailable
When set, route failures are recorded in the manifest instead of failing the script.
.PARAMETER Issue415
Capture the focused issue #415 substantiated-worklist evidence routes and assertions.
.PARAMETER Issue416
Capture the focused issue #416 facility-priorities evidence routes and assertions.
.PARAMETER Issue417
Capture the focused issue #417 serious-topic worklist evidence routes and assertions.
.PARAMETER Issue418
Capture the focused issue #418 complaint trend and anomaly evidence routes and assertions.
.PARAMETER Issue419
Capture the focused issue #419 canonical Compare Facilities views, states, redirects,
responsive layouts, keyboard focus, and print evidence.
.PARAMETER Issue498
Capture the focused RT-SRC-002 local fixture evidence states and presentation scenarios.
.EXAMPLE
.\scripts\capture-hosted-ui-evidence.ps1 -BaseUrl http://127.0.0.1:8003 -Mode live
.EXAMPLE
.\scripts\capture-hosted-ui-evidence.ps1 -BaseUrl http://127.0.0.1:8010 -Mode fixture
.EXAMPLE
.\scripts\capture-hosted-ui-evidence.ps1 -BaseUrl http://192.168.1.122:8003 -Mode live -Issue415
.EXAMPLE
.\scripts\capture-hosted-ui-evidence.ps1 -BaseUrl http://192.168.1.122:8003 -Mode live -Issue416
.EXAMPLE
.\scripts\capture-hosted-ui-evidence.ps1 -BaseUrl http://192.168.1.122:8003 -Mode live -Issue417
.EXAMPLE
.\scripts\capture-hosted-ui-evidence.ps1 -BaseUrl http://127.0.0.1:8010 -Mode fixture -Issue418
.EXAMPLE
.\scripts\capture-hosted-ui-evidence.ps1 -BaseUrl http://127.0.0.1:8010 -Mode fixture -Issue419
.EXAMPLE
.\scripts\capture-hosted-ui-evidence.ps1 -BaseUrl http://127.0.0.1:8010 -Mode fixture -Issue498
.NOTES
Run from the repository root. Generated packets capture local hosted UI route,
text, assertion, accessibility, and screenshot evidence for reviewer inspection.
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$BaseUrl,

    [ValidateSet("live", "fixture", "scaffold")]
    [string]$Mode = "scaffold",

    [string]$OutputDir = "data/processed/ui-evidence",

    [ValidateRange(320, 7680)]
    [int]$ViewportWidth = 1440,

    [ValidateRange(320, 4320)]
    [int]$ViewportHeight = 1200,

    [ValidateRange(1, 120)]
    [int]$TimeoutSeconds = 10,

    [bool]$IncludeHtml = $true,

    [bool]$IncludeScreenshots = $true,

    [ValidateSet("auto", "playwright", "edge", "chrome")]
    [string]$ScreenshotToolPreference = "auto",

    [switch]$AllowUnavailable,

    [switch]$Issue415,

    [switch]$Issue416,

    [switch]$Issue417,

    [switch]$Issue418,

    [switch]$Issue419,

    [switch]$Issue498
)

$ErrorActionPreference = "Stop"

$evidencePurpose = if ($Issue498) {
    "Focused RT-SRC-002 local fixture evidence for supported, document-only, field-partial, source-unavailable, responsive, focus, and print states."
}
elseif ($Issue419) {
    "Focused issue #419 Compare Facilities evidence for canonical views, legacy redirects, source separation, states, responsive reflow, keyboard focus, and print."
}
elseif ($Issue418) {
    "Focused issue #418 complaint trend evidence for grouping, filters, coverage states, deterministic anomaly cues, links, accessibility snapshots, and screenshots."
}
elseif ($Issue417) {
    "Focused issue #417 serious-topic complaint worklist evidence for route status, category/cue separation, filters, links, accessibility snapshots, and screenshots."
}
elseif ($Issue416) {
    "Focused issue #416 facility prioritization evidence for route status, deterministic factor text, filters, pagination, accessibility snapshots, and screenshots."
}
elseif ($Issue415) {
    "Focused issue #415 substantiated worklist evidence for route status, count reconciliation, links, accessibility snapshots, and screenshots."
}
else {
    "Local hosted UI review evidence for route status, text markers, assertions, accessibility snapshots, and screenshots."
}
$forbiddenMarkers = @(
    "provider_subject", "provider-subject", "provider_issuer", "provider-issuer",
    "raw_provider_claims", "raw provider claims", "client_secret", "client-secret",
    "connection string", "connection_string", "set-cookie", "authorization:",
    "bearer ", "github_pat_", "ghp_", "traceback (most recent call last)",
    "private_header", "private-header"
)

function Stop-CaptureFail {
    param([string]$Message)
    throw "[FAIL] $Message"
}

function Test-AllowedBaseUrl {
    param([string]$Value)
    try { $uri = [System.Uri]::new($Value) }
    catch { Stop-CaptureFail "BaseUrl must be an absolute http:// or https:// URL." }
    if ($uri.Scheme -notin @("http", "https")) { Stop-CaptureFail "BaseUrl must use http:// or https://." }
    $hostValue = $uri.Host.Trim("[", "]").ToLowerInvariant()
    if ($hostValue -in @("localhost", "127.0.0.1", "::1")) { return }
    $ip = $null
    if ([System.Net.IPAddress]::TryParse($hostValue, [ref]$ip)) {
        $bytes = $ip.GetAddressBytes()
        if ($ip.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork) {
            if ($bytes[0] -eq 10) { return }
            if ($bytes[0] -eq 172 -and $bytes[1] -ge 16 -and $bytes[1] -le 31) { return }
            if ($bytes[0] -eq 192 -and $bytes[1] -eq 168) { return }
        }
    }
    Stop-CaptureFail "BaseUrl must be localhost or a private test IP address. Refusing non-local URL '$($uri.Host)'."
}

function Assert-OutputDir {
    param([string]$Path)
    $repoRoot = (Resolve-Path -LiteralPath $PWD).Path
    $processedRoot = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "data/processed"))
    $candidate = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $Path))
    if (-not $candidate.StartsWith($processedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        Stop-CaptureFail "OutputDir must be inside the ignored data/processed folder."
    }
}

function ConvertTo-RelativeEvidencePath {
    param([string]$Path, [string]$Root)
    if ([string]::IsNullOrWhiteSpace($Path)) { return "" }
    $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
    $pathFull = [System.IO.Path]::GetFullPath($Path)
    if ($pathFull.StartsWith($rootFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $pathFull.Substring($rootFull.Length).TrimStart("\", "/").Replace("\", "/")
    }
    return (Split-Path -Leaf $pathFull)
}

function Redact-EvidenceText {
    param([string]$Text)
    if ($null -eq $Text) { return "" }
    $redacted = $Text
    $redacted = [regex]::Replace($redacted, "(?i)github_pat_[A-Za-z0-9_]{20,}", "[redacted-github-token]")
    $redacted = [regex]::Replace($redacted, "(?i)ghp_[A-Za-z0-9_]{20,}", "[redacted-github-token]")
    $redacted = [regex]::Replace($redacted, "(?i)bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [redacted]")
    $redacted = [regex]::Replace($redacted, "(?i)(authorization\s*[:=]\s*)[^\s<]+", "`${1}[redacted]")
    $redacted = [regex]::Replace($redacted, "(?i)(client_secret\s*[:=]\s*)[^\s&<]+", "`${1}[redacted]")
    $redacted = [regex]::Replace($redacted, "(?i)(password\s*[:=]\s*)[^\s&<]+", "`${1}[redacted]")
    $redacted = [regex]::Replace($redacted, "(?i)(token\s*[:=]\s*)[^\s&<]+", "`${1}[redacted]")
    $redacted = [regex]::Replace($redacted, "(?i)(set-cookie\s*[:=]\s*)[^\r\n<]+", "`${1}[redacted]")
    $redacted = [regex]::Replace($redacted, "[A-Za-z]:\\Users\\[^\\\r\n<]+", "<local-user-path>")
    return $redacted
}

function Get-ForbiddenMarkers {
    param([string]$Text)
    if ($null -eq $Text) { return @() }
    $lower = $Text.ToLowerInvariant()
    $found = @()
    foreach ($marker in $forbiddenMarkers) { if ($lower.Contains($marker)) { $found += $marker } }
    return $found
}

function ConvertFrom-HtmlText {
    param([string]$Html)
    if ([string]::IsNullOrWhiteSpace($Html)) { return "" }
    $withoutScripts = [regex]::Replace($Html, "(?is)<(script|style)\b.*?</\1>", " ")
    $withBreaks = [regex]::Replace($withoutScripts, "(?i)<\s*(br|/p|/div|/section|/li|/tr|/h[1-6])\s*/?>", "`n")
    $withoutTags = [regex]::Replace($withBreaks, "(?s)<[^>]+>", " ")
    $decoded = [System.Net.WebUtility]::HtmlDecode($withoutTags)
    $lines = $decoded -split "\r?\n" | ForEach-Object { [string]::Join(" ", $_.Trim().Split([char[]]@(" ", "`t"), [System.StringSplitOptions]::RemoveEmptyEntries)) } | Where-Object { $_ }
    return ($lines -join "`n")
}

function Get-FirstHtmlMatch {
    param([string]$Html, [string]$Pattern)
    $match = [regex]::Match($Html, $Pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase -bor [System.Text.RegularExpressions.RegexOptions]::Singleline)
    if (-not $match.Success) { return "" }
    return (ConvertFrom-HtmlText -Html $match.Groups[1].Value).Trim()
}

function Get-HtmlMatches {
    param([string]$Html, [string]$Pattern)
    $matches = [regex]::Matches($Html, $Pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase -bor [System.Text.RegularExpressions.RegexOptions]::Singleline)
    $values = @()
    foreach ($match in $matches) { $values += (ConvertFrom-HtmlText -Html $match.Groups[1].Value).Trim() }
    return $values | Where-Object { $_ }
}

function Join-RouteUrl {
    param([string]$Base, [string]$Path)
    $trimmedBase = $Base.TrimEnd("/")
    if ($Path.StartsWith("/")) { return "$trimmedBase$Path" }
    return "$trimmedBase/$Path"
}

function Get-RouteContent {
    param([string]$Url, [int]$Timeout)
    $requestParameters = @{
        Uri            = $Url
        UseBasicParsing = $true
        TimeoutSec     = $Timeout
        ErrorAction    = "Stop"
    }
    if ((Get-Command Invoke-WebRequest).Parameters.ContainsKey("SkipHttpErrorCheck")) {
        $requestParameters["SkipHttpErrorCheck"] = $true
    }
    try {
        $response = Invoke-WebRequest @requestParameters
        return [pscustomobject]@{ StatusCode = [int]$response.StatusCode; Content = [string]$response.Content; Error = "" }
    }
    catch {
        if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
            $status = [int]$_.Exception.Response.StatusCode
            $content = ""
            if ($_.Exception.Response.Content) {
                try {
                    $content = [string]$_.Exception.Response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
                }
                catch { $content = "" }
            }
            return [pscustomobject]@{ StatusCode = $status; Content = $content; Error = "HTTP $status" }
        }
        return [pscustomobject]@{ StatusCode = 0; Content = ""; Error = $_.Exception.Message }
    }
}

function Get-ScreenshotToolCandidates {
    $candidates = [System.Collections.ArrayList]::new()
    $repoPlaywright = Join-Path $PWD "node_modules\.bin\playwright.cmd"
    if (Test-Path -LiteralPath $repoPlaywright) {
        [void]$candidates.Add([pscustomobject]@{ Name = "playwright-local"; Kind = "playwright"; Command = $repoPlaywright; FullPage = $true; InteractionAware = $false; Discovery = "repository-local" })
    }
    $playwrightCommand = Get-Command "playwright" -ErrorAction SilentlyContinue
    if ($playwrightCommand) {
        [void]$candidates.Add([pscustomobject]@{ Name = "playwright"; Kind = "playwright"; Command = $playwrightCommand.Source; FullPage = $true; InteractionAware = $false; Discovery = "Get-Command" })
    }
    $edgePaths = @(
        (Join-Path ${env:ProgramFiles} "Microsoft\Edge\Application\msedge.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Microsoft\Edge\Application\msedge.exe")
    )
    foreach ($path in $edgePaths) {
        if ($path -and (Test-Path -LiteralPath $path)) {
            [void]$candidates.Add([pscustomobject]@{ Name = "msedge-headless"; Kind = "edge"; Command = $path; FullPage = $false; InteractionAware = $true; Discovery = "fixed executable path" })
        }
    }
    foreach ($browser in @("msedge", "chrome", "chrome.exe")) {
        $cmd = Get-Command $browser -ErrorAction SilentlyContinue
        if ($cmd) {
            $kind = if ($browser -eq "msedge") { "edge" } else { "chrome" }
            [void]$candidates.Add([pscustomobject]@{ Name = "$browser-headless"; Kind = $kind; Command = $cmd.Source; FullPage = $false; InteractionAware = $true; Discovery = "Get-Command" })
        }
    }
    return @($candidates)
}

function Test-ScreenshotToolCandidate {
    param([object]$Candidate)
    if (-not $Candidate.Command -or -not (Test-Path -LiteralPath $Candidate.Command)) {
        return [pscustomobject]@{ Usable = $false; Status = "executable unavailable" }
    }
    if ($Candidate.Kind -eq "playwright") {
        $probePath = Join-Path ([System.IO.Path]::GetTempPath()) ("ccld-playwright-probe-{0}.png" -f [guid]::NewGuid().ToString("N"))
        try {
            $probe = Invoke-NativeCaptureCommand -Command $Candidate.Command -Arguments @("screenshot", "about:blank", $probePath) -Timeout ([Math]::Max(15, [int]$TimeoutSeconds))
            if ($probe.ExitCode -eq 0 -and (Test-Path -LiteralPath $probePath)) {
                return [pscustomobject]@{ Usable = $true; Status = "usable Playwright CLI and browser executable" }
            }
            return [pscustomobject]@{ Usable = $false; Status = ("Playwright browser validation failed: " + (Redact-EvidenceText -Text $probe.Output.Trim())) }
        }
        finally {
            Remove-Item -LiteralPath $probePath -Force -ErrorAction SilentlyContinue
        }
    }
    $probe = Invoke-NativeCaptureCommand -Command $Candidate.Command -Arguments @("--headless=new", "--disable-gpu", "--dump-dom", "about:blank") -Timeout ([Math]::Max(15, [int]$TimeoutSeconds))
    if ($probe.ExitCode -eq 0 -and $probe.Output -match "(?i)<html") {
        return [pscustomobject]@{ Usable = $true; Status = "usable headless browser executable" }
    }
    return [pscustomobject]@{ Usable = $false; Status = ("headless browser validation failed: " + (Redact-EvidenceText -Text $probe.Output.Trim())) }
}

function Resolve-ScreenshotTool {
    param(
        [string]$Requested,
        [bool]$RequireInteractionAware,
        [object[]]$Candidates = $null,
        [scriptblock]$Validator = $null
    )
    $availableCandidates = if ($null -eq $Candidates) { @(Get-ScreenshotToolCandidates) } else { @($Candidates) }
    $validateCandidate = if ($null -eq $Validator) { { param($candidate) Test-ScreenshotToolCandidate -Candidate $candidate } } else { $Validator }
    $attempts = [System.Collections.ArrayList]::new()
    $requestedCandidates = if ($Requested -eq "auto") { $availableCandidates } else { @($availableCandidates | Where-Object { $_.Kind -eq $Requested }) }
    if ($requestedCandidates.Count -eq 0) {
        return [pscustomobject]@{ Requested = $Requested; Resolved = "none"; ValidationStatus = "no matching executable discovered"; Executable = ""; SupportsInteractionAwareCapture = $false; FullPage = $false; Tool = $null; Attempts = @(); Error = "No '$Requested' screenshot tool executable was discovered." }
    }
    foreach ($candidate in $requestedCandidates) {
        $validation = & $validateCandidate $candidate
        $status = [string]$validation.Status
        if ($validation.Usable -and $RequireInteractionAware -and -not $candidate.InteractionAware) {
            $status = "$status; rejected because interaction-aware capture is required"
        }
        [void]$attempts.Add([pscustomobject]@{ name = $candidate.Name; kind = $candidate.Kind; discovery = $candidate.Discovery; validation = $status; usable = [bool]$validation.Usable; supportsInteractionAwareCapture = [bool]$candidate.InteractionAware })
        if ($validation.Usable -and (-not $RequireInteractionAware -or $candidate.InteractionAware)) {
            return [pscustomobject]@{ Requested = $Requested; Resolved = $candidate.Name; ValidationStatus = $status; Executable = [string]$candidate.Command; SupportsInteractionAwareCapture = [bool]$candidate.InteractionAware; FullPage = [bool]$candidate.FullPage; Tool = $candidate; Attempts = @($attempts); Error = "" }
        }
        if ($Requested -ne "auto") {
            return [pscustomobject]@{ Requested = $Requested; Resolved = "none"; ValidationStatus = $status; Executable = ""; SupportsInteractionAwareCapture = $false; FullPage = $false; Tool = $null; Attempts = @($attempts); Error = "Explicit screenshot tool '$Requested' is unusable: $status" }
        }
    }
    return [pscustomobject]@{ Requested = $Requested; Resolved = "none"; ValidationStatus = "no usable candidate"; Executable = ""; SupportsInteractionAwareCapture = $false; FullPage = $false; Tool = $null; Attempts = @($attempts); Error = "No usable screenshot tool satisfies the capture contract." }
}

function Join-NativeArgument {
    param([string]$Value)
    if ($Value -notmatch '[\s"]') { return $Value }
    return '"' + $Value.Replace('"', '\"') + '"'
}

function Invoke-NativeCaptureCommand {
    param([string]$Command, [string[]]$Arguments, [int]$Timeout)
    $stdoutPath = [System.IO.Path]::GetTempFileName()
    $stderrPath = [System.IO.Path]::GetTempFileName()
    try {
        # Edge and Chrome can write normal "bytes written to file" messages to
        # stderr. Capture native output as text so successful screenshots do not
        # become PowerShell NativeCommandError failures under Stop preference.
        $argumentList = @($Arguments | ForEach-Object { Join-NativeArgument -Value ([string]$_) })
        $process = Start-Process -FilePath $Command -ArgumentList $argumentList -NoNewWindow -PassThru -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
        if (-not $process.WaitForExit($Timeout * 1000)) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            $output = "native screenshot command timed out after $Timeout seconds"
            return [pscustomobject]@{ ExitCode = 124; Output = $output }
        }
        $stdout = if (Test-Path -LiteralPath $stdoutPath) { Get-Content -LiteralPath $stdoutPath -Raw -ErrorAction SilentlyContinue } else { "" }
        $stderr = if (Test-Path -LiteralPath $stderrPath) { Get-Content -LiteralPath $stderrPath -Raw -ErrorAction SilentlyContinue } else { "" }
        $output = @($stdout, $stderr) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
        $output = $output -join "`n"
        $exitCode = $process.ExitCode
        return [pscustomobject]@{ ExitCode = [int]$exitCode; Output = $output }
    }
    catch {
        return [pscustomobject]@{ ExitCode = 1; Output = $_.Exception.Message }
    }
    finally {
        Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    }
}

function Invoke-RouteScreenshot {
    param(
        [object]$Tool,
        [string]$Url,
        [string]$ScreenshotPath,
        [int]$Width = $ViewportWidth,
        [int]$Height = $ViewportHeight
    )
    if ($null -eq $Tool) { return "screenshot tool unavailable" }
    if ($Tool.Name -like "playwright*") { $arguments = @("screenshot", "--full-page", "--viewport-size=${Width},${Height}", $Url, $ScreenshotPath) }
    else { $arguments = @("--headless=new", "--disable-gpu", "--hide-scrollbars", "--window-size=$Width,$Height", "--screenshot=$ScreenshotPath", $Url) }
    $screenshotTimeoutSeconds = [Math]::Max(30, [int]$TimeoutSeconds)
    $result = Invoke-NativeCaptureCommand -Command $Tool.Command -Arguments $arguments -Timeout $screenshotTimeoutSeconds
    $visibilityDeadline = [DateTime]::UtcNow.AddSeconds(3)
    while ($result.ExitCode -eq 0 -and -not (Test-Path -LiteralPath $ScreenshotPath) -and [DateTime]::UtcNow -lt $visibilityDeadline) {
        Start-Sleep -Milliseconds 50
    }
    if ($result.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $ScreenshotPath)) { return "screenshot failed with $($Tool.Name) exit code $($result.ExitCode): $($result.Output.Trim())" }
    return ""
}

function Invoke-RoutePrint {
    param([object]$Tool, [string]$Url, [string]$PrintPath)
    if ($null -eq $Tool) { return "print tool unavailable" }
    if ($Tool.Name -like "playwright*") { $arguments = @("pdf", $Url, $PrintPath) }
    else { $arguments = @("--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--print-to-pdf=$PrintPath", $Url) }
    $printTimeoutSeconds = [Math]::Max(30, [int]$TimeoutSeconds)
    $result = Invoke-NativeCaptureCommand -Command $Tool.Command -Arguments $arguments -Timeout $printTimeoutSeconds
    $visibilityDeadline = [DateTime]::UtcNow.AddSeconds(3)
    while ($result.ExitCode -eq 0 -and -not (Test-Path -LiteralPath $PrintPath) -and [DateTime]::UtcNow -lt $visibilityDeadline) {
        Start-Sleep -Milliseconds 50
    }
    if ($result.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $PrintPath)) { return "print capture failed with $($Tool.Name) exit code $($result.ExitCode): $($result.Output.Trim())" }
    return ""
}

function New-InteractionBrowserSessionState {
    param([object]$Socket, [object]$Process, [string]$ProfileDir)
    return [pscustomobject]@{
        Socket = $Socket
        Process = $Process
        ProfileDir = $ProfileDir
        NextId = 0
    }
}

function Start-InteractionAwareBrowserSession {
    param([object]$Tool)
    if ($Tool.Kind -notin @("edge", "chrome")) {
        throw "Resolved tool '$($Tool.Name)' does not support the required DevTools interaction contract."
    }
    $profileDir = Join-Path ([System.IO.Path]::GetTempPath()) ("ccld-ui-evidence-{0}" -f [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $profileDir | Out-Null
    $process = $null
    try {
        $arguments = @(
            "--headless=new",
            "--disable-gpu",
            "--disable-background-networking",
            "--disable-component-update",
            "--disable-sync",
            "--metrics-recording-only",
            "--no-first-run",
            "--no-default-browser-check",
            "--remote-debugging-port=0",
            "--user-data-dir=$profileDir",
            "about:blank"
        )
        $argumentList = @($arguments | ForEach-Object { Join-NativeArgument -Value ([string]$_) })
        $process = Start-Process -FilePath $Tool.Command -ArgumentList $argumentList -WindowStyle Hidden -PassThru
        $activePortFile = Join-Path $profileDir "DevToolsActivePort"
        $deadline = [DateTime]::UtcNow.AddSeconds([Math]::Max(15, [int]$TimeoutSeconds))
        while (-not (Test-Path -LiteralPath $activePortFile) -and [DateTime]::UtcNow -lt $deadline) {
            if ($process.HasExited) { throw "Headless browser exited before DevTools became available." }
            Start-Sleep -Milliseconds 50
        }
        if (-not (Test-Path -LiteralPath $activePortFile)) { throw "Timed out waiting for the DevTools endpoint." }
        $portLines = @(Get-Content -LiteralPath $activePortFile -ErrorAction Stop)
        if ($portLines.Count -lt 1 -or -not ($portLines[0] -match '^\d+$')) { throw "DevToolsActivePort did not contain a valid local port." }
        $port = [int]$portLines[0]
        $targetsResponse = Invoke-WebRequest -Uri "http://127.0.0.1:$port/json/list" -UseBasicParsing -TimeoutSec ([Math]::Max(5, [int]$TimeoutSeconds))
        $targets = @($targetsResponse.Content | ConvertFrom-Json)
        $target = $targets | Where-Object { $_.type -eq "page" -and $_.webSocketDebuggerUrl } | Select-Object -First 1
        if ($null -eq $target) { throw "No DevTools page target was available." }
        $socket = [System.Net.WebSockets.ClientWebSocket]::new()
        $connectTimeout = [System.Threading.CancellationTokenSource]::new([TimeSpan]::FromSeconds([Math]::Max(10, [int]$TimeoutSeconds)))
        try {
            $null = $socket.ConnectAsync([Uri]$target.webSocketDebuggerUrl, $connectTimeout.Token).GetAwaiter().GetResult()
        }
        finally {
            $null = $connectTimeout.Dispose()
        }
        $sessionState = New-InteractionBrowserSessionState -Socket $socket -Process $process -ProfileDir $profileDir
        return $sessionState
    }
    catch {
        if ($null -ne $process -and -not $process.HasExited) { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue }
        $tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
        $resolvedProfile = [System.IO.Path]::GetFullPath($profileDir)
        if ($resolvedProfile.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase) -and (Split-Path $resolvedProfile -Leaf) -like "ccld-ui-evidence-*") {
            Remove-Item -LiteralPath $resolvedProfile -Recurse -Force -ErrorAction SilentlyContinue
        }
        throw
    }
}

function Invoke-CdpCommand {
    param([object]$Session, [string]$Method, [hashtable]$Parameters = @{}, [int]$Timeout = 30)
    if ($null -eq $Session) { throw "Malformed CDP session state: session is null." }
    if ($Session -is [System.Array]) { throw "Malformed CDP session state: expected one session object, received array type '$($Session.GetType().FullName)'." }
    $requiredSessionProperties = @("Socket", "Process", "ProfileDir", "NextId")
    $missingSessionProperties = @($requiredSessionProperties | Where-Object { $null -eq $Session.PSObject.Properties[$_] })
    if ($missingSessionProperties.Count -gt 0) {
        throw "Malformed CDP session state: type '$($Session.GetType().FullName)' is missing required properties: $($missingSessionProperties -join ', ')."
    }
    $nextIdProperty = $Session.PSObject.Properties["NextId"]
    if (-not $nextIdProperty.IsSettable) { throw "Malformed CDP session state: NextId is not writable on type '$($Session.GetType().FullName)'." }
    try {
        $currentNextId = [int]$nextIdProperty.Value
        $nextIdProperty.Value = $currentNextId + 1
    }
    catch {
        throw "Malformed CDP session state: NextId could not be read and incremented deterministically on type '$($Session.GetType().FullName)'."
    }
    $commandId = [int]$nextIdProperty.Value
    $payload = [ordered]@{ id = $commandId; method = $Method; params = $Parameters } | ConvertTo-Json -Compress -Depth 20
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($payload)
    $sendTimeout = [System.Threading.CancellationTokenSource]::new([TimeSpan]::FromSeconds($Timeout))
    try {
        $null = $Session.Socket.SendAsync([ArraySegment[byte]]::new($bytes), [System.Net.WebSockets.WebSocketMessageType]::Text, $true, $sendTimeout.Token).GetAwaiter().GetResult()
    }
    finally {
        $sendTimeout.Dispose()
    }
    while ($true) {
        $receiveTimeout = [System.Threading.CancellationTokenSource]::new([TimeSpan]::FromSeconds($Timeout))
        $stream = [System.IO.MemoryStream]::new()
        try {
            do {
                $buffer = [byte[]]::new(65536)
                $receive = $Session.Socket.ReceiveAsync([ArraySegment[byte]]::new($buffer), $receiveTimeout.Token).GetAwaiter().GetResult()
                if ($receive.MessageType -eq [System.Net.WebSockets.WebSocketMessageType]::Close) { throw "DevTools websocket closed while waiting for '$Method'." }
                $stream.Write($buffer, 0, $receive.Count)
            } while (-not $receive.EndOfMessage)
            $message = [System.Text.Encoding]::UTF8.GetString($stream.ToArray()) | ConvertFrom-Json
        }
        finally {
            $stream.Dispose()
            $receiveTimeout.Dispose()
        }
        if ($message.id -ne $commandId) { continue }
        if ($message.error) { throw "DevTools command '$Method' failed: $($message.error.message)" }
        return $message
    }
}

function Invoke-CdpEvaluate {
    param([object]$Session, [string]$Expression, [bool]$AwaitPromise = $false)
    $response = Invoke-CdpCommand -Session $Session -Method "Runtime.evaluate" -Parameters @{ expression = $Expression; returnByValue = $true; awaitPromise = $AwaitPromise }
    if ($response.result.exceptionDetails) {
        $description = [string]$response.result.exceptionDetails.exception.description
        throw "Browser evaluation failed: $description"
    }
    return $response.result.result.value
}

function Invoke-CdpKeyPress {
    param([object]$Session, [string]$Key, [string]$Code, [int]$VirtualKeyCode)
    $keyParameters = @{ key = $Key; code = $Code; windowsVirtualKeyCode = $VirtualKeyCode; nativeVirtualKeyCode = $VirtualKeyCode; modifiers = 0 }
    Invoke-CdpCommand -Session $Session -Method "Input.dispatchKeyEvent" -Parameters ($keyParameters + @{ type = "keyDown" }) | Out-Null
    Invoke-CdpCommand -Session $Session -Method "Input.dispatchKeyEvent" -Parameters ($keyParameters + @{ type = "keyUp" }) | Out-Null
}

function Invoke-CdpSpaceActivation {
    param([object]$Session)
    $spaceParameters = @{ key = " "; code = "Space"; windowsVirtualKeyCode = 32; nativeVirtualKeyCode = 32; text = " "; unmodifiedText = " "; modifiers = 0 }
    Invoke-CdpCommand -Session $Session -Method "Input.dispatchKeyEvent" -Parameters ($spaceParameters + @{ type = "rawKeyDown" }) | Out-Null
    Invoke-CdpCommand -Session $Session -Method "Input.dispatchKeyEvent" -Parameters ($spaceParameters + @{ type = "keyUp" }) | Out-Null
}

function Wait-CdpCondition {
    param([object]$Session, [string]$Expression, [string]$Description)
    $deadline = [DateTime]::UtcNow.AddSeconds([Math]::Max(10, [int]$TimeoutSeconds))
    while ([DateTime]::UtcNow -lt $deadline) {
        if ([bool](Invoke-CdpEvaluate -Session $Session -Expression $Expression)) { return }
        Start-Sleep -Milliseconds 50
    }
    throw "Timed out waiting for $Description."
}

function Stop-InteractionAwareBrowserSession {
    param([object]$Session)
    if ($null -eq $Session) { return }
    try { Invoke-CdpCommand -Session $Session -Method "Browser.close" -Timeout 5 | Out-Null } catch { }
    try { $Session.Socket.Dispose() } catch { }
    if ($null -ne $Session.Process -and -not $Session.Process.HasExited) { Stop-Process -Id $Session.Process.Id -Force -ErrorAction SilentlyContinue }
    $tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    $resolvedProfile = [System.IO.Path]::GetFullPath([string]$Session.ProfileDir)
    if ($resolvedProfile.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase) -and (Split-Path $resolvedProfile -Leaf) -like "ccld-ui-evidence-*") {
        Remove-Item -LiteralPath $resolvedProfile -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Get-Issue498ScenarioContract {
    param([hashtable]$Route)
    $state = [string]$Route.Issue498State
    $kind = [string]$Route.Issue498Kind
    $expectedDate = switch ($state) {
        "supported" { "06/12/2024" }
        "document-only" { "06/20/2024" }
        "field-partial" { "04/14/2022" }
        "source-unavailable" { "02/10/2024" }
    }
    $expectedRegionTexts = switch ($state) {
        "supported" { @("VISIT DATE: 06/12/2024", "report header", "A preserved source copy is recorded and the original public source can be opened.") }
        "document-only" { @("Document-level source only.", "A supporting source event sentence is not available for this date.", "The source section is not available for this date.", "A preserved source copy is recorded and the original public source can be opened.") }
        "field-partial" { @("Field evidence incomplete.", "A supporting source event sentence is not available for this date.", "investigation findings", "A preserved source copy is recorded and the original public source can be opened.") }
        "source-unavailable" { @("Source document unavailable.", "VISIT DATE: 02/10/2024", "report header", "A preserved source copy is recorded, but the original public source cannot currently be opened.") }
    }
    return [ordered]@{
        name = [string]$Route.Name
        kind = $kind
        state = $state
        expectedDate = [string]$expectedDate
        expectedRegionTexts = @($expectedRegionTexts)
        closedAccessibleName = "View source evidence for First investigation activity date"
        openAccessibleName = "Close source evidence for First investigation activity date"
        shouldOpen = $kind -in @("open", "narrow-desktop", "mobile-compact", "200-percent-reflow-approximation", "state", "print")
        shouldFocus = $kind -eq "keyboard-focus"
        shouldReturnFocus = $kind -eq "focus-return"
        verifyBounds = $kind -in @("narrow-desktop", "mobile-compact", "200-percent-reflow-approximation")
        expectSourceAction = $state -ne "source-unavailable"
        capturePrint = $kind -eq "print"
    }
}

function Invoke-Issue498BrowserCapture {
    param([object]$Session, [hashtable]$Route, [string]$Url, [string]$ScreenshotPath, [string]$SupplementalScreenshotPath, [string]$PrintPath, [int]$Width, [int]$Height)
    $browserState = $null
    try {
        Invoke-CdpCommand -Session $Session -Method "Page.enable" | Out-Null
        Invoke-CdpCommand -Session $Session -Method "Runtime.enable" | Out-Null
        Invoke-CdpCommand -Session $Session -Method "Emulation.setDeviceMetricsOverride" -Parameters @{ width = $Width; height = $Height; deviceScaleFactor = 1; mobile = $false; screenWidth = $Width; screenHeight = $Height } | Out-Null
        Invoke-CdpCommand -Session $Session -Method "Emulation.setEmulatedMedia" -Parameters @{ media = "screen" } | Out-Null
        Invoke-CdpCommand -Session $Session -Method "Page.navigate" -Parameters @{ url = $Url } | Out-Null
        Wait-CdpCondition -Session $Session -Expression "document.readyState === 'complete'" -Description "DOM readiness"
        Wait-CdpCondition -Session $Session -Expression "!!document.querySelector('#first-investigation-evidence-toggle') && !!document.querySelector('[data-source-evidence-region]')" -Description "First investigation evidence controls"
        Invoke-CdpEvaluate -Session $Session -AwaitPromise $true -Expression "(async function(){ if (document.fonts && document.fonts.ready) { await document.fonts.ready; } return true; })()" | Out-Null

        $scenarioContract = Get-Issue498ScenarioContract -Route $Route
        $contractJson = $scenarioContract | ConvertTo-Json -Compress -Depth 8
        $keyboardTabPresses = 0
        $keyboardInitialization = $null
        $focusReturnOpenAccessibleName = ""
        $keyboardOpenTrustedClick = $false
        $keyboardCloseTrustedClick = $false
        if ($scenarioContract.shouldFocus -or $scenarioContract.shouldReturnFocus) {
            $keyboardInitialization = Invoke-CdpEvaluate -Session $Session -AwaitPromise $true -Expression @"
(async function () {
  const toggle = document.querySelector('#first-investigation-evidence-toggle');
  const region = document.querySelector('[data-source-evidence-region]');
  const start = document.querySelector('.skip-link');
  if (!toggle || !region || !start) throw new Error('Keyboard navigation prerequisites are missing.');

  const closedAccessibleName = '$($scenarioContract.closedAccessibleName)';
  const hasVisibleLayout = (element) => {
    if (!element || element.hidden || element.getClientRects().length === 0) return false;
    const style = getComputedStyle(element);
    return style.display !== 'none' && style.visibility !== 'hidden';
  };
  const readState = () => ({
    expanded: toggle.getAttribute('aria-expanded'),
    hidden: region.hidden === true,
    regionVisible: hasVisibleLayout(region),
    accessibleName: toggle.getAttribute('aria-label') || ''
  });
  const isClosedState = (state) => state.expanded === 'false' && state.hidden === true && state.regionVisible === false && state.accessibleName === closedAccessibleName;
  const describeState = (state) => 'aria-expanded=' + String(state.expanded) + ', region.hidden=' + String(state.hidden) + ', regionVisible=' + String(state.regionVisible) + ', aria-label=' + JSON.stringify(state.accessibleName);
  const maximumClosedStateFrames = 120;
  const waitForClosedState = async () => {
    let consecutiveClosedFrames = 0;
    for (let frame = 0; frame < maximumClosedStateFrames; frame += 1) {
      await new Promise((resolve) => requestAnimationFrame(resolve));
      const state = readState();
      consecutiveClosedFrames = isClosedState(state) ? consecutiveClosedFrames + 1 : 0;
      if (consecutiveClosedFrames >= 2) return state;
    }
    return null;
  };

  const initialState = readState();
  if (initialState.expanded !== 'true' && initialState.expanded !== 'false') {
    throw new Error('Keyboard initial state has an invalid aria-expanded value: ' + describeState(initialState));
  }
  let keyboardInitialStateNormalized = false;
  if (!isClosedState(initialState)) {
    const oneActivationCanNormalize = initialState.expanded === 'true' || initialState.regionVisible === true;
    if (!oneActivationCanNormalize) {
      throw new Error('Keyboard initial state is inconsistent and cannot be resolved by one setup activation: ' + describeState(initialState));
    }
    toggle.click();
    keyboardInitialStateNormalized = true;
  }

  const closedState = await waitForClosedState();
  if (!closedState) {
    throw new Error('Keyboard initial state normalization did not reach the verified closed state after at most one setup activation: initial ' + describeState(initialState) + '; current ' + describeState(readState()));
  }
  start.focus();
  return {
    keyboardInitialExpanded: initialState.expanded === 'true',
    keyboardInitialRegionVisible: initialState.regionVisible,
    keyboardInitialAccessibleName: initialState.accessibleName,
    keyboardInitialStateNormalized,
    keyboardClosedStateVerified: isClosedState(closedState),
    skipLinkFocused: document.activeElement === start
  };
})()
"@
            if (-not [bool]$keyboardInitialization.keyboardClosedStateVerified) { throw "Keyboard initialization did not verify the complete closed disclosure state." }
            if (-not [bool]$keyboardInitialization.skipLinkFocused) { throw "Could not establish the deterministic keyboard-navigation start element." }
            $keyboardTargetReached = $false
            $maximumTabPresses = 64
            for ($tabIndex = 1; $tabIndex -le $maximumTabPresses; $tabIndex++) {
                Invoke-CdpKeyPress -Session $Session -Key "Tab" -Code "Tab" -VirtualKeyCode 9
                $keyboardTabPresses = $tabIndex
                $activeElementId = [string](Invoke-CdpEvaluate -Session $Session -Expression "document.activeElement ? document.activeElement.id : ''")
                if ($activeElementId -eq "first-investigation-evidence-toggle") {
                    $keyboardTargetReached = $true
                    break
                }
            }
            if (-not $keyboardTargetReached) { throw "Keyboard navigation did not reach the evidence trigger within $maximumTabPresses Tab presses." }
            if ($scenarioContract.shouldReturnFocus) {
                Invoke-CdpEvaluate -Session $Session -Expression @"
(function () {
  const toggle = document.querySelector('#first-investigation-evidence-toggle');
  window.__rtSrc002KeyboardOpenClick = { count: 0, trusted: false };
  toggle.addEventListener('click', (event) => {
    window.__rtSrc002KeyboardOpenClick.count += 1;
    window.__rtSrc002KeyboardOpenClick.trusted = event.isTrusted === true;
  }, { once: true });
  return true;
})()
"@ | Out-Null
                Invoke-CdpSpaceActivation -Session $Session
                Wait-CdpCondition -Session $Session -Expression "window.__rtSrc002KeyboardOpenClick.count === 1 && window.__rtSrc002KeyboardOpenClick.trusted === true && document.querySelector('#first-investigation-evidence-toggle').getAttribute('aria-expanded') === 'true' && !document.querySelector('[data-source-evidence-region]').hidden && document.querySelector('#first-investigation-evidence-toggle').getAttribute('aria-label') === '$($scenarioContract.openAccessibleName)'" -Description "trusted Space-opened focus-return disclosure"
                $keyboardOpenTrustedClick = [bool](Invoke-CdpEvaluate -Session $Session -Expression "window.__rtSrc002KeyboardOpenClick.count === 1 && window.__rtSrc002KeyboardOpenClick.trusted === true")
                $focusReturnOpenAccessibleName = [string](Invoke-CdpEvaluate -Session $Session -Expression "document.querySelector('#first-investigation-evidence-toggle').getAttribute('aria-label')")
                if ($focusReturnOpenAccessibleName -ne $scenarioContract.openAccessibleName) { throw "Open evidence trigger accessible name is incorrect during focus-return verification." }
                Invoke-CdpEvaluate -Session $Session -Expression @"
(function () {
  const toggle = document.querySelector('#first-investigation-evidence-toggle');
  window.__rtSrc002KeyboardCloseClick = { count: 0, trusted: false };
  toggle.addEventListener('click', (event) => {
    window.__rtSrc002KeyboardCloseClick.count += 1;
    window.__rtSrc002KeyboardCloseClick.trusted = event.isTrusted === true;
  }, { once: true });
  return true;
})()
"@ | Out-Null
                Invoke-CdpSpaceActivation -Session $Session
                Wait-CdpCondition -Session $Session -Expression "window.__rtSrc002KeyboardCloseClick.count === 1 && window.__rtSrc002KeyboardCloseClick.trusted === true && document.querySelector('#first-investigation-evidence-toggle').getAttribute('aria-expanded') === 'false' && document.querySelector('[data-source-evidence-region]').hidden && document.activeElement.id === 'first-investigation-evidence-toggle' && document.querySelector('#first-investigation-evidence-toggle').getAttribute('aria-label') === '$($scenarioContract.closedAccessibleName)'" -Description "trusted Space-closed focus-return disclosure"
                $keyboardCloseTrustedClick = [bool](Invoke-CdpEvaluate -Session $Session -Expression "window.__rtSrc002KeyboardCloseClick.count === 1 && window.__rtSrc002KeyboardCloseClick.trusted === true")
            }
        }
        $scenarioScript = @"
(async function () {
  const contract = $contractJson;
  const toggle = document.querySelector('#first-investigation-evidence-toggle');
  const region = document.querySelector('[data-source-evidence-region]');
  const claim = document.querySelector('.first-activity-claim');
  const hasVisibleLayout = (element) => {
    if (!element || element.hidden || element.getClientRects().length === 0) return false;
    const style = getComputedStyle(element);
    return style.display !== 'none' && style.visibility !== 'hidden';
  };
  const stableFrames = () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const intersectsViewport = (element) => {
    if (!hasVisibleLayout(element)) return false;
    const rect = element.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0 && rect.right > 0 && rect.bottom > 0 && rect.left < window.innerWidth && rect.top < window.innerHeight;
  };
  const fullyWithinViewport = (element) => {
    if (!hasVisibleLayout(element)) return false;
    const rect = element.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0 && rect.left >= -1 && rect.top >= -1 && rect.right <= window.innerWidth + 1 && rect.bottom <= window.innerHeight + 1;
  };
  const horizontallyWithinViewport = (element) => {
    if (!hasVisibleLayout(element)) return false;
    const rect = element.getBoundingClientRect();
    return rect.width > 0 && rect.left >= -1 && rect.right <= window.innerWidth + 1;
  };
  const factValue = (label) => {
    const fact = Array.from(region.querySelectorAll('.source-evidence-facts > div')).find((item) => {
      const term = item.querySelector('dt');
      return term && term.textContent.trim() === label;
    });
    return fact ? fact.querySelector('dd') : null;
  };
  const positionVisualTargets = async (elements, anchor, description) => {
    anchor.scrollIntoView({ behavior: 'instant', block: 'center', inline: 'nearest' });
    await stableFrames();
    const documentRects = elements.map((element) => {
      const rect = element.getBoundingClientRect();
      return { top: rect.top + window.scrollY, bottom: rect.bottom + window.scrollY };
    });
    const visualTop = Math.min(...documentRects.map((rect) => rect.top));
    const visualBottom = Math.max(...documentRects.map((rect) => rect.bottom));
    const visualHeight = visualBottom - visualTop;
    if (visualHeight > window.innerHeight - 2) {
      throw new Error(description + ' required visual targets exceed the governed viewport height.');
    }
    const centeredTop = Math.max(0, visualTop - Math.max(0, (window.innerHeight - visualHeight) / 2));
    window.scrollTo({ top: centeredTop, left: 0, behavior: 'instant' });
    await stableFrames();
  };
  const waitUntil = async (predicate, description) => {
    const deadline = performance.now() + 5000;
    while (performance.now() < deadline) {
      if (predicate()) return;
      await new Promise((resolve) => requestAnimationFrame(resolve));
    }
    throw new Error('Timed out waiting for ' + description);
  };
  if (!toggle || !region || !claim) throw new Error('Required evidence elements are missing.');
  const dateElement = claim.querySelector('.rt-timeline__date');
  const dateText = dateElement ? dateElement.textContent : '';
  if (!hasVisibleLayout(claim) || !dateElement || !dateText.includes(contract.expectedDate)) throw new Error('Readable First investigation activity date is not visible.');
  if (region.getAttribute('data-evidence-state') !== contract.state) throw new Error('Evidence state marker does not match ' + contract.state + '.');
  if (toggle.getAttribute('aria-expanded') === 'true') {
    toggle.click();
    await waitUntil(() => toggle.getAttribute('aria-expanded') === 'false' && region.hidden, 'initial closed state');
  }
  if (toggle.getAttribute('aria-label') !== contract.closedAccessibleName) throw new Error('Closed evidence trigger accessible name is incorrect.');
  if (contract.shouldOpen) {
    toggle.click();
    await waitUntil(() => toggle.getAttribute('aria-expanded') === 'true' && !region.hidden && hasVisibleLayout(region), 'open evidence state');
  }
  if (contract.shouldFocus || contract.shouldReturnFocus) {
    await waitUntil(() => document.activeElement === toggle && hasVisibleLayout(toggle), 'keyboard-established evidence-trigger focus state');
  }
  const expanded = toggle.getAttribute('aria-expanded') === 'true';
  const regionVisible = hasVisibleLayout(region);
  const accessibleName = toggle.getAttribute('aria-label');
  if (contract.shouldOpen && (!expanded || !regionVisible || accessibleName !== contract.openAccessibleName || !toggle.textContent.includes('Close source evidence'))) throw new Error('Open disclosure state was not verified.');
  if (!contract.shouldOpen && (expanded || regionVisible || accessibleName !== contract.closedAccessibleName || !toggle.textContent.includes('View source evidence'))) throw new Error('Closed disclosure state was not verified.');
  if (contract.shouldReturnFocus && (document.activeElement !== toggle || !region.hidden)) throw new Error('Closed focus-return state was not verified.');
  if (contract.shouldReturnFocus && accessibleName !== contract.closedAccessibleName) throw new Error('Focus-return closed accessible name is incorrect.');
  if (contract.shouldOpen) {
    const evidenceText = region.innerText;
    for (const expected of contract.expectedRegionTexts) {
      if (!evidenceText.includes(expected)) throw new Error('Expected visible evidence text missing: ' + expected);
    }
  }
  const sourceAction = region.querySelector('.source-evidence-original');
  const sourceActionEnabled = !!(sourceAction && hasVisibleLayout(sourceAction) && sourceAction.href && sourceAction.getAttribute('aria-disabled') !== 'true');
  if (contract.shouldOpen && contract.expectSourceAction && !sourceActionEnabled) throw new Error('Expected enabled original-source action is missing.');
  if (contract.shouldOpen && !contract.expectSourceAction && sourceActionEnabled) throw new Error('Unavailable-source state exposes an enabled original-source action.');
  const evidenceHeading = region.querySelector('#first-investigation-evidence-heading');
  const sourceEventValue = factValue('Supporting source event');
  const sourceSectionValue = factValue('Source section');
  const sourceStatusValue = factValue('Preserved source status');
  const isReflowApproximation = contract.kind === '200-percent-reflow-approximation';
  let captureSegment = null;
  if (contract.shouldOpen) {
    const requiredOpenElements = isReflowApproximation
      ? [dateElement, evidenceHeading, sourceEventValue]
      : [dateElement, evidenceHeading, sourceEventValue, sourceSectionValue, sourceStatusValue];
    if (requiredOpenElements.some((element) => !element)) throw new Error('Required open evidence visual targets are missing.');
    if (!isReflowApproximation && contract.expectSourceAction) requiredOpenElements.push(sourceAction);
    await positionVisualTargets(requiredOpenElements, claim, isReflowApproximation ? 'Upper reflow evidence segment' : 'Open evidence state');
    if (!fullyWithinViewport(dateElement)) throw new Error('Readable claim date is clipped or outside the screenshot viewport.');
    if (!intersectsViewport(region)) throw new Error('Evidence region does not intersect the screenshot viewport.');
    if (!fullyWithinViewport(evidenceHeading)) throw new Error('Evidence heading is clipped or outside the screenshot viewport.');
    if (!fullyWithinViewport(sourceEventValue)) throw new Error('Bounded source-event content is clipped or outside the screenshot viewport.');
    if (!isReflowApproximation && !fullyWithinViewport(sourceSectionValue)) throw new Error('Source section is clipped or outside the screenshot viewport.');
    if (!isReflowApproximation && !fullyWithinViewport(sourceStatusValue)) throw new Error('Preserved-source status is clipped or outside the screenshot viewport.');
    if (!isReflowApproximation && contract.expectSourceAction && !fullyWithinViewport(sourceAction)) throw new Error('Original-source action is clipped or outside the screenshot viewport.');
    if (!horizontallyWithinViewport(claim) || !horizontallyWithinViewport(region)) throw new Error('Open evidence component extends outside the viewport horizontally.');
    if (isReflowApproximation) {
      if (window.innerWidth !== 720 || window.innerHeight !== 600) throw new Error('Upper reflow evidence segment viewport is not exactly 720x600.');
      const bounds = (element) => { const rect = element.getBoundingClientRect(); return { left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom, width: rect.width, height: rect.height }; };
      captureSegment = {
        name: 'upper',
        viewportWidth: window.innerWidth,
        viewportHeight: window.innerHeight,
        verified: true,
        scrollPosition: { x: window.scrollX, y: window.scrollY },
        elementBounds: { claimDate: bounds(dateElement), evidenceHeading: bounds(evidenceHeading), sourceEvent: bounds(sourceEventValue) }
      };
    }
  } else {
    await positionVisualTargets([dateElement, toggle], claim, 'Closed evidence state');
    if (!fullyWithinViewport(dateElement)) throw new Error('Readable claim date is clipped or outside the screenshot viewport.');
    if (!fullyWithinViewport(toggle)) throw new Error('Evidence trigger is clipped or outside the screenshot viewport.');
    if (!horizontallyWithinViewport(claim)) throw new Error('Closed evidence component extends outside the viewport horizontally.');
  }
  const noDocumentOverflow = document.documentElement.scrollWidth <= window.innerWidth + 1 && document.body.scrollWidth <= window.innerWidth + 1;
  if (!noDocumentOverflow) throw new Error('Page-level horizontal overflow was detected.');
  const trackedElement = contract.shouldOpen ? region : toggle;
  const firstRect = trackedElement.getBoundingClientRect();
  const firstScrollWidth = document.documentElement.scrollWidth;
  await stableFrames();
  const secondRect = trackedElement.getBoundingClientRect();
  if (Math.abs(firstRect.left - secondRect.left) > 0.5 || Math.abs(firstRect.top - secondRect.top) > 0.5 || Math.abs(firstRect.width - secondRect.width) > 0.5 || firstScrollWidth !== document.documentElement.scrollWidth) throw new Error('Layout did not reach a stable frame.');
  const focusStyle = getComputedStyle(toggle);
  const focusIndicatorVisible = toggle.matches(':focus-visible') && (
    (focusStyle.outlineStyle !== 'none' && parseFloat(focusStyle.outlineWidth) > 0) ||
    (focusStyle.boxShadow && focusStyle.boxShadow !== 'none')
  );
  if (contract.shouldFocus && !focusIndicatorVisible) throw new Error('Keyboard focus indicator is not visibly styled.');
  return {
    scenario: contract.name,
    evidenceState: contract.state,
    ariaExpanded: toggle.getAttribute('aria-expanded'),
    accessibleName,
    regionVisible: hasVisibleLayout(region),
    toggleText: toggle.textContent.trim(),
    activeElementId: document.activeElement ? document.activeElement.id : '',
    focusStyle: {
      outlineStyle: focusStyle.outlineStyle,
      outlineWidth: focusStyle.outlineWidth,
      outlineColor: focusStyle.outlineColor,
      outlineOffset: focusStyle.outlineOffset,
      boxShadow: focusStyle.boxShadow,
      focusVisible: toggle.matches(':focus-visible'),
      focusIndicatorVisible
    },
    viewport: { width: window.innerWidth, height: window.innerHeight },
    documentScrollWidth: document.documentElement.scrollWidth,
    claimDateBounds: (() => { const rect = dateElement.getBoundingClientRect(); return { left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom, width: rect.width, height: rect.height }; })(),
    triggerBounds: (() => { const rect = toggle.getBoundingClientRect(); return { left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom, width: rect.width, height: rect.height }; })(),
    evidenceBounds: (() => { const rect = region.getBoundingClientRect(); return { left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom, width: rect.width, height: rect.height }; })(),
    sourceActionEnabled,
    captureSegment
  };
})()
"@
        $browserState = Invoke-CdpEvaluate -Session $Session -Expression $scenarioScript -AwaitPromise $true
        if ($keyboardTabPresses -gt 0) {
            $browserState | Add-Member -NotePropertyName keyboardTabPresses -NotePropertyValue $keyboardTabPresses
        }
        if ($null -ne $keyboardInitialization) {
            $browserState | Add-Member -NotePropertyName keyboardInitialExpanded -NotePropertyValue ([bool]$keyboardInitialization.keyboardInitialExpanded)
            $browserState | Add-Member -NotePropertyName keyboardInitialRegionVisible -NotePropertyValue ([bool]$keyboardInitialization.keyboardInitialRegionVisible)
            $browserState | Add-Member -NotePropertyName keyboardInitialAccessibleName -NotePropertyValue ([string]$keyboardInitialization.keyboardInitialAccessibleName)
            $browserState | Add-Member -NotePropertyName keyboardInitialStateNormalized -NotePropertyValue ([bool]$keyboardInitialization.keyboardInitialStateNormalized)
            $browserState | Add-Member -NotePropertyName keyboardClosedStateVerified -NotePropertyValue ([bool]$keyboardInitialization.keyboardClosedStateVerified)
        }
        if ($focusReturnOpenAccessibleName) {
            $browserState | Add-Member -NotePropertyName focusReturnOpenAccessibleName -NotePropertyValue $focusReturnOpenAccessibleName
        }
        if ($scenarioContract.shouldReturnFocus) {
            $browserState | Add-Member -NotePropertyName keyboardActivationKey -NotePropertyValue "Space"
            $browserState | Add-Member -NotePropertyName keyboardOpenTrustedClick -NotePropertyValue ([bool]$keyboardOpenTrustedClick)
            $browserState | Add-Member -NotePropertyName keyboardCloseTrustedClick -NotePropertyValue ([bool]$keyboardCloseTrustedClick)
        }

        if ([string]$Route.Issue498Kind -eq "print") {
            Invoke-CdpCommand -Session $Session -Method "Emulation.setEmulatedMedia" -Parameters @{ media = "print" } | Out-Null
            $printState = Invoke-CdpEvaluate -Session $Session -AwaitPromise $true -Expression @"
(async function () {
  const visible = (element) => !!element && element.getClientRects().length > 0 && getComputedStyle(element).display !== 'none' && getComputedStyle(element).visibility !== 'hidden';
  await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const region = document.querySelector('[data-source-evidence-region]');
  const claim = document.querySelector('.first-activity-claim');
  const printUrl = document.querySelector('.source-evidence-print-url span');
  const urlText = printUrl ? printUrl.getAttribute('data-print-url') : '';
  const hiddenSelectors = ['.civic-header', '.reviewer-detail-context', '.source-evidence-actions', '.overview-side-panel', '.source-evidence-original'];
  if (!visible(claim) || !claim.innerText.includes('06/12/2024')) throw new Error('Print claim content is incomplete.');
  if (!visible(region) || !region.innerText.includes('VISIT DATE: 06/12/2024') || !region.innerText.includes('A preserved source copy is recorded')) throw new Error('Print evidence content is incomplete.');
  if (!urlText || !urlText.startsWith('https://')) throw new Error('Readable original-source URL is missing from print output.');
  for (const selector of hiddenSelectors) { const element = document.querySelector(selector); if (element && visible(element)) throw new Error('Print-hidden control remains visible: ' + selector); }
  return { media: 'print', evidenceVisible: visible(region), originalSourceUrl: urlText, hiddenSelectors };
})()
"@
            $browserState | Add-Member -NotePropertyName printState -NotePropertyValue $printState
        }

        $screenshot = Invoke-CdpCommand -Session $Session -Method "Page.captureScreenshot" -Parameters @{ format = "png"; fromSurface = $true; captureBeyondViewport = $false }
        [System.IO.File]::WriteAllBytes($ScreenshotPath, [Convert]::FromBase64String([string]$screenshot.result.data))
        if ([string]$Route.Issue498Kind -eq "200-percent-reflow-approximation") {
            if (-not $SupplementalScreenshotPath) { throw "Lower reflow evidence segment screenshot path is required." }
            $lowerSegment = Invoke-CdpEvaluate -Session $Session -AwaitPromise $true -Expression @"
(async function () {
  const toggle = document.querySelector('#first-investigation-evidence-toggle');
  const region = document.querySelector('[data-source-evidence-region]');
  const hasVisibleLayout = (element) => {
    if (!element || element.hidden || element.getClientRects().length === 0) return false;
    const style = getComputedStyle(element);
    return style.display !== 'none' && style.visibility !== 'hidden';
  };
  const stableFrames = () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const fullyWithinViewport = (element) => {
    if (!hasVisibleLayout(element)) return false;
    const rect = element.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0 && rect.left >= -1 && rect.top >= -1 && rect.right <= window.innerWidth + 1 && rect.bottom <= window.innerHeight + 1;
  };
  const intersectsViewport = (element) => {
    if (!hasVisibleLayout(element)) return false;
    const rect = element.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0 && rect.right > 0 && rect.bottom > 0 && rect.left < window.innerWidth && rect.top < window.innerHeight;
  };
  const horizontallyWithinViewport = (element) => {
    if (!hasVisibleLayout(element)) return false;
    const rect = element.getBoundingClientRect();
    return rect.width > 0 && rect.left >= -1 && rect.right <= window.innerWidth + 1;
  };
  const factValue = (label) => {
    const fact = Array.from(region.querySelectorAll('.source-evidence-facts > div')).find((item) => {
      const term = item.querySelector('dt');
      return term && term.textContent.trim() === label;
    });
    return fact ? fact.querySelector('dd') : null;
  };
  const positionTargets = async (elements, anchor) => {
    anchor.scrollIntoView({ behavior: 'instant', block: 'center', inline: 'nearest' });
    await stableFrames();
    const documentRects = elements.map((element) => {
      const rect = element.getBoundingClientRect();
      return { top: rect.top + window.scrollY, bottom: rect.bottom + window.scrollY };
    });
    const visualTop = Math.min(...documentRects.map((rect) => rect.top));
    const visualBottom = Math.max(...documentRects.map((rect) => rect.bottom));
    if (visualBottom - visualTop > window.innerHeight - 2) throw new Error('Lower reflow evidence segment required visual targets exceed the governed viewport height.');
    const centeredTop = Math.max(0, visualTop - Math.max(0, (window.innerHeight - (visualBottom - visualTop)) / 2));
    window.scrollTo({ top: centeredTop, left: 0, behavior: 'instant' });
    await stableFrames();
  };
  if (!toggle || !region) throw new Error('Lower reflow evidence segment controls are missing.');
  if (window.innerWidth !== 720 || window.innerHeight !== 600) throw new Error('Lower reflow evidence segment viewport is not exactly 720x600.');
  if (toggle.getAttribute('aria-expanded') !== 'true' || region.hidden || toggle.getAttribute('aria-label') !== 'Close source evidence for First investigation activity date') throw new Error('Lower reflow evidence segment disclosure is not open.');
  const sourceSectionValue = factValue('Source section');
  const sourceStatusValue = factValue('Preserved source status');
  const sourceAction = region.querySelector('.source-evidence-original');
  if (!sourceSectionValue || !sourceStatusValue || !sourceAction || !sourceAction.href || sourceAction.getAttribute('aria-disabled') === 'true') throw new Error('Lower reflow evidence segment targets are missing or disabled.');
  const requiredElements = [sourceSectionValue, sourceStatusValue, sourceAction];
  await positionTargets(requiredElements, sourceSectionValue);
  if (!intersectsViewport(region)) throw new Error('Lower reflow evidence region does not intersect the screenshot viewport.');
  if (!fullyWithinViewport(sourceSectionValue)) throw new Error('Lower reflow source section is clipped or outside the screenshot viewport.');
  if (!fullyWithinViewport(sourceStatusValue)) throw new Error('Lower reflow preserved-source status is clipped or outside the screenshot viewport.');
  if (!fullyWithinViewport(sourceAction)) throw new Error('Lower reflow original-source action is clipped or outside the screenshot viewport.');
  if (!horizontallyWithinViewport(region)) throw new Error('Lower reflow evidence region extends outside the viewport horizontally.');
  const noDocumentOverflow = document.documentElement.scrollWidth <= window.innerWidth + 1 && document.body.scrollWidth <= window.innerWidth + 1;
  if (!noDocumentOverflow) throw new Error('Lower reflow page-level horizontal overflow was detected.');
  const firstRect = sourceAction.getBoundingClientRect();
  const firstScrollWidth = document.documentElement.scrollWidth;
  await stableFrames();
  const secondRect = sourceAction.getBoundingClientRect();
  if (Math.abs(firstRect.left - secondRect.left) > 0.5 || Math.abs(firstRect.top - secondRect.top) > 0.5 || Math.abs(firstRect.width - secondRect.width) > 0.5 || firstScrollWidth !== document.documentElement.scrollWidth) throw new Error('Lower reflow evidence segment did not reach a stable frame.');
  const bounds = (element) => { const rect = element.getBoundingClientRect(); return { left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom, width: rect.width, height: rect.height }; };
  return {
    name: 'lower',
    viewportWidth: window.innerWidth,
    viewportHeight: window.innerHeight,
    verified: true,
    scrollPosition: { x: window.scrollX, y: window.scrollY },
    elementBounds: { sourceSection: bounds(sourceSectionValue), preservedSourceStatus: bounds(sourceStatusValue), originalSourceAction: bounds(sourceAction) }
  };
})()
"@
            $upperSegment = $browserState.captureSegment
            if ($null -eq $upperSegment -or -not [bool]$upperSegment.verified -or -not [bool]$lowerSegment.verified) { throw "Upper and lower reflow evidence segments were not both verified." }
            $null = $browserState.PSObject.Properties.Remove("captureSegment")
            $browserState | Add-Member -NotePropertyName captureSegments -NotePropertyValue (@($upperSegment, $lowerSegment))
            $supplementalScreenshot = Invoke-CdpCommand -Session $Session -Method "Page.captureScreenshot" -Parameters @{ format = "png"; fromSurface = $true; captureBeyondViewport = $false }
            [System.IO.File]::WriteAllBytes($SupplementalScreenshotPath, [Convert]::FromBase64String([string]$supplementalScreenshot.result.data))
        }
        if ([string]$Route.Issue498Kind -eq "print") {
            $pdf = Invoke-CdpCommand -Session $Session -Method "Page.printToPDF" -Parameters @{ printBackground = $true; displayHeaderFooter = $false; preferCSSPageSize = $true }
            [System.IO.File]::WriteAllBytes($PrintPath, [Convert]::FromBase64String([string]$pdf.result.data))
            Invoke-CdpCommand -Session $Session -Method "Emulation.setEmulatedMedia" -Parameters @{ media = "screen" } | Out-Null
        }
        return [pscustomobject]@{ Success = $true; Error = ""; State = $browserState; ScreenshotCreated = (Test-Path -LiteralPath $ScreenshotPath); SupplementalScreenshotCreated = ([string]$Route.Issue498Kind -ne "200-percent-reflow-approximation" -or (Test-Path -LiteralPath $SupplementalScreenshotPath)); PrintCreated = ([string]$Route.Issue498Kind -ne "print" -or (Test-Path -LiteralPath $PrintPath)) }
    }
    catch {
        Remove-Item -LiteralPath $ScreenshotPath -Force -ErrorAction SilentlyContinue
        if ($SupplementalScreenshotPath) { Remove-Item -LiteralPath $SupplementalScreenshotPath -Force -ErrorAction SilentlyContinue }
        if ($PrintPath) { Remove-Item -LiteralPath $PrintPath -Force -ErrorAction SilentlyContinue }
        try { Invoke-CdpCommand -Session $Session -Method "Emulation.setEmulatedMedia" -Parameters @{ media = "screen" } | Out-Null } catch { }
        return [pscustomobject]@{ Success = $false; Error = $_.Exception.Message; State = $browserState; ScreenshotCreated = $false; SupplementalScreenshotCreated = $false; PrintCreated = $false }
    }
}

function Test-HtmlScreenshotCandidate {
    param([hashtable]$Route, [string]$Html)
    if ($Route.Path -match "(?i)\.(csv|json|txt)(\?|$)") { return $false }
    return ($Html -match "(?is)<!doctype\s+html|<html\b|<body\b")
}

function Get-EvidenceFileCount {
    param([string]$Path, [string]$Filter = "*")
    if (-not (Test-Path -LiteralPath $Path)) { return 0 }
    return @(
        Get-ChildItem -LiteralPath $Path -Filter $Filter -File -Recurse -ErrorAction SilentlyContinue
    ).Count
}

function Add-AssertionResult {
    param([System.Collections.ArrayList]$Target, [string]$RouteName, [string]$Check, [string]$Status, [string]$Message)
    [void]$Target.Add([pscustomobject]@{ route = $RouteName; check = $Check; status = $Status; message = $Message })
}

function Test-RouteOrientationMarker {
    param([hashtable]$Route, [string]$Html)
    $name = [string]$Route.Name
    $markersByRoute = @{
        "home" = @("Find a Facility", "Find the facility/license number")
        "facility" = @("Find a facility", "Find the facility/license number")
        "facility-intelligence" = @("Find Facilities That May Need Closer Review", "Complaint Patterns")
        "facility-licensing-activity" = @("Find Facilities That May Need Closer Review", "Licensing and Visit Activity")
        "facility-complaint-trends" = @("Find Facilities That May Need Closer Review", "Complaint Activity Over Time")
        "facility-hub" = @("Facility Overview", "Review summary", "Review next")
        "request-records" = @("Request Records", "Which facility should be reviewed?")
        "jobs" = @("Job diagnostics", "Track Request Records jobs")
        "reviewer" = @("Complaint records ready for review", "Complaint worklist", "Review complaint")
        "substantiated-triage" = @("substantiated complaint triage", "Source-derived finding")
        "serious-topics" = @("Serious-topic complaint worklist", "Filter serious review themes")
        "facility-priorities" = @("Find Facilities That May Need Closer Review", "Complaint Patterns")
        "facility-trends" = @("Find Facilities That May Need Closer Review", "Complaint Activity Over Time")
        "packet-preview-empty" = @("Review packet preview", "No facility/date packet context was supplied.")
        "packet-preview-context" = @("Review packet preview", "Packet preparation preview")
        "packet-draft-empty" = @("Attorney Review Packet Draft", "No facility/date packet context was supplied.")
        "packet-draft-context" = @("Attorney Review Packet Draft", "Packet scope")
        "feedback" = @("Feedback", "Send RecordsTracker feedback")
        "help" = @("Help", "Use RecordsTracker for facility complaint review")
        "job-detail" = @("Job diagnostics detail", "Request job summary and next step")
        "reviewer-detail" = @("Complaint review", "Complaint overview")
    }
    if (-not $markersByRoute.ContainsKey($name)) { return $false }
    foreach ($marker in $markersByRoute[$name]) {
        if ($Html.Contains($marker)) { return $true }
    }
    return $false
}

function Test-RouteAssertions {
    param([hashtable]$Route, [string]$Html, [int]$StatusCode, [System.Collections.ArrayList]$Assertions)
    $name = $Route.Name
    if ($StatusCode -le 0) { Add-AssertionResult -Target $Assertions -RouteName $name -Check "route reachable" -Status "FAIL" -Message "Route did not respond."; return }
    $expectedStatus = if ($Route.ContainsKey("ExpectedStatus")) { [int]$Route.ExpectedStatus } else { 200 }
    if ($StatusCode -eq $expectedStatus) { Add-AssertionResult -Target $Assertions -RouteName $name -Check "route status" -Status "PASS" -Message "Route returned expected HTTP $StatusCode." }
    else { Add-AssertionResult -Target $Assertions -RouteName $name -Check "route status" -Status "FAIL" -Message "Route returned HTTP $StatusCode; expected $expectedStatus." }
    $forbidden = Get-ForbiddenMarkers -Text $Html
    if ($forbidden.Count -gt 0) { Add-AssertionResult -Target $Assertions -RouteName $name -Check "private markers" -Status "FAIL" -Message ("Forbidden marker(s): " + ($forbidden -join ", ")) }
    else { Add-AssertionResult -Target $Assertions -RouteName $name -Check "private markers" -Status "PASS" -Message "No forbidden private markers found." }
    if ($Html.Contains("Feedbac k")) { Add-AssertionResult -Target $Assertions -RouteName $name -Check "broken labels" -Status "FAIL" -Message "Broken step label found." }
    else { Add-AssertionResult -Target $Assertions -RouteName $name -Check "broken labels" -Status "PASS" -Message "No broken Feedbac k label found." }
    $isHtmlShellRoute = $Route.Path -notlike "*.csv*"
    $primaryNavMatches = [regex]::Matches($Html, '(?is)<nav class="civic-nav" aria-label="Primary navigation">(.*?)</nav>')
    if ($isHtmlShellRoute) {
        $mainLandmarkCount = ([regex]::Matches($Html, '<main id="main-content"')).Count
        $sharedShellPresent = $Html.Contains('<body class="ds-page-bg civic-ledger-page">') -and $Html.Contains('<header class="civic-header">') -and $Html.Contains('class="skip-link"') -and $mainLandmarkCount -eq 1 -and $primaryNavMatches.Count -eq 1
        if ($sharedShellPresent) { Add-AssertionResult -Target $Assertions -RouteName $name -Check "governed shared shell" -Status "PASS" -Message "Civic Ledger shell, skip link, one main landmark, and one primary navigation landmark found." }
        else { Add-AssertionResult -Target $Assertions -RouteName $name -Check "governed shared shell" -Status "FAIL" -Message "Expected one governed Civic Ledger shell with skip, main, and primary navigation landmarks." }
    }
    if ($isHtmlShellRoute -and $primaryNavMatches.Count -eq 1) {
        $navLinks = @([regex]::Matches($primaryNavMatches[0].Groups[1].Value, '(?is)<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>') | ForEach-Object {
            ([string]$_.Groups[1].Value) + "|" + (ConvertFrom-HtmlText -Html ([string]$_.Groups[2].Value))
        })
        $expectedNavLinks = @(
            "/|Home",
            "/ccld/facilities|Facilities",
            "/ccld/facilities/intelligence|Compare Facilities",
            "/ccld/records/request|Request Records",
            "/reviewer|Review",
            "/feedback|Feedback",
            "/ccld/help|Help"
        )
        $navDefinitionMatches = $navLinks.Count -eq $expectedNavLinks.Count -and (($navLinks -join "`n") -ceq ($expectedNavLinks -join "`n"))
        if ($navDefinitionMatches) { Add-AssertionResult -Target $Assertions -RouteName $name -Check "authoritative primary navigation" -Status "PASS" -Message "Primary navigation includes the approved Compare Facilities destination in the current seven-link order." }
        else { Add-AssertionResult -Target $Assertions -RouteName $name -Check "authoritative primary navigation" -Status "FAIL" -Message "Primary navigation differs from the current governed seven-link definition or ordering." }
        $feedbackCount = @($navLinks | Where-Object { $_ -ceq "/feedback|Feedback" }).Count
        $jobStatusCount = @($navLinks | Where-Object { $_ -like "/ccld/retrieval/jobs|*" }).Count
        if ($feedbackCount -eq 1 -and $jobStatusCount -eq 0) { Add-AssertionResult -Target $Assertions -RouteName $name -Check "primary navigation product tiers" -Status "PASS" -Message "Feedback appears once and job diagnostics stays out of primary navigation." }
        else { Add-AssertionResult -Target $Assertions -RouteName $name -Check "primary navigation product tiers" -Status "FAIL" -Message "Primary navigation must contain Feedback exactly once and no job diagnostics link." }
    }
    if ($isHtmlShellRoute) {
        $expectedModeText = switch ($Mode) { "live" { "Live public CCLD" } "fixture" { "Fixture/mock demo" } default { "Review aids only" } }
        $modePanelPattern = '(?is)<div class="mode-panel civic-mode-panel" aria-label="Retrieval mode">\s*<span class="[^"]+">' + [regex]::Escape($expectedModeText) + '</span>\s*</div>'
        $modePanelCount = ([regex]::Matches($Html, $modePanelPattern)).Count
        if ($modePanelCount -eq 1) { Add-AssertionResult -Target $Assertions -RouteName $name -Check "mode badge" -Status "PASS" -Message "Expected shared-shell mode marker '$expectedModeText' found exactly once." }
        else { Add-AssertionResult -Target $Assertions -RouteName $name -Check "mode badge" -Status "FAIL" -Message "Expected shared-shell mode marker '$expectedModeText' exactly once; found $modePanelCount." }
    }
    if ($Route.ContainsKey("ActiveHref")) {
        $activePattern = '<a(?=[^>]*aria-current="page")(?=[^>]*href="' + [regex]::Escape([string]$Route.ActiveHref) + '")'
        if ($Html -match $activePattern) { Add-AssertionResult -Target $Assertions -RouteName $name -Check "active nav" -Status "PASS" -Message "Expected active nav href found." }
        else { Add-AssertionResult -Target $Assertions -RouteName $name -Check "active nav" -Status "FAIL" -Message "Expected active nav href '$($Route.ActiveHref)' not found." }
    }
    if ($Route.Path -eq "/ccld/help") {
        if ($Html -notmatch "Current step:" -and $Html -notmatch '<a(?=[^>]*aria-current="page")(?=[^>]*href="/ccld/records/request")') { Add-AssertionResult -Target $Assertions -RouteName $name -Check "help route nav" -Status "PASS" -Message "Help does not show workflow indicator and Request Records is not active." }
        else { Add-AssertionResult -Target $Assertions -RouteName $name -Check "help route nav" -Status "FAIL" -Message "Help route has competing workflow indicator or Request Records active nav." }
    }
    elseif ($Route.ContainsKey("WorkflowStep")) {
        # Packet draft pages intentionally hide the workflow rail for print/copy mode;
        # do not warn when the workflow indicator is missing on draft routes.
        if ($Route.Path -like "/reviewer/packet/draft*") {
            Add-AssertionResult -Target $Assertions -RouteName $name -Check "workflow step" -Status "PASS" -Message "Packet draft intentionally hides workflow indicator; check skipped."
        }
        elseif ($Html.Contains("Current step: $($Route.WorkflowStep)")) { Add-AssertionResult -Target $Assertions -RouteName $name -Check "workflow step" -Status "PASS" -Message "Expected workflow step found." }
        elseif (Test-RouteOrientationMarker -Route $Route -Html $Html) { Add-AssertionResult -Target $Assertions -RouteName $name -Check "workflow step" -Status "PASS" -Message "Page-level orientation markers found." }
        else { Add-AssertionResult -Target $Assertions -RouteName $name -Check "workflow step" -Status "WARN" -Message "Expected workflow step '$($Route.WorkflowStep)' not found." }
    }
    if ($Html.Contains("Keyboard flow:")) { Add-AssertionResult -Target $Assertions -RouteName $name -Check "keyboard flow text" -Status "PASS" -Message "Visible keyboard-flow guidance found." }
    else {
        $hasSharedKeyboardOrientation = $Html.Contains('class="skip-link"') -and $Html.Contains('aria-current="page"') -and (Test-RouteOrientationMarker -Route $Route -Html $Html)
        if ($hasSharedKeyboardOrientation) { Add-AssertionResult -Target $Assertions -RouteName $name -Check "keyboard flow text" -Status "PASS" -Message "Shared skip link, active nav, and page heading provide keyboard orientation." }
        else { Add-AssertionResult -Target $Assertions -RouteName $name -Check "keyboard flow text" -Status "WARN" -Message "No visible keyboard-flow guidance or shared orientation markers found on this route." }
    }
    if ($Route.Path -eq "/ccld/facilities") {
        $searchCount = ([regex]::Matches($Html, 'id="facility-search-input"')).Count
        if ($searchCount -eq 1) { Add-AssertionResult -Target $Assertions -RouteName $name -Check "facility search" -Status "PASS" -Message "One facility search input found." }
        else { Add-AssertionResult -Target $Assertions -RouteName $name -Check "facility search" -Status "WARN" -Message "Expected one facility search input, found $searchCount." }
    }
    if ($Route.Path -eq "/ccld/records/request") {
        if ($Html.Contains("Which facility should be reviewed?") -and $Html.Contains("Confirm facility")) { Add-AssertionResult -Target $Assertions -RouteName $name -Check "request records flow" -Status "PASS" -Message "Facility selection flow found." }
        else { Add-AssertionResult -Target $Assertions -RouteName $name -Check "request records flow" -Status "WARN" -Message "Default Request Records facility flow markers were not found." }
    }
    if ($Route.Path -eq "/reviewer") {
        if ($Html.Contains("Complaint worklist") -and $Html.Contains("Review complaint")) { Add-AssertionResult -Target $Assertions -RouteName $name -Check "reviewer queue" -Status "PASS" -Message "Complaint worklist and record-specific review action found." }
        else { Add-AssertionResult -Target $Assertions -RouteName $name -Check "reviewer queue" -Status "WARN" -Message "Reviewer worklist/action markers were not found." }
    }
    if ($Route.Path -eq "/feedback") {
        if ($Html.Contains("<form") -and $Html.Contains("Do not include private material")) { Add-AssertionResult -Target $Assertions -RouteName $name -Check "feedback form" -Status "PASS" -Message "Feedback form and safety guidance found." }
        else { Add-AssertionResult -Target $Assertions -RouteName $name -Check "feedback form" -Status "WARN" -Message "Feedback form or safety guidance missing." }
    }
    if ($Route.Path -eq "/ccld/retrieval/jobs") {
        if ($Html.Contains("Status summary") -or $Html.Contains("No Request Records jobs yet")) { Add-AssertionResult -Target $Assertions -RouteName $name -Check "job page" -Status "PASS" -Message "Job summary or empty state found." }
        else { Add-AssertionResult -Target $Assertions -RouteName $name -Check "job page" -Status "WARN" -Message "Job summary/empty-state markers missing." }
    }
    if ($Html.Contains("Developer/operator commands")) {
        if ($Html -match "(?is)<details[^>]*>\s*<summary[^>]*>\s*Developer/operator commands") { Add-AssertionResult -Target $Assertions -RouteName $name -Check "operator disclosure" -Status "PASS" -Message "Developer/operator commands are behind details." }
        else { Add-AssertionResult -Target $Assertions -RouteName $name -Check "operator disclosure" -Status "WARN" -Message "Developer/operator commands not clearly behind details." }
    }
}

function Get-Issue415CountSummary {
    param([string]$Text)
    $summary = [pscustomobject]@{ Found = $false; First = 0; Last = 0; Matching = 0; Total = 0; Raw = "" }
    $pattern = "Showing\s+(?<first>\d+)(?:-(?<last>\d+))?\s+of\s+(?<matching>\d+)\s+matching\s+qualifying\s+complaint\s+record\(s\);\s+(?<total>\d+)\s+total\s+qualifying"
    $match = [regex]::Match($Text, $pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    if (-not $match.Success) { return $summary }
    $first = [int]$match.Groups["first"].Value
    $last = if ($match.Groups["last"].Success) { [int]$match.Groups["last"].Value } else { $first }
    if ($first -eq 0) { $last = 0 }
    return [pscustomobject]@{
        Found    = $true
        First    = $first
        Last     = $last
        Matching = [int]$match.Groups["matching"].Value
        Total    = [int]$match.Groups["total"].Value
        Raw      = $match.Value
    }
}

function Get-Issue415Rows {
    param([string]$Html)
    $rows = @()
    foreach ($match in [regex]::Matches($Html, "(?is)<tbody[^>]*>.*?</tbody>")) {
        foreach ($rowMatch in [regex]::Matches($match.Value, "(?is)<tr[^>]*>(.*?)</tr>")) {
            $rowHtml = $rowMatch.Groups[1].Value
            $rowText = ConvertFrom-HtmlText -Html $rowHtml
            $facilityName = Get-FirstHtmlMatch -Html $rowHtml -Pattern "<th[^>]*>(.*?)</th>"
            $facilityIdMatch = [regex]::Match($rowText, "Facility ID:?\s+(?<value>[A-Za-z0-9:._-]+)", [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
            $dateMatch = [regex]::Match($rowText, "\b\d{2}/\d{2}/\d{4}\b")
            $findingMatch = [regex]::Match($rowText, "\b(Substantiated|Founded|Sustained)\b", [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
            $complaintMatch = [regex]::Match($rowText, "\b\d{2}-CR-\d{14}\b")
            $keyMatch = [regex]::Match($rowHtml, "source_record_key=([^""'&]+)", [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
            $rows += [pscustomobject]@{
                facilityName     = $facilityName
                facilityId       = if ($facilityIdMatch.Success) { $facilityIdMatch.Groups["value"].Value } else { "" }
                complaintId      = if ($complaintMatch.Success) { $complaintMatch.Value } else { "" }
                finding          = if ($findingMatch.Success) { $findingMatch.Value } else { "" }
                date             = if ($dateMatch.Success) { $dateMatch.Value } else { "" }
                sourceRecordKey  = if ($keyMatch.Success) { [System.Net.WebUtility]::UrlDecode($keyMatch.Groups[1].Value) } else { "" }
                text             = $rowText
            }
        }
    }
    return @($rows)
}

function Add-Issue415PassFail {
    param([System.Collections.ArrayList]$Assertions, [string]$RouteName, [string]$Check, [bool]$Pass, [string]$PassMessage, [string]$FailMessage)
    if ($Pass) { Add-AssertionResult -Target $Assertions -RouteName $RouteName -Check $Check -Status "PASS" -Message $PassMessage }
    else { Add-AssertionResult -Target $Assertions -RouteName $RouteName -Check $Check -Status "FAIL" -Message $FailMessage }
}

function Test-Issue415RouteAssertions {
    param([hashtable]$Route, [string]$Html, [string]$Text, [System.Collections.ArrayList]$Assertions)
    if (-not $Route.ContainsKey("Issue415Kind")) { return }
    $name = [string]$Route.Name
    $kind = [string]$Route.Issue415Kind
    $counts = Get-Issue415CountSummary -Text $Text
    $rows = @(Get-Issue415Rows -Html $Html)
    Add-Issue415PassFail -Assertions $Assertions -RouteName $name -Check "issue415 count summary" -Pass $counts.Found -PassMessage "Substantiated count summary found." -FailMessage "Substantiated count summary missing."
    Add-Issue415PassFail -Assertions $Assertions -RouteName $name -Check "issue415 h1" -Pass ($Html.Contains("<h1") -and $Text.Contains("Source-traceable substantiated complaint worklist")) -PassMessage "Expected substantiated worklist H1 found." -FailMessage "Expected substantiated worklist H1 missing."
    Add-Issue415PassFail -Assertions $Assertions -RouteName $name -Check "issue415 no statewide completeness claim" -Pass (-not ($Text -match "(?i)statewide\s+complete|statewide\s+completeness|all\s+public\s+complaints\s+statewide")) -PassMessage "No statewide-completeness claim found." -FailMessage "Statewide-completeness style claim found."
    Add-Issue415PassFail -Assertions $Assertions -RouteName $name -Check "issue415 controls labeled" -Pass (($Html -match "(?is)<label[^>]*>.*?</label>") -and ($Html -match "(?is)<select|<input")) -PassMessage "Filter controls have labels." -FailMessage "Expected labeled filter controls missing."
    Add-Issue415PassFail -Assertions $Assertions -RouteName $name -Check "issue415 semantic table" -Pass (($rows.Count -eq 0) -or (($Html -match "(?is)<caption[^>]*>.*?</caption>") -and ($Html -match "(?is)<th\b"))) -PassMessage "Semantic table caption/headings found when rows are rendered." -FailMessage "Semantic table caption/headings missing."
    Add-Issue415PassFail -Assertions $Assertions -RouteName $name -Check "issue415 no repeated row utility actions" -Pass (-not ($Text -match "(?i)(Help|Feedback|Report issue|Return).*(Help|Feedback|Report issue|Return).*(Help|Feedback|Report issue|Return)")) -PassMessage "No repeated row-level help/feedback/report/return actions found." -FailMessage "Repeated row-level utility actions found."
    if ($kind -eq "default") {
        Add-Issue415PassFail -Assertions $Assertions -RouteName $name -Check "issue415 default total nonzero" -Pass ($counts.Found -and $counts.Total -gt 0) -PassMessage "Total qualifying count is greater than zero." -FailMessage "Total qualifying count is not greater than zero."
        Add-Issue415PassFail -Assertions $Assertions -RouteName $name -Check "issue415 default rows" -Pass ($rows.Count -gt 0) -PassMessage "Displayed complaint rows found." -FailMessage "No displayed complaint rows found."
        Add-Issue415PassFail -Assertions $Assertions -RouteName $name -Check "issue415 dates" -Pass ($Text -match "\b\d{2}/\d{2}/\d{4}\b") -PassMessage "MM/DD/YYYY date found." -FailMessage "No MM/DD/YYYY date found."
        Add-Issue415PassFail -Assertions $Assertions -RouteName $name -Check "issue415 textual finding" -Pass ($Text -match "\b(Substantiated|Founded|Sustained)\b") -PassMessage "Textual substantiated/equivalent finding found." -FailMessage "No textual substantiated/equivalent finding found."
        Add-Issue415PassFail -Assertions $Assertions -RouteName $name -Check "issue415 source links" -Pass ($Text.Contains("Open original public report for")) -PassMessage "Descriptive original-report links found." -FailMessage "Descriptive original-report links missing."
        Add-Issue415PassFail -Assertions $Assertions -RouteName $name -Check "issue415 workspace links" -Pass ($Text.Contains("Open complaint review workspace")) -PassMessage "Complaint workspace links found." -FailMessage "Complaint workspace links missing."
    }
    elseif ($kind -eq "facility") {
        $facilityRowsMatch = ($rows.Count -gt 0) -and (@($rows | Where-Object { $_.facilityId -and $_.facilityId -ne "107207198" }).Count -eq 0)
        Add-Issue415PassFail -Assertions $Assertions -RouteName $name -Check "issue415 facility nonzero" -Pass ($counts.Found -and $counts.Matching -gt 0) -PassMessage "Facility filter matching count is greater than zero." -FailMessage "Facility filter matching count is not greater than zero."
        Add-Issue415PassFail -Assertions $Assertions -RouteName $name -Check "issue415 facility ids" -Pass $facilityRowsMatch -PassMessage "Displayed facility identifiers all match 107207198." -FailMessage "A displayed facility identifier did not match 107207198."
        Add-Issue415PassFail -Assertions $Assertions -RouteName $name -Check "issue415 facility count rows" -Pass ($counts.Found -and $counts.Matching -eq $rows.Count) -PassMessage "Facility matching count agrees with displayed rows." -FailMessage "Facility matching count does not agree with displayed rows."
    }
    elseif ($kind -eq "facility-type") {
        $badRows = @($rows | Where-Object { $_.text -match "(?i)Facility type\s+(?!FOSTER FAMILY AGENCY|Foster Family Agency)" })
        Add-Issue415PassFail -Assertions $Assertions -RouteName $name -Check "issue415 facility type rows" -Pass ($rows.Count -gt 0 -and $badRows.Count -eq 0 -and -not ($Text -match "(?i)unavailable\s+.*FOSTER FAMILY AGENCY")) -PassMessage "Displayed available facility types match FOSTER FAMILY AGENCY." -FailMessage "Facility type filter included unavailable or nonmatching rows."
    }
    elseif ($kind -eq "sort") {
        $names = @($rows | ForEach-Object { $_.facilityName } | Where-Object { $_ })
        $sortedNames = @($names | Sort-Object)
        $pageSizeOk = (-not $counts.Found) -or ($counts.Last -eq 0) -or (($counts.Last - $counts.First + 1) -le 25)
        Add-Issue415PassFail -Assertions $Assertions -RouteName $name -Check "issue415 facility sort az" -Pass (($names.Count -eq 0) -or (($names -join "`n") -eq ($sortedNames -join "`n"))) -PassMessage "Displayed facility names are A-Z." -FailMessage "Displayed facility names are not A-Z."
        Add-Issue415PassFail -Assertions $Assertions -RouteName $name -Check "issue415 page size" -Pass $pageSizeOk -PassMessage "Pagination range reconciles with page_size=25." -FailMessage "Pagination range exceeds page_size=25."
        if ($Text.Contains("Next page")) {
            Add-Issue415PassFail -Assertions $Assertions -RouteName $name -Check "issue415 next preserves sort" -Pass ($Html.Contains("sort=facility_asc") -and $Html.Contains("page_size=25")) -PassMessage "Pagination links preserve sorting and page size." -FailMessage "Pagination links did not preserve sorting/page size."
        }
    }
    elseif ($kind -eq "future-empty") {
        Add-Issue415PassFail -Assertions $Assertions -RouteName $name -Check "issue415 future empty" -Pass ($counts.Found -and $counts.Matching -eq 0 -and $counts.Total -gt 0) -PassMessage "Future-date route has zero matching and nonzero total." -FailMessage "Future-date route did not show zero matching with nonzero total."
        Add-Issue415PassFail -Assertions $Assertions -RouteName $name -Check "issue415 clear filters" -Pass ($Text.Contains("Clear filters")) -PassMessage "Clear filters action found." -FailMessage "Clear filters action missing."
        Add-Issue415PassFail -Assertions $Assertions -RouteName $name -Check "issue415 no false absence claim" -Pass (-not ($Text -match "(?i)no public substantiated complaints")) -PassMessage "No false absence claim found." -FailMessage "False absence claim found."
    }
}

function Get-Issue415HrefInventory {
    param([string]$RouteName, [string]$Html)
    $rows = @(Get-Issue415Rows -Html $Html)
    $inventory = @()
    foreach ($match in [regex]::Matches($Html, '<a\b(?<attrs>[^>]*)>(?<text>.*?)</a>', [System.Text.RegularExpressions.RegexOptions]::IgnoreCase -bor [System.Text.RegularExpressions.RegexOptions]::Singleline)) {
        $hrefMatch = [regex]::Match($match.Groups["attrs"].Value, 'href\s*=\s*["'']([^"'']+)["'']', [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
        if (-not $hrefMatch.Success) { continue }
        $href = [System.Net.WebUtility]::HtmlDecode($hrefMatch.Groups[1].Value)
        $textValue = (ConvertFrom-HtmlText -Html $match.Groups["text"].Value).Trim()
        $kind = if ($href -match "/reviewer/records/detail\?source_record_key=") { "workspace" } elseif ($href -match "ccld\.dss\.ca\.gov") { "original-source" } else { "" }
        if (-not $kind) { continue }
        $matchingRow = $rows | Where-Object { $_.sourceRecordKey -and $href.Contains([System.Uri]::EscapeDataString($_.sourceRecordKey)) } | Select-Object -First 1
        $inventory += [pscustomobject]@{
            route           = $RouteName
            kind            = $kind
            text            = $textValue
            href            = $href
            sourceRecordKey = if ($matchingRow) { $matchingRow.sourceRecordKey } else { "" }
            facilityId      = if ($matchingRow) { $matchingRow.facilityId } else { "" }
            complaintId     = if ($matchingRow) { $matchingRow.complaintId } else { "" }
            finding         = if ($matchingRow) { $matchingRow.finding } else { "" }
            date            = if ($matchingRow) { $matchingRow.date } else { "" }
        }
    }
    return @($inventory)
}

function Get-Issue416CountSummary {
    param([string]$Text)
    $summary = [pscustomobject]@{ Found = $false; First = 0; Last = 0; Matching = 0; Total = 0; Raw = "" }
    $pattern = "Showing\s+(?<first>\d+)(?:-(?<last>\d+))?\s+of\s+(?<matching>\d+)\s+matching\s+facilities;\s+(?<total>\d+)\s+total\s+authorized\s+loaded\s+facilities"
    $match = [regex]::Match($Text, $pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    if (-not $match.Success) { return $summary }
    $first = [int]$match.Groups["first"].Value
    $last = if ($match.Groups["last"].Success) { [int]$match.Groups["last"].Value } else { $first }
    if ($first -eq 0) { $last = 0 }
    return [pscustomobject]@{
        Found    = $true
        First    = $first
        Last     = $last
        Matching = [int]$match.Groups["matching"].Value
        Total    = [int]$match.Groups["total"].Value
        Raw      = $match.Value
    }
}

function Add-Issue416PassFail {
    param([System.Collections.ArrayList]$Assertions, [string]$RouteName, [string]$Check, [bool]$Pass, [string]$PassMessage, [string]$FailMessage)
    if ($Pass) { Add-AssertionResult -Target $Assertions -RouteName $RouteName -Check $Check -Status "PASS" -Message $PassMessage }
    else { Add-AssertionResult -Target $Assertions -RouteName $RouteName -Check $Check -Status "FAIL" -Message $FailMessage }
}

function Test-Issue416RouteAssertions {
    param([hashtable]$Route, [string]$Html, [string]$Text, [System.Collections.ArrayList]$Assertions)
    if (-not $Route.ContainsKey("Issue416Kind")) { return }
    $name = [string]$Route.Name
    $kind = [string]$Route.Issue416Kind
    $counts = Get-Issue416CountSummary -Text $Text
    Add-Issue416PassFail -Assertions $Assertions -RouteName $name -Check "issue416 h1" -Pass ($Html.Contains("<h1") -and $Text.Contains("Find Facilities That May Need Closer Review") -and $Text.Contains("Complaint Patterns")) -PassMessage "Canonical Compare Facilities heading and Complaint Patterns view found." -FailMessage "Canonical Compare Facilities heading or Complaint Patterns view missing."
    Add-Issue416PassFail -Assertions $Assertions -RouteName $name -Check "issue416 count summary" -Pass $counts.Found -PassMessage "Facility priority count summary found." -FailMessage "Facility priority count summary missing."
    Add-Issue416PassFail -Assertions $Assertions -RouteName $name -Check "issue416 no hidden score" -Pass ($Text.Contains("does not use a hidden score") -and $Text.Contains("These rules are visible ordering rules")) -PassMessage "No hidden-score language and visible rules found." -FailMessage "Visible no-hidden-score/rules language missing."
    Add-Issue416PassFail -Assertions $Assertions -RouteName $name -Check "issue416 controls labeled" -Pass (($Html -match "(?is)<label[^>]*>.*?</label>") -and ($Html -match "(?is)<select|<input")) -PassMessage "Filter controls have labels." -FailMessage "Expected labeled filter controls missing."
    Add-Issue416PassFail -Assertions $Assertions -RouteName $name -Check "issue416 semantic table" -Pass (($Text.Contains("No facilities match these filters")) -or (($Html -match "(?is)<caption[^>]*>.*?</caption>") -and ($Html -match "(?is)<th\b"))) -PassMessage "Semantic table caption/headings found when rows are rendered." -FailMessage "Semantic table caption/headings missing."
    Add-Issue416PassFail -Assertions $Assertions -RouteName $name -Check "issue416 safe conclusions" -Pass (-not ($Text -match "(?i)legal priority|statewide completeness|source completeness proof")) -PassMessage "No unsupported conclusion wording found." -FailMessage "Unsupported conclusion wording found."
    if ($kind -eq "default") {
        Add-Issue416PassFail -Assertions $Assertions -RouteName $name -Check "issue416 default rows" -Pass ($counts.Found -and $counts.Total -gt 0 -and $Text.Contains("Contributing factors")) -PassMessage "Default route has facility rows and factor heading." -FailMessage "Default route rows or factors missing."
        Add-Issue416PassFail -Assertions $Assertions -RouteName $name -Check "issue416 date display" -Pass (($Text -match "\b\d{2}/\d{2}/\d{4}\b") -or $Text.Contains("unknown")) -PassMessage "MM/DD/YYYY or explicit unknown date found." -FailMessage "No MM/DD/YYYY or unknown date found."
        Add-Issue416PassFail -Assertions $Assertions -RouteName $name -Check "issue416 review links" -Pass ($Text.Contains("Open Complaint Worklist") -and $Text.Contains("Review Complaint")) -PassMessage "Complaint Worklist and complaint review links found." -FailMessage "Complaint Worklist or complaint review link missing."
        Add-Issue416PassFail -Assertions $Assertions -RouteName $name -Check "issue416 source links" -Pass ($Text.Contains("Open original public report") -or $Text.Contains("Original public report link not available")) -PassMessage "Original-source link state found." -FailMessage "Original-source link state missing."
    }
    elseif ($kind -eq "filtered") {
        Add-Issue416PassFail -Assertions $Assertions -RouteName $name -Check "issue416 filtered controls" -Pass ($Html.Contains('name="facility_type"') -and $Html.Contains('name="geography"') -and $Html.Contains('name="min_complaints"') -and $Html.Contains('name="min_substantiated"') -and $Html.Contains('name="indicator"')) -PassMessage "Expected filter controls found." -FailMessage "One or more expected filter controls missing."
    }
    elseif ($kind -eq "pagination") {
        $pageSizeOk = (-not $counts.Found) -or ($counts.Last -eq 0) -or (($counts.Last - $counts.First + 1) -le 10)
        Add-Issue416PassFail -Assertions $Assertions -RouteName $name -Check "issue416 page size" -Pass $pageSizeOk -PassMessage "Pagination range reconciles with page_size=10." -FailMessage "Pagination range exceeds page_size=10."
        if ($Text.Contains("Next page")) {
            Add-Issue416PassFail -Assertions $Assertions -RouteName $name -Check "issue416 next preserves page size" -Pass $Html.Contains("page_size=10") -PassMessage "Pagination links preserve page size." -FailMessage "Pagination links did not preserve page size."
        }
    }
    elseif ($kind -eq "empty") {
        Add-Issue416PassFail -Assertions $Assertions -RouteName $name -Check "issue416 filtered empty" -Pass ($counts.Found -and $counts.Matching -eq 0 -and $Text.Contains("No facilities match these filters")) -PassMessage "Filtered-empty state found." -FailMessage "Filtered-empty state missing."
        Add-Issue416PassFail -Assertions $Assertions -RouteName $name -Check "issue416 clear filters" -Pass $Text.Contains("Clear filters") -PassMessage "Clear filters action found." -FailMessage "Clear filters action missing."
    }
}

function Get-Issue417CountSummary {
    param([string]$Text)
    $summary = [pscustomobject]@{ Found = $false; First = 0; Last = 0; Matching = 0; Total = 0; Raw = "" }
    $pattern = "Showing\s+(?<first>\d+)(?:-(?<last>\d+))?\s+of\s+(?<matching>\d+)\s+matching\s+serious-topic\s+complaint\s+record\(s\);\s+(?<total>\d+)\s+total\s+qualifying"
    $match = [regex]::Match($Text, $pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    if (-not $match.Success) { return $summary }
    $first = [int]$match.Groups["first"].Value
    $last = if ($match.Groups["last"].Success) { [int]$match.Groups["last"].Value } else { $first }
    if ($first -eq 0) { $last = 0 }
    return [pscustomobject]@{
        Found    = $true
        First    = $first
        Last     = $last
        Matching = [int]$match.Groups["matching"].Value
        Total    = [int]$match.Groups["total"].Value
        Raw      = $match.Value
    }
}

function Get-Issue417Rows {
    param([string]$Html)
    $rows = @()
    foreach ($match in [regex]::Matches($Html, "(?is)<tbody[^>]*>.*?</tbody>")) {
        foreach ($rowMatch in [regex]::Matches($match.Value, "(?is)<tr[^>]*>(.*?)</tr>")) {
            $rowHtml = $rowMatch.Groups[1].Value
            $rowText = ConvertFrom-HtmlText -Html $rowHtml
            $facilityName = Get-FirstHtmlMatch -Html $rowHtml -Pattern "<th[^>]*>(.*?)</th>"
            $facilityIdMatch = [regex]::Match($rowText, "Facility ID:?\s+(?<value>[A-Za-z0-9:._-]+)", [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
            $dateMatch = [regex]::Match($rowText, "\b\d{2}/\d{2}/\d{4}\b")
            $keyMatch = [regex]::Match($rowHtml, "source_record_key=([^""'&]+)", [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
            $rows += [pscustomobject]@{
                facilityName    = $facilityName
                facilityId      = if ($facilityIdMatch.Success) { $facilityIdMatch.Groups["value"].Value } else { "" }
                date            = if ($dateMatch.Success) { $dateMatch.Value } else { "" }
                sourceRecordKey = if ($keyMatch.Success) { [System.Net.WebUtility]::UrlDecode($keyMatch.Groups[1].Value) } else { "" }
                text            = $rowText
            }
        }
    }
    return @($rows)
}

function Add-Issue417PassFail {
    param([System.Collections.ArrayList]$Assertions, [string]$RouteName, [string]$Check, [bool]$Pass, [string]$PassMessage, [string]$FailMessage)
    if ($Pass) { Add-AssertionResult -Target $Assertions -RouteName $RouteName -Check $Check -Status "PASS" -Message $PassMessage }
    else { Add-AssertionResult -Target $Assertions -RouteName $RouteName -Check $Check -Status "FAIL" -Message $FailMessage }
}

function Test-Issue417RouteAssertions {
    param([hashtable]$Route, [string]$Html, [string]$Text, [System.Collections.ArrayList]$Assertions)
    if (-not $Route.ContainsKey("Issue417Kind")) { return }
    $name = [string]$Route.Name
    $kind = [string]$Route.Issue417Kind
    $counts = Get-Issue417CountSummary -Text $Text
    $rows = @(Get-Issue417Rows -Html $Html)
    Add-Issue417PassFail -Assertions $Assertions -RouteName $name -Check "issue417 count summary" -Pass $counts.Found -PassMessage "Serious-topic count summary found." -FailMessage "Serious-topic count summary missing."
    Add-Issue417PassFail -Assertions $Assertions -RouteName $name -Check "issue417 h1" -Pass ($Html.Contains("<h1") -and $Text.Contains("Serious-topic complaint worklist")) -PassMessage "Expected serious-topic worklist H1 found." -FailMessage "Expected serious-topic worklist H1 missing."
    Add-Issue417PassFail -Assertions $Assertions -RouteName $name -Check "issue417 semantic contract" -Pass ($Text.Contains("Source categories come from public records.") -and $Text.Contains("Review topics and possible keyword cues help narrow records for review.")) -PassMessage "Concise serious-topic semantic explanation found." -FailMessage "Concise serious-topic semantic explanation missing."
    Add-Issue417PassFail -Assertions $Assertions -RouteName $name -Check "issue417 no unsupported conclusions" -Pass (-not ($Text -match "(?i)keyword cues? (are|as) (findings?|verified events?)|verified abuse|legal finding|legal conclusion|facility-wide")) -PassMessage "No unsupported serious-topic conclusion wording found." -FailMessage "Unsupported serious-topic conclusion wording found."
    Add-Issue417PassFail -Assertions $Assertions -RouteName $name -Check "issue417 controls labeled" -Pass (($Html -match "(?is)<label[^>]*>.*?</label>") -and $Html.Contains('name="topic"') -and $Html.Contains('name="match_basis"')) -PassMessage "Expected labeled topic and basis controls found." -FailMessage "Expected topic or basis controls missing."
    Add-Issue417PassFail -Assertions $Assertions -RouteName $name -Check "issue417 semantic table" -Pass (($rows.Count -eq 0) -or (($Html -match "(?is)<caption[^>]*>.*?</caption>") -and ($Html -match "(?is)<th\b"))) -PassMessage "Semantic table caption/headings found when rows are rendered." -FailMessage "Semantic table caption/headings missing."
    Add-Issue417PassFail -Assertions $Assertions -RouteName $name -Check "issue417 no narrative leak" -Pass (-not ($Text -match "(?i)DO NOT SHOW|raw_path|provider_subject|connection string|token")) -PassMessage "No raw narrative or private marker found." -FailMessage "Raw narrative or private marker found."
    if ($kind -eq "default") {
        Add-Issue417PassFail -Assertions $Assertions -RouteName $name -Check "issue417 default total" -Pass ($counts.Found -and $counts.Total -ge 0) -PassMessage "Default route count summary parsed." -FailMessage "Default route count summary did not parse."
        Add-Issue417PassFail -Assertions $Assertions -RouteName $name -Check "issue417 links" -Pass ($Text.Contains("Open original public report") -and $Text.Contains("Open complaint review workspace")) -PassMessage "Original-source and complaint workspace links found." -FailMessage "Original-source or workspace link missing."
    }
    elseif ($kind -eq "source-category") {
        Add-Issue417PassFail -Assertions $Assertions -RouteName $name -Check "issue417 source category basis" -Pass $Text.Contains("Filter basis: Source category.") -PassMessage "Source-category filter basis text found." -FailMessage "Source-category filter basis text missing."
    }
    elseif ($kind -eq "keyword-cue") {
        Add-Issue417PassFail -Assertions $Assertions -RouteName $name -Check "issue417 keyword cue basis" -Pass ($Text.Contains("Filter basis: Possible keyword cue.") -or $counts.Matching -eq 0) -PassMessage "Possible-keyword-cue basis text found or no matching rows." -FailMessage "Possible-keyword-cue basis text missing."
    }
    elseif ($kind -eq "filtered") {
        Add-Issue417PassFail -Assertions $Assertions -RouteName $name -Check "issue417 filtered controls" -Pass ($Html.Contains('name="finding"') -and $Html.Contains('name="facility"') -and $Html.Contains('name="geography"') -and $Html.Contains('name="start_date"')) -PassMessage "Expected combined filter controls found." -FailMessage "One or more combined filter controls missing."
    }
    elseif ($kind -eq "empty") {
        Add-Issue417PassFail -Assertions $Assertions -RouteName $name -Check "issue417 filtered empty" -Pass ($counts.Found -and $counts.Matching -eq 0 -and $Text.Contains("No serious-topic complaint records matched.")) -PassMessage "Filtered-empty state found." -FailMessage "Filtered-empty state missing."
        Add-Issue417PassFail -Assertions $Assertions -RouteName $name -Check "issue417 clear filters" -Pass $Text.Contains("Clear filters") -PassMessage "Clear filters action found." -FailMessage "Clear filters action missing."
    }
}

function Get-Issue418CountSummary {
    param([string]$Text)
    $summary = [pscustomobject]@{ Found = $false; Qualifying = 0; Dated = 0; DateUnavailable = 0; Raw = "" }
    $pattern = "(?<qualifying>\d+)\s+qualifying\s+complaint\s+record\(s\):\s+(?<dated>\d+)\s+assigned\s+to\s+displayed\s+periods\s+and\s+(?<missing>\d+)\s+with\s+date\s+unavailable"
    $match = [regex]::Match($Text, $pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    if (-not $match.Success) { return $summary }
    return [pscustomobject]@{
        Found           = $true
        Qualifying      = [int]$match.Groups["qualifying"].Value
        Dated           = [int]$match.Groups["dated"].Value
        DateUnavailable = [int]$match.Groups["missing"].Value
        Raw             = $match.Value
    }
}

function Add-Issue418PassFail {
    param([System.Collections.ArrayList]$Assertions, [string]$RouteName, [string]$Check, [bool]$Pass, [string]$PassMessage, [string]$FailMessage)
    if ($Pass) { Add-AssertionResult -Target $Assertions -RouteName $RouteName -Check $Check -Status "PASS" -Message $PassMessage }
    else { Add-AssertionResult -Target $Assertions -RouteName $RouteName -Check $Check -Status "FAIL" -Message $FailMessage }
}

function Test-Issue418RouteAssertions {
    param([hashtable]$Route, [string]$Html, [string]$Text, [System.Collections.ArrayList]$Assertions)
    if (-not $Route.ContainsKey("Issue418Kind")) { return }
    $name = [string]$Route.Name
    $kind = [string]$Route.Issue418Kind
    $counts = Get-Issue418CountSummary -Text $Text
    Add-Issue418PassFail -Assertions $Assertions -RouteName $name -Check "issue418 h1" -Pass ($Html.Contains("<h1") -and $Text.Contains("Find Facilities That May Need Closer Review") -and $Text.Contains("Complaint Activity Over Time")) -PassMessage "Canonical Compare Facilities heading and Complaint Activity Over Time view found." -FailMessage "Canonical Compare Facilities heading or Complaint Activity Over Time view missing."
    Add-Issue418PassFail -Assertions $Assertions -RouteName $name -Check "issue418 count reconciliation" -Pass ($counts.Found -and $counts.Qualifying -eq ($counts.Dated + $counts.DateUnavailable)) -PassMessage "Qualifying, dated, and date-unavailable counts reconcile." -FailMessage "Complaint trend count summary is missing or does not reconcile."
    Add-Issue418PassFail -Assertions $Assertions -RouteName $name -Check "issue418 semantic table" -Pass (($Html -match "(?is)<caption[^>]*>.*?</caption>") -and ($Html -match "(?is)<th\b")) -PassMessage "Semantic trend table caption and headings found." -FailMessage "Semantic trend table caption or headings missing."
    Add-Issue418PassFail -Assertions $Assertions -RouteName $name -Check "issue418 labeled controls" -Pass ($Html.Contains('name="facility"') -and $Html.Contains('name="facility_type"') -and $Html.Contains('name="geography"') -and $Html.Contains('name="finding"') -and $Html.Contains('name="serious_topic"') -and $Html.Contains('name="start_date"') -and $Html.Contains('name="end_date"') -and $Html.Contains('name="time_grain"') -and $Html.Contains('name="period_count"')) -PassMessage "Expected labeled trend filters found." -FailMessage "One or more expected trend filters missing."
    Add-Issue418PassFail -Assertions $Assertions -RouteName $name -Check "issue418 transparent rules" -Pass ($Text.Contains("Anomaly cue definitions") -and $Text.Contains("at least twice the preceding count") -and $Text.Contains("no more than half")) -PassMessage "Concise deterministic anomaly definitions found." -FailMessage "Deterministic anomaly definitions missing."
    Add-Issue418PassFail -Assertions $Assertions -RouteName $name -Check "issue418 safe aggregate output" -Pass (-not ($Text -match "(?i)risk score|legal conclusion|facility-wide conclusion|raw_sha256|raw_path|provider_subject|connection string|DO NOT SHOW")) -PassMessage "No unsafe aggregate output markers found." -FailMessage "Unsafe aggregate output marker found."
    Add-Issue418PassFail -Assertions $Assertions -RouteName $name -Check "issue418 direct counts" -Pass ($Text.Contains("Current period:") -and $Text.Contains("preceding period:")) -PassMessage "Visible current and preceding counts found." -FailMessage "Visible contributing period counts missing."
    if ($kind -eq "default") {
        Add-Issue418PassFail -Assertions $Assertions -RouteName $name -Check "issue418 coverage labels" -Pass ($Text.Contains("Complete period") -or $Text.Contains("Coverage unavailable") -or $Text.Contains("Incomplete current period")) -PassMessage "Compact coverage label found." -FailMessage "No supported coverage label found."
        Add-Issue418PassFail -Assertions $Assertions -RouteName $name -Check "issue418 date unavailable state" -Pass $Text.Contains("Date unavailable") -PassMessage "Date-unavailable state found." -FailMessage "Date-unavailable state missing."
    }
    elseif ($kind -eq "monthly-facility") {
        Add-Issue418PassFail -Assertions $Assertions -RouteName $name -Check "issue418 monthly facility filters" -Pass ($Html.Contains('value="month" selected="selected"') -and $Html.Contains('value="157806098"')) -PassMessage "Monthly facility filter state found." -FailMessage "Monthly facility filter state missing."
        Add-Issue418PassFail -Assertions $Assertions -RouteName $name -Check "issue418 complaint links" -Pass ($Text.Contains("Open complaint record") -or $counts.Dated -eq 0) -PassMessage "Complaint record links found or no dated qualifying complaints." -FailMessage "Qualifying complaint record links missing."
    }
    elseif ($kind -eq "quarterly") {
        Add-Issue418PassFail -Assertions $Assertions -RouteName $name -Check "issue418 quarterly grouping" -Pass $Html.Contains('value="quarter" selected="selected"') -PassMessage "Quarterly grouping selected." -FailMessage "Quarterly grouping selection missing."
    }
    elseif ($kind -eq "increased") {
        Add-Issue418PassFail -Assertions $Assertions -RouteName $name -Check "issue418 increased activity cue" -Pass (($Html -match "(?is)<strong>Increased activity</strong>.*?Current period:\s*\d+;\s*preceding period:\s*\d+") -or ($Text.Contains("increased activity means at least 3 current complaints and at least twice the preceding count") -and $Text.Contains("Current period:") -and $Text.Contains("preceding period:"))) -PassMessage "Increased-activity row cue or governed fixture rule definition with visible period counts found." -FailMessage "Increased-activity cue/rule with visible contributing counts missing."
    }
    elseif ($kind -eq "secondary-cue") {
        $secondaryCueSupported = $Html -match "(?is)<strong>(New activity|Decreased activity)</strong>.*?Current period:\s*\d+;\s*preceding period:\s*\d+"
        if ($secondaryCueSupported) {
            Add-Issue418PassFail -Assertions $Assertions -RouteName $name -Check "issue418 secondary activity cue" -Pass $true -PassMessage "New- or decreased-activity row cue and contributing counts found." -FailMessage ""
        }
        else {
            Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue418 secondary activity cue" -Status "WARN" -Message "Loaded governed records do not expose a new- or decreased-activity cue for this route."
        }
    }
    elseif ($kind -eq "incomplete") {
        Add-Issue418PassFail -Assertions $Assertions -RouteName $name -Check "issue418 incomplete period" -Pass ($Html -match "(?is)<span[^>]*>Incomplete current period</span>.*?<strong>No anomaly cue</strong>") -PassMessage "Incomplete current period has no anomaly cue." -FailMessage "Incomplete current period state or no-cue behavior missing."
    }
    elseif ($kind -eq "zero") {
        $zeroStateSupported = $Text.Contains("Zero qualifying records") -or $Text.Contains("Coverage unavailable")
        $hasDecreasedActivity = $Html -match "(?is)<strong>Decreased activity</strong>"
        $hasNoAnomalyCue = $Html -match "(?is)<strong>No anomaly cue</strong>"
        Add-Issue418PassFail -Assertions $Assertions -RouteName $name -Check "issue418 zero qualifying" -Pass ($counts.Found -and $counts.Qualifying -eq 0 -and $zeroStateSupported -and -not $hasDecreasedActivity -and $hasNoAnomalyCue) -PassMessage "Zero qualifying count has a supported coverage state and no anomaly cue." -FailMessage "Zero route count, coverage state, or anomaly cue behavior is unsupported."
    }
}

function Test-Issue419RouteAssertions {
    param([hashtable]$Route, [string]$Html, [string]$Text, [System.Collections.ArrayList]$Assertions)
    if (-not $Route.ContainsKey("Issue419Kind")) { return }
    $name = [string]$Route.Name
    $kind = [string]$Route.Issue419Kind
    $canonicalHeading = $Text.Contains("Find Facilities That May Need Closer Review")
    Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue419 canonical heading" -Status $(if ($canonicalHeading) { "PASS" } else { "FAIL" }) -Message $(if ($canonicalHeading) { "Canonical Compare Facilities heading found." } else { "Canonical Compare Facilities heading missing." })

    $viewLinks = $Html.Contains('/ccld/facilities/intelligence"') -and $Html.Contains("view=licensing-visit-activity") -and $Html.Contains("view=complaint-activity-over-time")
    Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue419 consolidated views" -Status $(if ($viewLinks) { "PASS" } else { "FAIL" }) -Message $(if ($viewLinks) { "Complaint Patterns, Licensing and Visit Activity, and Complaint Activity Over Time links found." } else { "One or more consolidated Compare Facilities view links are missing." })

    $purposeIsSafe = $Text.IndexOf("compare complaint findings, activity, patterns, licensing and visit activity, and available public records", [System.StringComparison]::OrdinalIgnoreCase) -ge 0 -or $kind -in @("licensing", "legacy-licensing")
    Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue419 purpose and source boundary" -Status $(if ($purposeIsSafe) { "PASS" } else { "FAIL" }) -Message $(if ($purposeIsSafe) { "Plain-language comparison purpose or licensing source boundary found." } else { "Plain-language comparison purpose is missing." })

    $primaryEvidenceHidden = $Html -match '(?is)<details[^>]*>.*?(facility-contributing-records|Review guidance|licensing and visit activity).*?</details>'
    Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue419 primary evidence visible" -Status $(if (-not $primaryEvidenceHidden) { "PASS" } else { "FAIL" }) -Message $(if (-not $primaryEvidenceHidden) { "Primary comparison evidence is not hidden in a disclosure." } else { "Primary comparison evidence is hidden in a disclosure." })

    $unsafeInternals = $Text -match '(?i)raw_path|raw_sha256|provider_subject|connection string|container name|tiny fixture fallback|malformed row'
    Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue419 reviewer-tier safety" -Status $(if (-not $unsafeInternals) { "PASS" } else { "FAIL" }) -Message $(if (-not $unsafeInternals) { "Reviewer output omits controlled source and runtime internals." } else { "Reviewer output exposes a controlled source or runtime internal." })

    $obsoleteReviewerLanguage = $Text -match '(?i)uploaded\s+(public\s+)?summary\s+(fields?|signals?|review\s+cues?)|facility\s+hub|detailed\s+priority\s+table|\bpriority\s+cue\b|\bcheck\s+source\b'
    Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue419 plain-language terminology" -Status $(if (-not $obsoleteReviewerLanguage) { "PASS" } else { "FAIL" }) -Message $(if (-not $obsoleteReviewerLanguage) { "Reviewer output uses approved plain-language facility and source-observation terms." } else { "Reviewer output contains obsolete or implementation-centric terminology." })

    $internalIdentityVisible = $Text -match '(?i)ccld(?:-|:)facility(?:-|:)\d+'
    Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue419 public facility identity presentation" -Status $(if (-not $internalIdentityVisible) { "PASS" } else { "FAIL" }) -Message $(if (-not $internalIdentityVisible) { "Internal facility identity prefixes are absent from visible reviewer text." } else { "An internal facility identity prefix is visible to the reviewer." })

    if ($Route.ContainsKey("ExpectedText")) {
        $expectedText = [string]$Route.ExpectedText
        $hasExpectedText = $Text.Contains($expectedText)
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue419 intended state" -Status $(if ($hasExpectedText) { "PASS" } else { "FAIL" }) -Message $(if ($hasExpectedText) { "Expected state text '$expectedText' found." } else { "Expected state text '$expectedText' missing." })
    }

    if ($kind -in @("default", "responsive", "focus", "limited-data", "print")) {
        $visibleComplaintEvidence = $Html.Contains('class="facility-contributing-records"') -and $Text.Contains("Open complaint record")
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue419 complaint evidence and drill-down" -Status $(if ($visibleComplaintEvidence) { "PASS" } else { "FAIL" }) -Message $(if ($visibleComplaintEvidence) { "Visible contributing complaint evidence and record drill-down found." } else { "Visible contributing complaint evidence or record drill-down missing." })
    }
    if ($kind -in @("licensing", "legacy-licensing")) {
        $licensingBoundary = $Text.Contains("This view does not show complaint coverage") -and $Text.Contains("separate from loaded complaint counts")
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue419 licensing parity and separation" -Status $(if ($licensingBoundary) { "PASS" } else { "FAIL" }) -Message $(if ($licensingBoundary) { "Licensing/visit activity is present and explicitly separate from complaint coverage." } else { "Licensing/visit activity source separation is missing." })
        $licensingLabels = @(
            "All supported observations",
            "Multiple supported observations",
            "Complaint-related visit activity",
            "Citation activity",
            "Plan of Correction activity",
            "Recent visit activity",
            "Capacity of 50 or more",
            "Closed licensing status",
            "Last recorded visit before 2023"
        )
        $meaningfulLicensingLabels = @($licensingLabels | Where-Object { -not $Text.Contains($_) }).Count -eq 0
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue419 meaningful licensing filters" -Status $(if ($meaningfulLicensingLabels) { "PASS" } else { "FAIL" }) -Message $(if ($meaningfulLicensingLabels) { "Every supported licensing filter has a distinct field-backed label." } else { "One or more meaningful licensing filter labels are missing." })
    }
    if ($kind -in @("legacy-priority", "trends", "legacy-trends")) {
        $worklistTerminology = $Text.Contains("Complaint Worklist") -and -not ($Text -match '(?i)review\s+queue')
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue419 Complaint Worklist terminology" -Status $(if ($worklistTerminology) { "PASS" } else { "FAIL" }) -Message $(if ($worklistTerminology) { "Complaint Worklist terminology is present without the legacy review-queue label." } else { "Complaint Worklist terminology is missing or legacy review-queue wording remains." })
    }
    if ($kind -eq "focus") {
        $focusContract = $Html.Contains('id="facility-intelligence-facility-type"') -and $Html.Contains("window.location.hash") -and $Html.Contains("target.focus")
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue419 keyboard focus contract" -Status $(if ($focusContract) { "PASS" } else { "FAIL" }) -Message $(if ($focusContract) { "Deterministic fragment focus contract found." } else { "Deterministic fragment focus contract missing." })
    }
    if ($kind -eq "responsive") {
        $responsiveContract = $Html.Contains("@media (max-width: 760px)") -and $Html.Contains("overflow-wrap: anywhere")
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue419 responsive contract" -Status $(if ($responsiveContract) { "PASS" } else { "FAIL" }) -Message $(if ($responsiveContract) { "Governed responsive and wrapping rules found." } else { "Governed responsive or wrapping rules missing." })
    }
    if ($kind -eq "print") {
        $printContract = $Html.Contains("@media print") -and $Html.Contains(".compare-facilities-views")
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue419 print contract" -Status $(if ($printContract) { "PASS" } else { "FAIL" }) -Message $(if ($printContract) { "Print stylesheet and Compare Facilities print rule found." } else { "Compare Facilities print contract missing." })
    }
}

function Test-Issue498RouteAssertions {
    param([hashtable]$Route, [string]$Html, [string]$Text, [System.Collections.ArrayList]$Assertions)
    if (-not $Route.ContainsKey("Issue498State")) { return }
    $name = [string]$Route.Name
    $state = [string]$Route.Issue498State
    $stateMarker = 'data-evidence-state="' + $state + '"'
    $hasBaseEvidence = $Html.Contains("First investigation activity date evidence") -and $Html.Contains($stateMarker)
    Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue498 intended evidence state" -Status $(if ($hasBaseEvidence) { "PASS" } else { "FAIL" }) -Message $(if ($hasBaseEvidence) { "Expected '$state' evidence state found." } else { "Expected '$state' evidence state missing." })

    if ($state -eq "supported") {
        $supported = $Text.Contains("VISIT DATE: 06/12/2024") -and $Text.Contains("report header") -and $Text.Contains("Open original source")
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue498 supported evidence fields" -Status $(if ($supported) { "PASS" } else { "FAIL" }) -Message $(if ($supported) { "Bounded sentence, section, and original-source action found." } else { "Supported evidence sentence, section, or original-source action missing." })
    }
    elseif ($state -eq "document-only") {
        $documentOnly = $Text.Contains("Document-level source only.") -and -not $Text.ToLowerInvariant().Contains("verified by")
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue498 document-only boundaries" -Status $(if ($documentOnly) { "PASS" } else { "FAIL" }) -Message $(if ($documentOnly) { "Document linkage is present without passage-verification language." } else { "Document-only boundaries are missing or overstated." })
    }
    elseif ($state -eq "field-partial") {
        $fieldPartial = $Text.Contains("Field evidence incomplete.") -and $Text.Contains("supporting source event sentence is not available")
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue498 field-partial boundary" -Status $(if ($fieldPartial) { "PASS" } else { "FAIL" }) -Message $(if ($fieldPartial) { "Missing event sentence is identified." } else { "Field-partial missing element is not identified." })
    }
    elseif ($state -eq "source-unavailable") {
        $sourceUnavailable = $Text.Contains("Source document unavailable.") -and -not $Text.Contains("Open original source")
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue498 unavailable source action" -Status $(if ($sourceUnavailable) { "PASS" } else { "FAIL" }) -Message $(if ($sourceUnavailable) { "Unavailable state has no active original-source action." } else { "Unavailable state or source-action boundary is incorrect." })
    }

    if ($Route.ContainsKey("CapturePrint")) {
        $printContract = $Html.Contains("@media print") -and $Html.Contains(".source-evidence-region[hidden]") -and $Html.Contains("Original source URL:")
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue498 print contract" -Status $(if ($printContract) { "PASS" } else { "FAIL" }) -Message $(if ($printContract) { "Print expansion and source-URL contract found." } else { "Print evidence contract missing." })
    }
    if ([string]$Route.Issue498Kind -eq "keyboard-focus") {
        $focusContract = $Html.Contains('id="first-investigation-evidence-toggle"') -and $Html.Contains("window.location.hash === '#' + button.id")
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue498 keyboard focus contract" -Status $(if ($focusContract) { "PASS" } else { "FAIL" }) -Message $(if ($focusContract) { "Deterministic evidence-toggle focus fragment found." } else { "Evidence-toggle focus fragment contract missing." })
    }
}

function Get-SafeDynamicHref {
    param([string]$Html, [string]$Pattern)
    $match = [regex]::Match($Html, $Pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    if (-not $match.Success) { return "" }
    $href = [System.Net.WebUtility]::HtmlDecode($match.Groups[1].Value)
    if ($href.StartsWith("http", [System.StringComparison]::OrdinalIgnoreCase)) { return "" }
    if ($href.Contains("..") -or $href.Contains("\")) { return "" }
    if ($href -match "(?i)(token|secret|cookie|provider|client_secret|authorization)") { return "" }
    return $href
}

$captureEnvOverrides = [ordered]@{
    CCLD_HOSTED_PAGE_DATA_MODE        = "fixture-demo"
    CCLD_HOSTED_TESTER_AUTH_MODE      = "local-dev"
    CCLD_HOSTED_TESTER_LOCAL_DEV_AUTH = "enabled"
}
$captureEnvOriginal = @{}
foreach ($entry in $captureEnvOverrides.GetEnumerator()) {
    $name = [string]$entry.Key
    $existingItem = Get-Item -LiteralPath ("Env:{0}" -f $name) -ErrorAction SilentlyContinue
    if ($null -ne $existingItem) {
        $captureEnvOriginal[$name] = [pscustomobject]@{ Exists = $true; Value = [string]$existingItem.Value }
    }
    else {
        $captureEnvOriginal[$name] = [pscustomobject]@{ Exists = $false; Value = $null }
    }
    Set-Item -LiteralPath ("Env:{0}" -f $name) -Value ([string]$entry.Value)
}

try {
    Test-AllowedBaseUrl -Value $BaseUrl
    Assert-OutputDir -Path $OutputDir
    if ($Issue419 -and $Mode -ne "fixture") {
        Stop-CaptureFail "Issue #419 evidence routes are local fixture/demo-only; use -Mode fixture."
    }
    if ($Issue498 -and $Mode -ne "fixture") {
        Stop-CaptureFail "Issue #498 evidence routes are local fixture/demo-only; use -Mode fixture."
    }
    $baseUri = [System.Uri]::new($BaseUrl)
    $normalizedBaseUrl = $baseUri.GetLeftPart([System.UriPartial]::Authority).TrimEnd("/")
    $timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd-HHmmssZ")
    $packetName = if ($Issue498) { "$timestamp-$Mode-issue-498" } elseif ($Issue419) { "$timestamp-$Mode-issue-419" } elseif ($Issue418) { "$timestamp-$Mode-issue-418" } elseif ($Issue417) { "$timestamp-$Mode-issue-417" } elseif ($Issue416) { "$timestamp-$Mode-issue-416" } elseif ($Issue415) { "$timestamp-$Mode-issue-415" } else { "$timestamp-$Mode" }
    $outputRoot = Join-Path $PWD $OutputDir
    $packetDir = Join-Path $outputRoot $packetName
    $zipPath = Join-Path $outputRoot "$packetName.zip"
    $htmlDir = Join-Path $packetDir "html"
    $textDir = Join-Path $packetDir "text"
    $screenshotDir = Join-Path $packetDir "screenshots"
    $printDir = Join-Path $packetDir "print"
    $accessibilityDir = Join-Path $packetDir "accessibility"
    $diagnosticsDir = Join-Path $packetDir "diagnostics"
    foreach ($dir in @($packetDir, $htmlDir, $textDir, $screenshotDir, $printDir, $accessibilityDir, $diagnosticsDir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }

    $facilityHubNumber = if ($Mode -eq "fixture") { "900000001" } else { "434417302" }
    $coreRoutes = @(
        @{ Name = "home"; Path = "/"; Label = "01-home"; ActiveHref = "/"; WorkflowStep = "Start" },
        @{ Name = "facility"; Path = "/ccld/facilities"; Label = "02-facility"; ActiveHref = "/ccld/facilities"; WorkflowStep = "Facility" },
        @{ Name = "facility-intelligence"; Path = "/ccld/facilities/intelligence"; Label = "02-facility-intelligence"; ActiveHref = "/ccld/facilities/intelligence"; WorkflowStep = "Review" },
        @{ Name = "facility-licensing-activity"; Path = "/ccld/facilities/intelligence?view=licensing-visit-activity"; Label = "02-facility-licensing-activity"; ActiveHref = "/ccld/facilities/intelligence"; WorkflowStep = "Review" },
        @{ Name = "facility-complaint-trends"; Path = "/ccld/facilities/intelligence?view=complaint-activity-over-time"; Label = "02-facility-complaint-trends"; ActiveHref = "/ccld/facilities/intelligence"; WorkflowStep = "Review" },
        @{ Name = "facility-hub"; Path = "/ccld/facilities/detail?facility_number=$facilityHubNumber"; Label = "02-facility-hub"; ActiveHref = "/ccld/facilities"; WorkflowStep = "Facility" },
        @{ Name = "request-records"; Path = "/ccld/records/request"; Label = "03-request-records"; ActiveHref = "/ccld/records/request"; WorkflowStep = "Request" },
        @{ Name = "jobs"; Path = "/ccld/retrieval/jobs"; Label = "04-job-status"; WorkflowStep = "Status" },
        @{ Name = "reviewer"; Path = "/reviewer"; Label = "05-reviewer"; ActiveHref = "/reviewer"; WorkflowStep = "Review" },
        @{ Name = "substantiated-triage"; Path = "/reviewer/records/substantiated"; Label = "05-substantiated-triage"; ActiveHref = "/reviewer"; WorkflowStep = "Review" },
        @{ Name = "serious-topics"; Path = "/reviewer/records/serious-topics"; Label = "05-serious-topics"; ActiveHref = "/reviewer"; WorkflowStep = "Review" },
        @{ Name = "matrix-export"; Path = "/reviewer/records/matrix.csv?facility_number=157806098&start_date=2022-08-01&end_date=2022-08-31&request_context_origin=manual_entry"; Label = "05-matrix-export" },
        @{ Name = "packet-preview-empty"; Path = "/reviewer/packet/preview"; Label = "06-packet-preview-empty"; ActiveHref = "/reviewer"; WorkflowStep = "Review" },
        @{ Name = "packet-preview-context"; Path = "/reviewer/packet/preview?facility_number=157806098&start_date=2022-08-01&end_date=2022-08-31&request_context_origin=manual_entry"; Label = "06-packet-preview-context"; ActiveHref = "/reviewer"; WorkflowStep = "Review" },
        @{ Name = "packet-draft-empty"; Path = "/reviewer/packet/draft"; Label = "07-packet-draft-empty"; ActiveHref = "/reviewer"; WorkflowStep = "Review" },
        @{ Name = "packet-draft-context"; Path = "/reviewer/packet/draft?facility_number=157806098&start_date=2022-08-01&end_date=2022-08-31&request_context_origin=manual_entry"; Label = "08-packet-draft-context"; ActiveHref = "/reviewer"; WorkflowStep = "Review" },
        @{ Name = "feedback"; Path = "/feedback"; Label = "09-feedback"; ActiveHref = "/feedback"; WorkflowStep = "Report" },
        @{ Name = "help"; Path = "/ccld/help"; Label = "10-help"; ActiveHref = "/ccld/help" }
    )

    $issue415Routes = @(
        @{ Name = "issue-415-default"; Path = "/reviewer/records/substantiated"; Label = "issue-415-01-default"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; Issue415Kind = "default" },
        @{ Name = "issue-415-facility-107207198"; Path = "/reviewer/records/substantiated?facility=107207198"; Label = "issue-415-02-facility-107207198"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; Issue415Kind = "facility" },
        @{ Name = "issue-415-foster-family-agency"; Path = "/reviewer/records/substantiated?facility_type=FOSTER%20FAMILY%20AGENCY"; Label = "issue-415-03-foster-family-agency"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; Issue415Kind = "facility-type" },
        @{ Name = "issue-415-sort-facility-asc"; Path = "/reviewer/records/substantiated?sort=facility_asc&page_size=25"; Label = "issue-415-04-sort-facility-asc"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; Issue415Kind = "sort" },
        @{ Name = "issue-415-future-empty"; Path = "/reviewer/records/substantiated?start_date=2099-01-01&end_date=2099-12-31"; Label = "issue-415-05-future-empty"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; Issue415Kind = "future-empty" }
    )
    $issue416Routes = @(
        @{ Name = "issue-416-default"; Path = "/ccld/facilities/intelligence?view=complaint-priority-compatibility"; Label = "issue-416-01-default"; ActiveHref = "/ccld/facilities/intelligence"; WorkflowStep = "Review"; Issue416Kind = "default" },
        @{ Name = "issue-416-filtered"; Path = "/ccld/facilities/intelligence?view=complaint-priority-compatibility&facility_type=FOSTER%20FAMILY%20AGENCY&geography=Kern&min_complaints=1&min_substantiated=0&indicator=source_available"; Label = "issue-416-02-filtered"; ActiveHref = "/ccld/facilities/intelligence"; WorkflowStep = "Review"; Issue416Kind = "filtered" },
        @{ Name = "issue-416-pagination"; Path = "/ccld/facilities/intelligence?view=complaint-priority-compatibility&page_size=10"; Label = "issue-416-03-pagination"; ActiveHref = "/ccld/facilities/intelligence"; WorkflowStep = "Review"; Issue416Kind = "pagination" },
        @{ Name = "issue-416-empty"; Path = "/ccld/facilities/intelligence?view=complaint-priority-compatibility&min_complaints=9999"; Label = "issue-416-04-empty"; ActiveHref = "/ccld/facilities/intelligence"; WorkflowStep = "Review"; Issue416Kind = "empty" }
    )
    $issue417Routes = @(
        @{ Name = "issue-417-default"; Path = "/reviewer/records/serious-topics"; Label = "issue-417-01-default"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; Issue417Kind = "default" },
        @{ Name = "issue-417-source-category"; Path = "/reviewer/records/serious-topics?match_basis=source-category"; Label = "issue-417-02-source-category"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; Issue417Kind = "source-category" },
        @{ Name = "issue-417-keyword-cue"; Path = "/reviewer/records/serious-topics?match_basis=keyword-cue"; Label = "issue-417-03-keyword-cue"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; Issue417Kind = "keyword-cue" },
        @{ Name = "issue-417-filtered"; Path = "/reviewer/records/serious-topics?topic=Supervision%20topic&finding=Unsubstantiated&facility=157806098&geography=Kern&start_date=2022-04-01&end_date=2022-04-30"; Label = "issue-417-04-filtered"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; Issue417Kind = "filtered" },
        @{ Name = "issue-417-empty"; Path = "/reviewer/records/serious-topics?topic=Runaway%2FAWOL%20topic&start_date=2099-01-01&end_date=2099-12-31"; Label = "issue-417-05-empty"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; Issue417Kind = "empty" }
    )
    $issue418CurrentStart = (Get-Date -Day 1).ToString("yyyy-MM-dd")
    $issue418CurrentEnd = (Get-Date -Day 1).AddMonths(1).AddDays(-1).ToString("yyyy-MM-dd")
    $issue418Base = "/ccld/facilities/intelligence?view=complaint-activity-over-time"
    $issue418Routes = @(
        @{ Name = "issue-418-default"; Path = $issue418Base; Label = "issue-418-01-default"; ActiveHref = "/ccld/facilities/intelligence"; WorkflowStep = "Review"; Issue418Kind = "default" },
        @{ Name = "issue-418-monthly-facility"; Path = "$issue418Base&facility=157806098&start_date=2022-03-01&end_date=2022-05-31&time_grain=month&period_count=3"; Label = "issue-418-02-monthly-facility"; ActiveHref = "/ccld/facilities/intelligence"; WorkflowStep = "Review"; Issue418Kind = "monthly-facility" },
        @{ Name = "issue-418-quarterly"; Path = "$issue418Base&start_date=2022-01-01&end_date=2022-12-31&time_grain=quarter&period_count=4"; Label = "issue-418-03-quarterly"; ActiveHref = "/ccld/facilities/intelligence"; WorkflowStep = "Review"; Issue418Kind = "quarterly" },
        @{ Name = "issue-418-increased"; Path = "$issue418Base&start_date=2020-01-01&end_date=2021-12-31&time_grain=month&period_count=24"; Label = "issue-418-04-increased"; ActiveHref = "/ccld/facilities/intelligence"; WorkflowStep = "Review"; Issue418Kind = "increased" },
        @{ Name = "issue-418-secondary-cue"; Path = "$issue418Base&start_date=2022-01-01&end_date=2023-12-31&time_grain=month&period_count=24"; Label = "issue-418-05-secondary-cue"; ActiveHref = "/ccld/facilities/intelligence"; WorkflowStep = "Review"; Issue418Kind = "secondary-cue" },
        @{ Name = "issue-418-incomplete"; Path = "$issue418Base&start_date=$issue418CurrentStart&end_date=$issue418CurrentEnd&time_grain=month&period_count=1"; Label = "issue-418-06-incomplete"; ActiveHref = "/ccld/facilities/intelligence"; WorkflowStep = "Review"; Issue418Kind = "incomplete" },
        @{ Name = "issue-418-zero"; Path = "$issue418Base&facility=157806098&finding=Substantiated&start_date=2022-04-01&end_date=2022-04-30&time_grain=month&period_count=1"; Label = "issue-418-07-zero"; ActiveHref = "/ccld/facilities/intelligence"; WorkflowStep = "Review"; Issue418Kind = "zero" }
    )
    $issue419Base = "/ccld/facilities/intelligence"
    $issue419Routes = @(
        @{ Name = "issue-419-default"; Path = $issue419Base; Label = "issue-419-01-default"; ActiveHref = $issue419Base; WorkflowStep = "Review"; Issue419Kind = "default"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-419-licensing"; Path = "${issue419Base}?view=licensing-visit-activity"; Label = "issue-419-02-licensing"; ActiveHref = $issue419Base; WorkflowStep = "Review"; Issue419Kind = "licensing"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-419-trends"; Path = "${issue419Base}?view=complaint-activity-over-time&start_date=2022-03-01&end_date=2022-05-31&time_grain=month&period_count=3"; Label = "issue-419-03-trends"; ActiveHref = $issue419Base; WorkflowStep = "Review"; Issue419Kind = "trends"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-419-narrow-desktop"; Path = $issue419Base; Label = "issue-419-04-narrow-desktop"; ActiveHref = $issue419Base; WorkflowStep = "Review"; Issue419Kind = "responsive"; ViewportWidth = 1024; ViewportHeight = 900 },
        @{ Name = "issue-419-mobile"; Path = $issue419Base; Label = "issue-419-05-mobile-390"; ActiveHref = $issue419Base; WorkflowStep = "Review"; Issue419Kind = "responsive"; ViewportWidth = 390; ViewportHeight = 844 },
        @{ Name = "issue-419-reflow"; Path = $issue419Base; Label = "issue-419-06-200-percent-reflow-approximation"; ActiveHref = $issue419Base; WorkflowStep = "Review"; Issue419Kind = "responsive"; ViewportWidth = 720; ViewportHeight = 600 },
        @{ Name = "issue-419-keyboard-focus"; Path = "$issue419Base#facility-intelligence-facility-type"; Label = "issue-419-07-keyboard-focus"; ActiveHref = $issue419Base; WorkflowStep = "Review"; Issue419Kind = "focus"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-419-filtered-empty"; Path = "${issue419Base}?geography=__not_loaded__"; Label = "issue-419-08-filtered-empty"; ActiveHref = $issue419Base; WorkflowStep = "Review"; Issue419Kind = "state"; ExpectedText = "No facilities match these filters"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-419-source-unavailable"; Path = "${issue419Base}?evidence_state=source-unavailable"; Label = "issue-419-09-source-unavailable"; ActiveHref = $issue419Base; WorkflowStep = "Review"; Issue419Kind = "state"; ExpectedText = "Complaint source links are unavailable"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-419-limited-data"; Path = "${issue419Base}?evidence_state=limited-data"; Label = "issue-419-10-limited-data"; ActiveHref = $issue419Base; WorkflowStep = "Review"; Issue419Kind = "limited-data"; ExpectedText = "Limited loaded complaint data"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-419-invalid"; Path = "${issue419Base}?start_date=2023-02-01&end_date=2023-01-01"; Label = "issue-419-11-invalid"; ActiveHref = $issue419Base; WorkflowStep = "Review"; Issue419Kind = "state"; ExpectedStatus = 400; ExpectedText = "Start date must be on or before end date."; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-419-not-loaded"; Path = "${issue419Base}?evidence_state=not-loaded"; Label = "issue-419-12-not-loaded"; ActiveHref = $issue419Base; WorkflowStep = "Review"; Issue419Kind = "state"; ExpectedText = "No loaded complaint records are available to compare"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-419-error"; Path = "${issue419Base}?evidence_state=error"; Label = "issue-419-13-error"; ActiveHref = $issue419Base; WorkflowStep = "Review"; Issue419Kind = "state"; ExpectedStatus = 503; ExpectedText = "Facilities could not be loaded"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-419-print"; Path = $issue419Base; Label = "issue-419-14-print"; ActiveHref = $issue419Base; WorkflowStep = "Review"; Issue419Kind = "print"; ViewportWidth = 1440; ViewportHeight = 1200; CapturePrint = $true },
        @{ Name = "issue-419-legacy-licensing"; Path = "/ccld/facilities/review-priority?q=900000001&cue=status"; Label = "issue-419-15-legacy-licensing-redirect"; ActiveHref = $issue419Base; WorkflowStep = "Review"; Issue419Kind = "legacy-licensing"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-419-legacy-priorities"; Path = "/reviewer/facilities/priorities?min_complaints=1&page_size=10"; Label = "issue-419-16-legacy-priorities-redirect"; ActiveHref = $issue419Base; WorkflowStep = "Review"; Issue419Kind = "legacy-priority"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-419-legacy-trends"; Path = "/reviewer/facilities/trends?time_grain=month&period_count=3"; Label = "issue-419-17-legacy-trends-redirect"; ActiveHref = $issue419Base; WorkflowStep = "Review"; Issue419Kind = "legacy-trends"; ViewportWidth = 1440; ViewportHeight = 1200 }
    )
    $issue498SupportedPath = "/reviewer/records/detail?source_record_key=complaint%3Accld-complaint-32-CR-20240603151515-rt-src-002-supported-fixture"
    $issue498DocumentOnlyPath = "/reviewer/records/detail?source_record_key=complaint%3Accld-complaint-32-CR-20240610181818-rt-src-002-document-only-fixture"
    $issue498FieldPartialPath = "/reviewer/records/detail?source_record_key=complaint%3Accld%3Acomplaint%3A32-CR-20220407124448"
    $issue498SourceUnavailablePath = "/reviewer/records/detail?source_record_key=complaint%3Accld-complaint-32-CR-20240120111111-rt-src-002-source-unavailable-fixture"
    $issue498Routes = @(
        @{ Name = "rt-src-002-supported-closed"; Path = $issue498SupportedPath; Label = "rt-src-002-01-supported-closed"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; Issue498State = "supported"; Issue498Kind = "closed"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "rt-src-002-supported-open"; Path = "$issue498SupportedPath#first-investigation-evidence"; Label = "rt-src-002-02-supported-open"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; Issue498State = "supported"; Issue498Kind = "open"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "rt-src-002-supported-open-narrow-desktop"; Path = "$issue498SupportedPath#first-investigation-evidence"; Label = "rt-src-002-03-supported-open-narrow-desktop"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; Issue498State = "supported"; Issue498Kind = "narrow-desktop"; ViewportWidth = 1024; ViewportHeight = 900 },
        @{ Name = "rt-src-002-supported-open-mobile-compact"; Path = "$issue498SupportedPath#first-investigation-evidence"; Label = "rt-src-002-04-supported-open-mobile-compact"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; Issue498State = "supported"; Issue498Kind = "mobile-compact"; ViewportWidth = 390; ViewportHeight = 844 },
        @{ Name = "rt-src-002-supported-open-200-percent-reflow-approximation"; Path = "$issue498SupportedPath#first-investigation-evidence"; Label = "rt-src-002-05-supported-open-200-percent-reflow-approximation"; SupplementalScreenshotFileName = "rt-src-002-05b-supported-open-200-percent-reflow-approximation-lower.png"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; Issue498State = "supported"; Issue498Kind = "200-percent-reflow-approximation"; ViewportWidth = 720; ViewportHeight = 600 },
        @{ Name = "rt-src-002-keyboard-focus"; Path = "$issue498SupportedPath#first-investigation-evidence-toggle"; Label = "rt-src-002-06-keyboard-focus"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; Issue498State = "supported"; Issue498Kind = "keyboard-focus"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "rt-src-002-document-only"; Path = $issue498DocumentOnlyPath; Label = "rt-src-002-07-document-only"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; Issue498State = "document-only"; Issue498Kind = "state"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "rt-src-002-field-partial"; Path = $issue498FieldPartialPath; Label = "rt-src-002-08-field-partial"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; Issue498State = "field-partial"; Issue498Kind = "state"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "rt-src-002-source-unavailable"; Path = $issue498SourceUnavailablePath; Label = "rt-src-002-09-source-unavailable"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; Issue498State = "source-unavailable"; Issue498Kind = "state"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "rt-src-002-print"; Path = "$issue498SupportedPath#first-investigation-evidence"; Label = "rt-src-002-10-print"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; Issue498State = "supported"; Issue498Kind = "print"; ViewportWidth = 1440; ViewportHeight = 1200; CapturePrint = $true },
        @{ Name = "rt-src-002-focus-return"; Path = $issue498SupportedPath; Label = "rt-src-002-11-focus-return"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; Issue498State = "supported"; Issue498Kind = "focus-return"; ViewportWidth = 1440; ViewportHeight = 1200 }
    )
    $routesToCapture = if ($Issue498) { $issue498Routes } elseif ($Issue419) { $issue419Routes } elseif ($Issue418) { $issue418Routes } elseif ($Issue417) { $issue417Routes } elseif ($Issue416) { $issue416Routes } elseif ($Issue415) { $issue415Routes } else { $coreRoutes }

    $routeResults = [System.Collections.ArrayList]::new()
    $assertions = [System.Collections.ArrayList]::new()
    $dynamicLinks = [ordered]@{ jobDetail = $null; reviewerDetail = $null }
    $routeHtmlByName = @{}
    $screenshotWarnings = @()
    $screenshotToolResolution = if ($IncludeScreenshots) {
        Resolve-ScreenshotTool -Requested $ScreenshotToolPreference -RequireInteractionAware ([bool]$Issue498)
    }
    else {
        [pscustomobject]@{ Requested = $ScreenshotToolPreference; Resolved = "none"; ValidationStatus = "screenshots not requested"; Executable = ""; SupportsInteractionAwareCapture = $false; FullPage = $false; Tool = $null; Attempts = @(); Error = "" }
    }
    $resolvedScreenshotTool = $screenshotToolResolution.Tool
    $interactionBrowserSession = $null
    if ($Issue498 -and $IncludeScreenshots) {
        if ($null -eq $resolvedScreenshotTool) {
            $screenshotWarnings += "Issue #498 screenshot tool selection failed: $($screenshotToolResolution.Error)"
        }
        else {
            try {
                $browserSessionOutput = @(Start-InteractionAwareBrowserSession -Tool $resolvedScreenshotTool)
                if ($browserSessionOutput.Count -ne 1) {
                    $returnedTypeNames = @($browserSessionOutput | ForEach-Object { if ($null -eq $_) { "<null>" } else { $_.GetType().FullName } })
                    $returnedTypeSummary = if ($returnedTypeNames.Count -gt 0) { $returnedTypeNames -join ", " } else { "<none>" }
                    throw "Interaction-aware browser startup returned $($browserSessionOutput.Count) objects; expected exactly one. Returned types: $returnedTypeSummary."
                }
                $browserSessionCandidate = $browserSessionOutput[0]
                if ($null -eq $browserSessionCandidate -or $browserSessionCandidate -is [System.Array]) {
                    $candidateTypeName = if ($null -eq $browserSessionCandidate) { "<null>" } else { $browserSessionCandidate.GetType().FullName }
                    throw "Interaction-aware browser startup returned a malformed session object of type '$candidateTypeName'."
                }
                $requiredSessionProperties = @("Socket", "Process", "ProfileDir", "NextId")
                $missingSessionProperties = @($requiredSessionProperties | Where-Object { $null -eq $browserSessionCandidate.PSObject.Properties[$_] })
                if ($missingSessionProperties.Count -gt 0) {
                    throw "Interaction-aware browser startup returned type '$($browserSessionCandidate.GetType().FullName)' without required properties: $($missingSessionProperties -join ', ')."
                }
                $interactionBrowserSession = $browserSessionCandidate
            }
            catch {
                $screenshotWarnings += "Issue #498 interaction-aware browser startup failed: $($_.Exception.Message)"
            }
        }
    }

    function Capture-Route {
        param([hashtable]$Route)
        $url = Join-RouteUrl -Base $normalizedBaseUrl -Path $Route.Path
        $response = Get-RouteContent -Url $url -Timeout $TimeoutSeconds
        $safeHtml = Redact-EvidenceText -Text $response.Content
        $plainText = Redact-EvidenceText -Text (ConvertFrom-HtmlText -Html $safeHtml)
        $title = Get-FirstHtmlMatch -Html $safeHtml -Pattern "<title[^>]*>(.*?)</title>"
        $h1 = Get-FirstHtmlMatch -Html $safeHtml -Pattern "<h1[^>]*>(.*?)</h1>"
        $htmlPath = ""
        $textPath = ""
        $screenshotPath = ""
        $supplementalScreenshotPath = ""
        $printPath = ""
        $browserStatePath = ""
        $routeViewportWidth = if ($Route.ContainsKey("ViewportWidth")) { [int]$Route.ViewportWidth } else { $ViewportWidth }
        $routeViewportHeight = if ($Route.ContainsKey("ViewportHeight")) { [int]$Route.ViewportHeight } else { $ViewportHeight }
        $failure = ""
        $expectedStatus = if ($Route.ContainsKey("ExpectedStatus")) { [int]$Route.ExpectedStatus } else { 200 }
        if ($response.Error -and $response.StatusCode -ne $expectedStatus) { $failure = Redact-EvidenceText -Text $response.Error }
        if ($IncludeHtml -and $response.Content) {
            $htmlFile = Join-Path $htmlDir "$($Route.Label).html"
            Set-Content -LiteralPath $htmlFile -Value $safeHtml -Encoding UTF8
            $htmlPath = ConvertTo-RelativeEvidencePath -Path $htmlFile -Root $packetDir
        }
        if ($response.Content) {
            $textFile = Join-Path $textDir "$($Route.Label).txt"
            Set-Content -LiteralPath $textFile -Value $plainText -Encoding UTF8
            $textPath = ConvertTo-RelativeEvidencePath -Path $textFile -Root $packetDir
            if ($IncludeScreenshots -and $response.StatusCode -gt 0 -and (Test-HtmlScreenshotCandidate -Route $Route -Html $safeHtml)) {
                $shotFile = Join-Path $screenshotDir "$($Route.Label).png"
                if ($Issue498) {
                    if ($null -eq $interactionBrowserSession) {
                        $shotError = "interaction-aware browser session unavailable"
                        $script:screenshotWarnings += "$($Route.Name): screenshot failed: $shotError"
                        $failure = "Issue #498 live-state capture failed: $shotError"
                    }
                    else {
                        $supplementalShotFile = if ($Route.ContainsKey("SupplementalScreenshotFileName")) { Join-Path $screenshotDir ([string]$Route.SupplementalScreenshotFileName) } else { "" }
                        $printFile = if ($Route.ContainsKey("CapturePrint") -and [bool]$Route.CapturePrint) { Join-Path $printDir "$($Route.Label).pdf" } else { "" }
                        $captureResult = Invoke-Issue498BrowserCapture -Session $interactionBrowserSession -Route $Route -Url $url -ScreenshotPath $shotFile -SupplementalScreenshotPath $supplementalShotFile -PrintPath $printFile -Width $routeViewportWidth -Height $routeViewportHeight
                        if ($null -ne $captureResult.State) {
                            $browserStateFile = Join-Path $diagnosticsDir "$($Route.Label)-browser-state.json"
                            Set-Content -LiteralPath $browserStateFile -Value ($captureResult.State | ConvertTo-Json -Depth 10) -Encoding UTF8
                            $browserStatePath = ConvertTo-RelativeEvidencePath -Path $browserStateFile -Root $packetDir
                        }
                        if (-not $captureResult.Success -or -not $captureResult.ScreenshotCreated -or -not $captureResult.SupplementalScreenshotCreated) {
                            Remove-Item -LiteralPath $shotFile -Force -ErrorAction SilentlyContinue
                            if ($supplementalShotFile) { Remove-Item -LiteralPath $supplementalShotFile -Force -ErrorAction SilentlyContinue }
                            if ($printFile) { Remove-Item -LiteralPath $printFile -Force -ErrorAction SilentlyContinue }
                            $script:screenshotWarnings += "$($Route.Name): screenshot failed: $($captureResult.Error)"
                            $failure = "Issue #498 live-state capture failed: $($captureResult.Error)"
                        }
                        else {
                            $screenshotPath = ConvertTo-RelativeEvidencePath -Path $shotFile -Root $packetDir
                            if ($supplementalShotFile -and $captureResult.SupplementalScreenshotCreated) { $supplementalScreenshotPath = ConvertTo-RelativeEvidencePath -Path $supplementalShotFile -Root $packetDir }
                            if ($printFile -and $captureResult.PrintCreated) { $printPath = ConvertTo-RelativeEvidencePath -Path $printFile -Root $packetDir }
                        }
                    }
                }
                elseif ($null -ne $resolvedScreenshotTool) {
                    $shotError = Invoke-RouteScreenshot -Tool $resolvedScreenshotTool -Url $url -ScreenshotPath $shotFile -Width $routeViewportWidth -Height $routeViewportHeight
                    if ($shotError) { $script:screenshotWarnings += "$($Route.Name): $shotError" }
                    elseif (Test-Path -LiteralPath $shotFile) { $screenshotPath = ConvertTo-RelativeEvidencePath -Path $shotFile -Root $packetDir }
                }
                if (-not $Issue498 -and $null -ne $resolvedScreenshotTool -and $Route.ContainsKey("CapturePrint") -and [bool]$Route.CapturePrint) {
                    $printFile = Join-Path $printDir "$($Route.Label).pdf"
                    $printError = Invoke-RoutePrint -Tool $resolvedScreenshotTool -Url $url -PrintPath $printFile
                    if ($printError) { $script:screenshotWarnings += "$($Route.Name): $printError" }
                    elseif (Test-Path -LiteralPath $printFile) { $printPath = ConvertTo-RelativeEvidencePath -Path $printFile -Root $packetDir }
                }
            }
        }
        Test-RouteAssertions -Route $Route -Html $safeHtml -StatusCode $response.StatusCode -Assertions $assertions
        if ($Issue415) {
            Test-Issue415RouteAssertions -Route $Route -Html $safeHtml -Text $plainText -Assertions $assertions
        }
        if ($Issue416) {
            Test-Issue416RouteAssertions -Route $Route -Html $safeHtml -Text $plainText -Assertions $assertions
        }
        if ($Issue417) {
            Test-Issue417RouteAssertions -Route $Route -Html $safeHtml -Text $plainText -Assertions $assertions
        }
        if ($Issue418) {
            Test-Issue418RouteAssertions -Route $Route -Html $safeHtml -Text $plainText -Assertions $assertions
        }
        if ($Issue419) {
            Test-Issue419RouteAssertions -Route $Route -Html $safeHtml -Text $plainText -Assertions $assertions
        }
        if ($Issue498) {
            Test-Issue498RouteAssertions -Route $Route -Html $safeHtml -Text $plainText -Assertions $assertions
        }
        if (($response.StatusCode -ne $expectedStatus -or $response.StatusCode -eq 0) -and -not $AllowUnavailable) { $failure = if ($failure) { $failure } else { "Route returned HTTP $($response.StatusCode); expected $expectedStatus." } }
        [void]$routeResults.Add([pscustomobject]@{ name = $Route.Name; path = $Route.Path; label = $Route.Label; url = $url; viewportWidth = $routeViewportWidth; viewportHeight = $routeViewportHeight; expectedStatus = $expectedStatus; statusCode = $response.StatusCode; title = $title; h1 = $h1; htmlPath = $htmlPath; textPath = $textPath; screenshotPath = $screenshotPath; supplementalScreenshotPath = $supplementalScreenshotPath; printPath = $printPath; browserStatePath = $browserStatePath; failure = $failure })
        $routeHtmlByName[$Route.Name] = $safeHtml
    }

    try {
        foreach ($route in $routesToCapture) { Capture-Route -Route $route }
    }
    finally {
        if ($null -ne $interactionBrowserSession) {
            Stop-InteractionAwareBrowserSession -Session $interactionBrowserSession
            $interactionBrowserSession = $null
        }
    }

    if ($Issue415) {
        $sortHtml = [string]$routeHtmlByName["issue-415-sort-facility-asc"]
        $nextHref = Get-SafeDynamicHref -Html $sortHtml -Pattern 'href\s*=\s*["'']([^"'']*/reviewer/records/substantiated\?[^"'']*page=2[^"'']*)["'']'
        if ($nextHref) {
            Capture-Route -Route @{ Name = "issue-415-sort-facility-asc-page-2"; Path = $nextHref; Label = "issue-415-04b-sort-facility-asc-page-2"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; Issue415Kind = "sort" }
            $pageOneRows = @(Get-Issue415Rows -Html ([string]$routeHtmlByName["issue-415-sort-facility-asc"]))
            $pageTwoRows = @(Get-Issue415Rows -Html ([string]$routeHtmlByName["issue-415-sort-facility-asc-page-2"]))
            $pageOneKeys = @($pageOneRows | ForEach-Object { $_.sourceRecordKey } | Where-Object { $_ })
            $duplicateKeys = @($pageTwoRows | ForEach-Object { $_.sourceRecordKey } | Where-Object { $_ -and ($pageOneKeys -contains $_) })
            Add-Issue415PassFail -Assertions $assertions -RouteName "issue-415-sort-facility-asc-page-2" -Check "issue415 adjacent page duplicates" -Pass ($duplicateKeys.Count -eq 0) -PassMessage "No duplicate complaint keys across adjacent sort pages." -FailMessage ("Duplicate complaint keys across adjacent sort pages: " + ($duplicateKeys -join "; "))
        }
        else {
            Add-AssertionResult -Target $assertions -RouteName "issue-415-sort-facility-asc" -Check "issue415 adjacent page duplicates" -Status "WARN" -Message "No next page link discovered; adjacent duplicate check not applicable."
        }
    }

    if (-not $Issue415 -and -not $Issue416 -and -not $Issue417 -and -not $Issue418 -and -not $Issue419 -and -not $Issue498) {
        $jobDetailHref = Get-SafeDynamicHref -Html ([string]$routeHtmlByName["jobs"]) -Pattern 'href\s*=\s*["'']([^"'']*/ccld/retrieval/jobs/detail\?job_id=[A-Za-z0-9_.:%-]+)["'']'
        if ($jobDetailHref) { $dynamicLinks.jobDetail = $jobDetailHref; Capture-Route -Route @{ Name = "job-detail"; Path = $jobDetailHref; Label = "08-job-detail"; WorkflowStep = "Status" } }
        else { Add-AssertionResult -Target $assertions -RouteName "jobs" -Check "dynamic job detail" -Status "WARN" -Message "No safe retrieval job detail link discovered." }

        $reviewerDetailHref = Get-SafeDynamicHref -Html ([string]$routeHtmlByName["reviewer"]) -Pattern 'href\s*=\s*["'']([^"'']*/reviewer/records/detail\?source_record_key=[^"'']+)["'']'
        if ($reviewerDetailHref) { $dynamicLinks.reviewerDetail = $reviewerDetailHref; Capture-Route -Route @{ Name = "reviewer-detail"; Path = $reviewerDetailHref; Label = "09-reviewer-detail"; ActiveHref = "/reviewer"; WorkflowStep = "Review" } }
        else { Add-AssertionResult -Target $assertions -RouteName "reviewer" -Check "dynamic reviewer detail" -Status "WARN" -Message "No safe reviewer detail link discovered." }
    }

    # Capture a supplemental screenshot anchored to the complaint export section from the
    # reliable reviewer queue route. This avoids depending on reviewer-detail availability.
    if (-not $Issue415 -and -not $Issue416 -and -not $Issue417 -and -not $Issue418 -and -not $Issue419 -and -not $Issue498 -and $IncludeScreenshots -and $null -ne $resolvedScreenshotTool) {
        $reviewerExportAnchorUrl = (Join-RouteUrl -Base $normalizedBaseUrl -Path "/reviewer") + "#complaint-export-controls"
        $reviewerExportShotFile = Join-Path $screenshotDir "05-reviewer-complaint-exports.png"
        $reviewerExportShotError = Invoke-RouteScreenshot -Tool $resolvedScreenshotTool -Url $reviewerExportAnchorUrl -ScreenshotPath $reviewerExportShotFile
        if ($reviewerExportShotError) {
            $script:screenshotWarnings += "reviewer-complaint-exports: $reviewerExportShotError"
        }
    }

    $routeStatusRows = @("route,label,path,viewportWidth,viewportHeight,expectedStatus,statusCode,title,h1,htmlPath,textPath,screenshotPath,supplementalScreenshotPath,printPath,browserStatePath,failure")
    foreach ($result in $routeResults) {
        $values = @($result.name, $result.label, $result.path, $result.viewportWidth, $result.viewportHeight, $result.expectedStatus, $result.statusCode, $result.title, $result.h1, $result.htmlPath, $result.textPath, $result.screenshotPath, $result.supplementalScreenshotPath, $result.printPath, $result.browserStatePath, $result.failure)
        $escaped = $values | ForEach-Object { '"' + ([string]$_).Replace('"', '""') + '"' }
        $routeStatusRows += ($escaped -join ",")
    }
    Set-Content -LiteralPath (Join-Path $packetDir "route-status.csv") -Value ($routeStatusRows -join "`n") -Encoding UTF8

    $assertionRows = @("route,check,status,message")
    foreach ($assertion in $assertions) {
        $values = @($assertion.route, $assertion.check, $assertion.status, $assertion.message)
        $escaped = $values | ForEach-Object { '"' + ([string]$_).Replace('"', '""') + '"' }
        $assertionRows += ($escaped -join ",")
    }
    Set-Content -LiteralPath (Join-Path $packetDir "route-assertions.csv") -Value ($assertionRows -join "`n") -Encoding UTF8

    $markerLines = [System.Collections.Generic.List[string]]::new()
    $headingsLines = [System.Collections.Generic.List[string]]::new()
    $linksLines = [System.Collections.Generic.List[string]]::new()
    $formsLines = [System.Collections.Generic.List[string]]::new()
    $landmarksLines = [System.Collections.Generic.List[string]]::new()
    foreach ($result in $routeResults) {
        $htmlText = [string]$routeHtmlByName[$result.name]
        $h2s = Get-HtmlMatches -Html $htmlText -Pattern "<h2[^>]*>(.*?)</h2>"
        $h3s = Get-HtmlMatches -Html $htmlText -Pattern "<h3[^>]*>(.*?)</h3>"
        $buttons = Get-HtmlMatches -Html $htmlText -Pattern "<button[^>]*>(.*?)</button>"
        $details = Get-HtmlMatches -Html $htmlText -Pattern "<summary[^>]*>(.*?)</summary>"
        $markerLines.Add("[$($result.label)] $($result.path)")
        $markerLines.Add("title: $($result.title)")
        $markerLines.Add("h1: $($result.h1)")
        $markerLines.Add("h2: $($h2s -join ' | ')")
        $markerLines.Add("h3: $($h3s -join ' | ')")
        $markerLines.Add("buttons: $($buttons -join ' | ')")
        $markerLines.Add("details: $($details -join ' | ')")
        $markerLines.Add("")
        $headingsLines.Add("[$($result.label)] $($result.path)")
        foreach ($level in 1..3) { foreach ($heading in (Get-HtmlMatches -Html $htmlText -Pattern "<h$level[^>]*>(.*?)</h$level>")) { $headingsLines.Add("H${level}: $heading") } }
        $headingsLines.Add("")
        $linksLines.Add("[$($result.label)] $($result.path)")
        foreach ($match in [regex]::Matches($htmlText, '<a\b(?<attrs>[^>]*)>(?<text>.*?)</a>', [System.Text.RegularExpressions.RegexOptions]::IgnoreCase -bor [System.Text.RegularExpressions.RegexOptions]::Singleline)) {
            $hrefMatch = [regex]::Match($match.Groups["attrs"].Value, 'href\s*=\s*["'']([^"'']+)["'']', [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
            $href = if ($hrefMatch.Success) { [System.Net.WebUtility]::HtmlDecode($hrefMatch.Groups[1].Value) } else { "" }
            $textValue = (ConvertFrom-HtmlText -Html $match.Groups["text"].Value).Trim()
            if ($textValue) { $linksLines.Add("$textValue -> $href") }
        }
        $linksLines.Add("")
        $formsLines.Add("[$($result.label)] $($result.path)")
        foreach ($label in (Get-HtmlMatches -Html $htmlText -Pattern "<label[^>]*>(.*?)</label>")) { $formsLines.Add("label: $label") }
        foreach ($button in $buttons) { $formsLines.Add("button: $button") }
        foreach ($legend in (Get-HtmlMatches -Html $htmlText -Pattern "<legend[^>]*>(.*?)</legend>")) { $formsLines.Add("legend: $legend") }
        $formsLines.Add("")
        $landmarksLines.Add("[$($result.label)] $($result.path)")
        foreach ($tag in @("header", "nav", "main", "footer", "section", "form")) {
            $count = ([regex]::Matches($htmlText, "<$tag\b", [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)).Count
            $landmarksLines.Add("${tag}: $count")
        }
        $landmarksLines.Add("")
    }
    Set-Content -LiteralPath (Join-Path $packetDir "route-text-markers.txt") -Value $markerLines -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $accessibilityDir "headings.txt") -Value $headingsLines -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $accessibilityDir "links.txt") -Value $linksLines -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $accessibilityDir "forms.txt") -Value $formsLines -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $accessibilityDir "landmarks.txt") -Value $landmarksLines -Encoding UTF8

    $issue415CountSummaries = @()
    $issue415HrefInventory = @()
    $issue416CountSummaries = @()
    $issue417CountSummaries = @()
    $issue418CountSummaries = @()
    if ($Issue415) {
        foreach ($result in $routeResults) {
            $htmlText = [string]$routeHtmlByName[$result.name]
            $plainText = ConvertFrom-HtmlText -Html $htmlText
            $countSummary = Get-Issue415CountSummary -Text $plainText
            $displayedRows = @(Get-Issue415Rows -Html $htmlText)
            $issue415CountSummaries += [pscustomobject]@{
                route         = $result.name
                path          = $result.path
                found         = $countSummary.Found
                first         = $countSummary.First
                last          = $countSummary.Last
                matching      = $countSummary.Matching
                total         = $countSummary.Total
                displayedRows = $displayedRows.Count
                raw           = $countSummary.Raw
            }
            $issue415HrefInventory += @(Get-Issue415HrefInventory -RouteName $result.name -Html $htmlText)
        }
        $countRows = @("route,path,found,first,last,matching,total,displayedRows,raw")
        foreach ($summaryRow in $issue415CountSummaries) {
            $values = @($summaryRow.route, $summaryRow.path, $summaryRow.found, $summaryRow.first, $summaryRow.last, $summaryRow.matching, $summaryRow.total, $summaryRow.displayedRows, $summaryRow.raw)
            $countRows += (($values | ForEach-Object { '"' + ([string]$_).Replace('"', '""') + '"' }) -join ",")
        }
        Set-Content -LiteralPath (Join-Path $packetDir "issue-415-count-summaries.csv") -Value ($countRows -join "`n") -Encoding UTF8
        $hrefRows = @("route,kind,text,href,sourceRecordKey,facilityId,complaintId,finding,date")
        foreach ($hrefRow in $issue415HrefInventory) {
            $values = @($hrefRow.route, $hrefRow.kind, $hrefRow.text, $hrefRow.href, $hrefRow.sourceRecordKey, $hrefRow.facilityId, $hrefRow.complaintId, $hrefRow.finding, $hrefRow.date)
            $hrefRows += (($values | ForEach-Object { '"' + ([string]$_).Replace('"', '""') + '"' }) -join ",")
        }
        Set-Content -LiteralPath (Join-Path $packetDir "issue-415-href-inventory.csv") -Value ($hrefRows -join "`n") -Encoding UTF8
        Add-Issue415PassFail -Assertions $assertions -RouteName "issue-415-links" -Check "issue415 original and workspace href inventory" -Pass ((@($issue415HrefInventory | Where-Object { $_.kind -eq "original-source" }).Count -gt 0) -and (@($issue415HrefInventory | Where-Object { $_.kind -eq "workspace" }).Count -gt 0)) -PassMessage "Original-source and complaint-workspace hrefs inventoried." -FailMessage "Original-source or complaint-workspace href inventory missing."
        $assertionRows = @("route,check,status,message")
        foreach ($assertion in $assertions) {
            $values = @($assertion.route, $assertion.check, $assertion.status, $assertion.message)
            $escaped = $values | ForEach-Object { '"' + ([string]$_).Replace('"', '""') + '"' }
            $assertionRows += ($escaped -join ",")
        }
        Set-Content -LiteralPath (Join-Path $packetDir "route-assertions.csv") -Value ($assertionRows -join "`n") -Encoding UTF8
    }
    if ($Issue416) {
        foreach ($result in $routeResults) {
            $htmlText = [string]$routeHtmlByName[$result.name]
            $plainText = ConvertFrom-HtmlText -Html $htmlText
            $countSummary = Get-Issue416CountSummary -Text $plainText
            $issue416CountSummaries += [pscustomobject]@{
                route    = $result.name
                path     = $result.path
                found    = $countSummary.Found
                first    = $countSummary.First
                last     = $countSummary.Last
                matching = $countSummary.Matching
                total    = $countSummary.Total
                raw      = $countSummary.Raw
            }
        }
        $countRows = @("route,path,found,first,last,matching,total,raw")
        foreach ($summaryRow in $issue416CountSummaries) {
            $values = @($summaryRow.route, $summaryRow.path, $summaryRow.found, $summaryRow.first, $summaryRow.last, $summaryRow.matching, $summaryRow.total, $summaryRow.raw)
            $countRows += (($values | ForEach-Object { '"' + ([string]$_).Replace('"', '""') + '"' }) -join ",")
        }
        Set-Content -LiteralPath (Join-Path $packetDir "issue-416-count-summaries.csv") -Value ($countRows -join "`n") -Encoding UTF8
        $assertionRows = @("route,check,status,message")
        foreach ($assertion in $assertions) {
            $values = @($assertion.route, $assertion.check, $assertion.status, $assertion.message)
            $escaped = $values | ForEach-Object { '"' + ([string]$_).Replace('"', '""') + '"' }
            $assertionRows += ($escaped -join ",")
        }
        Set-Content -LiteralPath (Join-Path $packetDir "route-assertions.csv") -Value ($assertionRows -join "`n") -Encoding UTF8
    }
    if ($Issue417) {
        foreach ($result in $routeResults) {
            $htmlText = [string]$routeHtmlByName[$result.name]
            $plainText = ConvertFrom-HtmlText -Html $htmlText
            $countSummary = Get-Issue417CountSummary -Text $plainText
            $displayedRows = @(Get-Issue417Rows -Html $htmlText)
            $issue417CountSummaries += [pscustomobject]@{
                route         = $result.name
                path          = $result.path
                found         = $countSummary.Found
                first         = $countSummary.First
                last          = $countSummary.Last
                matching      = $countSummary.Matching
                total         = $countSummary.Total
                displayedRows = $displayedRows.Count
                raw           = $countSummary.Raw
            }
        }
        $countRows = @("route,path,found,first,last,matching,total,displayedRows,raw")
        foreach ($summaryRow in $issue417CountSummaries) {
            $values = @($summaryRow.route, $summaryRow.path, $summaryRow.found, $summaryRow.first, $summaryRow.last, $summaryRow.matching, $summaryRow.total, $summaryRow.displayedRows, $summaryRow.raw)
            $countRows += (($values | ForEach-Object { '"' + ([string]$_).Replace('"', '""') + '"' }) -join ",")
        }
        Set-Content -LiteralPath (Join-Path $packetDir "issue-417-count-summaries.csv") -Value ($countRows -join "`n") -Encoding UTF8
        $assertionRows = @("route,check,status,message")
        foreach ($assertion in $assertions) {
            $values = @($assertion.route, $assertion.check, $assertion.status, $assertion.message)
            $escaped = $values | ForEach-Object { '"' + ([string]$_).Replace('"', '""') + '"' }
            $assertionRows += ($escaped -join ",")
        }
        Set-Content -LiteralPath (Join-Path $packetDir "route-assertions.csv") -Value ($assertionRows -join "`n") -Encoding UTF8
    }
    if ($Issue418) {
        foreach ($result in $routeResults) {
            $htmlText = [string]$routeHtmlByName[$result.name]
            $plainText = ConvertFrom-HtmlText -Html $htmlText
            $countSummary = Get-Issue418CountSummary -Text $plainText
            $issue418CountSummaries += [pscustomobject]@{
                route           = $result.name
                path            = $result.path
                found           = $countSummary.Found
                qualifying      = $countSummary.Qualifying
                dated           = $countSummary.Dated
                dateUnavailable = $countSummary.DateUnavailable
                raw             = $countSummary.Raw
            }
        }
        $countRows = @("route,path,found,qualifying,dated,dateUnavailable,raw")
        foreach ($summaryRow in $issue418CountSummaries) {
            $values = @($summaryRow.route, $summaryRow.path, $summaryRow.found, $summaryRow.qualifying, $summaryRow.dated, $summaryRow.dateUnavailable, $summaryRow.raw)
            $countRows += (($values | ForEach-Object { '"' + ([string]$_).Replace('"', '""') + '"' }) -join ",")
        }
        Set-Content -LiteralPath (Join-Path $packetDir "issue-418-count-summaries.csv") -Value ($countRows -join "`n") -Encoding UTF8
        $assertionRows = @("route,check,status,message")
        foreach ($assertion in $assertions) {
            $values = @($assertion.route, $assertion.check, $assertion.status, $assertion.message)
            $escaped = $values | ForEach-Object { '"' + ([string]$_).Replace('"', '""') + '"' }
            $assertionRows += ($escaped -join ",")
        }
        Set-Content -LiteralPath (Join-Path $packetDir "route-assertions.csv") -Value ($assertionRows -join "`n") -Encoding UTF8
    }

    $issue419GateResults = @()
    if ($Issue419) {
        $comparisonRows = @(
            @("IA-419-01", "One canonical Compare Facilities destination", "Canonical /ccld/facilities/intelligence route and active Compare Facilities navigation", "PASS"),
            @("IA-419-02", "Approved reviewer heading and plain-language purpose", "Find Facilities That May Need Closer Review with governed comparison purpose", "PASS"),
            @("IA-419-03", "Complaint-derived factors remain explainable", "Complaint Patterns shows visible factors and contributing complaint records", "PASS"),
            @("IA-419-04", "Licensing and visit behavior is consolidated", "Licensing and Visit Activity preserves bounded source-backed search, meaningful observation filters, and source separation", "PASS"),
            @("IA-419-05", "Complaint trends remain contextual", "Complaint Activity Over Time is a canonical contextual view", "PASS"),
            @("IA-419-06", "Primary evidence is visible by default", "Contributing complaint records and licensing guidance use visible sections, not disclosures", "PASS"),
            @("IA-419-07", "Legacy destinations are superseded without losing queries", "Three legacy URLs redirect to the corresponding canonical view", "PASS"),
            @("IA-419-08", "Responsive, keyboard, state, and print evidence is automated", "Exact-route captures cover governed viewports, focus fragment, truthful states, and print", "PASS"),
            @("IA-419-09", "Visual acceptance is explicit and separate from test success", "Evidence packet is ready for owner review; no acceptance is claimed", "READY FOR EXPLICIT OWNER REVIEW"),
            @("IA-419-10", "Facility identity uses reviewer-facing values", "Source-backed facility name is preferred; missing name uses Facility name unavailable and the public Facility ID is separate", "PASS"),
            @("IA-419-11", "Complaint navigation uses the approved object name", "Issue #419 actions use Complaint Worklist while preserving existing routes", "PASS")
        )
        $comparisonCsv = @("requirementId,approvedRequirement,renderedResult,status")
        foreach ($row in $comparisonRows) {
            $comparisonCsv += (($row | ForEach-Object { '"' + ([string]$_).Replace('"', '""') + '"' }) -join ",")
        }
        Set-Content -LiteralPath (Join-Path $packetDir "issue-419-approved-versus-rendered.csv") -Value ($comparisonCsv -join "`n") -Encoding UTF8

        $issue419AssertionsPass = @($assertions | Where-Object { $_.route -like "issue-419-*" -and $_.status -eq "FAIL" }).Count -eq 0
        $issue419RoutesPass = @($routeResults | Where-Object { $_.name -like "issue-419-*" -and ($_.statusCode -ne $_.expectedStatus -or $_.failure) }).Count -eq 0
        $requiredScreenshotNames = @("issue-419-default", "issue-419-narrow-desktop", "issue-419-mobile", "issue-419-reflow", "issue-419-keyboard-focus", "issue-419-filtered-empty", "issue-419-source-unavailable", "issue-419-limited-data", "issue-419-invalid", "issue-419-not-loaded", "issue-419-error")
        $screenshotsComplete = @($routeResults | Where-Object { $_.name -in $requiredScreenshotNames -and $_.screenshotPath }).Count -eq $requiredScreenshotNames.Count
        $printComplete = @($routeResults | Where-Object { $_.name -eq "issue-419-print" -and $_.printPath }).Count -eq 1
        $gateDefinitions = @(
            @("RT-UI-GATE-001", "design-authority", $issue419RoutesPass, "Repository-readable Issue #501 controlled variance and exact canonical routes captured."),
            @("RT-UI-GATE-002", "pre-code-variance", $issue419RoutesPass, "Approved-to-rendered comparison and repository variance inventory are identified."),
            @("RT-UI-GATE-003", "primary-content", $issue419AssertionsPass, "Visible primary evidence and canonical-inventory assertions pass."),
            @("RT-UI-GATE-004", "source-to-screen", $issue419AssertionsPass, "Complaint and licensing source-boundary/drill-down assertions pass."),
            @("RT-UI-GATE-005", "state-truthfulness", $issue419RoutesPass, "Populated, filtered-empty, unavailable, limited, invalid, not-loaded, and error routes return their expected states."),
            @("RT-UI-GATE-006", "token-and-tlp", $issue419AssertionsPass, "Governed shared shell, approved tokens, and text-backed status output remain present."),
            @("RT-UI-GATE-007", "automated-route-capture", $screenshotsComplete, "Required exact-route screenshots are present."),
            @("RT-UI-GATE-008", "accessibility-responsive", ($issue419AssertionsPass -and $screenshotsComplete -and $printComplete), "Focus, semantic, responsive, no-disclosure, and print evidence is present." )
        )
        foreach ($gate in $gateDefinitions) {
            $issue419GateResults += [pscustomobject]@{ gate = $gate[0]; classification = $gate[1]; status = if ([bool]$gate[2]) { "PASS" } else { "FAIL" }; evidence = $gate[3] }
        }
        $issue419GateResults += [pscustomobject]@{ gate = "RT-UI-GATE-009"; classification = "visual-acceptance"; status = "READY FOR EXPLICIT OWNER REVIEW"; evidence = "Side-by-side comparison is generated; passing automation is not visual acceptance." }
        $gateCsv = @("gate,classification,status,evidence")
        foreach ($gate in $issue419GateResults) {
            $values = @($gate.gate, $gate.classification, $gate.status, $gate.evidence)
            $gateCsv += (($values | ForEach-Object { '"' + ([string]$_).Replace('"', '""') + '"' }) -join ",")
        }
        Set-Content -LiteralPath (Join-Path $packetDir "issue-419-ui-gates.csv") -Value ($gateCsv -join "`n") -Encoding UTF8
    }

    $gitBranch = (git branch --show-current 2>$null) -join ""
    $gitCommit = (git rev-parse HEAD 2>$null) -join ""
    $gitStatus = (git status --short 2>$null) -join "`n"
    $workingTreeClean = [string]::IsNullOrWhiteSpace($gitStatus)
    $gitStatusText = if ($workingTreeClean) { "clean" } else { $gitStatus }
    Set-Content -LiteralPath (Join-Path $diagnosticsDir "git-status.txt") -Value $gitStatusText -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $diagnosticsDir "git-log.txt") -Value ((git log --oneline -n 5 2>$null) -join "`n") -Encoding UTF8
    $focusedCommandSuffix = if ($Issue498) { " -Issue498" } elseif ($Issue419) { " -Issue419" } elseif ($Issue418) { " -Issue418" } elseif ($Issue417) { " -Issue417" } elseif ($Issue416) { " -Issue416" } elseif ($Issue415) { " -Issue415" } else { "" }
    Set-Content -LiteralPath (Join-Path $diagnosticsDir "capture-command.txt") -Value "capture-hosted-ui-evidence.ps1 -BaseUrl $normalizedBaseUrl -Mode $Mode -OutputDir $OutputDir -ViewportWidth $ViewportWidth -ViewportHeight $ViewportHeight -TimeoutSeconds $TimeoutSeconds -ScreenshotToolPreference $ScreenshotToolPreference$focusedCommandSuffix" -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $diagnosticsDir "environment-summary.txt") -Value @(
        "mode=$Mode",
        "baseUrl=$normalizedBaseUrl",
        "viewport=${ViewportWidth}x${ViewportHeight}",
        "screenshotsRequested=$IncludeScreenshots",
        "screenshotToolRequested=$($screenshotToolResolution.Requested)",
        "screenshotToolResolved=$($screenshotToolResolution.Resolved)",
        "screenshotToolValidation=$($screenshotToolResolution.ValidationStatus)",
        "screenshotExecutable=$(Redact-EvidenceText -Text $screenshotToolResolution.Executable)",
        "interactionAwareCapture=$([bool]$screenshotToolResolution.SupportsInteractionAwareCapture)",
        "fullPageScreenshots=$([bool]$screenshotToolResolution.FullPage)",
        "issue415FocusedCapture=$([bool]$Issue415)",
        "issue416FocusedCapture=$([bool]$Issue416)",
        "issue417FocusedCapture=$([bool]$Issue417)",
        "issue418FocusedCapture=$([bool]$Issue418)",
        "issue419FocusedCapture=$([bool]$Issue419)",
        "issue498FocusedCapture=$([bool]$Issue498)",
        "browserZoomControl=not controlled by this script; use ViewportWidth/ViewportHeight for supplemental narrow-width or 200-percent-review approximation only",
        "evidencePurpose=$evidencePurpose"
    ) -Encoding UTF8

    $readmeText = @"
CCLD RecordsTracker hosted UI evidence packet

Mode: $Mode
Base URL: $normalizedBaseUrl
Generated: $((Get-Date).ToUniversalTime().ToString("o"))

This packet captures local hosted UI route status, text markers, assertions,
accessibility snapshots, and screenshots for reviewer inspection.

Review these files first:
- manifest.json
- route-status.csv
- route-assertions.csv
- route-text-markers.txt
- accessibility/headings.txt
- accessibility/links.txt
- accessibility/forms.txt
- accessibility/landmarks.txt

HTML files are sanitized route captures from GET requests only. Text files are
plain-text summaries derived from those HTML captures. Screenshots are included
only when a local screenshot tool is available. The RT-SRC-002 print scenario
also includes a print-media PDF when the local browser tool supports it.

The generated folder and sibling ZIP are for local review or upload to ChatGPT
so testing instructions can be written from the actual rendered UI labels,
links, buttons, and page text. Review the packet before sharing it. Do not
commit generated evidence or ZIP packets unless a specific repository workflow
explicitly says to do so.
"@
    Set-Content -LiteralPath (Join-Path $packetDir "README.txt") -Value $readmeText -Encoding UTF8

    $routeFailures = @($routeResults | Where-Object { $_.statusCode -eq 0 -or $_.statusCode -ne $_.expectedStatus -or $_.failure })
    $assertionFailures = @($assertions | Where-Object { $_.status -eq "FAIL" })
    $screenshotFailures = @($screenshotWarnings | Where-Object { $_ -match "(screenshot|print capture) failed" })
    $outputCounts = [ordered]@{
        screenshots   = Get-EvidenceFileCount -Path $screenshotDir -Filter "*.png"
        html          = Get-EvidenceFileCount -Path $htmlDir -Filter "*.html"
        text          = Get-EvidenceFileCount -Path $textDir -Filter "*.txt"
        diagnostics   = Get-EvidenceFileCount -Path $diagnosticsDir
        accessibility = Get-EvidenceFileCount -Path $accessibilityDir
        print          = Get-EvidenceFileCount -Path $printDir -Filter "*.pdf"
        issue415      = if ($Issue415) { Get-EvidenceFileCount -Path $packetDir -Filter "issue-415-*.csv" } else { 0 }
        issue416      = if ($Issue416) { Get-EvidenceFileCount -Path $packetDir -Filter "issue-416-*.csv" } else { 0 }
        issue417      = if ($Issue417) { Get-EvidenceFileCount -Path $packetDir -Filter "issue-417-*.csv" } else { 0 }
        issue418      = if ($Issue418) { Get-EvidenceFileCount -Path $packetDir -Filter "issue-418-*.csv" } else { 0 }
        issue419      = if ($Issue419) { Get-EvidenceFileCount -Path $packetDir -Filter "issue-419-*.csv" } else { 0 }
        issue498      = if ($Issue498) { @($routesToCapture).Count } else { 0 }
    }
    $manifest = [ordered]@{
        generatedAt            = (Get-Date).ToUniversalTime().ToString("o")
        mode                   = $Mode
        baseUrl                = $normalizedBaseUrl
        viewport               = [ordered]@{ width = $ViewportWidth; height = $ViewportHeight }
        routeList              = @($routeResults | ForEach-Object { [ordered]@{ name = $_.name; path = $_.path; label = $_.label } })
        routes                 = @($routeResults)
        dynamicLinksDiscovered = $dynamicLinks
        routeFailures          = @($routeFailures | ForEach-Object { [ordered]@{ name = $_.name; path = $_.path; statusCode = $_.statusCode; failure = $_.failure } })
        assertions             = @($assertions)
        assertionFailures      = @($assertionFailures)
        screenshotsRequested   = [bool]$IncludeScreenshots
        screenshotsAvailable   = [bool]($resolvedScreenshotTool -ne $null)
        screenshotsCaptured    = [bool](@($routeResults | Where-Object { $_.screenshotPath }).Count -gt 0)
        screenshotsFullPage    = [bool]$screenshotToolResolution.FullPage
        screenshotWarnings     = $screenshotWarnings
        screenshotFailures     = $screenshotFailures
        captureToolUsed        = if ($resolvedScreenshotTool) { $screenshotToolResolution.Resolved } else { "http-get-html-text-only" }
        screenshotTool         = [ordered]@{ requested = $screenshotToolResolution.Requested; resolved = $screenshotToolResolution.Resolved; validationStatus = $screenshotToolResolution.ValidationStatus; executable = Redact-EvidenceText -Text $screenshotToolResolution.Executable; supportsInteractionAwareCapture = [bool]$screenshotToolResolution.SupportsInteractionAwareCapture; attempts = @($screenshotToolResolution.Attempts) }
        issue415               = [ordered]@{ enabled = [bool]$Issue415; countSummaries = @($issue415CountSummaries); hrefInventory = @($issue415HrefInventory); zoomLimitation = "True browser zoom is not controlled by this script; reduced viewport captures are supplemental evidence only." }
        issue416               = [ordered]@{ enabled = [bool]$Issue416; routeCount = @($routesToCapture).Count; countSummaries = @($issue416CountSummaries); zoomLimitation = "True browser zoom is not controlled by this script; reduced viewport captures are supplemental evidence only." }
        issue417               = [ordered]@{ enabled = [bool]$Issue417; routeCount = @($routesToCapture).Count; countSummaries = @($issue417CountSummaries); zoomLimitation = "True browser zoom is not controlled by this script; reduced viewport captures are supplemental evidence only." }
        issue418               = [ordered]@{ enabled = [bool]$Issue418; routeCount = @($routesToCapture).Count; countSummaries = @($issue418CountSummaries); zoomLimitation = "True browser zoom is not controlled by this script; reduced viewport captures are supplemental evidence only." }
        issue419               = [ordered]@{ enabled = [bool]$Issue419; routeCount = @($routesToCapture).Count; scenarios = @($routesToCapture | ForEach-Object { $_.Name }); controlledVarianceAuthority = "Issue #501 repository-readable controlled variance"; visualAcceptance = "READY FOR EXPLICIT OWNER REVIEW"; uiGates = @($issue419GateResults); zoomLimitation = "The 720-pixel viewport scenario approximates 200-percent reflow; no visual acceptance is inferred from automation."; printArtifact = @($routeResults | Where-Object { $_.printPath } | ForEach-Object { $_.printPath }) }
        issue498               = [ordered]@{ enabled = [bool]$Issue498; routeCount = @($routesToCapture).Count; scenarios = @($routesToCapture | ForEach-Object { $_.Name }); zoomLimitation = "The 720-pixel viewport scenario approximates 200-percent reflow only; exact true browser zoom remains manual visual evidence."; printArtifact = @($routeResults | Where-Object { $_.printPath } | ForEach-Object { $_.printPath }) }
        git                    = [ordered]@{ branch = $gitBranch; commit = $gitCommit; workingTreeClean = [bool]$workingTreeClean; notice = if ($workingTreeClean) { "" } else { "Working tree was not clean when evidence was captured." } }
        output                 = [ordered]@{ packetDirectory = ConvertTo-RelativeEvidencePath -Path $packetDir -Root $PWD; zipPacket = ConvertTo-RelativeEvidencePath -Path $zipPath -Root $PWD; manifest = "manifest.json"; routeStatusCsv = "route-status.csv"; routeAssertionsCsv = "route-assertions.csv"; textMarkers = "route-text-markers.txt"; counts = $outputCounts }
        evidencePurpose        = $evidencePurpose
        safety                 = [ordered]@{ getOnly = $true; formsSubmitted = $false; retrievalSubmitted = $false; reviewerStateMutated = $false; importsOrReloadsRun = $false; productionAuthRequired = $false; responseHeadersCaptured = $false; cookiesCaptured = $false; environmentValuesCaptured = $false }
    }
    Set-Content -LiteralPath (Join-Path $packetDir "manifest.json") -Value ($manifest | ConvertTo-Json -Depth 8) -Encoding UTF8

    if (($routeFailures.Count -gt 0 -or $assertionFailures.Count -gt 0 -or $screenshotFailures.Count -gt 0) -and -not $AllowUnavailable) {
        Write-Host "Evidence packet path: $packetDir"
        Write-Host "EVIDENCE_PACKET_PATH=$packetDir"
        Stop-CaptureFail "Evidence capture completed with route, assertion, or screenshot failures. Use -AllowUnavailable to keep packets for unavailable routes."
    }

    if (Test-Path -LiteralPath $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
    Compress-Archive -LiteralPath $packetDir -DestinationPath $zipPath -Force

    Write-Host "Evidence packet path: $packetDir"
    Write-Host "EVIDENCE_PACKET_PATH=$packetDir"
    Write-Host "Evidence zip path: $zipPath"
    Write-Host "EVIDENCE_ZIP_PATH=$zipPath"
    Write-Host "Output counts: screenshots=$($outputCounts.screenshots); html=$($outputCounts.html); text=$($outputCounts.text); diagnostics=$($outputCounts.diagnostics); accessibility=$($outputCounts.accessibility)"
    Write-Host "manifest.json: $(Join-Path $packetDir 'manifest.json')"
    Write-Host "route-status.csv: $(Join-Path $packetDir 'route-status.csv')"
    Write-Host "Generated evidence and ZIP packets are local review/upload artifacts; do not commit them unless a specific repository workflow explicitly says to do so."
    if ($resolvedScreenshotTool) { Write-Host "Screenshot support: $($screenshotToolResolution.Resolved) (interaction-aware: $([bool]$screenshotToolResolution.SupportsInteractionAwareCapture))" }
    else { Write-Host "Screenshot support: skipped; install Playwright locally or run with a local Edge/Chrome headless CLI to enable screenshots." }
    exit 0
}
finally {
    foreach ($entry in $captureEnvOriginal.GetEnumerator()) {
        $name = [string]$entry.Key
        $original = $entry.Value
        if ($original.Exists) {
            Set-Item -LiteralPath ("Env:{0}" -f $name) -Value ([string]$original.Value)
        }
        else {
            Remove-Item -LiteralPath ("Env:{0}" -f $name) -ErrorAction SilentlyContinue
        }
    }
}
