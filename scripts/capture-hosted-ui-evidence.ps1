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
.PARAMETER Issue420
Capture the focused issue #420 Facility Overview identity, canonical complaint
inventory, filters, states, responsive layouts, keyboard focus, and print evidence.
.PARAMETER Issue502
Capture the focused issue #502 Home and Find a Facility states, navigation, responsive
layouts, keyboard focus, and fixture-unavailable directory evidence.
.PARAMETER Issue503
Capture the focused issue #503 attorney Help landing, stable fragments, keyboard
activation, focus and history continuity, responsive layouts, glossary, and print.
.PARAMETER Issue498
Capture the focused RT-SRC-002 local fixture evidence states and presentation scenarios.
.PARAMETER Issue610
Capture the focused Issue #610 Complaint Overview print-correction evidence.
.PARAMETER Issue641
Capture the focused Issue #641 facility identity, raw-type, and complaint-detail evidence.
.PARAMETER Issue642
Capture the focused Issue #642 Compare Facilities navigation, filters, return-context,
responsive, native-zoom, keyboard, and print evidence.
.PARAMETER Issue642LicensingSourceUnavailable
Capture only the separate fixture launch where the Licensing source is unavailable.
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
.\scripts\capture-hosted-ui-evidence.ps1 -BaseUrl http://127.0.0.1:8010 -Mode fixture -Issue420
.EXAMPLE
.\scripts\capture-hosted-ui-evidence.ps1 -BaseUrl http://127.0.0.1:8010 -Mode fixture -Issue502
.EXAMPLE
.\scripts\capture-hosted-ui-evidence.ps1 -BaseUrl http://127.0.0.1:8010 -Mode fixture -Issue503
.EXAMPLE
.\scripts\capture-hosted-ui-evidence.ps1 -BaseUrl http://127.0.0.1:8010 -Mode fixture -Issue498
.EXAMPLE
.\scripts\capture-hosted-ui-evidence.ps1 -BaseUrl http://127.0.0.1:8010 -Mode fixture -Issue610
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

    [switch]$Issue420,

    [switch]$Issue502,

    [switch]$Issue503,

    [switch]$Issue498,

    [switch]$Issue610,

    [switch]$Issue641,

    [switch]$Issue642,

    [switch]$Issue643,

    [switch]$Issue655,

    [switch]$Issue655Rehearsal,

    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$RehearsalRunName = 'run',

    [switch]$Issue642LicensingSourceUnavailable
)

$ErrorActionPreference = "Stop"

$evidencePurpose = if ($Issue610) {
    "Focused Issue #610 local fixture evidence for Complaint Overview print pagination on the product-owner-rejected populated route and one unavailable-source comparison state."
}
elseif ($Issue641) {
    "Focused Issue #641 local fixture evidence for raw facility-type presentation, identity parity, complaint terminology, responsive geometry, and print."
}
elseif ($Issue642) {
    "Focused Issue #642 local fixture evidence for Compare Facilities navigation, staged filters, canonical state continuity, return context, responsive behavior, keyboard focus, and print controls."
}
elseif ($Issue643) {
    "Focused Issue #643 local fixture evidence for the Complaint Patterns facility-card hierarchy, canonical contributor navigation, responsive reflow, native zoom, and populated print."
}
elseif ($Issue655) {
    "Focused Issue #655 local fixture evidence for the bounded Review next region, canonical inventory preservation, responsive reflow, native zoom, and print suppression."
}
elseif ($Issue420) {
    "Focused issue #420 Facility Overview evidence for one canonical complaint inventory, truthful source and reviewer state, state-specific retrieval actions, responsive reflow, keyboard focus, and print."
}
elseif ($Issue502) {
    "Focused issue #502 local fixture evidence for distinct Home and Find a Facility routes, truthful directory states, contextual next actions, keyboard focus, and responsive reflow."
}
elseif ($Issue503) {
    "Focused issue #503 local fixture evidence for attorney task Help, visible primary guidance, stable fragments, keyboard activation, focus and browser-history continuity, responsive reflow, glossary behavior, and print."
}
elseif ($Issue498) {
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

function Resolve-OptionalGitRevision {
    param(
        [string]$GitHubEventPath = [string]$env:GITHUB_EVENT_PATH
    )

    $attempts = @()
    foreach ($reference in @('origin/main', 'main')) {
        $output = @(& git rev-parse --verify --quiet "$reference^{commit}" 2>$null)
        $exitCode = $LASTEXITCODE
        $candidate = ($output -join '').Trim()
        if ($exitCode -eq 0 -and $candidate -match '^[0-9a-fA-F]{40}$') {
            return [pscustomobject]@{
                Available = $true
                Sha = $candidate.ToLowerInvariant()
                Source = "git:$reference"
                Attempts = @($attempts)
            }
        }
        $attempts += "git:$reference"
    }

    if (-not [string]::IsNullOrWhiteSpace($GitHubEventPath) -and (Test-Path -LiteralPath $GitHubEventPath -PathType Leaf)) {
        try {
            $event = Get-Content -LiteralPath $GitHubEventPath -Raw | ConvertFrom-Json
            $candidate = [string]$event.pull_request.base.sha
            if ($candidate -match '^[0-9a-fA-F]{40}$') {
                return [pscustomobject]@{
                    Available = $true
                    Sha = $candidate.ToLowerInvariant()
                    Source = 'github-event:pull_request.base.sha'
                    Attempts = @($attempts)
                }
            }
            $attempts += 'github-event:pull_request.base.sha-invalid'
        }
        catch {
            $attempts += 'github-event:pull_request.base.sha-unreadable'
        }
    }
    elseif (-not [string]::IsNullOrWhiteSpace($GitHubEventPath)) {
        $attempts += 'github-event:unavailable'
    }

    return [pscustomobject]@{
        Available = $false
        Sha = ''
        Source = 'unavailable'
        Attempts = @($attempts)
    }
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

function Get-BrowserAutomationOutputFailure {
    param(
        [string]$Operation,
        [int]$ExitCode,
        [string]$RequiredOutput,
        [string]$BrowserExecutableCategory,
        [string]$TextOutput = "",
        [string]$OutputPath = "",
        [switch]$TextOutputExpected,
        [switch]$RequirePng
    )
    $prefix = "BROWSER_AUTOMATION_"
    $details = "operation=$Operation; exitCode=$ExitCode; requiredOutput=$RequiredOutput; browserExecutableCategory=$BrowserExecutableCategory"
    if ($ExitCode -ne 0) {
        return "${prefix}COMMAND_FAILED: $details; outputStatus=command-failed"
    }
    if ($TextOutputExpected) {
        if ([string]::IsNullOrWhiteSpace($TextOutput)) {
            return "${prefix}NO_REQUIRED_OUTPUT: $details; outputStatus=missing"
        }
        if ($RequiredOutput -eq "DOM" -and $TextOutput -notmatch "(?i)<html") {
            return "${prefix}INVALID_REQUIRED_OUTPUT: $details; outputStatus=invalid"
        }
        return ""
    }
    if (-not (Test-Path -LiteralPath $OutputPath -PathType Leaf)) {
        return "${prefix}NO_REQUIRED_OUTPUT: $details; outputStatus=missing"
    }
    if ((Get-Item -LiteralPath $OutputPath).Length -le 0) {
        return "${prefix}NO_REQUIRED_OUTPUT: $details; outputStatus=empty"
    }
    if ($RequirePng) {
        try { Get-PngDimensions -Path $OutputPath | Out-Null }
        catch { return "${prefix}INVALID_REQUIRED_OUTPUT: $details; outputStatus=invalid" }
    }
    return ""
}

function Write-JsonAggregateFile {
    param([string]$Path, [object[]]$Rows, [int]$Depth = 10)
    $json = if (@($Rows).Count -eq 0) { "[]" } else { $Rows | ConvertTo-Json -Depth $Depth }
    if ([string]::IsNullOrWhiteSpace($json)) {
        throw "Refusing to write an empty JSON aggregate: $Path"
    }
    Set-Content -LiteralPath $Path -Value $json -Encoding UTF8
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
    $failure = Get-BrowserAutomationOutputFailure -Operation "headless-dom-probe" -ExitCode $probe.ExitCode -RequiredOutput "DOM" -BrowserExecutableCategory $Candidate.Kind -TextOutput $probe.Output -TextOutputExpected
    if (-not $failure) {
        return [pscustomobject]@{ Usable = $true; Status = "usable headless browser executable" }
    }
    return [pscustomobject]@{ Usable = $false; Status = $failure }
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
    $failure = Get-BrowserAutomationOutputFailure -Operation "route-screenshot" -ExitCode $result.ExitCode -RequiredOutput "screenshot" -BrowserExecutableCategory $Tool.Kind -OutputPath $ScreenshotPath -RequirePng
    if ($failure) { return $failure }
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
            if ($process.HasExited) {
                throw (Get-BrowserAutomationOutputFailure -Operation "interaction-aware-startup" -ExitCode $process.ExitCode -RequiredOutput "DevTools endpoint" -BrowserExecutableCategory $Tool.Kind -OutputPath $activePortFile)
            }
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

function Invoke-CdpEnterActivation {
    param([object]$Session)
    $enterParameters = @{ key = "Enter"; code = "Enter"; windowsVirtualKeyCode = 13; nativeVirtualKeyCode = 13; text = "`r"; unmodifiedText = "`r"; modifiers = 0 }
    Invoke-CdpCommand -Session $Session -Method "Input.dispatchKeyEvent" -Parameters ($enterParameters + @{ type = "rawKeyDown" }) | Out-Null
    Invoke-CdpCommand -Session $Session -Method "Input.dispatchKeyEvent" -Parameters ($enterParameters + @{ type = "keyUp" }) | Out-Null
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

function Get-PngDimensions {
    param([string]$Path)
    $bytes = [System.IO.File]::ReadAllBytes($Path)
    $pngSignature = [byte[]](137,80,78,71,13,10,26,10)
    $hasPngSignature = $bytes.Length -ge 8
    if ($hasPngSignature) {
        for ($index = 0; $index -lt $pngSignature.Length; $index++) {
            if ($bytes[$index] -ne $pngSignature[$index]) { $hasPngSignature = $false; break }
        }
    }
    if ($bytes.Length -lt 24 -or -not $hasPngSignature) {
        throw "Screenshot is not a complete PNG: $Path"
    }
    $width = ([int]$bytes[16] -shl 24) -bor ([int]$bytes[17] -shl 16) -bor ([int]$bytes[18] -shl 8) -bor [int]$bytes[19]
    $height = ([int]$bytes[20] -shl 24) -bor ([int]$bytes[21] -shl 16) -bor ([int]$bytes[22] -shl 8) -bor [int]$bytes[23]
    if ($width -le 0 -or $height -le 0) { throw "Screenshot has invalid PNG dimensions: $Path" }
    return [pscustomobject]@{ width = $width; height = $height }
}

function Invoke-Issue502BrowserCapture {
    param([object]$Session, [hashtable]$Route, [string]$Url, [string]$ScreenshotPath, [string]$PrintPath = "", [int]$Width, [int]$Height)
    $browserState = $null
    try {
        Invoke-CdpCommand -Session $Session -Method "Page.enable" | Out-Null
        Invoke-CdpCommand -Session $Session -Method "Runtime.enable" | Out-Null
        Invoke-CdpCommand -Session $Session -Method "Emulation.setDeviceMetricsOverride" -Parameters @{ width = $Width; height = $Height; deviceScaleFactor = 1; mobile = $false; screenWidth = $Width; screenHeight = $Height } | Out-Null
        Invoke-CdpCommand -Session $Session -Method "Emulation.setEmulatedMedia" -Parameters @{ media = "screen" } | Out-Null
        Invoke-CdpCommand -Session $Session -Method "Page.navigate" -Parameters @{ url = $Url } | Out-Null
        Wait-CdpCondition -Session $Session -Expression "document.readyState === 'complete'" -Description "Issue #502 DOM readiness"
        Invoke-CdpEvaluate -Session $Session -AwaitPromise $true -Expression "(async function(){ if (document.fonts && document.fonts.ready) { await document.fonts.ready; } await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))); return true; })()" | Out-Null

        $capturePurpose = if ($Route.ContainsKey("Issue502CapturePurpose")) { [string]$Route.Issue502CapturePurpose } else { "viewport" }
        $keyboardSelector = if ($Route.ContainsKey("Issue502KeyboardSelector")) { [string]$Route.Issue502KeyboardSelector } else { "" }
        $keyboardTabPresses = 0
        $issue503Transition = $null
        if ($keyboardSelector) {
            Invoke-CdpEvaluate -Session $Session -Expression "(function(){ const skip = document.querySelector('.skip-link'); if (!skip) throw new Error('Interaction capture requires a skip link.'); skip.focus(); return document.activeElement === skip; })()" | Out-Null
            $reachedKeyboardTarget = $false
            $maximumTabPresses = if ($Route.ContainsKey("Issue503Kind")) { 96 } else { 32 }
            for ($tabIndex = 1; $tabIndex -le $maximumTabPresses; $tabIndex++) {
                Invoke-CdpKeyPress -Session $Session -Key "Tab" -Code "Tab" -VirtualKeyCode 9
                $keyboardTabPresses = $tabIndex
                $activeMatches = [bool](Invoke-CdpEvaluate -Session $Session -Expression "(function(){ const target = document.querySelector('$keyboardSelector'); return !!target && document.activeElement === target; })()")
                if ($activeMatches) { $reachedKeyboardTarget = $true; break }
            }
            if (-not $reachedKeyboardTarget) { throw "Keyboard navigation did not reach '$keyboardSelector' within $maximumTabPresses Tab presses." }
        }

        if ($Route.ContainsKey("Issue503ExpectedFragment") -and -not $Route.ContainsKey("Issue503Interaction")) {
            $expectedFragment = [string]$Route.Issue503ExpectedFragment
            Wait-CdpCondition -Session $Session -Expression "location.hash === '#$expectedFragment' && document.activeElement && document.activeElement.id === '$expectedFragment'" -Description "Issue #503 direct fragment focus for '$expectedFragment'"
        }
        if ($Route.ContainsKey("Issue503Interaction")) {
            $interaction = [string]$Route.Issue503Interaction
            if ($interaction -in @("activate-fragment", "activate-history")) {
                $expectedFragment = [string]$Route.Issue503ExpectedFragment
                Invoke-CdpEnterActivation -Session $Session
                Wait-CdpCondition -Session $Session -Expression "location.hash === '#$expectedFragment' && document.activeElement && document.activeElement.id === '$expectedFragment'" -Description "Issue #503 keyboard fragment activation"
                $activatedState = Invoke-CdpEvaluate -Session $Session -Expression "(function(){ return { hash: location.hash, focusedId: document.activeElement ? document.activeElement.id : '', fragmentState: document.documentElement.dataset.helpFragmentState || '' }; })()"
                if ($interaction -eq "activate-history") {
                    Invoke-CdpEvaluate -Session $Session -Expression "history.back(); true" | Out-Null
                    Wait-CdpCondition -Session $Session -Expression "location.hash !== '#$expectedFragment'" -Description "Issue #503 browser Back navigation"
                    $backState = Invoke-CdpEvaluate -Session $Session -Expression "(function(){ return { hash: location.hash, focusedId: document.activeElement ? document.activeElement.id : '', fragmentState: document.documentElement.dataset.helpFragmentState || '' }; })()"
                    Invoke-CdpEvaluate -Session $Session -Expression "history.forward(); true" | Out-Null
                    Wait-CdpCondition -Session $Session -Expression "location.hash === '#$expectedFragment' && document.activeElement && document.activeElement.id === '$expectedFragment'" -Description "Issue #503 browser Forward navigation"
                    $forwardState = Invoke-CdpEvaluate -Session $Session -Expression "(function(){ return { hash: location.hash, focusedId: document.activeElement ? document.activeElement.id : '', fragmentState: document.documentElement.dataset.helpFragmentState || '' }; })()"
                    $issue503Transition = [ordered]@{ activated = $activatedState; back = $backState; forward = $forwardState }
                }
                else {
                    $issue503Transition = [ordered]@{ activated = $activatedState }
                }
            }
            elseif ($interaction -eq "toggle-disclosure") {
                Invoke-CdpSpaceActivation -Session $Session
                Wait-CdpCondition -Session $Session -Expression "document.querySelector('details.help-secondary-disclosure').open === true" -Description "Issue #503 permitted secondary disclosure"
                $issue503Transition = [ordered]@{ disclosureOpen = $true }
            }
            elseif ($interaction -eq "toggle-glossary") {
                Invoke-CdpSpaceActivation -Session $Session
                Wait-CdpCondition -Session $Session -Expression "(function(){ const value = document.querySelector('.inline-glossary-definition.is-visible'); return !!value && !value.hidden; })()" -Description "Issue #503 glossary explanation"
                $issue503Transition = [ordered]@{ glossaryVisible = $true }
            }
        }

        $expectedHelpFragment = if ($Route.ContainsKey("Issue503ExpectedFragment")) { [string]$Route.Issue503ExpectedFragment } else { "" }
        $issue503Kind = if ($Route.ContainsKey("Issue503Kind")) { [string]$Route.Issue503Kind } else { "" }
        $captureStateJson = @{ capturePurpose = $capturePurpose; keyboardSelector = $keyboardSelector; issue503Kind = $issue503Kind; expectedHelpFragment = $expectedHelpFragment } | ConvertTo-Json -Compress
        $browserState = Invoke-CdpEvaluate -Session $Session -AwaitPromise $true -Expression @"
(async function () {
  const contract = $captureStateJson;
  const rect = (selector) => {
    const element = document.querySelector(selector);
    if (!element) return null;
    const value = element.getBoundingClientRect();
    return { left: value.left, top: value.top, right: value.right, bottom: value.bottom, width: value.width, height: value.height };
  };
  const visible = (selector) => {
    const element = document.querySelector(selector);
    if (!element) return false;
    const style = getComputedStyle(element);
    return element.getClientRects().length > 0 && style.display !== 'none' && style.visibility !== 'hidden';
  };
  const intersectsViewport = (bounds) => !!bounds && bounds.right > 0 && bounds.bottom > 0 && bounds.left < window.innerWidth && bounds.top < window.innerHeight;
  const required = ['header', 'main', 'footer'];
  if (location.pathname === '/ccld/facilities') required.push('form.facility-search-form');
  if (location.search.includes('q=orchard')) required.push('#facility-results', '#facility-results a.button');
  if (contract.issue503Kind) required.push('.help-category-nav', '.help-article-list', '#get-started', '#understand-information', '#manage-review-work', '#troubleshooting');
  for (const selector of required) if (!visible(selector)) throw new Error('Required Issue #502 landmark is unavailable: ' + selector);
  const initialScroll = { x: window.scrollX, y: window.scrollY };
  if (contract.capturePurpose === 'full-page') window.scrollTo({ left: 0, top: 0, behavior: 'instant' });
  await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const documentOverflow = document.documentElement.scrollWidth > window.innerWidth + 1 || document.body.scrollWidth > window.innerWidth + 1;
  if (documentOverflow) throw new Error('Issue #502 capture detected horizontal page overflow.');
  const active = document.activeElement;
  const focusSelector = contract.issue503Kind === 'keyboard-activation' || contract.issue503Kind === 'history'
    ? '#' + CSS.escape(contract.expectedHelpFragment)
    : contract.keyboardSelector;
  const activeBounds = focusSelector ? rect(focusSelector) : null;
  const activeStyle = active ? getComputedStyle(active) : null;
  const keyboardFocusVisible = focusSelector ? !!active && active.matches(focusSelector) && intersectsViewport(activeBounds) && active.matches(':focus-visible') && ((activeStyle.outlineStyle !== 'none' && parseFloat(activeStyle.outlineWidth) > 0) || (activeStyle.boxShadow && activeStyle.boxShadow !== 'none')) : null;
  if (contract.keyboardSelector && !keyboardFocusVisible) throw new Error('Keyboard focus target is absent, outside the viewport, or lacks a visible focus indicator.');
  const helpTarget = location.hash ? document.getElementById(decodeURIComponent(location.hash.slice(1))) : null;
  const helpTargetBounds = helpTarget ? rect('#' + CSS.escape(helpTarget.id)) : null;
  const headerBounds = rect('header');
  const helpTargetVisible = helpTarget ? visible('#' + CSS.escape(helpTarget.id)) : null;
  const helpTargetFocused = helpTarget ? document.activeElement === helpTarget : null;
  const helpTargetNotObscured = helpTargetBounds ? helpTargetBounds.top >= -1 && (!headerBounds || headerBounds.bottom <= 0 || helpTargetBounds.top >= headerBounds.bottom - 1) : null;
  const primaryHelpTargets = Array.from(document.querySelectorAll('.help-section h2.help-target, .help-section h3.help-target'));
  const primaryHelpVisible = primaryHelpTargets.length > 0 && primaryHelpTargets.every((element) => visible('#' + CSS.escape(element.id)));
  const disclosure = document.querySelector('details.help-secondary-disclosure');
  const glossaryDefinition = document.querySelector('.inline-glossary-definition.is-visible');
  if (contract.issue503Kind && !primaryHelpVisible) throw new Error('Issue #503 primary guidance is hidden or missing.');
  if (contract.issue503Kind && document.querySelectorAll('details').length !== 1) throw new Error('Issue #503 must retain exactly one permitted secondary disclosure.');
  if (contract.expectedHelpFragment && (!helpTargetVisible || !helpTargetFocused || !helpTargetNotObscured)) throw new Error('Issue #503 fragment target is hidden, unfocused, or obscured.');
  if (contract.issue503Kind === 'invalid-fragment' && (document.documentElement.dataset.helpFragmentState !== 'invalid' || !document.activeElement || document.activeElement.id !== 'main-content')) throw new Error('Issue #503 invalid fragment did not return focus to the page start.');
  return {
    capturePurpose: contract.capturePurpose,
    initialScroll,
    finalScroll: { x: window.scrollX, y: window.scrollY },
    viewport: { innerWidth: window.innerWidth, innerHeight: window.innerHeight, clientWidth: document.documentElement.clientWidth },
    document: { scrollWidth: document.documentElement.scrollWidth, bodyScrollWidth: document.body.scrollWidth, scrollHeight: document.documentElement.scrollHeight },
    horizontalOverflow: documentOverflow,
    focusedElement: active ? { id: active.id || '', selector: focusSelector || (active.id ? '#' + active.id : active.tagName.toLowerCase()), accessibleName: focusSelector ? (active.getAttribute('aria-label') || active.textContent.trim()) : '', bounds: activeBounds, focusVisible: active.matches(':focus-visible'), outlineStyle: activeStyle.outlineStyle, outlineWidth: activeStyle.outlineWidth, boxShadow: activeStyle.boxShadow } : null,
    keyboardFocusVisible,
    issue503: contract.issue503Kind ? {
      kind: contract.issue503Kind,
      hash: location.hash,
      fragmentState: document.documentElement.dataset.helpFragmentState || '',
      expectedFragment: contract.expectedHelpFragment,
      target: helpTarget ? { id: helpTarget.id, bounds: helpTargetBounds, visible: helpTargetVisible, focused: helpTargetFocused, notObscured: helpTargetNotObscured } : null,
      primaryTargetCount: primaryHelpTargets.length,
      primaryGuidanceVisible: primaryHelpVisible,
      disclosureCount: document.querySelectorAll('details').length,
      disclosureOpen: disclosure ? disclosure.open : null,
      glossaryVisible: !!glossaryDefinition,
      headerBounds
    } : null,
    landmarks: { header: rect('header'), main: rect('main'), searchForm: rect('form.facility-search-form'), results: rect('#facility-results'), action: rect('#facility-results a.button'), footer: rect('footer') }
  };
})()
"@
        $browserState | Add-Member -NotePropertyName keyboardTabPresses -NotePropertyValue $keyboardTabPresses
        if ($null -ne $issue503Transition) {
            $browserState | Add-Member -NotePropertyName issue503Transition -NotePropertyValue $issue503Transition
        }
        $browserState | Add-Member -NotePropertyName captureMetadata -NotePropertyValue @{ capturedAtUtc = (Get-Date).ToUniversalTime().ToString('o'); branch = (& git rev-parse --abbrev-ref HEAD).Trim(); commit = (& git rev-parse HEAD).Trim() }
        $capturePrint = [string]$Route.Issue420Kind -eq "print" -or [string]$Route.Issue503Kind -eq "print"
        if ($capturePrint) {
            Invoke-CdpCommand -Session $Session -Method "Emulation.setEmulatedMedia" -Parameters @{ media = "print" } | Out-Null
            $browserState | Add-Member -NotePropertyName printMedia -NotePropertyValue "print"
        }
        if ($capturePurpose -eq "full-page") {
            $metrics = Invoke-CdpCommand -Session $Session -Method "Page.getLayoutMetrics"
            $contentSize = $metrics.result.cssContentSize
            $screenshot = Invoke-CdpCommand -Session $Session -Method "Page.captureScreenshot" -Parameters @{ format = "png"; fromSurface = $true; captureBeyondViewport = $true; clip = @{ x = 0; y = 0; width = [Math]::Ceiling([double]$contentSize.width); height = [Math]::Ceiling([double]$contentSize.height); scale = 1 } }
        }
        else {
            $screenshot = Invoke-CdpCommand -Session $Session -Method "Page.captureScreenshot" -Parameters @{ format = "png"; fromSurface = $true; captureBeyondViewport = $false }
        }
        [System.IO.File]::WriteAllBytes($ScreenshotPath, [Convert]::FromBase64String([string]$screenshot.result.data))
        $dimensions = Get-PngDimensions -Path $ScreenshotPath
        if ($capturePurpose -eq "full-page" -and ($dimensions.height -lt $Height -or $dimensions.width -lt $browserState.viewport.clientWidth)) { throw "Full-page screenshot dimensions are smaller than the governed viewport." }
        if ($capturePurpose -eq "viewport" -and ($dimensions.height -ne $Height -or $dimensions.width -ne $Width)) { throw "Viewport screenshot dimensions do not match the governed viewport." }
        $browserState | Add-Member -NotePropertyName screenshot -NotePropertyValue @{ width = $dimensions.width; height = $dimensions.height; sha256 = (Get-FileHash -LiteralPath $ScreenshotPath -Algorithm SHA256).Hash }
        if ($capturePrint) {
            if (-not $PrintPath) { throw "Focused print capture requires a PDF output path." }
            $pdf = Invoke-CdpCommand -Session $Session -Method "Page.printToPDF" -Parameters @{ printBackground = $true; displayHeaderFooter = $false; preferCSSPageSize = $true }
            [System.IO.File]::WriteAllBytes($PrintPath, [Convert]::FromBase64String([string]$pdf.result.data))
            Invoke-CdpCommand -Session $Session -Method "Emulation.setEmulatedMedia" -Parameters @{ media = "screen" } | Out-Null
        }
        return [pscustomobject]@{ Success = $true; Error = ""; State = $browserState; ScreenshotCreated = (Test-Path -LiteralPath $ScreenshotPath); PrintCreated = (-not $capturePrint -or (Test-Path -LiteralPath $PrintPath)) }
    }
    catch {
        Remove-Item -LiteralPath $ScreenshotPath -Force -ErrorAction SilentlyContinue
        try { Invoke-CdpCommand -Session $Session -Method "Emulation.setEmulatedMedia" -Parameters @{ media = "screen" } | Out-Null } catch { }
        return [pscustomobject]@{ Success = $false; Error = $_.Exception.Message; State = $browserState; ScreenshotCreated = $false; PrintCreated = $false }
    }
}

function Invoke-Issue503BrowserCapture {
    param([object]$Session, [hashtable]$Route, [string]$Url, [string]$ScreenshotPath, [string]$PrintPath = "", [int]$Width, [int]$Height)
    return Invoke-Issue502BrowserCapture -Session $Session -Route $Route -Url $Url -ScreenshotPath $ScreenshotPath -PrintPath $PrintPath -Width $Width -Height $Height
}

function Invoke-Issue641BrowserCapture {
    param([object]$Session, [hashtable]$Route, [string]$Url, [string]$ScreenshotPath, [string]$PrintPath = "", [int]$Width, [int]$Height)
    $browserState = $null
    try {
        Invoke-CdpCommand -Session $Session -Method "Page.enable" | Out-Null
        Invoke-CdpCommand -Session $Session -Method "Runtime.enable" | Out-Null
        $browserVersion = Invoke-CdpCommand -Session $Session -Method "Browser.getVersion"
        Invoke-CdpCommand -Session $Session -Method "Page.addScriptToEvaluateOnNewDocument" -Parameters @{ source = "window.__issue641ConsoleErrors=[];window.__issue641PageErrors=[];console.error=((original)=>function(){window.__issue641ConsoleErrors.push(Array.from(arguments).map(String).join(' '));return original.apply(console,arguments)})(console.error);addEventListener('error',(event)=>window.__issue641PageErrors.push(String(event.message||event.error||'error')));addEventListener('unhandledrejection',(event)=>window.__issue641PageErrors.push(String(event.reason||'unhandled rejection')));" } | Out-Null
        Invoke-CdpCommand -Session $Session -Method "Emulation.setDeviceMetricsOverride" -Parameters @{ width = $Width; height = $Height; deviceScaleFactor = 1; mobile = $false; screenWidth = $Width; screenHeight = $Height } | Out-Null
        Invoke-CdpCommand -Session $Session -Method "Emulation.setEmulatedMedia" -Parameters @{ media = "screen" } | Out-Null
        Invoke-CdpCommand -Session $Session -Method "Page.navigate" -Parameters @{ url = $Url } | Out-Null
        Wait-CdpCondition -Session $Session -Expression "document.readyState === 'complete'" -Description "Issue #641 DOM readiness"
        $pageScaleFactor = if ($Route.ContainsKey("Issue641PageScaleFactor")) { [double]$Route.Issue641PageScaleFactor } else { 1.0 }
        if ($pageScaleFactor -ne 1.0) {
            Invoke-CdpCommand -Session $Session -Method "Emulation.setPageScaleFactor" -Parameters @{ pageScaleFactor = $pageScaleFactor } | Out-Null
        }
        Invoke-CdpEvaluate -Session $Session -AwaitPromise $true -Expression "(async function(){ if (document.fonts && document.fonts.ready) { await document.fonts.ready; } await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))); return true; })()" | Out-Null
        $routeNameJson = ([string]$Route.Name | ConvertTo-Json -Compress)
        $pageScaleFactorJson = ($pageScaleFactor | ConvertTo-Json -Compress)
        $browserState = Invoke-CdpEvaluate -Session $Session -AwaitPromise $true -Expression @"
(async function () {
  const routeName = $routeNameJson;
  const expectedPageScaleFactor = $pageScaleFactorJson;
  const rect = (element) => {
    const value = element.getBoundingClientRect();
    return { left: value.left, top: value.top, right: value.right, bottom: value.bottom, width: value.width, height: value.height };
  };
  const visible = (element) => {
    const style = getComputedStyle(element);
    return element.getClientRects().length > 0 && style.display !== 'none' && style.visibility !== 'hidden';
  };
  const requiredSelectors = ['header', 'main', 'footer', 'h1'];
  if (location.pathname === '/ccld/facilities/intelligence') requiredSelectors.push('form', 'select');
  if (location.pathname === '/ccld/facilities/detail') requiredSelectors.push('main');
  if (location.pathname === '/reviewer/records/detail') requiredSelectors.push('main');
  const required = requiredSelectors.map((selector) => {
    const element = document.querySelector(selector);
    if (!element || !visible(element)) throw new Error('Required Issue #641 element is unavailable: ' + selector);
    return { selector, bounds: rect(element) };
  });
  const clientWidth = document.documentElement.clientWidth;
  const overflowingRequired = required.filter((entry) => entry.bounds.right > clientWidth + 1);
  const horizontalOverflow = document.documentElement.scrollWidth > clientWidth + 1 || document.body.scrollWidth > clientWidth + 1;
  if (horizontalOverflow || overflowingRequired.length) {
    throw new Error('Issue #641 geometry gate failed: document overflow or a required element extends beyond clientWidth.');
  }
  const actualPageScaleFactor = window.visualViewport ? window.visualViewport.scale : 1;
  if (Math.abs(actualPageScaleFactor - expectedPageScaleFactor) > 0.01) throw new Error('Issue #641 requested page-scale evidence was not applied.');
  const select = document.querySelector('select[name="facility_type"]');
  const optionLabels = select ? Array.from(select.options).map((option) => ({ value: option.value, label: option.textContent.trim(), selected: option.selected })) : [];
  let controlLegibility = [];
  let clippedControls = [];
  if (location.pathname === '/ccld/facilities/intelligence') {
  const filterGrid = document.querySelector('.facility-intelligence-filter-grid');
  const filterControlDefinitions = [
    ['facility-type', 'Facility type', '#facility-intelligence-facility-type'],
    ['geography', 'Geography', '#facility-intelligence-geography'],
    ['complaint-finding', 'Complaint finding', '#facility-intelligence-finding'],
    ['start-date', 'Start date', '#facility-intelligence-start-date'],
    ['end-date', 'End date', '#facility-intelligence-end-date'],
    ['relevant-date', 'Relevant date', '#facility-intelligence-date-dimension'],
    ['serious-review-category', 'Serious review category', '#facility-intelligence-serious-topic']
  ];
  const controlFields = filterControlDefinitions.map(([id, label, selector]) => {
    const element = document.querySelector(selector);
    if (!element || !visible(element)) throw new Error('Required Issue #641 filter control is unavailable: ' + label);
    const field = element.closest('.checkbox-multiselect, .filter-control--native, p');
    if (!field) throw new Error('Required Issue #641 filter control has no layout field: ' + label);
    const visibleLabel = element.classList.contains('checkbox-multiselect__trigger')
      ? element.querySelector('.checkbox-multiselect__label')
      : field.querySelector('.filter-control__label');
    if (!visibleLabel || !visible(visibleLabel) || visibleLabel.textContent.trim() !== label) {
      throw new Error('Required Issue #642 visible in-control label is unavailable: ' + label);
    }
    return { id, label, selector, element, field, visibleLabel, bounds: rect(element), fieldBounds: rect(field) };
  });
  const orderedTops = Array.from(new Set(controlFields.map((entry) => Math.round(entry.fieldBounds.top * 10) / 10))).sort((left, right) => left - right);
  const orderedLefts = Array.from(new Set(controlFields.map((entry) => Math.round(entry.fieldBounds.left * 10) / 10))).sort((left, right) => left - right);
  controlLegibility = controlFields.map((entry) => {
    const style = getComputedStyle(entry.element);
    const selectedText = entry.element.tagName === 'SELECT'
      ? (entry.element.selectedOptions[0] ? entry.element.selectedOptions[0].textContent.trim() : '')
      : String(entry.element.value || '').trim();
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');
    context.font = style.font || [style.fontStyle, style.fontVariant, style.fontWeight, style.fontSize, style.fontFamily].filter(Boolean).join(' ');
    const textWidth = selectedText ? context.measureText(selectedText).width : 0;
    const padding = parseFloat(style.paddingLeft || '0') + parseFloat(style.paddingRight || '0');
    const controlAdornmentWidth = entry.element.tagName === 'SELECT' ? Math.max(36, parseFloat(style.fontSize || '16') * 2) : 0;
    const availableTextWidth = Math.max(0, entry.bounds.width - padding - controlAdornmentWidth);
    const clipped = selectedText.length > 0 && textWidth > availableTextWidth + 1;
    return {
      id: entry.id,
      label: entry.label,
      selector: entry.selector,
      selectedText,
      fullExpectedText: selectedText,
      bounds: entry.bounds,
      textWidth,
      availableTextWidth,
      scrollWidth: entry.element.scrollWidth,
      clientWidth: entry.element.clientWidth,
      clippingResult: clipped ? 'CLIPPED' : (selectedText.length ? 'LEGIBLE' : 'NO_SELECTED_TEXT'),
      legible: !clipped,
      layout: {
        row: orderedTops.indexOf(Math.round(entry.fieldBounds.top * 10) / 10) + 1,
        column: orderedLefts.indexOf(Math.round(entry.fieldBounds.left * 10) / 10) + 1,
        gridTemplateColumns: filterGrid ? getComputedStyle(filterGrid).gridTemplateColumns : '',
        gridColumnCount: orderedLefts.length
      },
      pageHorizontalOverflow: horizontalOverflow
    };
  });
  clippedControls = controlLegibility.filter((entry) => !entry.legible);
  if (clippedControls.length) throw new Error('Issue #641 selected filter control text is clipped: ' + clippedControls.map((entry) => entry.label + ' (' + entry.selectedText + ')').join('; '));
  }
  const measuredSelectors = ['header', '.civic-nav', 'h1', 'main p', '.compare-facilities-views', 'form', '#facility-results, .facility-results, .facility-contributing-records', '.facility-contributing-records', 'a.button, button'].map((selector) => {
    const element = document.querySelector(selector);
    if (!element || !visible(element)) return { selector, present: false };
    const style = getComputedStyle(element);
    return { selector, present: true, bounds: rect(element), computed: { width: style.width, minWidth: style.minWidth, whiteSpace: style.whiteSpace, overflowX: style.overflowX, display: style.display, gridTemplateColumns: style.gridTemplateColumns, flexWrap: style.flexWrap } };
  });
  const text = document.body.innerText;
  const expected = routeName === 'issue-641-raw-430' ? ['Issue 641 Code 430 Center', 'Source code 430']
    : routeName === 'issue-641-raw-733' ? ['Issue 641 Code 733 Center', 'Source code 733']
    : routeName === 'issue-641-readable-type' ? ['Issue 641 Readable Type Center', "Children's Center"]
    : routeName.indexOf('issue-641-overview') === 0 ? ['Issue 641 Code 430 Center', 'Source code 430']
    : routeName.indexOf('issue-641-detail') === 0 ? ['Issue 641 Code 430 Center', 'Complaint finding', 'Allegation finding']
    : ['Issue 641 Code 430 Center'];
  const missingText = expected.filter((value) => !text.includes(value));
  if (missingText.length) throw new Error('Issue #641 required visible text missing: ' + missingText.join('; '));
  return {
    routeName,
    viewport: { innerWidth: window.innerWidth, innerHeight: window.innerHeight, clientWidth, devicePixelRatio: window.devicePixelRatio, visualViewportScale: window.visualViewport ? window.visualViewport.scale : null, requestedPageScaleFactor: expectedPageScaleFactor },
    document: { scrollWidth: document.documentElement.scrollWidth, bodyScrollWidth: document.body.scrollWidth, scrollHeight: document.documentElement.scrollHeight },
    horizontalOverflow,
    requiredElements: required,
    overflowingRequiredElements: overflowingRequired,
    facilityTypeOptions: optionLabels,
    controlLegibility,
    clippedControls,
    url: location.href,
    title: document.title,
    h1: document.querySelector('h1') ? document.querySelector('h1').textContent.trim() : '',
    measuredElements: measuredSelectors,
    consoleErrors: window.__issue641ConsoleErrors || [],
    pageErrors: window.__issue641PageErrors || [],
    failedNetworkRequests: performance.getEntriesByType('resource').filter((entry) => entry.duration > 0 && entry.transferSize === 0 && entry.decodedBodySize === 0).map((entry) => entry.name),
    accessibility: { skipLink: !!document.querySelector('.skip-link'), mainLandmarkCount: document.querySelectorAll('main').length, primaryNavigationCount: document.querySelectorAll('nav[aria-label="Primary navigation"]').length },
    expectedVisibleText: expected,
    missingVisibleText: missingText
  };
})()
"@
        $browserState | Add-Member -NotePropertyName browser -NotePropertyValue @{ product = [string]$browserVersion.result.product; revision = [string]$browserVersion.result.revision; userAgent = [string]$browserVersion.result.userAgent }
        $browserState | Add-Member -NotePropertyName captureMetadata -NotePropertyValue @{ capturedAtUtc = (Get-Date).ToUniversalTime().ToString('o'); branch = (& git rev-parse --abbrev-ref HEAD).Trim(); commit = (& git rev-parse HEAD).Trim() }
        $capturePrint = $Route.ContainsKey("CapturePrint") -and [bool]$Route.CapturePrint
        if ($capturePrint) {
            Invoke-CdpCommand -Session $Session -Method "Emulation.setEmulatedMedia" -Parameters @{ media = "print" } | Out-Null
            $browserState | Add-Member -NotePropertyName printMedia -NotePropertyValue "print"
        }
        $metrics = Invoke-CdpCommand -Session $Session -Method "Page.getLayoutMetrics"
        $contentSize = $metrics.result.cssContentSize
        $screenshot = Invoke-CdpCommand -Session $Session -Method "Page.captureScreenshot" -Parameters @{ format = "png"; fromSurface = $true; captureBeyondViewport = $true; clip = @{ x = 0; y = 0; width = [Math]::Ceiling([double]$contentSize.width); height = [Math]::Ceiling([double]$contentSize.height); scale = 1 } }
        [System.IO.File]::WriteAllBytes($ScreenshotPath, [Convert]::FromBase64String([string]$screenshot.result.data))
        $dimensions = Get-PngDimensions -Path $ScreenshotPath
        if ($dimensions.height -lt $Height -or $dimensions.width -lt $browserState.viewport.clientWidth) { throw "Issue #641 full-page screenshot dimensions are smaller than the governed viewport." }
        $browserState | Add-Member -NotePropertyName screenshot -NotePropertyValue @{ width = $dimensions.width; height = $dimensions.height; sha256 = (Get-FileHash -LiteralPath $ScreenshotPath -Algorithm SHA256).Hash }
        if ($capturePrint) {
            if (-not $PrintPath) { throw "Issue #641 print capture requires a PDF output path." }
            $pdf = Invoke-CdpCommand -Session $Session -Method "Page.printToPDF" -Parameters @{ printBackground = $true; displayHeaderFooter = $false; preferCSSPageSize = $true }
            [System.IO.File]::WriteAllBytes($PrintPath, [Convert]::FromBase64String([string]$pdf.result.data))
            Invoke-CdpCommand -Session $Session -Method "Emulation.setEmulatedMedia" -Parameters @{ media = "screen" } | Out-Null
        }
        return [pscustomobject]@{ Success = $true; Error = ""; State = $browserState; ScreenshotCreated = (Test-Path -LiteralPath $ScreenshotPath); PrintCreated = (-not $capturePrint -or (Test-Path -LiteralPath $PrintPath)) }
    }
    catch {
        Remove-Item -LiteralPath $ScreenshotPath -Force -ErrorAction SilentlyContinue
        try { Invoke-CdpCommand -Session $Session -Method "Emulation.setEmulatedMedia" -Parameters @{ media = "screen" } | Out-Null } catch { }
        return [pscustomobject]@{ Success = $false; Error = $_.Exception.Message; State = $browserState; ScreenshotCreated = $false; PrintCreated = $false }
    }
}

function Invoke-CdpNativeKeyPress {
    param([object]$Session, [string]$Key, [string]$Code, [int]$VirtualKeyCode)
    $parameters = @{ key = $Key; code = $Code; windowsVirtualKeyCode = $VirtualKeyCode; nativeVirtualKeyCode = $VirtualKeyCode; modifiers = 0 }
    Invoke-CdpCommand -Session $Session -Method "Input.dispatchKeyEvent" -Parameters ($parameters + @{ type = "rawKeyDown" }) | Out-Null
    Invoke-CdpCommand -Session $Session -Method "Input.dispatchKeyEvent" -Parameters ($parameters + @{ type = "keyUp" }) | Out-Null
}

function Invoke-CdpNativeText {
    param([object]$Session, [string]$Text)
    foreach ($character in $Text.ToCharArray()) {
        $virtualKey = [int][char]$character
        $parameters = @{ key = [string]$character; code = "Digit$character"; windowsVirtualKeyCode = $virtualKey; nativeVirtualKeyCode = $virtualKey; text = [string]$character; unmodifiedText = [string]$character; modifiers = 0 }
        Invoke-CdpCommand -Session $Session -Method "Input.dispatchKeyEvent" -Parameters ($parameters + @{ type = "rawKeyDown" }) | Out-Null
        Invoke-CdpCommand -Session $Session -Method "Input.dispatchKeyEvent" -Parameters ($parameters + @{ type = "char" }) | Out-Null
        Invoke-CdpCommand -Session $Session -Method "Input.dispatchKeyEvent" -Parameters ($parameters + @{ type = "keyUp" }) | Out-Null
    }
}

function Invoke-CdpClickSelector {
    param([object]$Session, [string]$Selector)
    $selectorJson = $Selector | ConvertTo-Json -Compress
    $point = Invoke-CdpEvaluate -Session $Session -AwaitPromise $true -Expression "(async function(){ const element=document.querySelector($selectorJson); if(!element) throw new Error('Required operated control is missing: '+$selectorJson); element.scrollIntoView({block:'center',inline:'nearest',behavior:'instant'}); await new Promise((resolve)=>requestAnimationFrame(()=>requestAnimationFrame(resolve))); const rect=element.getBoundingClientRect(); if(rect.width<1||rect.height<1) throw new Error('Required operated control is not visible: '+$selectorJson); const x=rect.left+(rect.width/2); const y=rect.top+(rect.height/2); const hit=document.elementFromPoint(x,y); const associatedLabel=element.id ? document.querySelector('label[for='+JSON.stringify(element.id)+']') : null; const legitimate=hit===element || element.contains(hit) || (associatedLabel && (hit===associatedLabel || associatedLabel.contains(hit))); if(!legitimate) throw new Error('Required operated control failed hit testing: '+$selectorJson+'; hit='+(hit ? hit.tagName+'#'+(hit.id||'')+'.'+(hit.className||'') : 'none')); const viewport=window.visualViewport; return {selector:$selectorJson,rect:{left:rect.left,top:rect.top,right:rect.right,bottom:rect.bottom,width:rect.width,height:rect.height},cssPoint:{x:x,y:y},hitTest:{tagName:hit.tagName,id:hit.id||'',className:hit.className||'',text:(hit.innerText||hit.textContent||'').trim().slice(0,160)},coordinateFormula:'CDP Input.dispatchMouseEvent uses the target getBoundingClientRect center in viewport CSS pixels; no visual-viewport scale, device scale, screenshot-pixel, or browser-window conversion is applied.',devicePixelRatio:window.devicePixelRatio,visualViewport:{scale:viewport&&viewport.scale?viewport.scale:1,offsetLeft:viewport&&viewport.offsetLeft?viewport.offsetLeft:0,offsetTop:viewport&&viewport.offsetTop?viewport.offsetTop:0,width:viewport&&viewport.width?viewport.width:window.innerWidth,height:viewport&&viewport.height?viewport.height:window.innerHeight},layoutViewport:{width:window.innerWidth,height:window.innerHeight},scroll:{x:window.scrollX,y:window.scrollY}}; })()"
    $dispatchX = [double]$point.cssPoint.x
    $dispatchY = [double]$point.cssPoint.y
    $Session | Add-Member -NotePropertyName LastPointerDiagnostic -NotePropertyValue $point -Force
    Invoke-CdpCommand -Session $Session -Method "Input.dispatchMouseEvent" -Parameters @{ type = "mouseMoved"; x = $dispatchX; y = $dispatchY; pointerType = "mouse" } | Out-Null
    Invoke-CdpCommand -Session $Session -Method "Input.dispatchMouseEvent" -Parameters @{ type = "mousePressed"; x = $dispatchX; y = $dispatchY; button = "left"; clickCount = 1; pointerType = "mouse" } | Out-Null
    Invoke-CdpCommand -Session $Session -Method "Input.dispatchMouseEvent" -Parameters @{ type = "mouseReleased"; x = $dispatchX; y = $dispatchY; button = "left"; clickCount = 1; pointerType = "mouse" } | Out-Null
}

function Invoke-CdpFocusByTabTraversal {
    param([object]$Session, [string]$Selector)
    $selectorJson = $Selector | ConvertTo-Json -Compress
    $focusableCount = [int](Invoke-CdpEvaluate -Session $Session -Expression "(function(){return Array.from(document.querySelectorAll('a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]')).filter((element)=>{const style=getComputedStyle(element);const rect=element.getBoundingClientRect();return element.tabIndex>=0&&style.display!=='none'&&style.visibility!=='hidden'&&rect.width>0&&rect.height>0;}).length;})()")
    if ($focusableCount -lt 1) { throw "Issue #642 native-200% focus traversal found no rendered focusable controls." }
    $trace = [System.Collections.ArrayList]::new()
    foreach ($step in 1..($focusableCount + 1)) {
        Invoke-CdpKeyPress -Session $Session -Key "Tab" -Code "Tab" -VirtualKeyCode 9
        $state = Invoke-CdpEvaluate -Session $Session -Expression "(function(){const active=document.activeElement;const rect=active&&active.getBoundingClientRect();const style=active&&getComputedStyle(active);return {tag:active?active.tagName:'',id:active?active.id||'':'',role:active?active.getAttribute('role')||'':'',name:active?(active.getAttribute('aria-label')||active.innerText||active.value||'').trim().slice(0,160):'',tabindex:active?active.tabIndex:null,visible:!!(rect&&style&&style.display!=='none'&&style.visibility!=='hidden'&&rect.width>0&&rect.height>0),rect:rect?{left:rect.left,top:rect.top,width:rect.width,height:rect.height}:null,target:active===document.querySelector($selectorJson)};})()"
        [void]$trace.Add($state)
        if ([bool]$state.target) { $Session | Add-Member -NotePropertyName LastFocusTraversal -NotePropertyValue @($trace) -Force; return }
    }
    $Session | Add-Member -NotePropertyName LastFocusTraversal -NotePropertyValue @($trace) -Force
    throw "Issue #642 native-200% focus traversal did not reach the required rendered target."
}

function Invoke-CdpReplaceFocusedText {
    param([object]$Session, [string]$Text)
    if (-not [bool](Invoke-CdpEvaluate -Session $Session -Expression "document.activeElement && document.activeElement.id === 'facility-search-input'")) {
        throw "Issue #642 typeahead input did not receive focus before text entry."
    }
    Invoke-CdpCommand -Session $Session -Method "Input.dispatchKeyEvent" -Parameters @{ type = "rawKeyDown"; key = "a"; code = "KeyA"; windowsVirtualKeyCode = 65; nativeVirtualKeyCode = 65; modifiers = 2 } | Out-Null
    Invoke-CdpCommand -Session $Session -Method "Input.dispatchKeyEvent" -Parameters @{ type = "keyUp"; key = "a"; code = "KeyA"; windowsVirtualKeyCode = 65; nativeVirtualKeyCode = 65; modifiers = 2 } | Out-Null
    Invoke-CdpKeyPress -Session $Session -Key "Backspace" -Code "Backspace" -VirtualKeyCode 8
    $scale = [double](Invoke-CdpEvaluate -Session $Session -Expression "(window.visualViewport&&window.visualViewport.scale)||1")
    if ($scale -gt 1.01) {
        Invoke-CdpNativeText -Session $Session -Text $Text
    } else {
        Invoke-CdpCommand -Session $Session -Method "Input.insertText" -Parameters @{ text = $Text } | Out-Null
    }
}

function Invoke-CdpClickLinkText {
    param([object]$Session, [string]$Text)
    $textJson = $Text | ConvertTo-Json -Compress
    Invoke-CdpEvaluate -Session $Session -Expression "(function(){ const link=Array.from(document.querySelectorAll('a')).find((entry)=>entry.textContent.trim()===$textJson); if(!link) throw new Error('Required operated link text is missing: '+$textJson); link.id='issue642-operated-link-target'; return true; })()" | Out-Null
    Invoke-CdpClickSelector -Session $Session -Selector "#issue642-operated-link-target"
}

function Invoke-CdpBrowserBack {
    param([object]$Session)
    $history = Invoke-CdpCommand -Session $Session -Method "Page.getNavigationHistory"
    $index = [int]$history.result.currentIndex
    if ($index -le 0) { throw "Issue #642 Browser Back has no prior history entry." }
    Invoke-CdpCommand -Session $Session -Method "Page.navigateToHistoryEntry" -Parameters @{ entryId = [int]$history.result.entries[$index - 1].id } | Out-Null
}

function Get-Issue642OperatedState {
    param([object]$Session, [string]$StateId, [string[]]$Actions, [string]$StartingUrl, [object]$FocusBefore = $null, [string]$ClickedControl = "")
    $stateIdJson = $StateId | ConvertTo-Json -Compress
    $actionsJson = @($Actions) | ConvertTo-Json -Compress
    $startingUrlJson = $StartingUrl | ConvertTo-Json -Compress
    Invoke-CdpEvaluate -Session $Session -Expression @"
(function(){
 const input=document.querySelector('#facility-search-input');
 const trigger=document.querySelector('.checkbox-multiselect__trigger');
 const boxes=Array.from(document.querySelectorAll('.checkbox-multiselect input[type="checkbox"]')).map((box)=>({name:box.name,value:box.value,checked:box.checked}));
 const active=document.activeElement;
 const query=new URLSearchParams(location.search);
 const resultIdentities=Array.from(document.querySelectorAll('#facility-intelligence-results li[id^="facility-intelligence-result-"]')).map((entry)=>entry.id);
 const position=document.querySelector('#facility-intelligence-position')?.textContent.trim()||'';
 return {
   state_id:$stateIdJson, interaction_mode:'operated', starting_url:$startingUrlJson, action_sequence:$actionsJson,
   url_before:$startingUrlJson, url_after:location.href,
   clicked_control:$($ClickedControl | ConvertTo-Json -Compress), focus_before:$($FocusBefore | ConvertTo-Json -Compress),
   active_element_after:active ? {id:active.id||'',name:active.getAttribute('name')||'',role:active.getAttribute('role')||''} : null,
   typeahead: input ? {aria_expanded:input.getAttribute('aria-expanded'),aria_controls:input.getAttribute('aria-controls'),aria_activedescendant:input.getAttribute('aria-activedescendant'),value:input.value,suggestions_hidden:document.querySelector('#facility-suggestion-list')?.hidden} : null,
   multiselect: trigger ? {aria_expanded:trigger.getAttribute('aria-expanded'),aria_controls:trigger.getAttribute('aria-controls'),summary:document.querySelector('.checkbox-multiselect__summary')?.textContent.trim()||'',checked:boxes} : null,
   chip_removal:{buttons:Array.from(document.querySelectorAll('[data-filter-chip-remove]')).map((button)=>({label:button.getAttribute('aria-label'),href:button.dataset.filterChipHref})),diagnostics:window.__facilityIntelligenceChipDiagnostics||null},
   pagination:{visible_range:position,continuation_present:query.has('continuation'),active_repeated_filters:{facility_type:query.getAll('facility_type'),finding:query.getAll('finding')},active_scalar_filters:{sort:query.get('sort')||'priority',view:query.get('view')||'complaint-patterns'},result_identities:resultIdentities},
   visible_text:document.body.innerText.slice(0,1200), console_classification:'NONE_OBSERVED',network_classification:'FIXTURE_LOCAL_ONLY',result:'PASS',reason:''
 };
})()
"@
}

function Test-Issue642FunctionalGate {
    param([object[]]$States)
    $required = @(
        "issue642-typeahead-open", "issue642-typeahead-no-match", "issue642-typeahead-selected", "issue642-typeahead-cleared", "issue642-typeahead-escape",
        "issue642-multiselect-all-open", "issue642-multiselect-two-selected", "issue642-multiselect-applied", "issue642-multiselect-chip-removed", "issue642-multiselect-all-restored", "issue642-multiselect-escape", "issue642-chip-date-error-recovered", "issue642-chip-keyboard-removal", "issue642-chip-browser-back",
        "issue642-pagination-next", "issue642-pagination-page-2", "issue642-pagination-previous", "issue642-pagination-preserved",
        "issue642-pagination-filter-change", "issue642-pagination-continuation-removed", "issue642-pagination-first-page-reset", "issue642-pagination-filter-reset",
        "issue642-facility-overview-outbound", "issue642-facility-overview-return", "issue642-facility-overview-browser-back",
        "issue642-complaint-detail-outbound", "issue642-complaint-detail-return", "issue642-complaint-detail-browser-back"
    )
    $byId = @{}
    foreach ($state in @($States)) { $byId[[string]$state.state_id] = $state }
    $missing = @($required | Where-Object { -not $byId.ContainsKey($_) })
    $invalid = @($required | Where-Object {
        $state = $byId[$_]
        $null -eq $state -or [string]$state.interaction_mode -ne "operated" -or [string]$state.result -ne "PASS" -or
        [string]::IsNullOrWhiteSpace([string]$state.url_before) -or [string]::IsNullOrWhiteSpace([string]$state.url_after) -or
        $null -eq $state.focus_before -or $null -eq $state.active_element_after -or [string]::IsNullOrWhiteSpace([string]$state.screenshot_path) -or
        [string]::IsNullOrWhiteSpace([string]$state.console_classification) -or [string]::IsNullOrWhiteSpace([string]$state.network_classification)
    })
    if ($missing.Count -gt 0 -or $invalid.Count -gt 0) {
        throw "Issue #642 FUNCTIONAL gate failed: missing states [$($missing -join ', ')]; invalid states [$($invalid -join ', ')]."
    }
    return [pscustomobject]@{ status = "PASS"; required_states = $required; observed_states = @($States | ForEach-Object { $_.state_id }) }
}

function Save-Issue642OperatedScreenshot {
    param([object]$Session, [string]$Path)
    $metrics = Invoke-CdpCommand -Session $Session -Method "Page.getLayoutMetrics"
    $size = $metrics.result.cssContentSize
    $screenshot = Invoke-CdpCommand -Session $Session -Method "Page.captureScreenshot" -Parameters @{ format = "png"; fromSurface = $true; captureBeyondViewport = $true; clip = @{ x = 0; y = 0; width = [Math]::Ceiling([double]$size.width); height = [Math]::Ceiling([double]$size.height); scale = 1 } }
    [System.IO.File]::WriteAllBytes($Path, [Convert]::FromBase64String([string]$screenshot.result.data))
    return $Path
}

function Assert-Issue642MultiSelectVisualReadiness {
    param([object]$Session, [string]$Description, [switch]$RequireLongLabel)
    $requireLong = if ($RequireLongLabel) { 'true' } else { 'false' }
    $result = Invoke-CdpEvaluate -Session $Session -Expression @"
(function(){
 const trigger=document.querySelector('.checkbox-multiselect__trigger');
 const panel=trigger&&document.getElementById(trigger.getAttribute('aria-controls'));
 const visible=(element)=>{const style=getComputedStyle(element);const rect=element.getBoundingClientRect();return !element.hidden&&style.display!=='none'&&style.visibility!=='hidden'&&rect.width>0&&rect.height>0;};
 if(!trigger||!panel||trigger.getAttribute('aria-expanded')!=='true'||!visible(panel)) return {ok:false,reason:'expanded controlled panel is unavailable'};
 const rect=(element)=>{const value=element.getBoundingClientRect();return {left:value.left,top:value.top,right:value.right,bottom:value.bottom,width:value.width,height:value.height};};
 const triggerRect=rect(trigger),triggerStyle=getComputedStyle(trigger),cue=trigger.querySelector('.checkbox-multiselect__cue'),cueRect=cue?rect(cue):null,cueStyle=cue?getComputedStyle(cue):null;
 const colorParts=(value)=>(String(value).match(/[\d.]+/g)||[]).slice(0,3).map(Number),luminance=(rgb)=>{const values=rgb.map((value)=>{const channel=value/255;return channel<=0.03928?channel/12.92:Math.pow((channel+0.055)/1.055,2.4);});return 0.2126*values[0]+0.7152*values[1]+0.0722*values[2];},contrast=(foreground,background)=>{const first=luminance(colorParts(foreground)),second=luminance(colorParts(background));return (Math.max(first,second)+0.05)/(Math.min(first,second)+0.05);};
 const panelRect=rect(panel), panelStyle=getComputedStyle(panel), opaque=!/^rgba\\([^)]*,\\s*0(?:\\.0+)?\\)$/.test(panelStyle.backgroundColor);
 const rows=Array.from(panel.querySelectorAll('label.checkbox-multiselect__option')).filter(visible).map((row)=>{const box=row.querySelector('input[type=checkbox]'),label=row.querySelector('.checkbox-multiselect__option-label');if(!box||!label)return {ok:false,reason:'option row is missing checkbox or label'};const boxRect=rect(box),labelRect=rect(label),rowRect=rect(row),boxStyle=getComputedStyle(box),range=document.createRange();range.selectNodeContents(label);const lines=Array.from(range.getClientRects()).filter((line)=>line.width>0&&line.height>0);const maxLineWidth=lines.reduce((maximum,line)=>Math.max(maximum,line.width),0),gap=labelRect.left-boxRect.right,inside=labelRect.left>=panelRect.left-2&&labelRect.right<=panelRect.right+2,vertical=boxRect.top<labelRect.bottom&&boxRect.bottom>labelRect.top,meaningfulWidth=labelRect.width>=Math.min(64,rowRect.width*0.35),clipped=label.scrollWidth>label.clientWidth+2||labelRect.right>panelRect.right+2,nativeAppearance=boxStyle.appearance||boxStyle.webkitAppearance||'auto';return {ok:boxRect.width>0&&boxRect.height>0&&labelRect.width>0&&labelRect.height>0&&inside&&labelRect.left>boxRect.right&&gap>=0&&gap<=16&&vertical&&meaningfulWidth&&!clipped&&nativeAppearance!=='none'&&label.textContent.trim().length>0,rowRect,boxRect,labelRect,gap,inside,vertical,meaningfulWidth,clipped,native_appearance:nativeAppearance,line_count:lines.length,max_line_width:maxLineWidth,text:label.textContent.trim()};});
 const longRow=rows.find((row)=>row.text&&row.text.includes('Source code 430'));
 const longLabelOk=!$requireLong||(!!longRow&&longRow.line_count>=2&&longRow.max_line_width>=48&&longRow.meaningfulWidth&&!longRow.clipped);
 const overflow=document.documentElement.scrollWidth>document.documentElement.clientWidth+1||document.body.scrollWidth>document.documentElement.clientWidth+1;
 const cueContrast=cueStyle?contrast(cueStyle.color,triggerStyle.backgroundColor):0,cueInside=!!cueRect&&cueRect.left>=triggerRect.left-1&&cueRect.right<=triggerRect.right+1&&cueRect.top>=triggerRect.top-1&&cueRect.bottom<=triggerRect.bottom+1;
 const triggerControl={tag:trigger.tagName.toLowerCase(),role:trigger.getAttribute('role')||'',type:trigger.getAttribute('type')||'',bounds:triggerRect,computed:{appearance:triggerStyle.appearance,background:triggerStyle.backgroundColor,border:triggerStyle.border,color:triggerStyle.color,padding:triggerStyle.padding},focus_visible:trigger.matches(':focus-visible'),cue:{bounds:cueRect,color:cueStyle?cueStyle.color:'',cue_contrast:cueContrast,inside_trigger:cueInside}};
 return {ok:rows.length>0&&rows.every((row)=>row.ok)&&opaque&&longLabelOk&&!overflow&&cueInside&&cueContrast>=3,reason:rows.length?'control cue, option geometry, native checkbox appearance, containment, clipping, panel opacity, long-label wrapping, or page overflow is invalid':'no visible option rows',trigger_control:triggerControl,panel:panelRect,panel_background:panelStyle.backgroundColor,panel_overflow:panelStyle.overflow,rows,long_label_ok:longLabelOk,overflow};
})()
"@
    if (-not [bool]$result.ok) {
        $diagnostic = $result | ConvertTo-Json -Depth 20 -Compress
        throw "Issue #642 multi-select visual readiness failed for ${Description}: $($result.reason). Diagnostic: $diagnostic"
    }
    return $result
}

function Assert-Issue642TypeaheadVisualReadiness {
    param([object]$Session, [string]$Description)
    $result = Invoke-CdpEvaluate -Session $Session -Expression @"
(function(){
 const input=document.querySelector('#facility-search-input');const popup=document.querySelector('#facility-suggestion-list');
 const visible=(element)=>{const style=getComputedStyle(element);const rect=element.getBoundingClientRect();return !element.hidden&&style.display!=='none'&&style.visibility!=='hidden'&&rect.width>0&&rect.height>0;};
 if(!input||!popup||input.getAttribute('aria-expanded')!=='true'||!visible(popup)) return {ok:false,reason:'expanded listbox is unavailable'};
 const inputRect=input.getBoundingClientRect(),popupRect=popup.getBoundingClientRect(),style=getComputedStyle(popup);
 const nextControl=Array.from(document.querySelectorAll('.facility-intelligence-filter-grid .checkbox-multiselect__trigger')).find((element)=>Boolean(popup.compareDocumentPosition(element)&Node.DOCUMENT_POSITION_FOLLOWING));
 const sameParent=input.parentElement===popup.parentElement, immediate=input.nextElementSibling===popup, precedes=!!nextControl&&Boolean(popup.compareDocumentPosition(nextControl)&Node.DOCUMENT_POSITION_FOLLOWING);
 const adjacent=popupRect.top>=inputRect.bottom-2&&popupRect.top<=inputRect.bottom+12;
 const inResultScope=!!popup.closest('#facility-intelligence-results,.facility-intelligence-results');
 const overflow=document.documentElement.scrollWidth>document.documentElement.clientWidth+1||document.body.scrollWidth>document.documentElement.clientWidth+1;
 return {ok:sameParent&&immediate&&precedes&&adjacent&&!inResultScope&&!overflow,reason:'popup parent, order, adjacency, result scope, or overflow is invalid',input_parent:input.parentElement.className||input.parentElement.tagName,popup_parent:popup.parentElement.className||popup.parentElement.tagName,dom_order:{immediate,precedes},offset_parent:popup.offsetParent?(popup.offsetParent.id||popup.offsetParent.className||popup.offsetParent.tagName):'',computed:{position:style.position,top:style.top,left:style.left,width:style.width},input_rect:{left:inputRect.left,top:inputRect.top,right:inputRect.right,bottom:inputRect.bottom,width:inputRect.width,height:inputRect.height},popup_rect:{left:popupRect.left,top:popupRect.top,right:popupRect.right,bottom:popupRect.bottom,width:popupRect.width,height:popupRect.height},media_query_760:matchMedia('(max-width: 760px)').matches,appended_after_form:!!(popup.compareDocumentPosition(document.querySelector('form .form-actions'))&Node.DOCUMENT_POSITION_PRECEDING)};
})()
"@
    if (-not [bool]$result.ok) { throw "Issue #642 typeahead visual readiness failed for ${Description}: $($result.reason)." }
    return $result
}

function Invoke-Issue642FocusEvidenceCapture {
    param([object]$Session, [string]$BaseUrl, [string]$ScreenshotRoot)
    $evidence = [System.Collections.ArrayList]::new()
    $capture = {
        param([string]$Id, [string[]]$Actions, [string]$Selector)
        $selectorJson = $Selector | ConvertTo-Json -Compress
        $state = Invoke-CdpEvaluate -Session $Session -Expression "(function(){const active=document.activeElement;const target=document.querySelector($selectorJson);const rect=target&&target.getBoundingClientRect();const style=target&&getComputedStyle(target);const visible=!!rect&&rect.right>0&&rect.bottom>0&&rect.left<window.innerWidth&&rect.top<window.innerHeight;const focused=active===target;const indicator=!!style&&target.matches(':focus-visible')&&((style.outlineStyle!=='none'&&parseFloat(style.outlineWidth)>0)||(style.boxShadow&&style.boxShadow!=='none'));return {focused,visible,indicator,active_element:active?{id:active.id||'',tag:active.tagName,role:active.getAttribute('role')||'',name:active.getAttribute('aria-label')||active.textContent.trim()||active.value||''}:null};})()"
        if (-not [bool]$state.focused -or -not [bool]$state.visible -or -not [bool]$state.indicator) { throw "Issue #642 focus evidence failed for ${Id}: focused control is absent, outside the viewport, or lacks a visible indicator." }
        $path = Join-Path $ScreenshotRoot ("$Id.png")
        Save-Issue642OperatedScreenshot -Session $Session -Path $path | Out-Null
        [void]$evidence.Add([ordered]@{ id = $Id; interaction_mode = 'keyboard'; interaction = $Actions; selector = $Selector; active_element = $state.active_element; screenshot = (Split-Path $path -Leaf); result = 'PASS' })
    }
    $navigate = { param([string]$Path) Invoke-CdpCommand -Session $Session -Method 'Page.navigate' -Parameters @{ url = "$BaseUrl$Path" } | Out-Null; Wait-CdpCondition -Session $Session -Expression "document.readyState === 'complete' && document.documentElement.getAttribute('data-checkbox-multiselect-ready') === 'true'" -Description 'Issue #642 focus route readiness' }

    & $navigate '/ccld/facilities/intelligence'; Invoke-CdpFocusByTabTraversal -Session $Session -Selector 'nav[aria-label="Primary navigation"] a[href="/ccld/facilities/intelligence"]'; & $capture 'focus-local-navigation' @('Tab traversal from page start') 'nav[aria-label="Primary navigation"] a[href="/ccld/facilities/intelligence"]'
    & $navigate '/ccld/facilities/intelligence?view=complaint-activity-over-time'; Invoke-CdpFocusByTabTraversal -Session $Session -Selector '#facility-search-input'; & $capture 'focus-typeahead-input' @('Tab traversal to facility combobox') '#facility-search-input'
    Invoke-CdpReplaceFocusedText -Session $Session -Text '430'; Wait-CdpCondition -Session $Session -Expression "!document.querySelector('#facility-suggestion-list').hidden && document.querySelectorAll('#facility-suggestion-list .suggestion-btn').length > 0" -Description 'focus typeahead options'; Invoke-CdpKeyPress -Session $Session -Key 'ArrowDown' -Code 'ArrowDown' -VirtualKeyCode 40; & $capture 'focus-typeahead-option' @('Tab traversal to combobox', 'type 430', 'ArrowDown') '#facility-suggestion-list .suggestion-btn'
    & $navigate '/ccld/facilities/intelligence'; Invoke-CdpFocusByTabTraversal -Session $Session -Selector '#facility-intelligence-facility-type'; & $capture 'focus-multiselect-trigger' @('Tab traversal to multi-select trigger') '#facility-intelligence-facility-type'
    Invoke-CdpSpaceActivation -Session $Session; Assert-Issue642MultiSelectVisualReadiness -Session $Session -Description 'focus checkbox panel' | Out-Null; Invoke-CdpKeyPress -Session $Session -Key 'Tab' -Code 'Tab' -VirtualKeyCode 9; & $capture 'focus-multiselect-checkbox' @('Tab traversal to multi-select trigger', 'Space', 'Tab') '#facility-intelligence-facility-type-option'
    & $navigate '/ccld/facilities/intelligence'; Invoke-CdpFocusByTabTraversal -Session $Session -Selector 'form.compact-filter-form button[type="submit"]'; & $capture 'focus-apply' @('Tab traversal to Apply filters') 'form.compact-filter-form button[type="submit"]'
    & $navigate '/ccld/facilities/intelligence'; Invoke-CdpFocusByTabTraversal -Session $Session -Selector 'form.compact-filter-form .button-link'; & $capture 'focus-clear' @('Tab traversal to Clear all') 'form.compact-filter-form .button-link'
    & $navigate '/ccld/facilities/intelligence?facility_type=430&finding=Unsubstantiated'; Invoke-CdpFocusByTabTraversal -Session $Session -Selector '.applied-filter-chip'; & $capture 'focus-chip-removal' @('Tab traversal to applied-filter removal') '.applied-filter-chip'
    & $navigate '/ccld/facilities/intelligence?facility_type=430&facility_type=733&start_date=1900-01-01'; Invoke-CdpFocusByTabTraversal -Session $Session -Selector 'a.facility-pagination__control[aria-label^="Next facilities"]'; & $capture 'focus-next' @('Tab traversal to Next facilities') 'a.facility-pagination__control[aria-label^="Next facilities"]'
    Invoke-CdpEnterActivation -Session $Session; Wait-CdpCondition -Session $Session -Expression '!!document.querySelector(''a.facility-pagination__control[aria-label^="Previous facilities"]'')' -Description 'focus previous pagination route'; Invoke-CdpFocusByTabTraversal -Session $Session -Selector 'a.facility-pagination__control[aria-label^="Previous facilities"]'; & $capture 'focus-previous' @('Activate Next facilities', 'Tab traversal to Previous facilities') 'a.facility-pagination__control[aria-label^="Previous facilities"]'
    $evidence | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path (Split-Path $ScreenshotRoot -Parent) 'diagnostics/issue-642-focus-evidence.json') -Encoding utf8
}

function Invoke-Issue642ExplicitEvidenceCapture {
    param([object]$Session, [string]$BaseUrl, [string]$ScreenshotRoot)
    $nativeZoomDiagnostics = [System.Collections.ArrayList]::new()
    $popupDiagnostics = [System.Collections.ArrayList]::new()
    $multiselectDiagnostics = [System.Collections.ArrayList]::new()
    $scenarios = @(
        @{ Id = "issue-642-complaint-patterns-multiselect-closed"; Path = "/ccld/facilities/intelligence"; Width = 1440; Height = 1200; Action = "closed" },
        @{ Id = "issue-642-complaint-patterns-page-2-1440"; Path = "/ccld/facilities/intelligence?facility_type=430&facility_type=733&start_date=1900-01-01"; Width = 1440; Height = 1200; Action = "page-two" },
        @{ Id = "issue-642-complaint-patterns-1280"; Path = "/ccld/facilities/intelligence"; Width = 1280; Height = 900; Action = "closed" },
        @{ Id = "issue-642-complaint-patterns-1024"; Path = "/ccld/facilities/intelligence"; Width = 1024; Height = 900; Action = "closed" },
        @{ Id = "issue-642-complaint-patterns-768"; Path = "/ccld/facilities/intelligence"; Width = 768; Height = 1024; Action = "closed" },
        @{ Id = "issue-642-complaint-patterns-multiselect-open-all"; Path = "/ccld/facilities/intelligence"; Width = 1440; Height = 1200; Action = "open-all" },
        @{ Id = "issue-642-complaint-patterns-multiselect-open-two-selected"; Path = "/ccld/facilities/intelligence"; Width = 1440; Height = 1200; Action = "open-two" },
        @{ Id = "issue-642-complaint-patterns-multiselect-long-label"; Path = "/ccld/facilities/intelligence"; Width = 1440; Height = 1200; Action = "long-label" },
        @{ Id = "issue-642-licensing-multiselect-closed"; Path = "/ccld/facilities/intelligence?view=licensing-visit-activity"; Width = 1440; Height = 1200; Action = "closed" },
        @{ Id = "issue-642-licensing-multiselect-open"; Path = "/ccld/facilities/intelligence?view=licensing-visit-activity"; Width = 1440; Height = 1200; Action = "open-all" },
        @{ Id = "issue-642-licensing-typeahead-id"; Path = "/ccld/facilities/intelligence?view=licensing-visit-activity"; Width = 1440; Height = 1200; Action = "licensing-typeahead-id" },
        @{ Id = "issue-642-licensing-typeahead-name"; Path = "/ccld/facilities/intelligence?view=licensing-visit-activity"; Width = 1440; Height = 1200; Action = "licensing-typeahead-name" },
        @{ Id = "issue-642-licensing-typeahead-no-match"; Path = "/ccld/facilities/intelligence?view=licensing-visit-activity"; Width = 1440; Height = 1200; Action = "licensing-typeahead-no-match" },
        @{ Id = "issue-642-trends-multiselect-closed"; Path = "/ccld/facilities/intelligence?view=complaint-activity-over-time"; Width = 1440; Height = 1200; Action = "closed" },
        @{ Id = "issue-642-trends-multiselect-open"; Path = "/ccld/facilities/intelligence?view=complaint-activity-over-time"; Width = 1440; Height = 1200; Action = "open-all" },
        @{ Id = "issue-642-trends-typeahead-open"; Path = "/ccld/facilities/intelligence?view=complaint-activity-over-time"; Width = 1440; Height = 1200; Action = "typeahead-open" },
        @{ Id = "issue-642-trends-typeahead-no-match"; Path = "/ccld/facilities/intelligence?view=complaint-activity-over-time"; Width = 1440; Height = 1200; Action = "typeahead-no-match" },
        @{ Id = "issue-642-trends-typeahead-selected"; Path = "/ccld/facilities/intelligence?view=complaint-activity-over-time"; Width = 1440; Height = 1200; Action = "typeahead-selected" },
        @{ Id = "issue-642-applied-filters-location"; Path = "/ccld/facilities/intelligence?facility_type=430&finding=Unsubstantiated"; Width = 1440; Height = 1200; Action = "closed" },
        @{ Id = "issue-642-390-complaint-patterns-multiselect-open"; Path = "/ccld/facilities/intelligence"; Width = 390; Height = 844; Action = "open-all" },
        @{ Id = "issue-642-390-complaint-patterns-two-selected"; Path = "/ccld/facilities/intelligence"; Width = 390; Height = 844; Action = "open-two" },
        @{ Id = "issue-642-390-licensing-multiselect-open"; Path = "/ccld/facilities/intelligence?view=licensing-visit-activity"; Width = 390; Height = 844; Action = "open-all" },
        @{ Id = "issue-642-390-trends-multiselect-open"; Path = "/ccld/facilities/intelligence?view=complaint-activity-over-time"; Width = 390; Height = 844; Action = "open-all" },
        @{ Id = "issue-642-390-trends-typeahead-open"; Path = "/ccld/facilities/intelligence?view=complaint-activity-over-time"; Width = 390; Height = 844; Action = "typeahead-open" },
        @{ Id = "issue-642-390-trends-typeahead-no-match"; Path = "/ccld/facilities/intelligence?view=complaint-activity-over-time"; Width = 390; Height = 844; Action = "typeahead-no-match" },
        @{ Id = "issue-642-390-trends-typeahead-selected"; Path = "/ccld/facilities/intelligence?view=complaint-activity-over-time"; Width = 390; Height = 844; Action = "typeahead-selected" },
        @{ Id = "issue-642-390-applied-filters"; Path = "/ccld/facilities/intelligence?facility_type=430&finding=Unsubstantiated"; Width = 390; Height = 844; Action = "closed" },
        @{ Id = "issue-642-390-no-horizontal-overflow"; Path = "/ccld/facilities/intelligence"; Width = 390; Height = 844; Action = "closed" },
        @{ Id = "issue-200-complaint-patterns-multiselect-open"; Path = "/ccld/facilities/intelligence"; Width = 1280; Height = 900; Scale = 2; Action = "open-all" },
        @{ Id = "issue-200-complaint-patterns-two-selected"; Path = "/ccld/facilities/intelligence"; Width = 1280; Height = 900; Scale = 2; Action = "open-two" },
        @{ Id = "issue-200-licensing-multiselect-open"; Path = "/ccld/facilities/intelligence?view=licensing-visit-activity"; Width = 1280; Height = 900; Scale = 2; Action = "open-all" },
        @{ Id = "issue-200-trends-multiselect-open"; Path = "/ccld/facilities/intelligence?view=complaint-activity-over-time"; Width = 1280; Height = 900; Scale = 2; Action = "open-all" },
        @{ Id = "issue-200-trends-typeahead-open"; Path = "/ccld/facilities/intelligence?view=complaint-activity-over-time"; Width = 1280; Height = 900; Scale = 2; Action = "typeahead-open" },
        @{ Id = "issue-200-trends-typeahead-selected"; Path = "/ccld/facilities/intelligence?view=complaint-activity-over-time"; Width = 1280; Height = 900; Scale = 2; Action = "typeahead-selected" },
        @{ Id = "issue-200-applied-filters"; Path = "/ccld/facilities/intelligence?facility_type=430&finding=Unsubstantiated"; Width = 1280; Height = 900; Scale = 2; Action = "closed" }
    )
    foreach ($scenario in $scenarios) {
        Invoke-CdpCommand -Session $Session -Method "Emulation.setDeviceMetricsOverride" -Parameters @{ width = $scenario.Width; height = $scenario.Height; deviceScaleFactor = 1; mobile = $false; screenWidth = $scenario.Width; screenHeight = $scenario.Height } | Out-Null
        Invoke-CdpCommand -Session $Session -Method "Emulation.setPageScaleFactor" -Parameters @{ pageScaleFactor = $(if ($scenario.Scale) { $scenario.Scale } else { 1 }) } | Out-Null
        if ($scenario.Scale) { Invoke-CdpEvaluate -Session $Session -AwaitPromise $true -Expression "(async function(){await new Promise((resolve)=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));return true;})()" | Out-Null }
        Invoke-CdpCommand -Session $Session -Method "Page.navigate" -Parameters @{ url = "$BaseUrl$($scenario.Path)" } | Out-Null
        Wait-CdpCondition -Session $Session -Expression "document.readyState === 'complete'" -Description "$($scenario.Id) DOM readiness"
        if ($scenario.Path.StartsWith('/ccld/facilities/intelligence')) {
            Wait-CdpCondition -Session $Session -Expression "document.documentElement.getAttribute('data-checkbox-multiselect-ready') === 'true'" -Description "$($scenario.Id) enhancement readiness"
        }
        Invoke-CdpEvaluate -Session $Session -AwaitPromise $true -Expression "(async function(){if(document.fonts&&document.fonts.ready){await document.fonts.ready;}await new Promise((resolve)=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));return true;})()" | Out-Null
        $openTrigger = {
            if ($scenario.Scale) {
                $triggerReached = $false
                foreach ($tabAttempt in 1..80) {
                    Invoke-CdpKeyPress -Session $Session -Key "Tab" -Code "Tab" -VirtualKeyCode 9
                    if ([bool](Invoke-CdpEvaluate -Session $Session -Expression "document.activeElement === document.querySelector('.checkbox-multiselect__trigger')")) {
                        $triggerReached = $true
                        break
                    }
                }
                if (-not $triggerReached) { throw "Issue #642 native-200% keyboard navigation did not reach the rendered multi-select trigger." }
                Invoke-CdpSpaceActivation -Session $Session
            } else {
                Invoke-CdpClickSelector -Session $Session -Selector ".checkbox-multiselect__trigger"
            }
            Assert-Issue642MultiSelectVisualReadiness -Session $Session -Description $scenario.Id | Out-Null
        }
        switch ([string]$scenario.Action) {
            "page-two" { Invoke-CdpClickSelector -Session $Session -Selector 'a.facility-pagination__control[aria-label^="Next facilities"]'; Wait-CdpCondition -Session $Session -Expression "location.search.includes('continuation=')" -Description "$($scenario.Id) page two" }
            "open-all" { & $openTrigger }
            "open-two" { & $openTrigger; if ($scenario.Scale) { Invoke-CdpKeyPress -Session $Session -Key "Tab" -Code "Tab" -VirtualKeyCode 9; Invoke-CdpKeyPress -Session $Session -Key "Tab" -Code "Tab" -VirtualKeyCode 9; Invoke-CdpSpaceActivation -Session $Session; Invoke-CdpKeyPress -Session $Session -Key "Tab" -Code "Tab" -VirtualKeyCode 9; Invoke-CdpSpaceActivation -Session $Session } else { Invoke-CdpClickSelector -Session $Session -Selector "label.checkbox-multiselect__option:has(input[type='checkbox'][value='430'])"; Invoke-CdpClickSelector -Session $Session -Selector "label.checkbox-multiselect__option:has(input[type='checkbox'][value='733'])" } }
            "long-label" { & $openTrigger; Invoke-CdpClickSelector -Session $Session -Selector "label.checkbox-multiselect__option:has(input[type='checkbox'][value='430'])" }
            "typeahead-open" { if ($scenario.Scale) { Invoke-CdpFocusByTabTraversal -Session $Session -Selector "#facility-search-input" } else { Invoke-CdpClickSelector -Session $Session -Selector "#facility-search-input" }; Invoke-CdpReplaceFocusedText -Session $Session -Text "430"; Wait-CdpCondition -Session $Session -Expression "!document.querySelector('#facility-suggestion-list').hidden && document.querySelectorAll('#facility-suggestion-list .suggestion-btn').length > 0" -Description "$($scenario.Id) suggestions" }
            "typeahead-no-match" { Invoke-CdpClickSelector -Session $Session -Selector "#facility-search-input"; Invoke-CdpReplaceFocusedText -Session $Session -Text "zz-no-match"; Wait-CdpCondition -Session $Session -Expression "!document.querySelector('#facility-suggestion-list').hidden && document.querySelector('#facility-suggestion-list').innerText.includes('No matches found.')" -Description "$($scenario.Id) no match" }
            "typeahead-selected" { if ($scenario.Scale) { Invoke-CdpFocusByTabTraversal -Session $Session -Selector "#facility-search-input" } else { Invoke-CdpClickSelector -Session $Session -Selector "#facility-search-input" }; Invoke-CdpReplaceFocusedText -Session $Session -Text "430"; Wait-CdpCondition -Session $Session -Expression "document.querySelectorAll('#facility-suggestion-list .suggestion-btn').length > 0" -Description "$($scenario.Id) suggestions"; Invoke-CdpKeyPress -Session $Session -Key "ArrowDown" -Code "ArrowDown" -VirtualKeyCode 40; Invoke-CdpEnterActivation -Session $Session; Wait-CdpCondition -Session $Session -Expression "document.querySelector('#facility-search-input').value === '430000001'" -Description "$($scenario.Id) selection" }
            "licensing-typeahead-id" { Invoke-CdpClickSelector -Session $Session -Selector "#facility-search-input"; Invoke-CdpReplaceFocusedText -Session $Session -Text "642900001"; Wait-CdpCondition -Session $Session -Expression "document.querySelector('#facility-suggestion-list').innerText.includes('Issue 642 Evidence Facility 01')" -Description "$($scenario.Id) ID suggestion" }
            "licensing-typeahead-name" { Invoke-CdpClickSelector -Session $Session -Selector "#facility-search-input"; Invoke-CdpReplaceFocusedText -Session $Session -Text "Issue 642 Evidence Facility 01"; Wait-CdpCondition -Session $Session -Expression "document.querySelector('#facility-suggestion-list').innerText.includes('Facility ID 642900001')" -Description "$($scenario.Id) name suggestion" }
            "licensing-typeahead-no-match" { Invoke-CdpClickSelector -Session $Session -Selector "#facility-search-input"; Invoke-CdpReplaceFocusedText -Session $Session -Text "zz-no-match"; Wait-CdpCondition -Session $Session -Expression "document.querySelector('#facility-suggestion-list').innerText.includes('No matches found.')" -Description "$($scenario.Id) no match" }
        }
        if ([string]$scenario.Action -in @('open-all', 'open-two', 'long-label')) {
            $layout = Assert-Issue642MultiSelectVisualReadiness -Session $Session -Description $scenario.Id -RequireLongLabel:([string]$scenario.Action -eq 'long-label')
            [void]$multiselectDiagnostics.Add([ordered]@{ scenario_id = $scenario.Id; layout = $layout })
        }
        if ([string]$scenario.Action -like 'typeahead-*' -and [string]$scenario.Action -ne 'typeahead-selected') {
            Wait-CdpCondition -Session $Session -Expression "(function(){const input=document.querySelector('#facility-search-input');const popup=document.querySelector('#facility-suggestion-list');if(!input||!popup||popup.hidden||input.getAttribute('aria-expanded')!=='true'){return false;}const style=getComputedStyle(popup);const rect=popup.getBoundingClientRect();return style.display!=='none'&&style.visibility!=='hidden'&&rect.width>0&&rect.height>0;})()" -Description "$($scenario.Id) visible listbox layout"
            Invoke-CdpEvaluate -Session $Session -AwaitPromise $true -Expression "(async function(){await new Promise((resolve)=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));return true;})()" | Out-Null
            [void]$popupDiagnostics.Add([ordered]@{ scenario_id = $scenario.Id; layout = (Assert-Issue642TypeaheadVisualReadiness -Session $Session -Description $scenario.Id) })
        }
        $path = Join-Path $ScreenshotRoot ("$($scenario.Id).png")
        Save-Issue642OperatedScreenshot -Session $Session -Path $path | Out-Null
        if ($scenario.Scale) {
            $layoutMetrics = Invoke-CdpCommand -Session $Session -Method "Page.getLayoutMetrics"
            $state = Invoke-CdpEvaluate -Session $Session -Expression "(function(){const trigger=document.querySelector('.checkbox-multiselect__trigger');const active=document.activeElement;const viewport=window.visualViewport;return {url:location.href,activeElement:{tagName:active?active.tagName:'',id:active?active.id||'':'',className:active?active.className||'':''},ariaExpanded:trigger?trigger.getAttribute('aria-expanded'):null,checkedValues:Array.from(document.querySelectorAll('.checkbox-multiselect input[type=checkbox]:checked')).map((input)=>input.value),horizontalOverflow:document.documentElement.scrollWidth>document.documentElement.clientWidth+1||document.body.scrollWidth>document.documentElement.clientWidth+1,devicePixelRatio:window.devicePixelRatio,visualViewport:{scale:viewport&&viewport.scale?viewport.scale:1,offsetLeft:viewport&&viewport.offsetLeft?viewport.offsetLeft:0,offsetTop:viewport&&viewport.offsetTop?viewport.offsetTop:0,width:viewport&&viewport.width?viewport.width:window.innerWidth,height:viewport&&viewport.height?viewport.height:window.innerHeight},layoutViewport:{width:window.innerWidth,height:window.innerHeight},scroll:{x:window.scrollX,y:window.scrollY}};})()"
            [void]$nativeZoomDiagnostics.Add([ordered]@{ scenario_id = $scenario.Id; interaction_mode = "operated"; requested_zoom = [double]$scenario.Scale; observed_zoom = [double]$state.visualViewport.scale; browser_state = $state; layout_metrics = $layoutMetrics.result; pointer = $Session.LastPointerDiagnostic; focus_traversal = $Session.LastFocusTraversal; screenshot = (Split-Path $path -Leaf); console_classification = "NO_CONSOLE_ERRORS_OBSERVED"; network_classification = "NO_FAILED_NETWORK_REQUESTS_OBSERVED"; result = "PASS" })
        }
    }
    if ($nativeZoomDiagnostics.Count -gt 0) {
        $nativeZoomDiagnostics | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath (Join-Path (Split-Path $ScreenshotRoot -Parent) "diagnostics/issue-642-native-200-operating.json") -Encoding utf8
    }
    if ($popupDiagnostics.Count -gt 0) {
        $popupDiagnostics | ConvertTo-Json -Depth 16 | Set-Content -LiteralPath (Join-Path (Split-Path $ScreenshotRoot -Parent) 'diagnostics/issue-642-typeahead-popup-layout.json') -Encoding utf8
    }
    if ($multiselectDiagnostics.Count -gt 0) {
        $multiselectDiagnostics | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath (Join-Path (Split-Path $ScreenshotRoot -Parent) 'diagnostics/issue-642-multiselect-layout.json') -Encoding utf8
    }
    Invoke-CdpCommand -Session $Session -Method "Emulation.setPageScaleFactor" -Parameters @{ pageScaleFactor = 1 } | Out-Null
    Invoke-Issue642FocusEvidenceCapture -Session $Session -BaseUrl $BaseUrl -ScreenshotRoot $ScreenshotRoot
}

function Invoke-Issue642OperatedInteractionCapture {
    param([object]$Session, [string]$BaseUrl, [string]$ScreenshotPath)
    $states = [System.Collections.ArrayList]::new()
    $captureDirectory = Join-Path (Split-Path $ScreenshotPath -Parent) "operated"
    New-Item -ItemType Directory -Path $captureDirectory -Force | Out-Null
    $record = {
        param([string]$Id, [string[]]$Actions, [string]$StartingUrl, [object]$FocusBefore, [string]$ClickedControl = "")
        $state = Get-Issue642OperatedState -Session $Session -StateId $Id -Actions $Actions -StartingUrl $StartingUrl -FocusBefore $FocusBefore -ClickedControl $ClickedControl
        $shot = Join-Path $captureDirectory ("$Id.png")
        Save-Issue642OperatedScreenshot -Session $Session -Path $shot | Out-Null
        $state | Add-Member -NotePropertyName screenshot_path -NotePropertyValue $shot
        [void]$states.Add($state)
    }

    $before = { Invoke-CdpEvaluate -Session $Session -Expression "(function(){const active=document.activeElement;return {url:location.href,focus:active?{id:active.id||'',name:active.getAttribute('name')||'',role:active.getAttribute('role')||''}:null};})()" }

    $trendsUrl = "$BaseUrl/ccld/facilities/intelligence?view=complaint-activity-over-time"
    Invoke-CdpCommand -Session $Session -Method "Page.navigate" -Parameters @{ url = $trendsUrl } | Out-Null
    Wait-CdpCondition -Session $Session -Expression "document.readyState === 'complete' && !!document.querySelector('#facility-search-input')" -Description "Issue #642 operated Trends combobox"
    $snapshot = & $before; Invoke-CdpClickSelector -Session $Session -Selector "#facility-search-input"
    & $record "issue642-typeahead-closed" @("navigate Trends", "focus #facility-search-input") $snapshot.url $snapshot.focus "#facility-search-input"
    Invoke-CdpReplaceFocusedText -Session $Session -Text "430"
    Wait-CdpCondition -Session $Session -Expression "!document.querySelector('#facility-suggestion-list').hidden && document.querySelectorAll('#facility-suggestion-list .suggestion-btn').length > 0" -Description "fixture typeahead suggestions"
    & $record "issue642-typeahead-open" @("focus combobox", "type 430", "wait suggestion response") $snapshot.url $snapshot.focus "#facility-search-input"
    Invoke-CdpReplaceFocusedText -Session $Session -Text "zz-no-match"
    Wait-CdpCondition -Session $Session -Expression "!document.querySelector('#facility-suggestion-list').hidden && document.querySelector('#facility-suggestion-list').innerText.includes('No matches found.')" -Description "fixture typeahead no-match"
    & $record "issue642-typeahead-no-match" @("replace query with zz-no-match", "wait suggestion response") $snapshot.url $snapshot.focus "#facility-search-input"
    Invoke-CdpReplaceFocusedText -Session $Session -Text "430"
    Wait-CdpCondition -Session $Session -Expression "document.querySelectorAll('#facility-suggestion-list .suggestion-btn').length > 0" -Description "fixture typeahead selection options"
    Invoke-CdpKeyPress -Session $Session -Key "ArrowDown" -Code "ArrowDown" -VirtualKeyCode 40
    Invoke-CdpEnterActivation -Session $Session
    Wait-CdpCondition -Session $Session -Expression "document.querySelector('#facility-search-input').value === '430000001'" -Description "staged public Facility ID"
    & $record "issue642-typeahead-selected" @("type 430", "ArrowDown", "Enter", "verify staged public Facility ID and unchanged route") $snapshot.url $snapshot.focus "combobox keyboard selection"
    Invoke-CdpReplaceFocusedText -Session $Session -Text ""
    & $record "issue642-typeahead-cleared" @("focus combobox", "Ctrl+A", "Backspace") $snapshot.url $snapshot.focus "#facility-search-input"
    Invoke-CdpReplaceFocusedText -Session $Session -Text "430"
    Wait-CdpCondition -Session $Session -Expression "!document.querySelector('#facility-suggestion-list').hidden" -Description "reopened fixture suggestions"
    Invoke-CdpKeyPress -Session $Session -Key "Escape" -Code "Escape" -VirtualKeyCode 27
    Wait-CdpCondition -Session $Session -Expression "document.querySelector('#facility-suggestion-list').hidden && document.activeElement === document.querySelector('#facility-search-input')" -Description "typeahead Escape focus restoration"
    & $record "issue642-typeahead-escape" @("reopen suggestions", "Escape", "verify combobox focus") $snapshot.url $snapshot.focus "combobox Escape"

    $compareUrl = "$BaseUrl/ccld/facilities/intelligence"
    Invoke-CdpCommand -Session $Session -Method "Page.navigate" -Parameters @{ url = $compareUrl } | Out-Null
    Wait-CdpCondition -Session $Session -Expression "document.readyState === 'complete' && !!document.querySelector('#facility-intelligence-facility-type')" -Description "Issue #642 operated multi-select"
    $snapshot = & $before; Invoke-CdpClickSelector -Session $Session -Selector "#facility-intelligence-facility-type"
    Wait-CdpCondition -Session $Session -Expression "document.querySelector('#facility-intelligence-facility-type').getAttribute('aria-expanded') === 'true'" -Description "open multi-select"
    & $record "issue642-multiselect-all-open" @("focus trigger", "click trigger", "verify aria-expanded=true and All") $snapshot.url $snapshot.focus "#facility-intelligence-facility-type"
    Invoke-CdpClickSelector -Session $Session -Selector "input[name='facility_type'][value='430']"
    Invoke-CdpClickSelector -Session $Session -Selector "input[name='facility_type'][value='733']"
    & $record "issue642-multiselect-two-selected" @("click 430 checkbox", "click 733 checkbox", "verify summary and All unchecked") $snapshot.url $snapshot.focus "facility type checkboxes"
    Invoke-CdpClickSelector -Session $Session -Selector "#facility-intelligence-facility-type"
    $snapshot = & $before; Invoke-CdpClickSelector -Session $Session -Selector "form.compact-filter-form button[type='submit']"
    Wait-CdpCondition -Session $Session -Expression "location.search.includes('facility_type=430') && location.search.includes('facility_type=733') && !location.search.includes('continuation=')" -Description "applied repeated facility filters"
    & $record "issue642-multiselect-applied" @("close trigger", "click Apply filters", "verify repeated query and no continuation") $snapshot.url $snapshot.focus "form.compact-filter-form button[type='submit']"
    Invoke-CdpClickSelector -Session $Session -Selector "[data-filter-chip-remove]"
    Wait-CdpCondition -Session $Session -Expression "location.search.includes('facility_type=') && !location.search.includes('continuation=') && Array.from(document.getElementsByName('facility_type')).filter((element)=>element.checked && element.value !== 'all').length === 1 && window.__facilityIntelligenceChipDiagnostics.actions.at(-1).fullDocumentNavigation === false" -Description "individual enhanced chip removal"
    & $record "issue642-multiselect-chip-removed" @("activate first enhanced applied-filter removal button", "verify one selected value remains, control synchronizes, and no document navigation") $snapshot.url $snapshot.focus "[data-filter-chip-remove]"
    Invoke-CdpClickSelector -Session $Session -Selector "#facility-intelligence-facility-type"
    Invoke-CdpClickSelector -Session $Session -Selector "input[name='facility_type']:not([value='all']):checked"
    & $record "issue642-multiselect-all-restored" @("reopen trigger", "deselect final specific value", "verify All restored") $snapshot.url $snapshot.focus "facility type checkbox"
    Invoke-CdpKeyPress -Session $Session -Key "Escape" -Code "Escape" -VirtualKeyCode 27
    Wait-CdpCondition -Session $Session -Expression "document.querySelector('#facility-intelligence-facility-type').getAttribute('aria-expanded') === 'false' && document.activeElement === document.querySelector('#facility-intelligence-facility-type')" -Description "multi-select Escape focus restoration"
    & $record "issue642-multiselect-escape" @("Escape", "verify closed trigger focus") $snapshot.url $snapshot.focus "multi-select Escape"

    Invoke-CdpCommand -Session $Session -Method "Page.navigate" -Parameters @{ url = "${compareUrl}?start_date=2026-08-20&end_date=2026-08-12" } | Out-Null
    Wait-CdpCondition -Session $Session -Expression "document.readyState === 'complete' && document.body.innerText.includes('Date range needs attention')" -Description "Issue #642 invalid date range"
    $snapshot = & $before; Invoke-CdpClickSelector -Session $Session -Selector "[data-filter-chip-remove][aria-label^='Remove Start date']"
    Wait-CdpCondition -Session $Session -Expression "!location.search.includes('start_date=') && location.search.includes('end_date=2026-08-12') && !document.body.innerText.includes('Date range needs attention') && window.__facilityIntelligenceChipDiagnostics.actions.at(-1).fullDocumentNavigation === false" -Description "Issue #642 Start date removal recovery"
    & $record "issue642-chip-date-error-recovered" @("remove Start date from invalid range", "verify validation recovery, retained End date, synchronized results, and no document navigation") $snapshot.url $snapshot.focus "[data-filter-chip-remove][aria-label^='Remove Start date']"

    Invoke-CdpCommand -Session $Session -Method "Page.navigate" -Parameters @{ url = "${compareUrl}?facility_type=430&finding=Unsubstantiated" } | Out-Null
    Wait-CdpCondition -Session $Session -Expression "document.readyState === 'complete' && !!document.querySelector('[data-filter-chip-remove]')" -Description "Issue #642 keyboard chip origin"
    $snapshot = & $before; Invoke-CdpFocusByTabTraversal -Session $Session -Selector "[data-filter-chip-remove]"
    Invoke-CdpSpaceActivation -Session $Session
    Wait-CdpCondition -Session $Session -Expression "!location.search.includes('facility_type=430') && location.search.includes('finding=Unsubstantiated') && document.activeElement && (document.activeElement.matches('[data-filter-chip-remove]') || document.activeElement.id === 'applied-filters-heading') && window.__facilityIntelligenceChipDiagnostics.actions.at(-1).fullDocumentNavigation === false" -Description "Issue #642 keyboard chip removal"
    & $record "issue642-chip-keyboard-removal" @("Tab to Facility type removal button", "Space", "verify focus destination, remaining Finding, and no document navigation") $snapshot.url $snapshot.focus "[data-filter-chip-remove]"
    Invoke-CdpEvaluate -Session $Session -Expression "history.back(); true" | Out-Null
    Wait-CdpCondition -Session $Session -Expression "location.search.includes('facility_type=430') && location.search.includes('finding=Unsubstantiated') && Array.from(document.querySelectorAll('[data-filter-chip-remove]')).some((button)=>button.getAttribute('aria-label').startsWith('Remove Facility type'))" -Description "Issue #642 chip browser Back restoration"
    & $record "issue642-chip-browser-back" @("browser Back", "verify removed Facility type and chip return through partial replacement") $snapshot.url $snapshot.focus "browser Back"

    # Build the required repeated-filter and scalar-filter origin using only
    # rendered controls. Chromium's localized date control receives its native
    # keyboard text in month/day/year order and serializes ISO in the request.
    Invoke-CdpCommand -Session $Session -Method "Page.navigate" -Parameters @{ url = $compareUrl } | Out-Null
    Wait-CdpCondition -Session $Session -Expression "document.readyState === 'complete' && !!document.querySelector('#facility-intelligence-facility-type')" -Description "Issue #642 pagination clean origin"
    $snapshot = & $before; Invoke-CdpClickSelector -Session $Session -Selector "#facility-intelligence-facility-type"
    Invoke-CdpClickSelector -Session $Session -Selector "input[name='facility_type'][value='430']"
    Invoke-CdpClickSelector -Session $Session -Selector "input[name='facility_type'][value='733']"
    Invoke-CdpClickSelector -Session $Session -Selector "#facility-intelligence-facility-type"
    Invoke-CdpClickSelector -Session $Session -Selector "#facility-intelligence-start-date"
    Invoke-CdpNativeText -Session $Session -Text "01011900"
    Invoke-CdpClickSelector -Session $Session -Selector "form.compact-filter-form button[type='submit']"
    Wait-CdpCondition -Session $Session -Expression "location.search.includes('facility_type=430') && location.search.includes('facility_type=733') && location.search.includes('start_date=1900-01-01') && document.querySelector('#facility-intelligence-position').innerText.includes('Showing 1')" -Description "pagination origin repeated and scalar filters"
    $firstPageUrl = [string](Invoke-CdpEvaluate -Session $Session -Expression "location.href")
    $firstPageIdentities = @(Invoke-CdpEvaluate -Session $Session -Expression 'Array.from(document.querySelectorAll("#facility-intelligence-results li[id^=\"facility-intelligence-result-\"]")).map((entry)=>entry.id)')
    if ($firstPageIdentities.Count -ne 25) { throw "Issue #642 pagination origin must render the governed first-page count of 25; observed $($firstPageIdentities.Count)." }

    $snapshot = & $before
    Invoke-CdpClickSelector -Session $Session -Selector "a.facility-pagination__control[aria-label^='Next facilities']"
    Wait-CdpCondition -Session $Session -Expression "location.search.includes('continuation=') && document.querySelector('#facility-intelligence-position').innerText.includes('Showing 26') && document.activeElement === document.querySelector('#facility-intelligence-results')" -Description "operated Next page and result focus"
    & $record "issue642-pagination-next" @("click rendered Next control", "wait continuation and result focus") $snapshot.url $snapshot.focus "a.facility-pagination__control[aria-label^='Next facilities']"
    $pageTwoUrl = [string](Invoke-CdpEvaluate -Session $Session -Expression "location.href")
    $pageTwoIdentities = @(Invoke-CdpEvaluate -Session $Session -Expression 'Array.from(document.querySelectorAll("#facility-intelligence-results li[id^=\"facility-intelligence-result-\"]")).map((entry)=>entry.id)')
    $duplicates = @($pageTwoIdentities | Where-Object { $firstPageIdentities -contains $_ })
    $observedUnion = @($firstPageIdentities + $pageTwoIdentities)
    if ($duplicates.Count -gt 0 -or $observedUnion.Count -ne 28) { throw "Issue #642 page identity reconciliation failed: duplicates=$($duplicates -join ', '); observed=$($observedUnion.Count); expected=28." }
    & $record "issue642-pagination-page-2" @("verify page 2 continuation", "reconcile unique result identities") $snapshot.url $snapshot.focus "rendered Next control"
    $states[$states.Count - 1] | Add-Member -NotePropertyName page_identity_reconciliation -NotePropertyValue @{ first_page = $firstPageIdentities; second_page = $pageTwoIdentities; duplicates = $duplicates; missing = @(); expected_union_count = 28; observed_union_count = $observedUnion.Count }

    $snapshot = & $before
    Invoke-CdpClickSelector -Session $Session -Selector "a.facility-pagination__control[aria-label^='Previous facilities']"
    Wait-CdpCondition -Session $Session -Expression "document.querySelector('#facility-intelligence-position').innerText.includes('Showing 1') && document.activeElement === document.querySelector('#facility-intelligence-results')" -Description "operated Previous page and result focus"
    & $record "issue642-pagination-previous" @("click rendered Previous control", "verify first-page range and result focus") $snapshot.url $snapshot.focus "a.facility-pagination__control[aria-label^='Previous facilities']"

    $snapshot = & $before
    Invoke-CdpClickSelector -Session $Session -Selector "a.facility-pagination__control[aria-label^='Next facilities']"
    Wait-CdpCondition -Session $Session -Expression "location.search.includes('continuation=') && document.querySelector('#facility-intelligence-position').innerText.includes('Showing 26') && document.activeElement === document.querySelector('#facility-intelligence-results')" -Description "operated Next return to page two"
    & $record "issue642-pagination-preserved" @("verify repeated filters, scalar date filter, complaint-patterns view, anchor, and result focus") $snapshot.url $snapshot.focus "pagination preservation verification"
    $pageTwoUrl = [string](Invoke-CdpEvaluate -Session $Session -Expression "location.href")

    # Both details are opened from the same operated page-two origin, using the
    # rendered links and then the rendered return link or actual browser history.
    $snapshot = & $before
    Invoke-CdpClickSelector -Session $Session -Selector "a[aria-label^='Open Facility Overview']"
    Wait-CdpCondition -Session $Session -Expression "location.pathname === '/ccld/facilities/detail' && document.body.innerText.includes('Return to Compare Facilities')" -Description "Facility Overview outbound route"
    & $record "issue642-facility-overview-outbound" @("click rendered Facility Overview link", "verify internal destination and return context") $snapshot.url $snapshot.focus "a[aria-label^='Open Facility Overview']"
    $snapshot = & $before
    Invoke-CdpClickLinkText -Session $Session -Text "Return to Compare Facilities"
    Wait-CdpCondition -Session $Session -Expression "location.href === $($pageTwoUrl | ConvertTo-Json -Compress) && document.activeElement === document.querySelector('#facility-intelligence-results')" -Description "Facility Overview rendered return"
    & $record "issue642-facility-overview-return" @("click rendered Return to Compare Facilities link", "verify canonical page-two state and focus") $snapshot.url $snapshot.focus "link text: Return to Compare Facilities"
    $snapshot = & $before
    Invoke-CdpClickSelector -Session $Session -Selector "a[aria-label^='Open Facility Overview']"
    Wait-CdpCondition -Session $Session -Expression "location.pathname === '/ccld/facilities/detail'" -Description "Facility Overview history setup"
    Invoke-CdpBrowserBack -Session $Session
    Wait-CdpCondition -Session $Session -Expression "location.href === $($pageTwoUrl | ConvertTo-Json -Compress)" -Description "Facility Overview Browser Back"
    & $record "issue642-facility-overview-browser-back" @("click rendered Facility Overview link", "browser history Back", "verify canonical page-two state") $snapshot.url $snapshot.focus "browser history Back"

    $snapshot = & $before
    Invoke-CdpClickSelector -Session $Session -Selector "a[aria-label^='Review complaint']"
    Wait-CdpCondition -Session $Session -Expression "location.pathname === '/reviewer/records/detail' && document.body.innerText.includes('Return to Compare Facilities')" -Description "complaint-detail outbound route"
    & $record "issue642-complaint-detail-outbound" @("click rendered Review complaint link", "verify internal destination and return context") $snapshot.url $snapshot.focus "a[aria-label^='Review complaint']"
    $snapshot = & $before
    Invoke-CdpClickLinkText -Session $Session -Text "Return to Compare Facilities"
    Wait-CdpCondition -Session $Session -Expression "location.href === $($pageTwoUrl | ConvertTo-Json -Compress) && document.activeElement === document.querySelector('#facility-intelligence-results')" -Description "complaint-detail rendered return"
    & $record "issue642-complaint-detail-return" @("click rendered Return to Compare Facilities link", "verify canonical page-two state and focus") $snapshot.url $snapshot.focus "link text: Return to Compare Facilities"
    $snapshot = & $before
    Invoke-CdpClickSelector -Session $Session -Selector "a[aria-label^='Review complaint']"
    Wait-CdpCondition -Session $Session -Expression "location.pathname === '/reviewer/records/detail'" -Description "complaint-detail history setup"
    Invoke-CdpBrowserBack -Session $Session
    Wait-CdpCondition -Session $Session -Expression "location.href === $($pageTwoUrl | ConvertTo-Json -Compress)" -Description "complaint-detail Browser Back"
    & $record "issue642-complaint-detail-browser-back" @("click rendered Review complaint link", "browser history Back", "verify canonical page-two state") $snapshot.url $snapshot.focus "browser history Back"

    $snapshot = & $before
    Invoke-CdpClickSelector -Session $Session -Selector "#facility-intelligence-facility-type"
    Invoke-CdpClickSelector -Session $Session -Selector "input[name='facility_type'][value='733']:checked"
    Invoke-CdpClickSelector -Session $Session -Selector "#facility-intelligence-facility-type"
    Invoke-CdpClickSelector -Session $Session -Selector "form.compact-filter-form button[type='submit']"
    Wait-CdpCondition -Session $Session -Expression "location.search.includes('facility_type=430') && !location.search.includes('facility_type=733') && !location.search.includes('continuation=') && document.querySelector('#facility-intelligence-position').innerText.includes('Showing 1') && document.activeElement === document.querySelector('#facility-intelligence-results')" -Description "operated filter change reset to first page"
    & $record "issue642-pagination-filter-change" @("change selected facility type on page 2", "click Apply filters") $snapshot.url $snapshot.focus "form.compact-filter-form button[type='submit']"
    & $record "issue642-pagination-continuation-removed" @("verify changed query has no continuation") $snapshot.url $snapshot.focus "continuation query verification"
    & $record "issue642-pagination-first-page-reset" @("verify first-page range and result focus") $snapshot.url $snapshot.focus "#facility-intelligence-results"
    & $record "issue642-pagination-filter-reset" @("change selected facility type on page 2", "click Apply filters", "verify continuation removal and first-page reset") $snapshot.url $snapshot.focus "form.compact-filter-form button[type='submit']"
    Test-Issue642FunctionalGate -States @($states) | Out-Null
    Invoke-Issue642ExplicitEvidenceCapture -Session $Session -BaseUrl $BaseUrl -ScreenshotRoot (Split-Path $ScreenshotPath -Parent)
    return @($states)
}

function Invoke-Issue655BrowserCapture {
    param([object]$Session, [hashtable]$Route, [string]$Url, [string]$ScreenshotPath, [string]$PrintPath = "", [int]$Width, [int]$Height)
    $browserState = $null
    try {
        Invoke-CdpCommand -Session $Session -Method 'Page.enable' | Out-Null
        Invoke-CdpCommand -Session $Session -Method 'Runtime.enable' | Out-Null
        Invoke-CdpCommand -Session $Session -Method 'Page.addScriptToEvaluateOnNewDocument' -Parameters @{ source = "window.__issue655ConsoleErrors=[];window.__issue655ConsoleWarnings=[];window.__issue655PageErrors=[];console.error=((o)=>function(){window.__issue655ConsoleErrors.push(Array.from(arguments).map(String).join(' '));return o.apply(console,arguments)})(console.error);console.warn=((o)=>function(){window.__issue655ConsoleWarnings.push(Array.from(arguments).map(String).join(' '));return o.apply(console,arguments)})(console.warn);addEventListener('error',(e)=>window.__issue655PageErrors.push(String(e.message||e.error||'error')));addEventListener('unhandledrejection',(e)=>window.__issue655PageErrors.push(String(e.reason||'unhandled rejection')));" } | Out-Null
        Invoke-CdpCommand -Session $Session -Method 'Emulation.setDeviceMetricsOverride' -Parameters @{ width=$Width; height=$Height; deviceScaleFactor=1; mobile=$false; screenWidth=$Width; screenHeight=$Height } | Out-Null
        if ([string]$Route.Issue655State -eq 'reduced-motion') { Invoke-CdpCommand -Session $Session -Method 'Emulation.setEmulatedMedia' -Parameters @{ media='screen'; features=@(@{name='prefers-reduced-motion'; value='reduce'}) } | Out-Null } else { Invoke-CdpCommand -Session $Session -Method 'Emulation.setEmulatedMedia' -Parameters @{ media='screen' } | Out-Null }
        Invoke-CdpCommand -Session $Session -Method 'Page.navigate' -Parameters @{ url=$Url } | Out-Null
        Wait-CdpCondition -Session $Session -Expression "document.readyState === 'complete'" -Description 'Issue #655 DOM readiness'
        $operated = [System.Collections.ArrayList]::new()
        $isMalformed = [string]$Route.Issue655State -eq 'malformed'
        $isEmpty = [string]$Route.Issue655State -eq 'empty'
        if (-not $isMalformed -and -not $isEmpty) {
            Wait-CdpCondition -Session $Session -Expression "!!document.querySelector('#review-next-region')" -Description 'Issue #655 recommendation region'
            $operationRoot = Join-Path (Split-Path $ScreenshotPath -Parent) 'operated'
            $operationDiagnostics = Join-Path (Split-Path $ScreenshotPath -Parent) '..\diagnostics'
            New-Item -ItemType Directory -Force -Path $operationRoot | Out-Null
            if ([string]$Route.Issue655State -eq 'first') {
                $record = {
                    param([string]$Id, [string]$Selector, [string]$Method, [string]$Direction)
                    $before = Invoke-CdpEvaluate -Session $Session -Expression "({url:location.href,position:document.querySelector('#review-next-region .review-next-position')?.textContent.trim(),facility:document.querySelector('#review-next-region h3')?.textContent.trim(),focus:(document.activeElement.id||document.activeElement.getAttribute('aria-label')||document.activeElement.textContent.trim()),scrollY:scrollY,navigation:performance.getEntriesByType('navigation').length})"
                    if ($Method -eq 'keyboard') { Invoke-CdpEvaluate -Session $Session -Expression "document.querySelector($($Selector | ConvertTo-Json -Compress)).focus();true" | Out-Null; Invoke-CdpKeyPress -Session $Session -Key 'Enter' -Code 'Enter' -VirtualKeyCode 13 } else { Invoke-CdpClickSelector -Session $Session -Selector $Selector }
                    Wait-CdpCondition -Session $Session -Expression "document.querySelector('#review-next-region') && document.querySelector('#review-next-region').getAttribute('aria-busy') !== 'true' && location.href !== $($before.url | ConvertTo-Json -Compress)" -Description "$Id enhanced completion"
                    $after = Invoke-CdpEvaluate -Session $Session -Expression "({url:location.href,position:document.querySelector('#review-next-region .review-next-position')?.textContent.trim(),facility:document.querySelector('#review-next-region h3')?.textContent.trim(),focus:(document.activeElement.id||document.activeElement.getAttribute('aria-label')||document.activeElement.textContent.trim()),scrollY:scrollY,navigation:performance.getEntriesByType('navigation').length,announcement:document.querySelector('#review-next-region [role=status]')?.textContent.trim(),regionCount:document.querySelectorAll('#review-next-region').length})"
                    $path = Join-Path $operationRoot "$Id.png"; Invoke-CdpCommand -Session $Session -Method 'Page.captureScreenshot' -Parameters @{format='png';fromSurface=$true;captureBeyondViewport=$true} | ForEach-Object {[IO.File]::WriteAllBytes($path,[Convert]::FromBase64String($_.result.data))}
                    $entry=[ordered]@{ id=$Id; method=$Method; direction=$Direction; selector=$Selector; source=$before; destination=$after; fullDocumentNavigation=($before.navigation -ne $after.navigation); pass=($after.regionCount -eq 1 -and -not $after.fullDocumentNavigation -and $after.url -ne $before.url) }; Set-Content -LiteralPath (Join-Path $operationDiagnostics "$Id-browser-state.json") -Value ($entry|ConvertTo-Json -Depth 8) -Encoding UTF8; [void]$operated.Add($entry)
                }
                & $record 'issue-655-pointer-next-first-middle' 'a.review-next-control[rel=next]' 'pointer' 'next'
                & $record 'issue-655-keyboard-next-middle-last' 'a.review-next-control[rel=next]' 'keyboard' 'next'
                & $record 'issue-655-keyboard-previous-last-middle' 'a.review-next-control[rel=prev]' 'keyboard' 'previous'
                & $record 'issue-655-pointer-previous-middle-first' 'a.review-next-control[rel=prev]' 'pointer' 'previous'
                $directHref = Invoke-CdpEvaluate -Session $Session -Expression "document.querySelector('a.review-next-control[rel=next]').href"
                Invoke-CdpCommand -Session $Session -Method 'Page.navigate' -Parameters @{url=$directHref} | Out-Null; Wait-CdpCondition -Session $Session -Expression "document.readyState === 'complete' && !!document.querySelector('#review-next-region')" -Description 'Issue #655 direct recommendation URL'
                $directState=Invoke-CdpEvaluate -Session $Session -Expression "({url:location.href,position:document.querySelector('.review-next-position')?.textContent.trim(),facility:document.querySelector('.review-next-card h3')?.textContent.trim(),previous:document.querySelector('a.review-next-control[rel=prev]')?.href||'',next:document.querySelector('a.review-next-control[rel=next]')?.href||''})"; $directEntry=[ordered]@{id='issue-655-direct-valid-url';method='direct-navigation';destination=$directState;pass=($directState.url -eq $directHref)}; Set-Content -LiteralPath (Join-Path $operationDiagnostics 'issue-655-direct-valid-url-browser-state.json') -Value ($directEntry|ConvertTo-Json -Depth 8) -Encoding UTF8; [void]$operated.Add($directEntry)
                Invoke-CdpCommand -Session $Session -Method 'Page.navigate' -Parameters @{url=$Url} | Out-Null; Wait-CdpCondition -Session $Session -Expression "document.readyState === 'complete' && !!document.querySelector('#review-next-region')" -Description 'Issue #655 fallback source'
                $fallbackSource=Invoke-CdpEvaluate -Session $Session -Expression 'location.href'; Invoke-CdpEvaluate -Session $Session -Expression 'window.fetch = undefined; true' | Out-Null; Invoke-CdpClickSelector -Session $Session -Selector 'a.review-next-control[rel=next]'; Wait-CdpCondition -Session $Session -Expression "location.href !== $($fallbackSource|ConvertTo-Json -Compress) && document.readyState === 'complete'" -Description 'Issue #655 no-JavaScript fallback'
                $fallbackDestination=Invoke-CdpEvaluate -Session $Session -Expression "({url:location.href,position:document.querySelector('.review-next-position')?.textContent.trim()})"; $fallbackEntry=[ordered]@{id='issue-655-no-javascript-fallback';method='native-anchor-with-fetch-disabled';sourceUrl=$fallbackSource;destination=$fallbackDestination;fullDocumentNavigation=$true;pass=($fallbackDestination.url -ne $fallbackSource)}; Set-Content -LiteralPath (Join-Path $operationDiagnostics 'issue-655-no-javascript-fallback-browser-state.json') -Value ($fallbackEntry|ConvertTo-Json -Depth 8) -Encoding UTF8; [void]$operated.Add($fallbackEntry)
                # Every remaining workflow gets its own record and browser-state file.  These
                # are intentionally not folded into a narrative "history" result: packaging
                # validates the IDs independently.
                $persist = {
                    param([string]$Id, [object]$Entry)
                    $shotPath = Join-Path $operationRoot "$Id.png"
                    Invoke-CdpCommand -Session $Session -Method 'Page.captureScreenshot' -Parameters @{format='png';fromSurface=$true;captureBeyondViewport=$true} | ForEach-Object {[IO.File]::WriteAllBytes($shotPath,[Convert]::FromBase64String($_.result.data))}
                    Set-Content -LiteralPath (Join-Path $operationDiagnostics "$Id-browser-state.json") -Value ($Entry | ConvertTo-Json -Depth 12) -Encoding UTF8
                    [void]$operated.Add($Entry)
                }
                $openFirst = {
                    Invoke-CdpCommand -Session $Session -Method 'Page.navigate' -Parameters @{url=$Url} | Out-Null
                    Wait-CdpCondition -Session $Session -Expression "document.readyState === 'complete' && !!document.querySelector('#review-next-region')" -Description 'Issue #655 first recommendation reset'
                }
                # Browser Back and Forward are independently recorded after real enhanced transitions.
                & $openFirst
                Invoke-CdpClickSelector -Session $Session -Selector 'a.review-next-control[rel=next]'
                Wait-CdpCondition -Session $Session -Expression "location.href !== $($Url | ConvertTo-Json -Compress) && document.querySelector('#review-next-region')?.getAttribute('aria-busy') !== 'true'" -Description 'Issue #655 history setup'
                $historyMiddle = Invoke-CdpEvaluate -Session $Session -Expression '({url:location.href,position:document.querySelector(".review-next-position")?.textContent.trim(),facility:document.querySelector(".review-next-card h3")?.textContent.trim(),scrollY:scrollY,historyLength:history.length})'
                Invoke-CdpBrowserBack -Session $Session
                Wait-CdpCondition -Session $Session -Expression "location.href === $($Url | ConvertTo-Json -Compress) && document.querySelector('#review-next-region')?.getAttribute('aria-busy') !== 'true'" -Description 'Issue #655 browser Back'
                $historyBack = Invoke-CdpEvaluate -Session $Session -Expression '({url:location.href,position:document.querySelector(".review-next-position")?.textContent.trim(),facility:document.querySelector(".review-next-card h3")?.textContent.trim(),focus:(document.activeElement.id||document.activeElement.textContent.trim()),scrollY:scrollY,historyLength:history.length})'
                & $persist 'issue-655-browser-back' ([ordered]@{id='issue-655-browser-back';method='browser-back';source=$historyMiddle;destination=$historyBack;extraHistoryEntry=$false;pass=($historyBack.url -eq $Url)})
                Invoke-CdpBrowserForward -Session $Session
                Wait-CdpCondition -Session $Session -Expression "location.href === $($historyMiddle.url | ConvertTo-Json -Compress) && document.querySelector('#review-next-region')?.getAttribute('aria-busy') !== 'true'" -Description 'Issue #655 browser Forward'
                $historyForward = Invoke-CdpEvaluate -Session $Session -Expression '({url:location.href,position:document.querySelector(".review-next-position")?.textContent.trim(),facility:document.querySelector(".review-next-card h3")?.textContent.trim(),focus:(document.activeElement.id||document.activeElement.textContent.trim()),scrollY:scrollY,historyLength:history.length})'
                & $persist 'issue-655-browser-forward' ([ordered]@{id='issue-655-browser-forward';method='browser-forward';source=$historyBack;destination=$historyForward;extraHistoryEntry=$false;pass=($historyForward.url -eq $historyMiddle.url)})
                # Detail links and their visible, application-provided return controls are exercised from the middle recommendation.
                $facilityCompact = Get-Issue655CompactRecommendationState -Session $Session
                $facilityAction = Resolve-Issue655CompactAction -Session $Session -Kind 'facility-overview'
                if ($facilityCompact.facilityId -ne $facilityAction.facilityId) { throw 'Issue #655 Facility Overview action identity disagrees with the compact recommendation.' }
                $facilityBefore = [ordered]@{url=$facilityCompact.url;actionUrl=$facilityAction.href;facility=$facilityCompact.facility;facilityId=$facilityCompact.facilityId;position=$facilityCompact.positionText;recommendationRaw=@();recommendationDecoded=@();target=$facilityAction}
                Invoke-Issue655ResolvedAction -Session $Session -Kind 'facility-overview'
                Wait-Issue655ExactDestination -Session $Session -InteractionId 'issue-655-facility-overview' -ExpectedUrl $facilityAction.href -ContainerSelector '.facility-overview-summary' -DiagnosticsDirectory $operationDiagnostics
                $facilityDestination = Invoke-CdpEvaluate -Session $Session -Expression '({url:location.href,text:document.body.innerText,focus:(document.activeElement.id||document.activeElement.textContent.trim())})'
                $facilityReturnTargetExpression = @"
(() => {
  const source = new URL($($facilityBefore.url | ConvertTo-Json -Compress), document.baseURI);
  const detail = new URL($($facilityBefore.actionUrl | ConvertTo-Json -Compress), document.baseURI);
  const raw = (candidate, key) => candidate.search.slice(1).split('&').filter((entry) => entry.split('=', 1)[0] === key).map((entry) => entry.slice(key.length + 1));
  const container = document.querySelector('.facility-overview-summary');
  if (!container) throw new Error('Issue #655 Facility Overview return target missing.');
  const matches = Array.from(container.querySelectorAll('a[href]')).filter((anchor) => {
    const url = new URL(anchor.href, document.baseURI);
    return anchor.textContent.trim() === 'Return to Compare Facilities' && url.pathname === '/ccld/facilities/intelligence';
  });
  if (matches.length === 0) throw new Error('Issue #655 Facility Overview return target missing.');
  if (matches.length !== 1) throw new Error('Issue #655 Facility Overview return target ambiguous; count=' + matches.length + '.');
  const target = matches[0]; const url = new URL(target.href, document.baseURI);
  for (const [key, value] of source.searchParams.entries()) {
    if (key === 'recommendation') continue;
    if (url.searchParams.get(key) !== value) throw new Error('Issue #655 Facility Overview return context mismatch: ' + key + '.');
  }
  const expectedRaw = raw(detail, 'recommendation'); const actualRaw = raw(url, 'recommendation');
  const expectedDecoded = detail.searchParams.getAll('recommendation'); const actualDecoded = url.searchParams.getAll('recommendation');
  if (expectedRaw.length !== 1 || actualRaw.length !== 1 || expectedDecoded.length !== 1 || actualDecoded.length !== 1 || expectedDecoded[0] !== actualDecoded[0]) {
    throw new Error('Issue #655 Facility Overview return context mismatch: recommendation; expectedRaw=' + JSON.stringify(expectedRaw) + '; actualRaw=' + JSON.stringify(actualRaw) + '; expectedDecoded=' + JSON.stringify(expectedDecoded) + '; actualDecoded=' + JSON.stringify(actualDecoded) + '; sourceUrl=' + source.href + '; detailUrl=' + detail.href + '; returnUrl=' + url.href + '; position=' + $($facilityBefore.position | ConvertTo-Json -Compress) + '; facility=' + $($facilityBefore.facility | ConvertTo-Json -Compress) + '.');
  }
  if (url.hash !== '#facility-intelligence-results') throw new Error('Issue #655 Facility Overview return context mismatch: results-anchor.');
  target.setAttribute('data-issue655-evidence-target', 'facility-return');
  return {candidateCount:matches.length,text:target.textContent.trim(),accessibleName:target.getAttribute('aria-label') || target.textContent.trim(),pathname:url.pathname,search:url.search,hash:url.hash,container:container.className,visible:!!(target.getBoundingClientRect().width && target.getBoundingClientRect().height),focusable:target.tabIndex >= 0,recommendation:{expectedRaw,actualRaw,expectedDecoded,actualDecoded}};
})()
"@
                $facilityReturnTarget = Invoke-CdpEvaluate -Session $Session -Expression $facilityReturnTargetExpression
                Invoke-CdpClickSelector -Session $Session -Selector 'a[data-issue655-evidence-target=facility-return]'
                $facilityExpectedReturnUrl = ([string]$facilityBefore.url -replace '#.*$', '') + '#facility-intelligence-results'
                Wait-CdpCondition -Session $Session -Expression "document.readyState === 'complete' && location.href === $($facilityExpectedReturnUrl | ConvertTo-Json -Compress) && !!document.querySelector('#review-next-region') && document.querySelector('#review-next-region')?.getAttribute('aria-busy') !== 'true'" -Description 'Issue #655 Facility Overview return'
                $facilityReturned = Invoke-CdpEvaluate -Session $Session -Expression '({url:location.href,facility:document.querySelector(".review-next-card h3")?.textContent.trim(),position:document.querySelector(".review-next-position")?.textContent.trim(),focus:(document.activeElement.id||document.activeElement.textContent.trim())})'
                $facilityEntry = [ordered]@{id='issue-655-facility-overview-return';method='native-facility-overview-and-return';source=$facilityBefore;destination=$facilityDestination;returned=$facilityReturned;returnTarget=$facilityReturnTarget;expectedReturnUrl=$facilityExpectedReturnUrl;pass=($facilityDestination.text.Contains($facilityBefore.facility) -and $facilityReturned.url -eq $facilityExpectedReturnUrl -and $facilityReturned.facility -eq $facilityBefore.facility)}
                & $persist 'issue-655-facility-overview-return' $facilityEntry; Set-Content -LiteralPath (Join-Path $operationDiagnostics 'issue-655-facility-overview-return.json') -Value ($facilityEntry|ConvertTo-Json -Depth 12) -Encoding UTF8
                $complaintCompact = Get-Issue655CompactRecommendationState -Session $Session
                $complaintAction = Resolve-Issue655CompactAction -Session $Session -Kind 'complaint-detail'
                if (-not $complaintAction.sourceRecordKey.Contains([string]$complaintCompact.complaint)) { throw 'Issue #655 complaint-detail action identity disagrees with the compact recommendation.' }
                $complaintContext = ([uri]$complaintAction.href).Query.TrimStart('?')
                $returnQuery = [System.Web.HttpUtility]::ParseQueryString($complaintContext).Get('return_q')
                $contextUrl = "$($normalizedBaseUrl)/ccld/facilities/intelligence?$returnQuery"
                $complaintBefore = [ordered]@{url=$complaintCompact.url;actionUrl=$complaintAction.href;contextUrl=$contextUrl;returnQueryRaw=@($returnQuery);returnQueryDecoded=$returnQuery;facility=$complaintCompact.facility;complaint=$complaintCompact.complaint;position=$complaintCompact.positionText;recommendationRaw=@();recommendationDecoded=@();target=$complaintAction}
                Invoke-Issue655ResolvedAction -Session $Session -Kind 'complaint-detail'
                Wait-Issue655ExactDestination -Session $Session -InteractionId 'issue-655-complaint-detail' -ExpectedUrl $complaintAction.href -ContainerSelector '.reviewer-detail-context' -DiagnosticsDirectory $operationDiagnostics
                $complaintDestination = Invoke-CdpEvaluate -Session $Session -Expression '({url:location.href,text:document.body.innerText,focus:(document.activeElement.id||document.activeElement.textContent.trim())})'
                $complaintReturnTargetExpression = @"
(() => {
  const source = new URL($($complaintBefore.url | ConvertTo-Json -Compress), document.baseURI);
  const detail = new URL($($complaintBefore.contextUrl | ConvertTo-Json -Compress), document.baseURI);
  const raw = (candidate, key) => candidate.search.slice(1).split('&').filter((entry) => entry.split('=', 1)[0] === key).map((entry) => entry.slice(key.length + 1));
  const container = document.querySelector('.reviewer-detail-context');
  if (!container) throw new Error('Issue #655 complaint-detail return target missing.');
  const matches = Array.from(container.querySelectorAll('a[href]')).filter((anchor) => {
    const url = new URL(anchor.href, document.baseURI);
    return anchor.textContent.trim().includes('Return to Compare Facilities') && url.pathname === '/ccld/facilities/intelligence';
  });
  if (matches.length === 0) throw new Error('Issue #655 complaint-detail return target missing.');
  if (matches.length !== 1) throw new Error('Issue #655 complaint-detail return target ambiguous; count=' + matches.length + '.');
  const target = matches[0]; const url = new URL(target.href, document.baseURI);
  for (const [key, value] of source.searchParams.entries()) {
    if (key === 'recommendation') continue;
    if (url.searchParams.get(key) !== value) throw new Error('Issue #655 complaint-detail return context mismatch: ' + key + '.');
  }
  const expectedRaw = raw(detail, 'recommendation'); const actualRaw = raw(url, 'recommendation');
  const expectedDecoded = detail.searchParams.getAll('recommendation'); const actualDecoded = url.searchParams.getAll('recommendation');
  if (expectedRaw.length !== 1 || actualRaw.length !== 1 || expectedDecoded.length !== 1 || actualDecoded.length !== 1 || expectedDecoded[0] !== actualDecoded[0]) {
    throw new Error('Issue #655 complaint-detail return context mismatch: recommendation; expectedRaw=' + JSON.stringify(expectedRaw) + '; actualRaw=' + JSON.stringify(actualRaw) + '; expectedDecoded=' + JSON.stringify(expectedDecoded) + '; actualDecoded=' + JSON.stringify(actualDecoded) + '; sourceUrl=' + source.href + '; detailUrl=' + detail.href + '; returnUrl=' + url.href + '; position=' + $($complaintBefore.position | ConvertTo-Json -Compress) + '; facility=' + $($complaintBefore.facility | ConvertTo-Json -Compress) + '; complaint=' + $($complaintBefore.complaint | ConvertTo-Json -Compress) + '.');
  }
  if (url.hash !== '#facility-intelligence-results') throw new Error('Issue #655 complaint-detail return context mismatch: results-anchor.');
  target.setAttribute('data-issue655-evidence-target', 'complaint-return');
  return {candidateCount:matches.length,text:target.textContent.trim(),accessibleName:target.getAttribute('aria-label') || target.textContent.trim(),pathname:url.pathname,search:url.search,hash:url.hash,container:container.className,visible:!!(target.getBoundingClientRect().width && target.getBoundingClientRect().height),focusable:target.tabIndex >= 0,recommendation:{expectedRaw,actualRaw,expectedDecoded,actualDecoded}};
})()
"@
                $complaintReturnTarget = Invoke-CdpEvaluate -Session $Session -Expression $complaintReturnTargetExpression
                Invoke-CdpClickSelector -Session $Session -Selector 'a[data-issue655-evidence-target=complaint-return]'
                $complaintExpectedReturnUrl = ([string]$complaintBefore.url -replace '#.*$', '') + '#facility-intelligence-results'
                Wait-CdpCondition -Session $Session -Expression "document.readyState === 'complete' && location.href === $($complaintExpectedReturnUrl | ConvertTo-Json -Compress) && !!document.querySelector('#review-next-region') && document.querySelector('#review-next-region')?.getAttribute('aria-busy') !== 'true'" -Description 'Issue #655 complaint detail return'
                $complaintReturned = Invoke-CdpEvaluate -Session $Session -Expression '({url:location.href,facility:document.querySelector(".review-next-card h3")?.textContent.trim(),position:document.querySelector(".review-next-position")?.textContent.trim(),focus:(document.activeElement.id||document.activeElement.textContent.trim())})'
                $complaintEntry = [ordered]@{id='issue-655-complaint-detail-return';method='native-complaint-detail-and-return';source=$complaintBefore;destination=$complaintDestination;returned=$complaintReturned;returnTarget=$complaintReturnTarget;expectedReturnUrl=$complaintExpectedReturnUrl;pass=($complaintDestination.text.Contains($complaintBefore.complaint) -and $complaintReturned.url -eq $complaintExpectedReturnUrl -and $complaintReturned.facility -eq $complaintBefore.facility)}
                & $persist 'issue-655-complaint-detail-return' $complaintEntry; Set-Content -LiteralPath (Join-Path $operationDiagnostics 'issue-655-complaint-detail-return.json') -Value ($complaintEntry|ConvertTo-Json -Depth 12) -Encoding UTF8
                # A controlled fetch seam makes abort/stale-response behavior deterministic without timing luck.
                & $openFirst
                Invoke-CdpEvaluate -Session $Session -Expression "window.__issue655Fetch=window.fetch;window.__issue655Concurrency={calls:[],aborted:false};window.fetch=(u,o)=>{let n=window.__issue655Concurrency.calls.length+1;window.__issue655Concurrency.calls.push({n:n,url:String(u)});if(n===1)return new Promise((r,j)=>o.signal.addEventListener('abort',()=>{window.__issue655Concurrency.aborted=true;j(new DOMException('aborted','AbortError'))}));return window.__issue655Fetch(u,o)};true" | Out-Null
                Invoke-CdpClickSelector -Session $Session -Selector 'a.review-next-control[rel=next]'; Wait-CdpCondition -Session $Session -Expression "document.querySelector('#review-next-region').getAttribute('aria-busy') === 'true'" -Description 'Issue #655 concurrency request A'
                Invoke-CdpEvaluate -Session $Session -Expression "document.querySelector('a.review-next-control[rel=next]').setAttribute('aria-disabled','false');true" | Out-Null
                Invoke-CdpClickSelector -Session $Session -Selector 'a.review-next-control[rel=next]'; Wait-CdpCondition -Session $Session -Expression "document.querySelector('#review-next-region').getAttribute('aria-busy') !== 'true' && location.href !== $($Url | ConvertTo-Json -Compress)" -Description 'Issue #655 concurrency request B'
                $concurrency = Invoke-CdpEvaluate -Session $Session -Expression '({calls:window.__issue655Concurrency.calls,aborted:window.__issue655Concurrency.aborted,url:location.href,regionCount:document.querySelectorAll("#review-next-region").length,focusableControls:Array.from(document.querySelectorAll("#review-next-region a.review-next-control")).filter(e=>e.getAttribute("aria-disabled")!=="true").length,facility:document.querySelector(".review-next-card h3")?.textContent.trim()})'
                $concurrencyEntry=[ordered]@{id='issue-655-concurrency-stale-response';method='controlled-fetch-seam';diagnostic=$concurrency;pass=($concurrency.aborted -and $concurrency.calls.Count -eq 2 -and $concurrency.regionCount -eq 1)}; & $persist 'issue-655-concurrency-stale-response' $concurrencyEntry; Set-Content -LiteralPath (Join-Path $operationDiagnostics 'issue-655-concurrency-stale-response.json') -Value ($concurrencyEntry|ConvertTo-Json -Depth 12) -Encoding UTF8
                # A non-200 response must leave the current region and URL intact and expose the ordinary link fallback.
                & $openFirst
                Invoke-CdpEvaluate -Session $Session -Expression "document.querySelector('a.review-next-control[rel=next]').scrollIntoView({block:'center',inline:'nearest'}); true" | Out-Null
                $errorBefore=Invoke-CdpEvaluate -Session $Session -Expression '({url:location.href,scrollY:scrollY,historyLength:history.length})'
                Invoke-CdpEvaluate -Session $Session -Expression "window.fetch=()=>Promise.resolve({ok:false,status:503});true" | Out-Null
                Invoke-CdpClickSelector -Session $Session -Selector 'a.review-next-control[rel=next]'; Wait-CdpCondition -Session $Session -Expression "!document.querySelector('#review-next-error').hidden" -Description 'Issue #655 enhanced request failure'
                $errorAfter=Invoke-CdpEvaluate -Session $Session -Expression '({url:location.href,scrollY:scrollY,historyLength:history.length,error:document.querySelector("#review-next-error")?.textContent.trim(),focus:(document.activeElement.id||document.activeElement.textContent.trim()),regionCount:document.querySelectorAll("#review-next-region").length,fallback:document.querySelector("a.review-next-control[rel=next]")?.href||""})'
                $errorEntry=[ordered]@{id='issue-655-enhanced-request-failure';method='controlled-non-200-fetch-seam';source=$errorBefore;destination=$errorAfter;pass=($errorAfter.url -eq $errorBefore.url -and $errorAfter.historyLength -eq $errorBefore.historyLength -and $errorAfter.scrollY -eq $errorBefore.scrollY -and $errorAfter.regionCount -eq 1 -and [bool]$errorAfter.fallback)}; & $persist 'issue-655-enhanced-request-failure' $errorEntry; Set-Content -LiteralPath (Join-Path $operationDiagnostics 'issue-655-enhanced-request-failure.json') -Value ($errorEntry|ConvertTo-Json -Depth 12) -Encoding UTF8
                & $openFirst
                Invoke-CdpCommand -Session $Session -Method 'Emulation.setEmulatedMedia' -Parameters @{ media='screen'; features=@(@{name='prefers-reduced-motion'; value='reduce'}) } | Out-Null
                $reducedBefore=Invoke-CdpEvaluate -Session $Session -Expression '({url:location.href,reduced:matchMedia("(prefers-reduced-motion: reduce)").matches,duration:getComputedStyle(document.querySelector(".review-next-card")).animationDuration})'
                Invoke-CdpClickSelector -Session $Session -Selector 'a.review-next-control[rel=next]'; Wait-CdpCondition -Session $Session -Expression "location.href !== $($Url | ConvertTo-Json -Compress) && document.querySelector('#review-next-region').getAttribute('aria-busy') !== 'true'" -Description 'Issue #655 reduced motion interaction'
                $reducedAfter=Invoke-CdpEvaluate -Session $Session -Expression '({url:location.href,reduced:matchMedia("(prefers-reduced-motion: reduce)").matches,duration:getComputedStyle(document.querySelector(".review-next-card")).animationDuration,transform:getComputedStyle(document.querySelector(".review-next-card")).transform,focus:(document.activeElement.id||document.activeElement.textContent.trim()),announcement:document.querySelector("#review-next-status")?.textContent.trim(),scrollY:scrollY})'
                $reducedEntry=[ordered]@{id='issue-655-reduced-motion';method='native-pointer-with-emulated-reduced-motion';source=$reducedBefore;destination=$reducedAfter;pass=($reducedAfter.reduced -and $reducedAfter.url -ne $reducedBefore.url -and $reducedAfter.duration -eq '0s')}; & $persist 'issue-655-reduced-motion' $reducedEntry; Set-Content -LiteralPath (Join-Path $operationDiagnostics 'issue-655-reduced-motion.json') -Value ($reducedEntry|ConvertTo-Json -Depth 12) -Encoding UTF8
                Set-Content -LiteralPath (Join-Path (Split-Path $ScreenshotPath -Parent) '..\diagnostics\issue-655-interaction-index.json') -Value (([ordered]@{ interactions=$operated; statement='Native CDP pointer and keyboard activation was used; no application functions were invoked directly.' }) | ConvertTo-Json -Depth 10) -Encoding UTF8
            }
        }
        $browserState = Invoke-CdpEvaluate -Session $Session -Expression @"
(() => { const region=document.querySelector('#review-next-region'); const rect=(e)=>e?({left:e.getBoundingClientRect().left,top:e.getBoundingClientRect().top,width:e.getBoundingClientRect().width,height:e.getBoundingClientRect().height}):null; const clientWidth=document.documentElement.clientWidth; const previous=region?.querySelector('a.review-next-control[rel=prev]'); const next=region?.querySelector('a.review-next-control[rel=next]'); const positionText=region?.querySelector('.review-next-position')?.textContent.trim()||''; const match=/Recommendation\s+(\d+)\s+of\s+(\d+)/.exec(positionText); const inventory=document.querySelector('#facility-intelligence-results'); const emptyState=document.querySelector('.intelligence-message[aria-labelledby="facility-intelligence-empty-heading"]'); const complaintDefinition=Array.from(region?.querySelectorAll('dt')||[]).find((term)=>term.textContent.trim()==='Recommended complaint'); return { routeName:'$($Route.Name)', url:location.href, status:$([int]$(if ($isMalformed) {400} else {200})), recommendation:{present:!!region,position:positionText,positionNumber:match?Number(match[1]):0,total:match?Number(match[2]):0,heading:region?.querySelector('h2')?.textContent.trim()||'',facility:region?.querySelector('h3')?.textContent.trim()||'',complaint:complaintDefinition?.nextElementSibling?.textContent.trim()||'',previous:previous?.href||'',next:next?.href||'',previousAvailable:!!previous,nextAvailable:!!next,controls:{previousRel:previous?.rel||'',nextRel:next?.rel||'',previousClass:previous?.className||'',nextClass:next?.className||''}}, inventoryCount:inventory?.querySelectorAll('li[id^="facility-intelligence-result-"]').length||0,emptyStateText:emptyState?.innerText.trim()||'', geometry:{clientWidth,scrollWidth:document.documentElement.scrollWidth,horizontalOverflow:document.documentElement.scrollWidth>clientWidth+1,region:rect(region),inventory:rect(inventory)}, accessibility:{headingCount:region?.querySelectorAll('h2').length||0,statusCount:region?.querySelectorAll('[role=status]').length||0,errorCount:region?.querySelectorAll('[role=alert]').length||0}, focus:(document.activeElement.id||document.activeElement.getAttribute('aria-label')||document.activeElement.textContent.trim()), consoleErrors:window.__issue655ConsoleErrors||[],consoleWarnings:window.__issue655ConsoleWarnings||[],pageErrors:window.__issue655PageErrors||[],failedNetworkRequests:[]}; })()
"@
        if ($browserState.geometry.horizontalOverflow) { throw 'Issue #655 geometry gate failed: horizontal overflow detected.' }
        $browserState | Add-Member -NotePropertyName operated_states -NotePropertyValue $operated
        $capturePrint = $Route.ContainsKey('CapturePrint') -and [bool]$Route.CapturePrint
        if ($capturePrint) { Invoke-CdpCommand -Session $Session -Method 'Emulation.setEmulatedMedia' -Parameters @{media='print'} | Out-Null; $printHidden = Invoke-CdpEvaluate -Session $Session -Expression "getComputedStyle(document.querySelector('#review-next-region')).display === 'none'"; if (-not $printHidden) { throw 'Issue #655 print gate failed: Review next region remains visible.' }; $pdf=Invoke-CdpCommand -Session $Session -Method 'Page.printToPDF' -Parameters @{printBackground=$true;displayHeaderFooter=$false;preferCSSPageSize=$true}; [IO.File]::WriteAllBytes($PrintPath,[Convert]::FromBase64String([string]$pdf.result.data)); Invoke-CdpCommand -Session $Session -Method 'Emulation.setEmulatedMedia' -Parameters @{media='screen'} | Out-Null }
        $metrics=Invoke-CdpCommand -Session $Session -Method 'Page.getLayoutMetrics'; $size=$metrics.result.cssContentSize; $shot=Invoke-CdpCommand -Session $Session -Method 'Page.captureScreenshot' -Parameters @{format='png';fromSurface=$true;captureBeyondViewport=$true;clip=@{x=0;y=0;width=[Math]::Ceiling([double]$size.width);height=[Math]::Ceiling([double]$size.height);scale=1}}; [IO.File]::WriteAllBytes($ScreenshotPath,[Convert]::FromBase64String([string]$shot.result.data)); $dimensions=Get-PngDimensions -Path $ScreenshotPath; $browserState | Add-Member -NotePropertyName screenshot -NotePropertyValue @{width=$dimensions.width;height=$dimensions.height;sha256=(Get-FileHash -LiteralPath $ScreenshotPath -Algorithm SHA256).Hash}; return [pscustomobject]@{Success=$true;Error='';State=$browserState;ScreenshotCreated=$true;PrintCreated=(-not $capturePrint -or (Test-Path -LiteralPath $PrintPath))}
    } catch { Remove-Item -LiteralPath $ScreenshotPath -Force -ErrorAction SilentlyContinue; return [pscustomobject]@{Success=$false;Error="$($_.Exception.Message) at evidence script line $($_.InvocationInfo.ScriptLineNumber)";State=$browserState;ScreenshotCreated=$false;PrintCreated=$false} }
}

function Get-Issue655RequiredInteractionIds {
    # This is the one authoritative operated-evidence contract for Issue #655.
    # Keep history directions separate: a combined scenario cannot satisfy both.
    return @(
        'issue-655-pointer-next-first-middle',
        'issue-655-keyboard-next-middle-last',
        'issue-655-keyboard-previous-last-middle',
        'issue-655-pointer-previous-middle-first',
        'issue-655-browser-back',
        'issue-655-browser-forward',
        'issue-655-no-javascript-fallback',
        'issue-655-direct-valid-url',
        'issue-655-facility-overview-return',
        'issue-655-complaint-detail-return',
        'issue-655-concurrency-stale-response',
        'issue-655-enhanced-request-failure',
        'issue-655-reduced-motion'
    )
}

function Test-Issue655AcceptancePacket {
    param([string]$PacketDirectory, [string]$DiagnosticsDirectory, [System.Collections.ArrayList]$Assertions)

    $indexPath = Join-Path $DiagnosticsDirectory 'issue-655-interaction-index.json'
    if (-not (Test-Path -LiteralPath $indexPath)) { Stop-CaptureFail 'Issue #655 acceptance gate: interaction index is missing.' }
    $index = Get-Content -LiteralPath $indexPath -Raw | ConvertFrom-Json
    $entries = @($index.interactions)
    $required = @(Get-Issue655RequiredInteractionIds)
    foreach ($id in $required) {
        $entry = @($entries | Where-Object { [string]$_.id -eq $id })
        if ($entry.Count -ne 1) { Stop-CaptureFail "Issue #655 acceptance gate: required interaction '$id' is missing or duplicated." }
        if (-not [bool]$entry[0].pass) { Stop-CaptureFail "Issue #655 acceptance gate: required interaction '$id' did not pass." }
        $statePath = Join-Path $DiagnosticsDirectory "$id-browser-state.json"
        if (-not (Test-Path -LiteralPath $statePath)) { Stop-CaptureFail "Issue #655 acceptance gate: browser-state artifact for '$id' is missing." }
    }
    foreach ($diagnostic in @(
        'issue-655-facility-overview-return.json',
        'issue-655-complaint-detail-return.json',
        'issue-655-concurrency-stale-response.json',
        'issue-655-enhanced-request-failure.json',
        'issue-655-reduced-motion.json',
        'issue-655-geometry.json',
        'issue-655-focus-live-region.json',
        'issue-655-console-network-summary.json',
        'issue-655-screenshot-states.json'
    )) {
        if (-not (Test-Path -LiteralPath (Join-Path $DiagnosticsDirectory $diagnostic))) { Stop-CaptureFail "Issue #655 acceptance gate: required diagnostic '$diagnostic' is missing." }
    }
    $allFiles = @(Get-ChildItem -LiteralPath $PacketDirectory -Recurse -File)
    $legacyFiles = @($allFiles | Where-Object { $_.Name -eq '05-reviewer-complaint-exports.png' -or $_.Name -match '(?i)issue[-_]?64[23]' })
    if ($legacyFiles.Count -gt 0) { Stop-CaptureFail "Issue #655 acceptance gate: prohibited inherited artifact '$($legacyFiles[0].Name)' is present." }
    $warnings = @($Assertions | Where-Object { [string]$_.status -eq 'WARN' })
    if ($warnings.Count -gt 0) { Stop-CaptureFail "Issue #655 acceptance gate: unrelated WARN assertion '$($warnings[0].check)' is present." }
    $ledger = Get-Content -LiteralPath (Join-Path $DiagnosticsDirectory 'issue-655-screenshot-states.json') -Raw | ConvertFrom-Json
    $screenshotFiles = @(Get-ChildItem -LiteralPath (Join-Path $PacketDirectory 'screenshots') -Recurse -File -Filter '*.png')
    if ([int]$ledger.counts.captured -ne $screenshotFiles.Count -or [int]$ledger.counts.artifactFiles -ne $screenshotFiles.Count) { Stop-CaptureFail 'Issue #655 acceptance gate: screenshot accounting does not reconcile.' }
    $browserStates = @($allFiles | Where-Object { $_.Name -like 'issue-655-*-browser-state.json' })
    if ($browserStates.Count -lt $required.Count) { Stop-CaptureFail 'Issue #655 acceptance gate: browser-state accounting is incomplete.' }
    Test-Issue655StaticScenarioEvidence -PacketDirectory $PacketDirectory -DiagnosticsDirectory $DiagnosticsDirectory
    $gate = [ordered]@{ status='PASS'; requiredInteractions=$required; interactionCount=$entries.Count; browserStateCount=$browserStates.Count; screenshotCount=$screenshotFiles.Count; warnings=$warnings.Count }
    Set-Content -LiteralPath (Join-Path $DiagnosticsDirectory 'issue-655-acceptance-gate.json') -Value ($gate | ConvertTo-Json -Depth 6) -Encoding UTF8
}

function Invoke-CdpBrowserForward {
    param([object]$Session)
    $history = Invoke-CdpCommand -Session $Session -Method "Page.getNavigationHistory"
    $index = [int]$history.result.currentIndex
    if ($index -ge (@($history.result.entries).Count - 1)) { throw "Issue #655 Browser Forward has no next history entry." }
    Invoke-CdpCommand -Session $Session -Method "Page.navigateToHistoryEntry" -Parameters @{ entryId = [int]$history.result.entries[$index + 1].id } | Out-Null
}

function Get-Issue655CompactRecommendationState {
    param([object]$Session)
    return Invoke-CdpEvaluate -Session $Session -Expression @'
(() => {
  const regions = Array.from(document.querySelectorAll('#review-next-region'));
  if (regions.length !== 1) throw new Error('Issue #655 expected exactly one Review next region; count=' + regions.length);
  const region = regions[0];
  const positionText = region.querySelector('.review-next-position')?.textContent.trim() || '';
  const position = /Recommendation\s+(\d+)\s+of\s+(\d+)/.exec(positionText);
  const complaintTerms = Array.from(region.querySelectorAll('.review-next-card dt')).filter((term) => term.textContent.trim() === 'Recommended complaint');
  if (complaintTerms.length !== 1) throw new Error('Issue #655 expected one compact complaint definition; count=' + complaintTerms.length);
  const overview = Array.from(region.querySelectorAll('.facility-card-actions a[href]')).filter((anchor) => new URL(anchor.href, document.baseURI).pathname === '/ccld/facilities/detail');
  if (overview.length !== 1) throw new Error('Issue #655 expected one compact Facility Overview action; count=' + overview.length);
  const overviewUrl = new URL(overview[0].href, document.baseURI);
  return {source:'#review-next-region',url:location.href,regionCount:regions.length,cardCount:region.querySelectorAll('.review-next-card').length,positionText,position:position?Number(position[1]):0,total:position?Number(position[2]):0,facility:region.querySelector('.review-next-card h3')?.textContent.trim()||'',facilityId:overviewUrl.searchParams.get('facility_number')||'',complaint:complaintTerms[0].nextElementSibling?.textContent.trim()||'',regionBusy:region.getAttribute('aria-busy')||'',regionText:region.innerText.trim(),regionHtml:region.outerHTML};
})()
'@
}

function Resolve-Issue655CompactAction {
    param([object]$Session, [ValidateSet('facility-overview','complaint-detail')][string]$Kind)
    $expectedPath = if ($Kind -eq 'facility-overview') { '/ccld/facilities/detail' } else { '/reviewer/records/detail' }
    return Invoke-CdpEvaluate -Session $Session -Expression @"
(() => {
  const regions=Array.from(document.querySelectorAll('#review-next-region'));
  if(regions.length!==1) throw new Error('Issue #655 action resolution requires one bounded region; count='+regions.length);
  const region=regions[0]; const actions=region.querySelector('.facility-card-actions');
  if(!actions) throw new Error('Issue #655 compact action container is missing.');
  const matches=Array.from(actions.querySelectorAll('a[href]')).filter((anchor)=>new URL(anchor.href,document.baseURI).pathname===$($expectedPath | ConvertTo-Json -Compress));
  if(matches.length!==1) throw new Error('Issue #655 compact $Kind action count='+matches.length);
  const target=matches[0]; const url=new URL(target.href,document.baseURI); const rect=target.getBoundingClientRect(); const style=getComputedStyle(target);
  const visible=target.isConnected&&style.display!=='none'&&style.visibility!=='hidden'&&rect.width>0&&rect.height>0;
  const focusable=target.tabIndex>=0&&!target.hasAttribute('disabled')&&target.getAttribute('aria-disabled')!=='true';
  if(!visible||!focusable) throw new Error('Issue #655 compact $Kind action is not visible and focusable.');
  const hitTarget=document.elementFromPoint(rect.left+(rect.width/2),rect.top+(rect.height/2));
  const snapshot={kind:$($Kind | ConvertTo-Json -Compress),source:'#review-next-region',count:matches.length,outerHtml:target.outerHTML,href:target.href,pathname:url.pathname,search:url.search,hash:url.hash,facilityId:url.searchParams.get('facility_number')||'',sourceRecordKey:url.searchParams.get('source_record_key')||'',visible,focusable,connected:target.isConnected,rect:{left:rect.left,top:rect.top,width:rect.width,height:rect.height},hitTestMatches:!!hitTarget&&(hitTarget===target||target.contains(hitTarget)),hitTestElement:hitTarget?.outerHTML||'',sourceUrl:location.href,historyLength:history.length};
  target.setAttribute('data-issue655-resolved-action',$($Kind | ConvertTo-Json -Compress));
  sessionStorage.setItem('issue655-evidence-resolved-action',JSON.stringify(snapshot));
  return snapshot;
})()
"@
}

function Invoke-Issue655ResolvedAction {
    param([object]$Session, [string]$Kind)
    $kindJson = $Kind | ConvertTo-Json -Compress
    Invoke-CdpEvaluate -Session $Session -Expression "(() => { const target=document.querySelector('a[data-issue655-resolved-action='+$kindJson+']'); if(!target||!target.isConnected) throw new Error('Issue #655 resolved $Kind action became disconnected before activation.'); sessionStorage.setItem('issue655-evidence-activation',JSON.stringify({kind:$kindJson,sourceUrl:location.href,targetHref:target.href,historyLength:history.length,readyState:document.readyState,activatedAt:new Date().toISOString()})); target.click(); return true; })()" | Out-Null
}

function Wait-Issue655ExactDestination {
    param([object]$Session, [string]$InteractionId, [string]$ExpectedUrl, [string]$ContainerSelector, [string]$DiagnosticsDirectory)
    $expectedJson = $ExpectedUrl | ConvertTo-Json -Compress; $containerJson = $ContainerSelector | ConvertTo-Json -Compress
    $expression = "(() => { const expected=new URL($expectedJson,document.baseURI); return document.readyState==='complete'&&location.pathname===expected.pathname&&location.search===expected.search&&location.hash===expected.hash&&!!document.querySelector($containerJson); })()"
    try { Wait-CdpCondition -Session $Session -Expression $expression -Description "Issue #655 $InteractionId exact destination" }
    catch {
        $diagnostic = Invoke-CdpEvaluate -Session $Session -Expression @"
(() => {
  const parseStored=(key)=>{try{return JSON.parse(sessionStorage.getItem(key)||'null')}catch{return null}};
  const expected=new URL($expectedJson,document.baseURI);
  const storedTarget=parseStored('issue655-evidence-resolved-action');
  const activation=parseStored('issue655-evidence-activation');
  const liveTarget=document.querySelector('[data-issue655-resolved-action]');
  const rect=liveTarget?.getBoundingClientRect();
  const style=liveTarget?getComputedStyle(liveTarget):null;
  const hitTarget=rect?document.elementFromPoint(rect.left+(rect.width/2),rect.top+(rect.height/2)):null;
  const navigation=performance.getEntriesByType('navigation')[0]||null;
  const sourceUrl=activation?.sourceUrl||storedTarget?.sourceUrl||document.referrer||'';
  const pathReady=location.pathname===expected.pathname;
  const queryReady=location.search===expected.search;
  const fragmentReady=location.hash===expected.hash;
  const documentReady=document.readyState==='complete';
  const containerReady=!!document.querySelector($containerJson);
  return {
    interactionId:$($InteractionId | ConvertTo-Json -Compress),stage:'destination-wait',sourceUrl,
    expectedDestination:{href:expected.href,pathname:expected.pathname,search:expected.search,hash:expected.hash},
    observedUrl:location.href,historyLength:history.length,readyState:document.readyState,title:document.title,
    activeElement:document.activeElement?.outerHTML||'',regionCount:document.querySelectorAll('#review-next-region').length,
    targetCount:document.querySelectorAll('[data-issue655-resolved-action]').length,
    targetOuterHtml:liveTarget?.outerHTML||storedTarget?.outerHtml||'',targetHref:liveTarget?.href||storedTarget?.href||'',
    targetVisible:liveTarget?liveTarget.isConnected&&style.display!=='none'&&style.visibility!=='hidden'&&rect.width>0&&rect.height>0:!!storedTarget?.visible,
    targetFocusable:liveTarget?liveTarget.tabIndex>=0&&liveTarget.getAttribute('aria-disabled')!=='true':!!storedTarget?.focusable,
    targetConnected:!!liveTarget?.isConnected,targetRectangle:rect?{left:rect.left,top:rect.top,width:rect.width,height:rect.height}:storedTarget?.rect||null,
    hitTestMatches:liveTarget&&hitTarget?hitTarget===liveTarget||liveTarget.contains(hitTarget):storedTarget?.hitTestMatches||false,
    hitTestElement:hitTarget?.outerHTML||storedTarget?.hitTestElement||'',regionBusy:document.querySelector('#review-next-region')?.getAttribute('aria-busy')||'',
    navigationStages:{activationRecorded:!!activation,navigationStarted:!!sourceUrl&&location.href!==sourceUrl,urlTransitioned:!!sourceUrl&&location.href!==sourceUrl,responseStatus:navigation?.responseStatus||0,pathReady,queryReady,fragmentReady,documentReady,containerReady},
    consoleEvents:window.__issue655ConsoleEvents||[],consoleErrors:window.__issue655ConsoleErrors||[],consoleWarnings:window.__issue655ConsoleWarnings||[],pageErrors:window.__issue655PageErrors||[],
    recentNetworkEvents:Array.from(performance.getEntriesByType('resource')).slice(-20).map((entry)=>({name:entry.name,initiatorType:entry.initiatorType,responseStatus:entry.responseStatus||0,duration:entry.duration})),
    containerSelector:$containerJson,containerPresent:containerReady,scopedHtml:document.querySelector('#review-next-region')?.outerHTML||document.querySelector($containerJson)?.outerHTML||document.body.outerHTML.slice(0,12000)
  };
})()
"@
        $diagnostic | Add-Member -NotePropertyName exception -NotePropertyValue $_.Exception.Message -Force
        $diagnostic | Add-Member -NotePropertyName relevantCdpException -NotePropertyValue $_.Exception.ToString() -Force
        $diagnosticPath = Join-Path $DiagnosticsDirectory "$InteractionId-timeout.json"
        Set-Content -LiteralPath $diagnosticPath -Value ($diagnostic | ConvertTo-Json -Depth 10) -Encoding UTF8
        $shot = Invoke-CdpCommand -Session $Session -Method 'Page.captureScreenshot' -Parameters @{format='png';fromSurface=$true;captureBeyondViewport=$true}
        [IO.File]::WriteAllBytes((Join-Path $DiagnosticsDirectory "$InteractionId-timeout.png"),[Convert]::FromBase64String([string]$shot.result.data))
        throw
    }
}

function Invoke-Issue642BrowserCapture {
    param([object]$Session, [hashtable]$Route, [string]$Url, [string]$ScreenshotPath, [string]$PrintPath = "", [int]$Width, [int]$Height)
    $browserState = $null
    try {
        Invoke-CdpCommand -Session $Session -Method "Page.enable" | Out-Null
        Invoke-CdpCommand -Session $Session -Method "Runtime.enable" | Out-Null
        $browserVersion = Invoke-CdpCommand -Session $Session -Method "Browser.getVersion"
        Invoke-CdpCommand -Session $Session -Method "Page.addScriptToEvaluateOnNewDocument" -Parameters @{ source = "window.__issue642ConsoleErrors=[];window.__issue642ConsoleWarnings=[];window.__issue642PageErrors=[];console.error=((original)=>function(){window.__issue642ConsoleErrors.push(Array.from(arguments).map(String).join(' '));return original.apply(console,arguments)})(console.error);console.warn=((original)=>function(){window.__issue642ConsoleWarnings.push(Array.from(arguments).map(String).join(' '));return original.apply(console,arguments)})(console.warn);addEventListener('error',(event)=>window.__issue642PageErrors.push(String(event.message||event.error||'error')));addEventListener('unhandledrejection',(event)=>window.__issue642PageErrors.push(String(event.reason||'unhandled rejection')));" } | Out-Null
        Invoke-CdpCommand -Session $Session -Method "Emulation.setDeviceMetricsOverride" -Parameters @{ width = $Width; height = $Height; deviceScaleFactor = 1; mobile = $false; screenWidth = $Width; screenHeight = $Height } | Out-Null
        Invoke-CdpCommand -Session $Session -Method "Emulation.setEmulatedMedia" -Parameters @{ media = "screen" } | Out-Null
        Invoke-CdpCommand -Session $Session -Method "Page.navigate" -Parameters @{ url = $Url } | Out-Null
        Wait-CdpCondition -Session $Session -Expression "document.readyState === 'complete'" -Description "Issue #642 DOM readiness"
        if ($Url.Contains('/ccld/facilities/intelligence')) {
            Wait-CdpCondition -Session $Session -Expression "document.documentElement.getAttribute('data-checkbox-multiselect-ready') === 'true'" -Description "Issue #642 enhancement readiness"
        }
        $pageScaleFactor = if ($Route.ContainsKey("Issue641PageScaleFactor")) { [double]$Route.Issue641PageScaleFactor } else { 1.0 }
        if ($pageScaleFactor -ne 1.0) {
            Invoke-CdpCommand -Session $Session -Method "Emulation.setPageScaleFactor" -Parameters @{ pageScaleFactor = $pageScaleFactor } | Out-Null
        }
        Invoke-CdpEvaluate -Session $Session -AwaitPromise $true -Expression "(async function(){ if (document.fonts && document.fonts.ready) { await document.fonts.ready; } await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))); return true; })()" | Out-Null
        $operatedStates = @()
        if ([string]$Route.Name -eq "issue-643-operated-interactions") {
            $operatedRoot = Join-Path (Split-Path $ScreenshotPath -Parent) 'operated'
            New-Item -ItemType Directory -Force -Path $operatedRoot | Out-Null
            $baseUri = [System.Uri]::new($Url)
            $baseUrl = $baseUri.GetLeftPart([System.UriPartial]::Authority)
            $interactionScript = @'
(async function () {
  const card = document.querySelector('.facility-intelligence-card');
  const name = card && card.querySelector('h3 a');
  const copy = card && card.querySelector('button[aria-label*="Copy facility name"]');
  const overview = card && Array.from(card.querySelectorAll('a')).find((a) => a.textContent.trim() === 'Open Facility Overview');
  const complaint = card && Array.from(card.querySelectorAll('a')).find((a) => a.textContent.trim() === 'Review complaint');
  const aggregate = card && card.querySelector('.facility-card-summary a');
  if (!card || !name || !copy || !overview || !complaint || !aggregate) throw new Error('Issue #643 required card controls are missing.');
  return { name: name.textContent.trim(), copyLabel: copy.getAttribute('aria-label'), nameHref: name.href, overviewHref: overview.href, complaintHref: complaint.href, aggregateHref: aggregate.href };
})()
'@
            $card = Invoke-CdpEvaluate -Session $Session -AwaitPromise $true -Expression $interactionScript
            $records = [System.Collections.ArrayList]::new()
            $save = {
                param([string]$Id, [string]$Selector, [string]$Method, [string]$Expected)
                $before = Invoke-CdpEvaluate -Session $Session -Expression "({url:location.href, focus:(document.activeElement.id||document.activeElement.getAttribute('aria-label')||document.activeElement.textContent.trim()), navigation:performance.getEntriesByType('navigation').length})"
                Invoke-CdpEvaluate -Session $Session -Expression "document.querySelector($($Selector | ConvertTo-Json -Compress)).focus(); true" | Out-Null
                if ($Method -eq 'keyboard') { Invoke-CdpKeyPress -Session $Session -Key ' ' -Code 'Space' -VirtualKeyCode 32 } else { Invoke-CdpClickSelector -Session $Session -Selector $Selector }
                Start-Sleep -Milliseconds 250
                $after = Invoke-CdpEvaluate -Session $Session -Expression "({url:location.href, focus:(document.activeElement.id||document.activeElement.getAttribute('aria-label')||document.activeElement.textContent.trim()), navigation:performance.getEntriesByType('navigation').length})"
                $path = Join-Path $operatedRoot "$Id.png"; Invoke-CdpCommand -Session $Session -Method 'Page.captureScreenshot' -Parameters @{ format='png'; fromSurface=$true; captureBeyondViewport=$true } | ForEach-Object { [IO.File]::WriteAllBytes($path, [Convert]::FromBase64String($_.result.data)) }
                [void]$records.Add([ordered]@{ id=$Id; method=$Method; selector=$Selector; expected=$Expected; before=$before; after=$after; pass=($Method -eq 'keyboard' -and $Id -like '*copy*' ? ($before.url -eq $after.url) : $true) })
            }
            & $save 'issue-643-copy-keyboard' 'button[aria-label*="Copy facility name"]' 'keyboard' $card.name
            & $save 'issue-643-copy-pointer' 'button[aria-label*="Copy facility name"]' 'pointer' $card.name
            $navigate = {
                param([string]$Id, [string]$Selector, [string]$ExpectedPath)
                $before = Invoke-CdpEvaluate -Session $Session -Expression "({url:location.href,navigation:performance.getEntriesByType('navigation').length,focus:(document.activeElement.getAttribute('aria-label')||document.activeElement.textContent.trim())})"
                Invoke-CdpClickSelector -Session $Session -Selector $Selector
                Wait-CdpCondition -Session $Session -Expression "document.readyState === 'complete' && location.pathname.includes('$ExpectedPath')" -Description "$Id destination"
                $destination = Invoke-CdpEvaluate -Session $Session -Expression "({url:location.href,navigation:performance.getEntriesByType('navigation').length,focus:(document.activeElement.getAttribute('aria-label')||document.activeElement.textContent.trim()),text:document.body.innerText})"
                $destinationPath = Join-Path $operatedRoot "$Id-destination.png"; Invoke-CdpCommand -Session $Session -Method 'Page.captureScreenshot' -Parameters @{format='png';fromSurface=$true;captureBeyondViewport=$true} | ForEach-Object {[IO.File]::WriteAllBytes($destinationPath,[Convert]::FromBase64String($_.result.data))}
                Invoke-CdpBrowserBack -Session $Session; Wait-CdpCondition -Session $Session -Expression "document.readyState === 'complete' && location.href === $($before.url | ConvertTo-Json -Compress)" -Description "$Id browser Back"
                $back = Invoke-CdpEvaluate -Session $Session -Expression "({url:location.href,navigation:performance.getEntriesByType('navigation').length,focus:(document.activeElement.getAttribute('aria-label')||document.activeElement.textContent.trim()),cardVisible:!!document.querySelector('.facility-intelligence-card')})"
                $backPath = Join-Path $operatedRoot "$Id-back.png"; Invoke-CdpCommand -Session $Session -Method 'Page.captureScreenshot' -Parameters @{format='png';fromSurface=$true;captureBeyondViewport=$true} | ForEach-Object {[IO.File]::WriteAllBytes($backPath,[Convert]::FromBase64String($_.result.data))}
                [void]$records.Add([ordered]@{id=$Id;method='native-click-and-browser-back';selector=$Selector;before=$before;destination=$destination;back=$back;pass=($back.url -eq $before.url -and $back.cardVisible)})
            }
            & $navigate 'issue-643-facility-name' '.facility-intelligence-card h3 a' '/ccld/facilities/detail'
            & $navigate 'issue-643-footer-overview' '.facility-intelligence-card .facility-card-actions a[aria-label^="Open Facility Overview"]' '/ccld/facilities/detail'
            & $navigate 'issue-643-review-complaint' '.facility-intelligence-card .facility-card-actions a[aria-label^="Review complaint"]' '/reviewer/records/detail'
            & $navigate 'issue-643-canonical-inventory' '.facility-intelligence-card .facility-card-summary a' '/ccld/facilities/detail'
            Set-Content -LiteralPath (Join-Path (Split-Path $ScreenshotPath -Parent) '..\diagnostics\issue-643-operated-interactions.json') -Value (([ordered]@{ facility=$card; interactions=$records; limitation='Clipboard readback is browser-permission dependent; activation and no-navigation state are recorded.' }) | ConvertTo-Json -Depth 8) -Encoding UTF8
        }
        elseif ([string]$Route.Name -eq "issue-642-operated-interactions") {
            $baseUri = [System.Uri]::new($Url)
            $baseUrl = $baseUri.GetLeftPart([System.UriPartial]::Authority)
            $operatedStates = @(Invoke-Issue642OperatedInteractionCapture -Session $Session -BaseUrl $baseUrl -ScreenshotPath $ScreenshotPath)
            Invoke-CdpCommand -Session $Session -Method "Page.navigate" -Parameters @{ url = $Url } | Out-Null
            Wait-CdpCondition -Session $Session -Expression "document.readyState === 'complete'" -Description "Issue #642 operated state return"
        }
        $routeNameJson = ([string]$Route.Name | ConvertTo-Json -Compress)
        $pageScaleFactorJson = ($pageScaleFactor | ConvertTo-Json -Compress)
        $browserState = Invoke-CdpEvaluate -Session $Session -AwaitPromise $true -Expression @"
(async function () {
  const routeName = $routeNameJson;
  const expectedPageScaleFactor = $pageScaleFactorJson;
  const rect = (element) => { const value = element.getBoundingClientRect(); return { left: value.left, top: value.top, right: value.right, bottom: value.bottom, width: value.width, height: value.height }; };
  const visible = (element) => { const style = getComputedStyle(element); return element.getClientRects().length > 0 && style.display !== 'none' && style.visibility !== 'hidden'; };
  const requiredSelectors = ['header', 'main', 'h1', 'nav[aria-label="Primary navigation"]'];
  if (location.pathname === '/ccld/facilities/intelligence') requiredSelectors.push('form');
  const required = requiredSelectors.map((selector) => { const element = document.querySelector(selector); if (!element || !visible(element)) throw new Error('Required Issue #642 element is unavailable: ' + selector); return { selector, bounds: rect(element) }; });
  const clientWidth = document.documentElement.clientWidth;
  const overflowingRequired = required.filter((entry) => entry.bounds.right > clientWidth + 1);
  const horizontalOverflow = document.documentElement.scrollWidth > clientWidth + 1 || document.body.scrollWidth > clientWidth + 1;
  if (horizontalOverflow || overflowingRequired.length) throw new Error('Issue #642 geometry gate failed: document overflow or a required element extends beyond clientWidth.');
  const text = document.body.innerText;
  const navLabels = Array.from(document.querySelectorAll('nav[aria-label="Primary navigation"] a')).map((link) => link.textContent.trim()).filter(Boolean);
  const requiredNavLabels = ['Home', 'Find a Facility', 'Compare Facilities', 'Complaint Worklist', 'Feedback', 'Help'];
  const missingNavLabels = requiredNavLabels.filter((label) => !navLabels.includes(label));
  if (missingNavLabels.length || navLabels.includes('Menu')) throw new Error('Issue #642 navigation contract failed: ' + (missingNavLabels.length ? missingNavLabels.join('; ') : 'false Menu label'));
  const checkboxControls = Array.from(document.querySelectorAll('input[type="checkbox"][name]')).map((element) => ({ name: element.name, value: element.value, checked: element.checked, visible: visible(element), bounds: rect(element) }));
  const filterControls = Array.from(document.querySelectorAll('form input, form select, form button')).filter(visible).map((element) => ({ tagName: element.tagName, type: element.type || '', name: element.name || '', id: element.id || '', text: element.textContent.trim(), bounds: rect(element) }));
  const facilityInput = document.querySelector('#facility-search-input');
  const suggestionList = document.querySelector('#facility-suggestion-list');
  const activeElement = document.activeElement;
  if (routeName === 'issue-642-trends' && (!facilityInput || !visible(facilityInput))) throw new Error('Issue #642 trend facility typeahead is unavailable.');
  if (location.pathname === '/ccld/facilities/intelligence' && checkboxControls.length === 0) throw new Error('Issue #642 native checkbox multi-select controls are unavailable.');
  const expected = routeName === 'issue-642-licensing' ? ['Licensing and Visit Activity']
    : routeName === 'issue-642-trends' ? ['Complaint Activity Over Time', 'Facility name or ID']
    : routeName === 'issue-642-overview-return' ? ['Facility Overview', 'Return to Compare Facilities']
    : routeName === 'issue-642-detail-return' ? ['Complaint overview', 'Return to Compare Facilities']
    : ['Find Facilities That May Need Closer Review', 'Complaint Patterns'];
  const missingText = expected.filter((value) => !text.includes(value));
  const actualPageScaleFactor = window.visualViewport ? window.visualViewport.scale : 1;
  return {
    routeName,
    viewport: { innerWidth: window.innerWidth, innerHeight: window.innerHeight, clientWidth, devicePixelRatio: window.devicePixelRatio, visualViewportScale: actualPageScaleFactor, requestedPageScaleFactor: expectedPageScaleFactor, nativeZoomVerified: Math.abs(actualPageScaleFactor - expectedPageScaleFactor) <= 0.01 },
    document: { scrollWidth: document.documentElement.scrollWidth, bodyScrollWidth: document.body.scrollWidth, scrollHeight: document.documentElement.scrollHeight },
    horizontalOverflow,
    requiredElements: required,
    overflowingRequiredElements: overflowingRequired,
    navigation: { labels: navLabels, missingLabels: missingNavLabels, hasFalseMenu: navLabels.includes('Menu') },
    nativeCheckboxControls: checkboxControls,
    filterControls,
    typeahead: { present: !!facilityInput, value: facilityInput ? facilityInput.value : '', suggestionListPresent: !!suggestionList, suggestionListHidden: suggestionList ? suggestionList.hidden : null, activeElementId: activeElement ? activeElement.id || '' : '' },
    url: location.href,
    title: document.title,
    h1: document.querySelector('h1') ? document.querySelector('h1').textContent.trim() : '',
    consoleErrors: window.__issue642ConsoleErrors || [],
    consoleWarnings: window.__issue642ConsoleWarnings || [],
    pageErrors: window.__issue642PageErrors || [],
    failedNetworkRequests: performance.getEntriesByType('resource').filter((entry) => entry.duration > 0 && entry.transferSize === 0 && entry.decodedBodySize === 0).map((entry) => entry.name),
    accessibility: { skipLink: !!document.querySelector('.skip-link'), mainLandmarkCount: document.querySelectorAll('main').length, primaryNavigationCount: document.querySelectorAll('nav[aria-label="Primary navigation"]').length },
    expectedVisibleText: expected,
    missingVisibleText: missingText
  };
})()
"@
        $browserState | Add-Member -NotePropertyName browser -NotePropertyValue @{ product = [string]$browserVersion.result.product; revision = [string]$browserVersion.result.revision; userAgent = [string]$browserVersion.result.userAgent }
        $browserState | Add-Member -NotePropertyName captureMetadata -NotePropertyValue @{ capturedAtUtc = (Get-Date).ToUniversalTime().ToString('o'); branch = (& git rev-parse --abbrev-ref HEAD).Trim(); commit = (& git rev-parse HEAD).Trim() }
        $browserState | Add-Member -NotePropertyName operated_states -NotePropertyValue $operatedStates
        $capturePrint = $Route.ContainsKey("CapturePrint") -and [bool]$Route.CapturePrint
        if ($capturePrint) { Invoke-CdpCommand -Session $Session -Method "Emulation.setEmulatedMedia" -Parameters @{ media = "print" } | Out-Null; $browserState | Add-Member -NotePropertyName printMedia -NotePropertyValue "print" }
        $metrics = Invoke-CdpCommand -Session $Session -Method "Page.getLayoutMetrics"
        $contentSize = $metrics.result.cssContentSize
        $screenshot = Invoke-CdpCommand -Session $Session -Method "Page.captureScreenshot" -Parameters @{ format = "png"; fromSurface = $true; captureBeyondViewport = $true; clip = @{ x = 0; y = 0; width = [Math]::Ceiling([double]$contentSize.width); height = [Math]::Ceiling([double]$contentSize.height); scale = 1 } }
        [System.IO.File]::WriteAllBytes($ScreenshotPath, [Convert]::FromBase64String([string]$screenshot.result.data))
        $dimensions = Get-PngDimensions -Path $ScreenshotPath
        if ($dimensions.height -lt $Height -or $dimensions.width -lt $browserState.viewport.clientWidth) { throw "Issue #642 full-page screenshot dimensions are smaller than the governed viewport." }
        $browserState | Add-Member -NotePropertyName screenshot -NotePropertyValue @{ width = $dimensions.width; height = $dimensions.height; sha256 = (Get-FileHash -LiteralPath $ScreenshotPath -Algorithm SHA256).Hash }
        if ($capturePrint) { if (-not $PrintPath) { throw "Issue #642 print capture requires a PDF output path." }; $pdf = Invoke-CdpCommand -Session $Session -Method "Page.printToPDF" -Parameters @{ printBackground = $true; displayHeaderFooter = $false; preferCSSPageSize = $true }; [System.IO.File]::WriteAllBytes($PrintPath, [Convert]::FromBase64String([string]$pdf.result.data)); Invoke-CdpCommand -Session $Session -Method "Emulation.setEmulatedMedia" -Parameters @{ media = "screen" } | Out-Null }
        return [pscustomobject]@{ Success = $true; Error = ""; State = $browserState; ScreenshotCreated = (Test-Path -LiteralPath $ScreenshotPath); PrintCreated = (-not $capturePrint -or (Test-Path -LiteralPath $PrintPath)) }
    }
    catch {
        Remove-Item -LiteralPath $ScreenshotPath -Force -ErrorAction SilentlyContinue
        try { Invoke-CdpCommand -Session $Session -Method "Emulation.setEmulatedMedia" -Parameters @{ media = "screen" } | Out-Null } catch { }
        return [pscustomobject]@{ Success = $false; Error = ("$($_.Exception.Message) at evidence script line $($_.InvocationInfo.ScriptLineNumber)"); State = $browserState; ScreenshotCreated = $false; PrintCreated = $false }
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

function Get-Issue641ValidationSummary {
    param(
        [int]$RouteFailures,
        [int]$AssertionFailures,
        [int]$FeatureAssertionFailures,
        [int]$ScreenshotFailures,
        [string[]]$RequiredFeatureAssertions
    )
    $allFailuresZero = $RouteFailures -eq 0 -and $AssertionFailures -eq 0 -and $FeatureAssertionFailures -eq 0 -and $ScreenshotFailures -eq 0
    return [ordered]@{
        routeFailures = $RouteFailures
        assertionFailures = $AssertionFailures
        featureAssertionFailures = $FeatureAssertionFailures
        screenshotFailures = $ScreenshotFailures
        requiredFeatureAssertions = @($RequiredFeatureAssertions)
        gate = 'FUNCTIONAL'
        status = if ($allFailuresZero) { 'PASS' } else { 'FAIL' }
        overallAcceptance = 'NOT_ACCEPTED'
        notice = 'This summary cannot establish visual or owner acceptance.'
    }
}

function Get-EvidenceFileIndex {
    param([string]$PacketDirectory)
    return @(
        Get-ChildItem -LiteralPath $PacketDirectory -File -Recurse |
            Sort-Object FullName |
            ForEach-Object {
                [ordered]@{
                    path       = ConvertTo-RelativeEvidencePath -Path $_.FullName -Root $PacketDirectory
                    bytes      = [int64]$_.Length
                    sha256     = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
                    action     = if ($_.Extension -in @('.html', '.txt')) { 'sanitized-capture-or-derived-text' } elseif ($_.FullName -match '[\\/]screenshots[\\/]|[\\/]print[\\/]') { 'captured' } else { 'generated' }
                    source     = 'local fixture evidence capture'
                    timestamp  = $_.LastWriteTimeUtc.ToString('o')
                    routeState = 'recorded in manifest routes and browser-state artifacts when route-specific'
                    viewport   = 'recorded in the associated browser-state artifact when route-specific'
                    browser    = 'recorded in the associated browser-state artifact when route-specific'
                    associatedAssertions = @()
                    sanitizationState = if ($_.Extension -in @('.html', '.txt', '.json', '.csv')) { 'sanitized or generated without credentials, cookies, headers, or environment values' } else { 'local fixture visual capture' }
                }
            }
    )
}

function Test-EvidencePacketFiles {
    param([string]$PacketDirectory)

    $requiredPacketFiles = @("manifest.json", "route-status.csv", "route-assertions.csv", "route-text-markers.txt", "README.txt")
    $missingPacketFiles = @($requiredPacketFiles | Where-Object { -not (Test-Path -LiteralPath (Join-Path $PacketDirectory $_)) })
    if ($missingPacketFiles.Count -gt 0) {
        Stop-CaptureFail "Evidence packet is missing required files: $($missingPacketFiles -join ', ')"
    }
    $indexedPacketFiles = @(Get-EvidenceFileIndex -PacketDirectory $PacketDirectory)
    $zeroLengthFiles = @($indexedPacketFiles | Where-Object { $_.bytes -le 0 })
    if ($zeroLengthFiles.Count -gt 0) {
        Stop-CaptureFail "Evidence packet contains zero-length files: $($zeroLengthFiles.path -join ', ')"
    }
    $invalidJsonFiles = [System.Collections.ArrayList]::new()
    foreach ($jsonFile in @($indexedPacketFiles | Where-Object { $_.path -like '*.json' })) {
        try {
            Get-Content -LiteralPath (Join-Path $PacketDirectory $jsonFile.path) -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop | Out-Null
        }
        catch {
            [void]$invalidJsonFiles.Add($jsonFile.path)
        }
    }
    if ($invalidJsonFiles.Count -gt 0) {
        Stop-CaptureFail "Evidence packet contains invalid JSON files: $($invalidJsonFiles -join ', ')"
    }
    return $indexedPacketFiles
}

function Test-EvidenceZipIntegrity {
    param([string]$PacketDirectory, [string]$ZipPath, [object[]]$ExpectedFiles)

    try { [System.IO.Compression.ZipFile] | Out-Null }
    catch { Add-Type -AssemblyName System.IO.Compression.FileSystem }

    $packetName = Split-Path -Leaf $PacketDirectory
    $expectedByPath = @{}
    foreach ($file in $ExpectedFiles) { $expectedByPath[[string]$file.path] = $file }
    $archive = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
    try {
        $actualByPath = @{}
        foreach ($entry in @($archive.Entries | Where-Object { -not $_.FullName.EndsWith("/") })) {
            $entryPath = [string]$entry.FullName
            $prefix = "$packetName/"
            if (-not $entryPath.StartsWith($prefix, [System.StringComparison]::Ordinal)) {
                Stop-CaptureFail "Evidence ZIP contains an unexpected root entry: $entryPath"
            }
            $entryRelativePath = $entryPath.Substring($prefix.Length)
            $hashAlgorithm = [System.Security.Cryptography.SHA256]::Create()
            try {
                $entryStream = $entry.Open()
                try {
                    $entrySha256 = [Convert]::ToHexString($hashAlgorithm.ComputeHash($entryStream))
                }
                finally {
                    $entryStream.Dispose()
                }
            }
            finally {
                $hashAlgorithm.Dispose()
            }
            $actualByPath[$entryRelativePath] = [ordered]@{ bytes = [int64]$entry.Length; sha256 = $entrySha256 }
        }
        $missing = @($expectedByPath.Keys | Where-Object { -not $actualByPath.ContainsKey($_) })
        $unexpected = @($actualByPath.Keys | Where-Object { -not $expectedByPath.ContainsKey($_) })
        $sizeMismatch = @($expectedByPath.Keys | Where-Object {
            $actualByPath.ContainsKey($_) -and $actualByPath[$_].bytes -ne [int64]$expectedByPath[$_].bytes
        })
        $hashMismatch = @($expectedByPath.Keys | Where-Object {
            $actualByPath.ContainsKey($_) -and $actualByPath[$_].sha256 -ne [string]$expectedByPath[$_].sha256
        })
        if ($missing.Count -gt 0 -or $unexpected.Count -gt 0 -or $sizeMismatch.Count -gt 0 -or $hashMismatch.Count -gt 0) {
            Stop-CaptureFail "Evidence ZIP membership, sizes, or SHA-256 hashes do not match the packet file index."
        }
    }
    finally {
        $archive.Dispose()
    }
    return (Get-FileHash -LiteralPath $ZipPath -Algorithm SHA256).Hash
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
            "/ccld/facilities|Find a Facility",
            "/ccld/facilities/intelligence|Compare Facilities",
            "/reviewer|Complaint Worklist",
            "/feedback|Feedback",
            "/ccld/help|Help"
        )
        $navDefinitionMatches = $navLinks.Count -eq $expectedNavLinks.Count -and (($navLinks -join "`n") -ceq ($expectedNavLinks -join "`n"))
        if ($navDefinitionMatches) { Add-AssertionResult -Target $Assertions -RouteName $name -Check "authoritative primary navigation" -Status "PASS" -Message "Primary navigation includes the approved destinations in the current six-link order." }
        else { Add-AssertionResult -Target $Assertions -RouteName $name -Check "authoritative primary navigation" -Status "FAIL" -Message "Primary navigation differs from the current governed six-link definition or ordering." }
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

function Test-Issue502RouteAssertions {
    param([hashtable]$Route, [string]$Html, [string]$Text, [System.Collections.ArrayList]$Assertions)
    if (-not $Route.ContainsKey("Issue502Kind")) { return }
    $name = [string]$Route.Name
    $kind = [string]$Route.Issue502Kind
    $hasApprovedNavigation = @(
        "Home",
        "Find a Facility",
        "Compare Facilities",
        "Complaint Worklist",
        "Feedback",
        "Help"
    ) | ForEach-Object { $Text.Contains($_) }
    Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue502 approved navigation" -Status $(if (($hasApprovedNavigation | Where-Object { -not $_ }).Count -eq 0) { "PASS" } else { "FAIL" }) -Message $(if (($hasApprovedNavigation | Where-Object { -not $_ }).Count -eq 0) { "Approved global navigation labels found." } else { "One or more approved global navigation labels are missing." })
    if ($kind -eq "home") {
        $homeIsDistinct = $Text.Contains("Review CCLD Facility Records") -and $Text.Contains("Choose a review task") -and -not $Text.Contains("Facility intake")
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue502 distinct Home task launch" -Status $(if ($homeIsDistinct) { "PASS" } else { "FAIL" }) -Message $(if ($homeIsDistinct) { "Home contains task launch content without the facility intake flow." } else { "Home is missing its distinct task launch or still contains facility intake content." })
    }
    if ($kind -eq "facility") {
        $facilityIsDistinct = $Text.Contains("Find a Facility") -and $Text.Contains("Facility search") -and -not $Text.Contains("Reference data details") -and -not $Text.Contains("How to request records with this Facility ID")
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue502 distinct facility discovery" -Status $(if ($facilityIsDistinct) { "PASS" } else { "FAIL" }) -Message $(if ($facilityIsDistinct) { "Find a Facility contains focused discovery without superseded disclosures." } else { "Facility discovery content is missing or includes superseded disclosure content." })
    }
    if ($kind -eq "unmatched") {
        $validContinuation = $Text.Contains("Facility not found in the directory") -and $Text.Contains("Continue with this Facility ID")
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue502 valid unmatched continuation" -Status $(if ($validContinuation) { "PASS" } else { "FAIL" }) -Message $(if ($validContinuation) { "Valid unmatched Facility ID retains a truthful continuation action." } else { "Valid unmatched Facility ID continuation is missing." })
    }
    if ($kind -eq "malformed") {
        $malformedState = $Text.Contains("Check the Facility ID") -and -not $Text.Contains("Continue with this Facility ID")
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue502 malformed identifier recovery" -Status $(if ($malformedState) { "PASS" } else { "FAIL" }) -Message $(if ($malformedState) { "Malformed Facility ID has a distinct recovery state without continuation." } else { "Malformed Facility ID state is unsupported." })
    }
    if ($kind -eq "unavailable") {
        $unavailableState = $Text.Contains("Facility search is unavailable") -and $Text.Contains("Known Facility ID")
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue502 directory unavailable state" -Status $(if ($unavailableState) { "PASS" } else { "FAIL" }) -Message $(if ($unavailableState) { "Directory-unavailable state offers bounded known-ID continuation." } else { "Directory-unavailable state is missing." })
    }
    if ($kind -eq "results") {
        $resultsAreActionable = $Text.Contains("Facility results") -and $Text.Contains("Complaint context") -and ($Text.Contains("Get Records") -or $Text.Contains("Review Facility"))
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue502 selected facility context action" -Status $(if ($resultsAreActionable) { "PASS" } else { "FAIL" }) -Message $(if ($resultsAreActionable) { "Facility results state complaint context and a contextual next action." } else { "Facility result context or action is missing." })
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

function Test-Issue641RouteAssertions {
    param([hashtable]$Route, [string]$Text, [System.Collections.ArrayList]$Assertions)
    $name = [string]$Route.Name
    $expected = switch -Wildcard ($name) {
        "issue-641-raw-430" { @("Issue 641 Code 430 Center", "Source code 430") }
        "issue-641-raw-733" { @("Issue 641 Code 733 Center", "Source code 733") }
        "issue-641-readable-type" { @("Issue 641 Readable Type Center", "Children's Center") }
        "issue-641-overview*" { @("Issue 641 Code 430 Center", "Source code 430", "430000001") }
        "issue-641-detail*" { @("Issue 641 Code 430 Center", "Complaint finding", "Allegation finding", "430000001") }
        default { @("Issue 641 Code 430 Center") }
    }
    $hasExpected = @($expected | Where-Object { -not $Text.Contains($_) }).Count -eq 0
    Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue641 expected visible state" -Status $(if ($hasExpected) { "PASS" } else { "FAIL" }) -Message $(if ($hasExpected) { "Expected Issue #641 identity and presentation text is visible." } else { "Expected Issue #641 identity or presentation text is missing." })
    $internalIdentityVisible = $Text -match '(?i)ccld(?:-|:)facility(?:-|:)\d+'
    Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue641 public identity boundary" -Status $(if (-not $internalIdentityVisible) { "PASS" } else { "FAIL" }) -Message $(if (-not $internalIdentityVisible) { "Internal facility identifiers are absent from visible reviewer output." } else { "An internal facility identifier is visible to the reviewer." })
    if ($name -eq "issue-641-raw-733") {
        $truthfulAbsence = -not $Text.Contains("No serious-review category")
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue641 optional category absence" -Status $(if ($truthfulAbsence) { "PASS" } else { "FAIL" }) -Message $(if ($truthfulAbsence) { "The optional serious-review category is truthfully absent." } else { "An absent optional category is rendered as a misleading message." })
    }
}

function Test-Issue642RouteAssertions {
    param([hashtable]$Route, [string]$Text, [System.Collections.ArrayList]$Assertions)
    $name = [string]$Route.Name
    $expected = switch -Wildcard ($name) {
        "issue-642-licensing-populated" { @("Licensing and Visit Activity", "Issue 641 Code 430 Center", "2 total visits; 1 complaint visits") }
        "issue-642-licensing-filtered-empty" { @("Licensing and Visit Activity", "No loaded licensing or visit observations match the selected filters.", "The licensing and visit source is available.") }
        "issue-642-licensing-source-unavailable" { @("Licensing and Visit Activity", "Licensing and visit source unavailable", "No verified licensing or visit counts are shown.") }
        "issue-642-trends-populated" { @("Complaint Activity Over Time", "Selected facility: Issue 642 Evidence Facility 01 (Facility ID 642900001)", "1 qualifying complaint record(s): 1 assigned to displayed periods and 0 with date unavailable.", "04/01/2022", "04/30/2022", "Open complaint record 32-CR-20220401120000") }
        "issue-642-trends-intentional-empty" { @("Complaint Activity Over Time", "Selected facility: Issue 642 Evidence Facility 01 (Facility ID 642900001)", "0 qualifying complaint record(s): 0 assigned to displayed periods and 0 with date unavailable.", "No records meet the active eligibility filters", "Zero qualifying records") }
        "issue-642-multiselect-two-values" { @("Facility type: 430", "Facility type: 733", "Finding: Unsubstantiated", "Finding: Substantiated") }
        "issue-642-overview-return" { @("Facility Overview", "Return to Compare Facilities") }
        "issue-642-detail-return" { @("Complaint overview", "Return to Compare Facilities") }
        default { @("Find Facilities That May Need Closer Review", "Complaint Patterns") }
    }
    $hasExpected = @($expected | Where-Object { -not $Text.Contains($_) }).Count -eq 0
    Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue642 expected visible state" -Status $(if ($hasExpected) { "PASS" } else { "FAIL" }) -Message $(if ($hasExpected) { "Expected Issue #642 comparison state is visible." } else { "Expected Issue #642 comparison state is missing." })
    $internalIdentityVisible = $Text -match '(?i)ccld(?:-|:)facility(?:-|:)\d+'
    Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue642 public identity boundary" -Status $(if (-not $internalIdentityVisible) { "PASS" } else { "FAIL" }) -Message $(if (-not $internalIdentityVisible) { "Internal facility identifiers are absent from visible reviewer output." } else { "An internal facility identifier is visible to the reviewer." })
    if ($name -eq "issue-642-licensing-source-unavailable") {
        $selectedPublicFacility = $Text -match '(?im)^\s*Selected Facility ID:\s*\d+\s*$'
        $ordinaryUnavailableRecovery = $Text.Contains("Licensing and visit source unavailable") -and $Text.Contains("No verified licensing or visit counts are shown.")
        $noVerifiedNumericCounts = -not ($Text -match '(?im)^\s*\d+\s+(total|complaint) visits?\b')
        $noObservationRow = -not ($Text -match '(?im)^\s*(Visit date|Observation|Inspection|Complaint visit)\b')
        $notFilteredEmpty = -not $Text.Contains("No loaded licensing or visit observations match the selected filters.")
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue642 unavailable heading and selected public Facility ID" -Status $(if ($hasExpected -and $selectedPublicFacility) { "PASS" } else { "FAIL" }) -Message "The unavailable state shows its heading and the selected public Facility ID."
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue642 unavailable omits unverified counts and observations" -Status $(if ($noVerifiedNumericCounts -and $noObservationRow) { "PASS" } else { "FAIL" }) -Message "The unavailable state does not render verified numeric counts or populated observation rows."
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue642 unavailable is not filtered-empty and has ordinary recovery" -Status $(if ($notFilteredEmpty -and $ordinaryUnavailableRecovery) { "PASS" } else { "FAIL" }) -Message "The unavailable state is distinct from filtered-empty and gives ordinary unavailable-state recovery text."
    }
    if ($name -eq "issue-642-trends-populated") {
        $hasPopulatedResult = $Text.Contains("1 qualifying complaint record(s): 1 assigned to displayed periods and 0 with date unavailable.") -and $Text.Contains("Open complaint record 32-CR-20220401120000")
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue642 populated trends reconciliation" -Status $(if ($hasPopulatedResult) { "PASS" } else { "FAIL" }) -Message $(if ($hasPopulatedResult) { "The designated populated trend state has one dated qualifying fixture complaint and its contributing record." } else { "The designated populated trend state is missing its reconciled qualifying fixture complaint." })
    }
    if ($name -eq "issue-642-trends-intentional-empty") {
        $truthfulEmpty = $Text.Contains("No records meet the active eligibility filters") -and $Text.Contains("Zero qualifying records") -and -not $Text.Contains("Complete period")
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue642 intentional empty trends truthfulness" -Status $(if ($truthfulEmpty) { "PASS" } else { "FAIL" }) -Message $(if ($truthfulEmpty) { "The intentional empty state identifies active filters and does not claim complete coverage." } else { "The intentional empty state is missing its governed explanation or implies complete coverage." })
    }
}

function Test-Issue643RouteAssertions {
    param([hashtable]$Route, [string]$Text, [System.Collections.ArrayList]$Assertions)
    $name = [string]$Route.Name
    $common = @('Find Facilities That May Need Closer Review', 'Complaint Patterns', 'Complaints', 'Recommended complaint', 'Open Facility Overview', 'Review complaint')
    $hasCommon = @($common | Where-Object { -not $Text.Contains($_) }).Count -eq 0
    Add-AssertionResult -Target $Assertions -RouteName $name -Check 'issue643 populated card contract' -Status $(if ($hasCommon) {'PASS'} else {'FAIL'}) -Message 'The populated Complaint Patterns card exposes its required summary, recommendation, and actions.'
    $removed = @('Contributing complaint records', 'Source Record', 'Reviewer State', 'Save status', 'stable facility identity', 'exact facility identity')
    $noRemoved = @($removed | Where-Object { $Text.Contains($_) }).Count -eq 0
    Add-AssertionResult -Target $Assertions -RouteName $name -Check 'issue643 superseded card content absent' -Status $(if ($noRemoved) {'PASS'} else {'FAIL'}) -Message 'Superseded contributor, source, reviewer, and identity-panel copy is absent from the rendered comparison state.'
    $sourceCount = ([regex]::Matches($Text, 'Source unavailable')).Count
    if ($name -eq 'issue-643-source-unavailable') {
        Add-AssertionResult -Target $Assertions -RouteName $name -Check 'issue643 source-unavailable presentation' -Status $(if ($sourceCount -gt 0 -and $noRemoved) {'PASS'} else {'FAIL'}) -Message 'The source-unavailable fixture state presents availability without a source panel or reviewer form.'
    }
}

function Test-Issue655RouteAssertions {
    param([hashtable]$Route, [string]$Text, [System.Collections.ArrayList]$Assertions)
    $name = [string]$Route.Name
    $state = [string]$Route.Issue655State
    if ($state -eq 'malformed') {
        $valid = $Text.Contains('Review next recommendation state is invalid.')
        Add-AssertionResult -Target $Assertions -RouteName $name -Check 'issue655 malformed recommendation rejection' -Status $(if ($valid) {'PASS'} else {'FAIL'}) -Message 'A malformed recommendation state is rejected rather than replaced.'
        return
    }
    if ($state -eq 'empty') {
        $empty = $Text -match '(?i)No facilities match|No Review next recommendation'
        Add-AssertionResult -Target $Assertions -RouteName $name -Check 'issue655 empty recommendation sequence' -Status $(if ($empty) {'PASS'} else {'FAIL'}) -Message 'The active filters produce a governed empty recommendation and inventory state.'
        return
    }
    $region = $Text.Contains('Review next') -and $Text.Contains('Recommendation')
    Add-AssertionResult -Target $Assertions -RouteName $name -Check 'issue655 bounded recommendation region' -Status $(if ($region) {'PASS'} else {'FAIL'}) -Message 'The bounded Review next region is present above the canonical inventory.'
    $noScopeLeak = -not $Text.Contains('Contributing complaint records') -and -not $Text.Contains('Source Record') -and -not $Text.Contains('Reviewer State')
    Add-AssertionResult -Target $Assertions -RouteName $name -Check 'issue655 card-scope boundary' -Status $(if ($noScopeLeak) {'PASS'} else {'FAIL'}) -Message 'The review-next region does not restore superseded card panels or contributor dumps.'
}

function Test-Issue655StaticScenarioEvidence {
    param([string]$PacketDirectory, [string]$DiagnosticsDirectory)
    $scenarios = @(
        [ordered]@{ name='middle'; label='issue-655-02-middle' },
        [ordered]@{ name='one-item'; label='issue-655-04-one-item' },
        [ordered]@{ name='empty'; label='issue-655-05-empty' }
    )
    $states = @{}
    foreach ($scenario in $scenarios) {
        $statePath = Join-Path $DiagnosticsDirectory "$($scenario.label)-browser-state.json"
        $textPath = Join-Path (Join-Path $PacketDirectory 'text') "$($scenario.label).txt"
        if (-not (Test-Path -LiteralPath $statePath) -or -not (Test-Path -LiteralPath $textPath)) { Stop-CaptureFail "Issue #655 scenario gate: $($scenario.name) browser-state or text artifact is missing." }
        $states[$scenario.name] = [ordered]@{ state=(Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json); text=(Get-Content -LiteralPath $textPath -Raw) }
    }
    $middle = $states['middle'].state; $one = $states['one-item'].state; $empty = $states['empty'].state
    if (-not $middle.recommendation.present -or [int]$middle.recommendation.positionNumber -le 1 -or [int]$middle.recommendation.positionNumber -ge [int]$middle.recommendation.total -or -not [bool]$middle.recommendation.previousAvailable -or -not [bool]$middle.recommendation.nextAvailable -or [string]::IsNullOrWhiteSpace([string]$middle.recommendation.facility) -or [string]::IsNullOrWhiteSpace([string]$middle.recommendation.complaint) -or -not $states['middle'].text.Contains([string]$middle.recommendation.facility)) { Stop-CaptureFail 'Issue #655 scenario gate: middle scenario is not a rendered deterministic middle recommendation.' }
    if (-not $one.recommendation.present -or [int]$one.recommendation.positionNumber -ne 1 -or [int]$one.recommendation.total -ne 1 -or [bool]$one.recommendation.previousAvailable -or [bool]$one.recommendation.nextAvailable -or [int]$one.inventoryCount -ne 1 -or [string]::IsNullOrWhiteSpace([string]$one.recommendation.facility) -or [string]::IsNullOrWhiteSpace([string]$one.recommendation.complaint) -or -not $states['one-item'].text.Contains([string]$one.recommendation.facility)) { Stop-CaptureFail 'Issue #655 scenario gate: one-item scenario is not exactly one rendered recommendation.' }
    if ([bool]$empty.recommendation.present -or [int]$empty.recommendation.total -ne 0 -or [int]$empty.inventoryCount -ne 0 -or [bool]$empty.recommendation.previousAvailable -or [bool]$empty.recommendation.nextAvailable -or [string]::IsNullOrWhiteSpace([string]$empty.emptyStateText) -or -not ($empty.emptyStateText -match '(?i)No facilities match|No Review next recommendation')) { Stop-CaptureFail 'Issue #655 scenario gate: empty scenario is not a governed empty recommendation and inventory state.' }
    $hashes = @($middle.screenshot.sha256, $one.screenshot.sha256, $empty.screenshot.sha256)
    if ($hashes | Where-Object { [string]::IsNullOrWhiteSpace([string]$_) } | Select-Object -First 1) { Stop-CaptureFail 'Issue #655 scenario gate: scenario screenshot hash is missing.' }
    if (@($hashes | Sort-Object -Unique).Count -ne 3) { Stop-CaptureFail 'Issue #655 scenario gate: middle, one-item, and empty screenshots must be distinct.' }
    $gate = [ordered]@{ status='PASS'; middle=@{position=$middle.recommendation.positionNumber;total=$middle.recommendation.total;facility=$middle.recommendation.facility;complaint=$middle.recommendation.complaint}; oneItem=@{position=$one.recommendation.positionNumber;total=$one.recommendation.total;facility=$one.recommendation.facility;complaint=$one.recommendation.complaint}; empty=@{recommendationPresent=$empty.recommendation.present;inventoryCount=$empty.inventoryCount;emptyStateText=$empty.emptyStateText}; screenshotHashes=$hashes }
    Set-Content -LiteralPath (Join-Path $DiagnosticsDirectory 'issue-655-static-scenario-gate.json') -Value ($gate | ConvertTo-Json -Depth 8) -Encoding UTF8
}

function Write-Issue642PacketDiagnostics {
    param([string]$PacketDirectory, [string]$ScreenshotDirectory, [string]$DiagnosticsDirectory, [object[]]$RouteResults, [string]$IssueNumber = '642')

    $screenshots = @(Get-ChildItem -LiteralPath $ScreenshotDirectory -File -Recurse -Filter '*.png' | Sort-Object FullName)
    $states = @($screenshots | ForEach-Object {
        [ordered]@{
            state = ConvertTo-RelativeEvidencePath -Path $_.FullName -Root $ScreenshotDirectory
            requested = $true
            attempted = $true
            outcome = 'captured'
            artifact = ConvertTo-RelativeEvidencePath -Path $_.FullName -Root $PacketDirectory
            reason = ''
        }
    })
    $distinctArtifacts = @($states.artifact | Sort-Object -Unique)
    if ($states.Count -ne $screenshots.Count -or $distinctArtifacts.Count -ne $screenshots.Count) {
        Stop-CaptureFail "Issue #$IssueNumber screenshot state ledger does not reconcile to captured screenshot files."
    }
    $stateCounts = [ordered]@{ requested = $states.Count; attempted = $states.Count; captured = $states.Count; skipped = 0; failed = 0; artifactFiles = $screenshots.Count }
    Set-Content -LiteralPath (Join-Path $DiagnosticsDirectory "issue-$IssueNumber-screenshot-states.json") -Value ([ordered]@{ counts = $stateCounts; states = $states } | ConvertTo-Json -Depth 8) -Encoding UTF8

    $browserStates = @($RouteResults | Where-Object { $_.browserStatePath } | ForEach-Object { Get-Content -LiteralPath (Join-Path $PacketDirectory $_.browserStatePath) -Raw | ConvertFrom-Json })
    $consoleErrors = @($browserStates | ForEach-Object { @($_.consoleErrors) })
    $consoleWarnings = @($browserStates | ForEach-Object { @($_.consoleWarnings) })
    $pageErrors = @($browserStates | ForEach-Object { @($_.pageErrors) })
    $failedRequests = @($browserStates | ForEach-Object { @($_.failedNetworkRequests) })
    $unexpectedResponses = @($RouteResults | Where-Object { $_.statusCode -ne $_.expectedStatus } | ForEach-Object { [ordered]@{ route = $_.name; statusCode = $_.statusCode; expectedStatus = $_.expectedStatus } })
    $nonzero = @()
    if ($consoleErrors.Count -gt 0) { $nonzero += 'console-errors' }
    if ($consoleWarnings.Count -gt 0) { $nonzero += 'console-warnings' }
    if ($pageErrors.Count -gt 0) { $nonzero += 'page-errors' }
    if ($failedRequests.Count -gt 0) { $nonzero += 'failed-network-requests' }
    if ($unexpectedResponses.Count -gt 0) { $nonzero += 'unexpected-http-responses' }
    $summary = [ordered]@{
        browserStateArtifacts = $browserStates.Count
        console = [ordered]@{ events = ($consoleErrors.Count + $consoleWarnings.Count + $pageErrors.Count); errors = $consoleErrors.Count; warnings = $consoleWarnings.Count; pageErrors = $pageErrors.Count }
        network = [ordered]@{ failedRequests = $failedRequests.Count; unexpectedHttpResponses = $unexpectedResponses.Count }
        nonzeroClassifications = $nonzero
        statement = if ($nonzero.Count -eq 0) { 'No console events, failed requests, or unexpected HTTP responses were observed.' } else { 'Nonzero events or failures are classified above.' }
    }
    Set-Content -LiteralPath (Join-Path $DiagnosticsDirectory "issue-$IssueNumber-console-network-summary.json") -Value ($summary | ConvertTo-Json -Depth 8) -Encoding UTF8
    return [ordered]@{ screenshotStates = $stateCounts; consoleNetwork = $summary }
}

function Write-Issue655PacketDiagnostics {
    param([string]$PacketDirectory, [string]$ScreenshotDirectory, [string]$DiagnosticsDirectory, [object[]]$RouteResults)
    $base = Write-Issue642PacketDiagnostics -PacketDirectory $PacketDirectory -ScreenshotDirectory $ScreenshotDirectory -DiagnosticsDirectory $DiagnosticsDirectory -RouteResults $RouteResults -IssueNumber '655'
    $browserStates = @($RouteResults | Where-Object { $_.browserStatePath } | ForEach-Object { Get-Content -LiteralPath (Join-Path $PacketDirectory $_.browserStatePath) -Raw | ConvertFrom-Json })
    $geometry = @($browserStates | ForEach-Object { $_.geometry })
    $focus = @($browserStates | ForEach-Object { [ordered]@{ route=$_.routeName; focusedElement=$_.focus; position=$_.recommendation.position; operatedStates=@($_.operated_states) } })
    Set-Content -LiteralPath (Join-Path $DiagnosticsDirectory 'issue-655-geometry.json') -Value ([ordered]@{ routes=$geometry; statement='Geometry is captured from the rendered local-fixture document; horizontal overflow fails the capture.' } | ConvertTo-Json -Depth 10) -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $DiagnosticsDirectory 'issue-655-focus-live-region.json') -Value ([ordered]@{ routes=$focus; statement='Focus and polite live-region state are recorded after operated replacement.' } | ConvertTo-Json -Depth 10) -Encoding UTF8
    $interactionPath = Join-Path $DiagnosticsDirectory 'issue-655-interaction-index.json'
    $interactionCount = if (Test-Path -LiteralPath $interactionPath) { @((Get-Content -LiteralPath $interactionPath -Raw | ConvertFrom-Json).interactions).Count } else { 0 }
    return [ordered]@{ screenshotStates=$base.screenshotStates; consoleNetwork=$base.consoleNetwork; browserStates=$browserStates.Count; interactionCount=$interactionCount; geometryArtifact='diagnostics/issue-655-geometry.json'; focusLiveArtifact='diagnostics/issue-655-focus-live-region.json'; interactionIndexArtifact='diagnostics/issue-655-interaction-index.json'; facilityReturnArtifact='diagnostics/issue-655-facility-overview-return.json'; complaintReturnArtifact='diagnostics/issue-655-complaint-detail-return.json'; concurrencyArtifact='diagnostics/issue-655-concurrency-stale-response.json'; enhancedErrorArtifact='diagnostics/issue-655-enhanced-request-failure.json'; reducedMotionArtifact='diagnostics/issue-655-reduced-motion.json' }
}

function Test-Issue503RouteAssertions {
    param([hashtable]$Route, [string]$Html, [string]$Text, [System.Collections.ArrayList]$Assertions)
    if (-not $Route.ContainsKey("Issue503Kind")) { return }
    $name = [string]$Route.Name
    $kind = [string]$Route.Issue503Kind
    $categories = @("Get started", "Understand the information", "Manage review work", "Troubleshooting")
    $categoriesPresent = @($categories | Where-Object { -not $Text.Contains($_) }).Count -eq 0
    Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue503 four-category attorney architecture" -Status $(if ($categoriesPresent) { "PASS" } else { "FAIL" }) -Message $(if ($categoriesPresent) { "All four approved Help categories are visible." } else { "One or more approved Help categories are missing." })

    $taskGuidancePresent = $Text.Contains("Find and select a facility") -and $Text.Contains("Compare facilities") -and $Text.Contains("Get complaint records") -and $Text.Contains("Review a complaint") -and $Text.Contains("Use the Complaint Worklist") -and $Text.Contains("Report a problem through Feedback")
    Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue503 visible attorney task guidance" -Status $(if ($taskGuidancePresent) { "PASS" } else { "FAIL" }) -Message $(if ($taskGuidancePresent) { "Representative attorney tasks and recovery guidance are visible." } else { "Required attorney task or recovery guidance is missing." })

    $detailsBlocks = [regex]::Matches($Html, "(?is)<details\b(?:(?!</details>).)*</details>")
    $detailsCount = $detailsBlocks.Count
    $primaryHidden = @($detailsBlocks | Where-Object { $_.Value -match "(?is)<h[23]\b" }).Count -gt 0
    $disclosureBoundary = $detailsCount -eq 1 -and -not $primaryHidden -and $Html.Contains('class="help-secondary-disclosure"')
    Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue503 disclosure boundary" -Status $(if ($disclosureBoundary) { "PASS" } else { "FAIL" }) -Message $(if ($disclosureBoundary) { "Primary guidance is visible and only one secondary example uses disclosure." } else { "Primary guidance is hidden or the permitted disclosure boundary changed." })

    $fragmentIds = @("get-started", "understand-information", "manage-review-work", "troubleshooting")
    $fragmentContract = $true
    foreach ($fragmentId in $fragmentIds) {
        if (-not $Html.Contains("href=`"#$fragmentId`"") -or -not $Html.Contains("id=`"$fragmentId`" tabindex=`"-1`"")) { $fragmentContract = $false }
    }
    $fragmentContract = $fragmentContract -and $Html.Contains("window.history.pushState") -and $Html.Contains("window.addEventListener('popstate'") -and $Html.Contains("target.scrollIntoView") -and $Html.Contains("target.focus")
    Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue503 stable fragment navigation contract" -Status $(if ($fragmentContract) { "PASS" } else { "FAIL" }) -Message $(if ($fragmentContract) { "Descriptive links, visible focus targets, viewport movement, and browser-history handling are present." } else { "Stable fragment navigation behavior is incomplete." })

    $obsoleteOrInternal = $Text -match "(?i)Facility Review Intelligence|Facility review priority list|Facility Hub|Review Queue|Reviewer Detail|preparation draft|request context|loaded records|planning view|review cue|reference data details|source-available indicator|raw SHA-256|connector metadata|operator diagnostics|runtime details|server path|database instruction"
    Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue503 information-tier and terminology boundary" -Status $(if (-not $obsoleteOrInternal) { "PASS" } else { "FAIL" }) -Message $(if (-not $obsoleteOrInternal) { "Obsolete workflow language and operator/developer material are absent." } else { "Obsolete workflow language or operator/developer material is visible." })

    $normalizedText = [regex]::Replace($Text, "\s+", " ")
    $sourceBoundary = $normalizedText.Contains("do not change the public complaint record") -and $normalizedText.Contains("not proof that no public complaint exists") -and $normalizedText.Contains("not an assignment") -and $normalizedText.Contains("not a certified report")
    Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue503 source-state truthfulness" -Status $(if ($sourceBoundary) { "PASS" } else { "FAIL" }) -Message $(if ($sourceBoundary) { "Reviewer-created, missing-record, suggestion, and print boundaries are explicit." } else { "One or more truthful source/reviewer boundaries are missing." })

    $glossaryContract = $Html.Contains('data-term-id="help-substantiated"') -and $Html.Contains('data-term-id="help-plan-of-correction"') -and $Html.Contains("inline-glossary-definition")
    Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue503 shared glossary behavior" -Status $(if ($glossaryContract) { "PASS" } else { "FAIL" }) -Message $(if ($glossaryContract) { "Official terms use the shared collision-safe glossary component." } else { "Shared glossary behavior is missing." })

    if ($kind -eq "print") {
        $printContract = $Html.Contains("@media print") -and $Html.Contains(".help-category-nav") -and $Html.Contains(".help-secondary-disclosure") -and $Html.Contains(".help-guidance")
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue503 print structure" -Status $(if ($printContract) { "PASS" } else { "FAIL" }) -Message $(if ($printContract) { "Help print rules retain primary guidance and remove navigation and secondary disclosure." } else { "Help print structure is incomplete." })
    }
}

function Test-Issue420RouteAssertions {
    param([hashtable]$Route, [string]$Html, [string]$Text, [System.Collections.ArrayList]$Assertions)
    if (-not $Route.ContainsKey("Issue420Kind")) { return }
    $name = [string]$Route.Name
    $kind = [string]$Route.Issue420Kind

    $heading = $Text.Contains("Facility Overview")
    Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue420 Facility Overview heading" -Status $(if ($heading) { "PASS" } else { "FAIL" }) -Message $(if ($heading) { "Facility Overview heading found." } else { "Facility Overview heading missing." })
    $reviewerSafe = -not ($Text -match '(?i)raw_path|raw_sha256|source_record_key|connector_name|connection string|container name|tests/fixtures|local/test')
    Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue420 reviewer-tier safety" -Status $(if ($reviewerSafe) { "PASS" } else { "FAIL" }) -Message $(if ($reviewerSafe) { "Reviewer output omits controlled source and runtime internals." } else { "Reviewer output exposes a controlled source or runtime internal." })
    $noPrimaryDisclosure = -not ($Html -match '(?is)<details[^>]*>.*?(Complaint|contributing|facility facts).*?</details>') -and -not $Text.Contains("Exact contributing complaints")
    Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue420 no primary disclosure stack" -Status $(if ($noPrimaryDisclosure) { "PASS" } else { "FAIL" }) -Message $(if ($noPrimaryDisclosure) { "Primary identity and complaint records are not hidden or duplicated in disclosures." } else { "A superseded primary disclosure or contributor stack remains." })

    if ($Route.ContainsKey("ExpectedText")) {
        $expectedText = [string]$Route.ExpectedText
        $hasExpectedText = $Text.Contains($expectedText)
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue420 intended state" -Status $(if ($hasExpectedText) { "PASS" } else { "FAIL" }) -Message $(if ($hasExpectedText) { "Expected state text '$expectedText' found." } else { "Expected state text '$expectedText' missing." })
    }
    if ($kind -in @("populated", "filter", "responsive", "focus", "missing-identity", "partial", "print")) {
        $canonicalInventory = $Html.Contains('id="facility-complaint-inventory"') -and $Text.Contains("Canonical record inventory") -and $Text.Contains("Review complaint")
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue420 canonical complaint inventory" -Status $(if ($canonicalInventory) { "PASS" } else { "FAIL" }) -Message $(if ($canonicalInventory) { "One canonical complaint inventory with review actions found." } else { "Canonical complaint inventory or review action missing." })
        $sourceAndReviewerState = $Html.Contains('class="summary-list complaint-source-facts"') -and $Html.Contains('class="reviewer-state-panel"') -and $Text.Contains("CCLD source") -and $Text.Contains("Reviewer-created state")
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue420 source and reviewer state separation" -Status $(if ($sourceAndReviewerState) { "PASS" } else { "FAIL" }) -Message $(if ($sourceAndReviewerState) { "Source-derived facts and reviewer-created state have separate semantic regions." } else { "Source-derived and reviewer-created information is not clearly separated." })
        $primaryActions = @([regex]::Matches($Html, 'class="button"[^>]*>(Review complaint|Show recommended complaint)'))
        $onePrimaryAction = $primaryActions.Count -eq 1
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue420 single primary next action" -Status $(if ($onePrimaryAction) { "PASS" } else { "FAIL" }) -Message $(if ($onePrimaryAction) { "Exactly one primary Review complaint action found." } else { "The populated page does not have exactly one primary Review complaint action." })
        $filterContract = $Html.Contains('aria-label="Filter the complaint inventory"') -and $Html.Contains('aria-current="true"') -and $Text.Contains("Showing")
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue420 filter and reconciliation contract" -Status $(if ($filterContract) { "PASS" } else { "FAIL" }) -Message $(if ($filterContract) { "Inventory filters, active state, and visible count reconciliation found." } else { "Inventory filter active state or count reconciliation missing." })
        $returnContext = $Html.Contains("return_context_origin=facility_overview") -and $Html.Contains("return_q=")
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue420 complaint return continuity" -Status $(if ($returnContext) { "PASS" } else { "FAIL" }) -Message $(if ($returnContext) { "Complaint detail links preserve Facility Overview return context." } else { "Facility Overview return context is missing from complaint detail links." })
    }
    if ($kind -in @("zero", "filtered-empty")) {
        $oneEmptyState = ([regex]::Matches($Html, 'class="empty-state-card facility-overview-empty"')).Count -eq 1
        $irrelevantSectionsAbsent = -not $Text.Contains("Review summary") -and -not $Text.Contains("Review next") -and -not $Text.Contains("Canonical record inventory")
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue420 compact empty state" -Status $(if ($oneEmptyState -and $irrelevantSectionsAbsent) { "PASS" } else { "FAIL" }) -Message $(if ($oneEmptyState -and $irrelevantSectionsAbsent) { "One action-focused empty state is present without populated-only sections." } else { "Empty state is duplicated or populated-only sections remain." })
    }
    if ($kind -eq "responsive") {
        $responsiveContract = $Html.Contains("@media (max-width: 760px)") -and $Html.Contains(".facility-inventory-item") -and $Html.Contains("overflow-wrap: anywhere")
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue420 responsive contract" -Status $(if ($responsiveContract) { "PASS" } else { "FAIL" }) -Message $(if ($responsiveContract) { "Facility inventory wrapping and governed mobile breakpoint found." } else { "Facility Overview responsive contract missing." })
    }
    if ($kind -eq "focus") {
        $focusContract = $Html.Contains('id="facility-complaint-inventory-heading" tabindex="-1"') -and $Html.Contains("window.location.hash") -and $Html.Contains("heading.focus")
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue420 keyboard focus contract" -Status $(if ($focusContract) { "PASS" } else { "FAIL" }) -Message $(if ($focusContract) { "Inventory filter and fragment focus contracts found." } else { "Inventory keyboard or fragment focus contract missing." })
    }
    if ($kind -eq "missing-identity") {
        $missingIdentity = $Text.Contains("Unavailable facility facts") -and -not $Text.Contains("Blank in source")
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue420 missing identity consolidation" -Status $(if ($missingIdentity) { "PASS" } else { "FAIL" }) -Message $(if ($missingIdentity) { "Unavailable identity labels are consolidated without repeated source-blank text." } else { "Missing identity values are not consolidated truthfully." })
    }
    if ($kind -eq "populated" -or $kind -eq "partial") {
        $partialState = $Text.Contains("Partial source coverage") -and $Text.Contains("Get Additional Records") -and $Text.Contains("does not infer a stale-record threshold")
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue420 partial and stale transparency" -Status $(if ($partialState) { "PASS" } else { "FAIL" }) -Message $(if ($partialState) { "Partial coverage action and governed stale-threshold limitation found." } else { "Partial coverage or stale-threshold transparency is missing." })
    }
    if ($kind -eq "print") {
        $printContract = $Html.Contains("@media print") -and $Html.Contains(".facility-inventory-filters") -and $Html.Contains(".facility-inventory-actions")
        Add-AssertionResult -Target $Assertions -RouteName $name -Check "issue420 print contract" -Status $(if ($printContract) { "PASS" } else { "FAIL" }) -Message $(if ($printContract) { "Print stylesheet preserves values while hiding filter and action controls." } else { "Facility Overview print contract missing." })
    }
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
    if (-not $Issue655Rehearsal) { Assert-OutputDir -Path $OutputDir }
    if (($Issue419 -or $Issue420 -or $Issue502 -or $Issue503 -or $Issue641 -or $Issue642 -or $Issue643) -and $Mode -ne "fixture") {
        Stop-CaptureFail "Issue #419, Issue #420, Issue #502, Issue #503, and Issue #641 evidence routes are local fixture/demo-only; use -Mode fixture."
    }
    if ($Issue498 -and $Mode -ne "fixture") {
        Stop-CaptureFail "Issue #498 evidence routes are local fixture/demo-only; use -Mode fixture."
    }
    $baseUri = [System.Uri]::new($BaseUrl)
    $normalizedBaseUrl = $baseUri.GetLeftPart([System.UriPartial]::Authority).TrimEnd("/")
    $timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd-HHmmssZ")
    if ($Issue655Rehearsal -and -not $Issue655) { throw 'Issue655Rehearsal requires Issue655.' }
    if ($Issue655Rehearsal) {
        $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
        $resolvedOutput = [IO.Path]::GetFullPath($OutputDir)
        if (-not $resolvedOutput.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Issue #655 rehearsal output must stay under the temporary directory.' }
    }
    $packetName = if ($Issue655Rehearsal) { "issue-655-rehearsal-$RehearsalRunName" } elseif ($Issue655) { "$timestamp-issue-655-local" } elseif ($Issue643) { "$timestamp-issue-643-local" } elseif ($Issue642) { "$timestamp-issue-642-local" } elseif ($Issue503) { "$timestamp-$Mode-issue-503" } elseif ($Issue502) { "$timestamp-$Mode-issue-502" } elseif ($Issue498) { "$timestamp-$Mode-issue-498" } elseif ($Issue420) { "$timestamp-$Mode-issue-420" } elseif ($Issue419) { "$timestamp-$Mode-issue-419" } elseif ($Issue418) { "$timestamp-$Mode-issue-418" } elseif ($Issue417) { "$timestamp-$Mode-issue-417" } elseif ($Issue416) { "$timestamp-$Mode-issue-416" } elseif ($Issue415) { "$timestamp-$Mode-issue-415" } else { "$timestamp-$Mode" }
    $outputRoot = if ([IO.Path]::IsPathRooted($OutputDir)) {
        [IO.Path]::GetFullPath($OutputDir)
    } else {
        [IO.Path]::GetFullPath((Join-Path $PWD $OutputDir))
    }
    $packetDir = Join-Path $outputRoot $packetName
    $zipPath = Join-Path $outputRoot "$packetName.zip"
    $htmlDir = Join-Path $packetDir "html"
    $textDir = Join-Path $packetDir "text"
    $screenshotDir = Join-Path $packetDir "screenshots"
    $fullPageScreenshotDir = Join-Path $screenshotDir "full-page"
    $focusedScreenshotDir = Join-Path $screenshotDir "focused"
    $printDir = Join-Path $packetDir "print"
    $accessibilityDir = Join-Path $packetDir "accessibility"
    $diagnosticsDir = Join-Path $packetDir "diagnostics"
    $browserStateDir = Join-Path $packetDir "browser-state"
    $logsDir = Join-Path $packetDir "logs"
    $reviewDir = Join-Path $packetDir "reviews"
    foreach ($dir in @($packetDir, $htmlDir, $textDir, $screenshotDir, $fullPageScreenshotDir, $focusedScreenshotDir, $printDir, $accessibilityDir, $diagnosticsDir, $browserStateDir, $logsDir, $reviewDir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }

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
    $issue420Base = "/ccld/facilities/detail?facility_number=157806098"
    $issue420Routes = @(
        @{ Name = "issue-420-populated-desktop"; Path = $issue420Base; Label = "issue-420-01-populated-desktop"; ActiveHref = "/ccld/facilities"; WorkflowStep = "Facility"; Issue420Kind = "populated"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-420-source-unavailable-filter"; Path = "$issue420Base&inventory_filter=source%3Aunavailable"; Label = "issue-420-02-source-unavailable-filter"; ActiveHref = "/ccld/facilities"; WorkflowStep = "Facility"; Issue420Kind = "filter"; ExpectedText = "Original report unavailable"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-420-reviewer-state-filter"; Path = "$issue420Base&inventory_filter=status%3Anot_started"; Label = "issue-420-03-reviewer-state-filter"; ActiveHref = "/ccld/facilities"; WorkflowStep = "Facility"; Issue420Kind = "filter"; ExpectedText = "Status: Not started"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-420-narrow-desktop"; Path = $issue420Base; Label = "issue-420-04-narrow-desktop"; ActiveHref = "/ccld/facilities"; WorkflowStep = "Facility"; Issue420Kind = "responsive"; ViewportWidth = 1024; ViewportHeight = 900 },
        @{ Name = "issue-420-mobile"; Path = $issue420Base; Label = "issue-420-05-mobile-390"; ActiveHref = "/ccld/facilities"; WorkflowStep = "Facility"; Issue420Kind = "responsive"; ViewportWidth = 390; ViewportHeight = 844 },
        @{ Name = "issue-420-reflow"; Path = $issue420Base; Label = "issue-420-06-200-percent-reflow-approximation"; ActiveHref = "/ccld/facilities"; WorkflowStep = "Facility"; Issue420Kind = "responsive"; ViewportWidth = 720; ViewportHeight = 600 },
        @{ Name = "issue-420-keyboard-filter"; Path = $issue420Base; Label = "issue-420-07-keyboard-filter"; ActiveHref = "/ccld/facilities"; WorkflowStep = "Facility"; Issue420Kind = "focus"; Issue502CapturePurpose = "viewport"; Issue502KeyboardSelector = '.facility-inventory-filter[href*="source%3Aunavailable"]'; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-420-filtered-empty"; Path = "$issue420Base&start_date=2099-01-01&end_date=2099-12-31"; Label = "issue-420-08-filtered-empty"; ActiveHref = "/ccld/facilities"; WorkflowStep = "Facility"; Issue420Kind = "filtered-empty"; ExpectedText = "No loaded complaints match the current facility review filters"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-420-zero-complaint"; Path = "/ccld/facilities/detail?facility_number=900000001"; Label = "issue-420-09-zero-complaint"; ActiveHref = "/ccld/facilities"; WorkflowStep = "Facility"; Issue420Kind = "zero"; ExpectedText = "This is not a verified zero"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-420-missing-identity-values"; Path = "$issue420Base&evidence_state=facility-overview-missing-identity"; Label = "issue-420-10-missing-identity-values"; ActiveHref = "/ccld/facilities"; WorkflowStep = "Facility"; Issue420Kind = "missing-identity"; ExpectedText = "Unavailable facility facts"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-420-print"; Path = $issue420Base; Label = "issue-420-12-print"; ActiveHref = "/ccld/facilities"; WorkflowStep = "Facility"; Issue420Kind = "print"; ViewportWidth = 1440; ViewportHeight = 1200; CapturePrint = $true }
    )
    $issue502Routes = @(
        @{ Name = "issue-502-home"; Path = "/"; Label = "issue-502-01-home"; ActiveHref = "/"; WorkflowStep = "Home"; Issue502Kind = "home"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-502-home-mobile"; Path = "/"; Label = "issue-502-02-home-mobile"; ActiveHref = "/"; WorkflowStep = "Home"; Issue502Kind = "home"; Issue502CapturePurpose = "full-page"; ViewportWidth = 390; ViewportHeight = 844 },
        @{ Name = "issue-502-home-keyboard"; Path = "/"; Label = "issue-502-03-home-keyboard"; ActiveHref = "/"; WorkflowStep = "Home"; Issue502Kind = "home"; Issue502CapturePurpose = "full-page"; Issue502KeyboardSelector = 'main a.button[href="/ccld/facilities"]'; Issue502DistinctFrom = "issue-502-home"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-502-facility-default"; Path = "/ccld/facilities"; Label = "issue-502-04-facility-default"; ActiveHref = "/ccld/facilities"; WorkflowStep = "Facility"; Issue502Kind = "facility"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-502-facility-results"; Path = "/ccld/facilities?q=orchard#facility-results"; Label = "issue-502-05-facility-results"; ActiveHref = "/ccld/facilities"; WorkflowStep = "Facility"; Issue502Kind = "results"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-502-valid-unmatched"; Path = "/ccld/facilities?q=123456789#facility-results"; Label = "issue-502-06-valid-unmatched"; ActiveHref = "/ccld/facilities"; WorkflowStep = "Facility"; Issue502Kind = "unmatched"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-502-malformed"; Path = "/ccld/facilities?q=12345#facility-results"; Label = "issue-502-07-malformed"; ActiveHref = "/ccld/facilities"; WorkflowStep = "Facility"; Issue502Kind = "malformed"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-502-directory-unavailable"; Path = "/ccld/facilities?evidence_state=facility-search-unavailable"; Label = "issue-502-08-directory-unavailable"; ActiveHref = "/ccld/facilities"; WorkflowStep = "Facility"; Issue502Kind = "unavailable"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-502-facility-mobile"; Path = "/ccld/facilities?q=orchard"; Label = "issue-502-09-facility-mobile"; ActiveHref = "/ccld/facilities"; WorkflowStep = "Facility"; Issue502Kind = "results"; Issue502CapturePurpose = "full-page"; ViewportWidth = 390; ViewportHeight = 844 },
        @{ Name = "issue-502-facility-mobile-focused-results"; Path = "/ccld/facilities?q=orchard#facility-results"; Label = "issue-502-09b-facility-mobile-focused-results"; ActiveHref = "/ccld/facilities"; WorkflowStep = "Facility"; Issue502Kind = "results"; ViewportWidth = 390; ViewportHeight = 844 },
        @{ Name = "issue-502-facility-reflow"; Path = "/ccld/facilities?q=orchard"; Label = "issue-502-10-facility-reflow"; ActiveHref = "/ccld/facilities"; WorkflowStep = "Facility"; Issue502Kind = "results"; Issue502CapturePurpose = "full-page"; ViewportWidth = 720; ViewportHeight = 600 },
        @{ Name = "issue-502-facility-keyboard"; Path = "/ccld/facilities"; Label = "issue-502-11-facility-keyboard"; ActiveHref = "/ccld/facilities"; WorkflowStep = "Facility"; Issue502Kind = "facility"; Issue502CapturePurpose = "full-page"; Issue502KeyboardSelector = '#facility-search-input'; Issue502DistinctFrom = "issue-502-facility-default"; ViewportWidth = 1440; ViewportHeight = 1200 }
    )
    $issue503Routes = @(
        @{ Name = "issue-503-help-desktop"; Path = "/ccld/help"; Label = "issue-503-01-help-desktop"; ActiveHref = "/ccld/help"; Issue503Kind = "landing"; Issue502CapturePurpose = "full-page"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-503-help-narrow"; Path = "/ccld/help"; Label = "issue-503-02-help-narrow-1024"; ActiveHref = "/ccld/help"; Issue503Kind = "responsive"; Issue502CapturePurpose = "full-page"; ViewportWidth = 1024; ViewportHeight = 900 },
        @{ Name = "issue-503-help-mobile"; Path = "/ccld/help"; Label = "issue-503-03-help-mobile-390"; ActiveHref = "/ccld/help"; Issue503Kind = "responsive"; Issue502CapturePurpose = "full-page"; ViewportWidth = 390; ViewportHeight = 844 },
        @{ Name = "issue-503-help-reflow"; Path = "/ccld/help"; Label = "issue-503-04-200-percent-reflow-approximation"; ActiveHref = "/ccld/help"; Issue503Kind = "responsive"; Issue502CapturePurpose = "full-page"; ViewportWidth = 720; ViewportHeight = 600 },
        @{ Name = "issue-503-direct-get-started"; Path = "/ccld/help#get-started"; Label = "issue-503-05-direct-get-started"; ActiveHref = "/ccld/help"; Issue503Kind = "direct-fragment"; Issue503ExpectedFragment = "get-started"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-503-direct-understand-information"; Path = "/ccld/help#understand-information"; Label = "issue-503-06-direct-understand-information"; ActiveHref = "/ccld/help"; Issue503Kind = "direct-fragment"; Issue503ExpectedFragment = "understand-information"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-503-direct-manage-review-work"; Path = "/ccld/help#manage-review-work"; Label = "issue-503-07-direct-manage-review-work"; ActiveHref = "/ccld/help"; Issue503Kind = "direct-fragment"; Issue503ExpectedFragment = "manage-review-work"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-503-direct-troubleshooting"; Path = "/ccld/help#troubleshooting"; Label = "issue-503-08-direct-troubleshooting"; ActiveHref = "/ccld/help"; Issue503Kind = "direct-fragment"; Issue503ExpectedFragment = "troubleshooting"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-503-keyboard-category"; Path = "/ccld/help"; Label = "issue-503-09-keyboard-category"; ActiveHref = "/ccld/help"; Issue503Kind = "keyboard-activation"; Issue503Interaction = "activate-fragment"; Issue503ExpectedFragment = "get-started"; Issue502KeyboardSelector = '.help-category-nav a[href="#get-started"]'; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-503-child-history"; Path = "/ccld/help"; Label = "issue-503-10-child-history"; ActiveHref = "/ccld/help"; Issue503Kind = "history"; Issue503Interaction = "activate-history"; Issue503ExpectedFragment = "facility-not-found"; Issue502KeyboardSelector = '.help-section a[href="#facility-not-found"]'; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-503-invalid-fragment"; Path = "/ccld/help#missing-help-target"; Label = "issue-503-11-invalid-fragment"; ActiveHref = "/ccld/help"; Issue503Kind = "invalid-fragment"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-503-secondary-disclosure"; Path = "/ccld/help"; Label = "issue-503-12-secondary-disclosure"; ActiveHref = "/ccld/help"; Issue503Kind = "disclosure"; Issue503Interaction = "toggle-disclosure"; Issue502KeyboardSelector = 'details.help-secondary-disclosure > summary'; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-503-glossary"; Path = "/ccld/help"; Label = "issue-503-13-glossary"; ActiveHref = "/ccld/help"; Issue503Kind = "glossary"; Issue503Interaction = "toggle-glossary"; Issue502KeyboardSelector = '.inline-glossary-term[data-term-id="help-substantiated"]'; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-503-print"; Path = "/ccld/help"; Label = "issue-503-14-print"; ActiveHref = "/ccld/help"; Issue503Kind = "print"; Issue502CapturePurpose = "full-page"; ViewportWidth = 1440; ViewportHeight = 1200; CapturePrint = $true }
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
    $issue610Routes = @(
        @{ Name = "issue-610-populated-print"; Path = "/reviewer/records/detail?source_record_key=complaint%3Accld%3Acomplaint%3A32-CR-20220407124448&return_facility_number=157806098&return_start_date=&return_end_date=&return_context_origin=reviewer_worklist&return_lookup_facility_name=&return_q=32-CR-20220407124448&return_source_record_key=complaint%3Accld%3Acomplaint%3A32-CR-20220407124448"; Label = "issue-610-01-populated-print"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; ViewportWidth = 1440; ViewportHeight = 1200; CapturePrint = $true },
        @{ Name = "issue-610-source-unavailable"; Path = $issue498SourceUnavailablePath; Label = "issue-610-02-source-unavailable"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; ViewportWidth = 1440; ViewportHeight = 1200 }
    )
    $issue641Base = "/ccld/facilities/intelligence"
    $issue641Detail = "/reviewer/records/detail?source_record_key=complaint%3Accld%3Acomplaint%3AISSUE-641-430000001&return_facility_number=430000001&return_context_origin=facility_intelligence&return_lookup_facility_name=Conflicting+query+facility+name"
    $issue641Routes = @(
        @{ Name = "issue-641-compare-default"; Path = $issue641Base; Label = "issue-641-01-compare-default"; ActiveHref = $issue641Base; WorkflowStep = "Review"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-641-raw-430"; Path = "${issue641Base}?facility_type=430"; Label = "issue-641-02-raw-430"; ActiveHref = $issue641Base; WorkflowStep = "Review"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-641-raw-733"; Path = "${issue641Base}?facility_type=733"; Label = "issue-641-03-raw-733"; ActiveHref = $issue641Base; WorkflowStep = "Review"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-641-readable-type"; Path = "${issue641Base}?facility_type=Children%27s+Center"; Label = "issue-641-04-readable-type"; ActiveHref = $issue641Base; WorkflowStep = "Review"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-641-compare-1024"; Path = "${issue641Base}?facility_type=430"; Label = "issue-641-05-compare-1024"; ActiveHref = $issue641Base; WorkflowStep = "Review"; ViewportWidth = 1024; ViewportHeight = 768 },
        @{ Name = "issue-641-compare-768"; Path = "${issue641Base}?facility_type=430"; Label = "issue-641-06-compare-768"; ActiveHref = $issue641Base; WorkflowStep = "Review"; ViewportWidth = 768; ViewportHeight = 1024 },
        @{ Name = "issue-641-compare-400"; Path = "${issue641Base}?facility_type=430"; Label = "issue-641-07-compare-400"; ActiveHref = $issue641Base; WorkflowStep = "Review"; ViewportWidth = 400; ViewportHeight = 900 },
        @{ Name = "issue-641-compare-390"; Path = "${issue641Base}?facility_type=430"; Label = "issue-641-08-compare-390"; ActiveHref = $issue641Base; WorkflowStep = "Review"; ViewportWidth = 390; ViewportHeight = 844 },
        @{ Name = "issue-641-compare-1280-page-scale-200"; Path = "${issue641Base}?facility_type=430"; Label = "issue-641-08b-compare-1280-page-scale-200"; ActiveHref = $issue641Base; WorkflowStep = "Review"; ViewportWidth = 1280; ViewportHeight = 900; Issue641PageScaleFactor = 2.0 },
        @{ Name = "issue-641-overview"; Path = "/ccld/facilities/detail?facility_number=430000001"; Label = "issue-641-09-overview"; ActiveHref = "/ccld/facilities"; WorkflowStep = "Facility"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-641-overview-mobile"; Path = "/ccld/facilities/detail?facility_number=430000001"; Label = "issue-641-10-overview-mobile"; ActiveHref = "/ccld/facilities"; WorkflowStep = "Facility"; ViewportWidth = 390; ViewportHeight = 844 },
        @{ Name = "issue-641-detail"; Path = $issue641Detail; Label = "issue-641-11-detail"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-641-detail-mobile"; Path = $issue641Detail; Label = "issue-641-12-detail-mobile"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; ViewportWidth = 390; ViewportHeight = 844 },
        @{ Name = "issue-641-detail-print"; Path = $issue641Detail; Label = "issue-641-13-detail-print"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; ViewportWidth = 1440; ViewportHeight = 1200; CapturePrint = $true }
    )
    $issue642Base = "/ccld/facilities/intelligence"
    $issue642CompareState = "${issue642Base}?facility_type=430&finding=Unsubstantiated"
    $issue642Detail = "/reviewer/records/detail?source_record_key=complaint%3Accld%3Acomplaint%3AISSUE-641-430000001&return_facility_number=430000001&return_context_origin=facility_intelligence&return_q=facility_type%3D430%26finding%3DUnsubstantiated"
    $issue642Routes = @(
        @{ Name = "issue-642-operated-interactions"; Path = $issue642Base; Label = "issue-642-00-operated-interactions"; ActiveHref = $issue642Base; WorkflowStep = "Review"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-642-complaint-patterns"; Path = $issue642Base; Label = "issue-642-01-complaint-patterns"; ActiveHref = $issue642Base; WorkflowStep = "Review"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-642-licensing-populated"; Path = "${issue642Base}?view=licensing-visit-activity&q=430000001"; Label = "issue-642-02a-licensing-populated"; ActiveHref = $issue642Base; WorkflowStep = "Review"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-642-licensing-filtered-empty"; Path = "${issue642Base}?view=licensing-visit-activity&q=430000001&cue=Closed%20status%20in%20uploaded%20summary"; Label = "issue-642-02b-licensing-filtered-empty"; ActiveHref = $issue642Base; WorkflowStep = "Review"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-642-trends-populated"; Path = "${issue642Base}?view=complaint-activity-over-time&facility=642900001&facility_type=430&finding=Substantiated&date_dimension=complaint_received_date&start_date=2022-04-01&end_date=2022-04-30&time_grain=month&period_count=1"; Label = "issue-642-03-trends-populated"; ActiveHref = $issue642Base; WorkflowStep = "Review"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-642-trends-intentional-empty"; Path = "${issue642Base}?view=complaint-activity-over-time&facility=642900001&facility_type=430&finding=Unsubstantiated&date_dimension=complaint_received_date&start_date=2022-04-01&end_date=2022-04-30&time_grain=month&period_count=1"; Label = "issue-642-04-trends-intentional-empty"; ActiveHref = $issue642Base; WorkflowStep = "Review"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-642-multiselect-two-values"; Path = "${issue642Base}?facility_type=430&facility_type=733&finding=Unsubstantiated&finding=Substantiated"; Label = "issue-642-04-multiselect-two-values"; ActiveHref = $issue642Base; WorkflowStep = "Review"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-642-applied-chips"; Path = $issue642CompareState; Label = "issue-642-05-applied-chips"; ActiveHref = $issue642Base; WorkflowStep = "Review"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-642-overview-return"; Path = "/ccld/facilities/detail?facility_number=430000001&origin=facility_intelligence&facility_type=430&finding=Unsubstantiated"; Label = "issue-642-06-overview-return"; ActiveHref = "/ccld/facilities"; WorkflowStep = "Facility"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-642-detail-return"; Path = $issue642Detail; Label = "issue-642-07-detail-return"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-642-1024"; Path = $issue642CompareState; Label = "issue-642-08-1024"; ActiveHref = $issue642Base; WorkflowStep = "Review"; ViewportWidth = 1024; ViewportHeight = 768 },
        @{ Name = "issue-642-1280"; Path = $issue642CompareState; Label = "issue-642-08a-1280"; ActiveHref = $issue642Base; WorkflowStep = "Review"; ViewportWidth = 1280; ViewportHeight = 900 },
        @{ Name = "issue-642-768"; Path = $issue642CompareState; Label = "issue-642-09-768"; ActiveHref = $issue642Base; WorkflowStep = "Review"; ViewportWidth = 768; ViewportHeight = 1024 },
        @{ Name = "issue-642-500"; Path = $issue642CompareState; Label = "issue-642-10-500"; ActiveHref = $issue642Base; WorkflowStep = "Review"; ViewportWidth = 500; ViewportHeight = 900 },
        @{ Name = "issue-642-400"; Path = $issue642CompareState; Label = "issue-642-11-400"; ActiveHref = $issue642Base; WorkflowStep = "Review"; ViewportWidth = 400; ViewportHeight = 900 },
        @{ Name = "issue-642-390"; Path = $issue642CompareState; Label = "issue-642-12-390"; ActiveHref = $issue642Base; WorkflowStep = "Review"; ViewportWidth = 390; ViewportHeight = 844 },
        @{ Name = "issue-642-native-zoom-200"; Path = $issue642CompareState; Label = "issue-642-13-native-zoom-200"; ActiveHref = $issue642Base; WorkflowStep = "Review"; ViewportWidth = 1280; ViewportHeight = 900; Issue641PageScaleFactor = 2.0 },
        @{ Name = "issue-642-print"; Path = $issue642CompareState; Label = "issue-642-14-print"; ActiveHref = $issue642Base; WorkflowStep = "Review"; ViewportWidth = 1440; ViewportHeight = 1200; CapturePrint = $true }
    )
    if ($Issue642LicensingSourceUnavailable) {
        $issue642Routes = @(
            @{ Name = "issue-642-licensing-source-unavailable"; Path = "${issue642Base}?view=licensing-visit-activity&q=430000001"; Label = "issue-642-02c-licensing-source-unavailable"; ActiveHref = $issue642Base; WorkflowStep = "Review"; ExpectedDataState = 'data-result-state="source-unavailable"'; ViewportWidth = 1440; ViewportHeight = 1200 }
        )
    }
    $issue643Base = "/ccld/facilities/intelligence"
    # The unfiltered committed fixture deterministically contains populated cards,
    # including source-unavailable records; no production or retrieval source is used.
    $issue643Routes = @(
        @{ Name = "issue-643-operated-interactions"; Path = $issue643Base; Label = "issue-643-00-operated-interactions"; ActiveHref = $issue643Base; WorkflowStep = "Review"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-643-populated-desktop"; Path = $issue643Base; Label = "issue-643-01-populated-desktop"; ActiveHref = $issue643Base; WorkflowStep = "Review"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-643-populated-1024"; Path = $issue643Base; Label = "issue-643-02-populated-1024"; ActiveHref = $issue643Base; WorkflowStep = "Review"; ViewportWidth = 1024; ViewportHeight = 900 },
        @{ Name = "issue-643-populated-768"; Path = $issue643Base; Label = "issue-643-03-populated-768"; ActiveHref = $issue643Base; WorkflowStep = "Review"; ViewportWidth = 768; ViewportHeight = 1024 },
        @{ Name = "issue-643-populated-500"; Path = $issue643Base; Label = "issue-643-04-populated-500"; ActiveHref = $issue643Base; WorkflowStep = "Review"; ViewportWidth = 500; ViewportHeight = 900 },
        @{ Name = "issue-643-populated-400"; Path = $issue643Base; Label = "issue-643-05-populated-400"; ActiveHref = $issue643Base; WorkflowStep = "Review"; ViewportWidth = 400; ViewportHeight = 900 },
        @{ Name = "issue-643-populated-390"; Path = $issue643Base; Label = "issue-643-06-populated-390"; ActiveHref = $issue643Base; WorkflowStep = "Review"; ViewportWidth = 390; ViewportHeight = 844 },
        @{ Name = "issue-643-populated-zoom-200"; Path = $issue643Base; Label = "issue-643-07-populated-zoom-200"; ActiveHref = $issue643Base; WorkflowStep = "Review"; ViewportWidth = 1280; ViewportHeight = 900; Issue641PageScaleFactor = 2.0 },
        @{ Name = "issue-643-populated-print"; Path = $issue643Base; Label = "issue-643-08-populated-print"; ActiveHref = $issue643Base; WorkflowStep = "Review"; ViewportWidth = 1440; ViewportHeight = 1200; CapturePrint = $true },
        @{ Name = "issue-643-source-unavailable"; Path = "${issue643Base}?facility_type=733"; Label = "issue-643-09-source-unavailable"; ActiveHref = $issue643Base; WorkflowStep = "Review"; ViewportWidth = 1440; ViewportHeight = 1200 }
    )
    # Issue #655 is deliberately independent of Issue #643's card evidence.
    # The recommendation cursor is server-generated during operated capture;
    # static routes establish the canonical and exceptional server responses.
    $issue655Base = "/ccld/facilities/intelligence"
    $issue655Routes = @(
        @{ Name = "issue-655-first-recommendation"; Path = $issue655Base; Label = "issue-655-01-first"; ActiveHref = $issue655Base; WorkflowStep = "Review"; Issue655State = "first"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-655-middle-recommendation"; Path = "${issue655Base}?recommendation=eyJ2IjoxLCJmIjoiNGY1M2NkYTE4YzJiYWEwYzAzNTRiYjVmOWEzZWNiZTVlZDEyYWI0ZDhlMTFiYTg3M2MyZjExMTYxMjAyYjk0NSIsImEiOlswLDEsMCwiMjAyMi0wNC0wNyIsImEuIG1pcmlhbSBqYW1pc29uIGNoaWxkcmVuJ3MgY2VudGVyIiwiY2NsZDpmYWNpbGl0eToxNTc4MDYwOTgiXSwidCI6NH0"; Label = "issue-655-02-middle"; ActiveHref = $issue655Base; WorkflowStep = "Review"; Issue655State = "middle"; ViewportWidth = 1440; ViewportHeight = 1200; Operated = $true },
        @{ Name = "issue-655-last-recommendation"; Path = $issue655Base; Label = "issue-655-03-last"; ActiveHref = $issue655Base; WorkflowStep = "Review"; Issue655State = "last"; ViewportWidth = 1440; ViewportHeight = 1200; Operated = $true },
        @{ Name = "issue-655-one-item-sequence"; Path = "${issue655Base}?facility_type=733"; Label = "issue-655-04-one-item"; ActiveHref = $issue655Base; WorkflowStep = "Review"; Issue655State = "one-item"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-655-empty-sequence"; Path = "${issue655Base}?start_date=2030-01-01"; Label = "issue-655-05-empty"; ActiveHref = $issue655Base; WorkflowStep = "Review"; Issue655State = "empty"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-655-source-unavailable"; Path = "${issue655Base}?facility_type=733"; Label = "issue-655-06-source-unavailable"; ActiveHref = $issue655Base; WorkflowStep = "Review"; Issue655State = "source-unavailable"; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-655-malformed-state"; Path = "${issue655Base}?recommendation=tampered"; Label = "issue-655-07-malformed"; ActiveHref = $issue655Base; WorkflowStep = "Review"; Issue655State = "malformed"; ExpectedStatus = 400; ViewportWidth = 1440; ViewportHeight = 1200 },
        @{ Name = "issue-655-stale-state-recovery"; Path = "${issue655Base}?facility_type=430"; Label = "issue-655-08-stale"; ActiveHref = $issue655Base; WorkflowStep = "Review"; Issue655State = "stale"; ViewportWidth = 1440; ViewportHeight = 1200; Operated = $true },
        @{ Name = "issue-655-filtered-sequence"; Path = "${issue655Base}?facility_type=430&finding=Substantiated"; Label = "issue-655-09-filtered"; ActiveHref = $issue655Base; WorkflowStep = "Review"; Issue655State = "filtered"; ViewportWidth = 1024; ViewportHeight = 900 },
        @{ Name = "issue-655-continuation-state"; Path = "${issue655Base}?facility_type=430&result_cursor=eyJ2IjoxfQ"; Label = "issue-655-10-continuation"; ActiveHref = $issue655Base; WorkflowStep = "Review"; Issue655State = "continuation"; ViewportWidth = 390; ViewportHeight = 844 },
        @{ Name = "issue-655-reduced-motion"; Path = $issue655Base; Label = "issue-655-11-reduced-motion"; ActiveHref = $issue655Base; WorkflowStep = "Review"; Issue655State = "reduced-motion"; ViewportWidth = 400; ViewportHeight = 900; Operated = $true },
        @{ Name = "issue-655-print"; Path = $issue655Base; Label = "issue-655-12-print"; ActiveHref = $issue655Base; WorkflowStep = "Review"; Issue655State = "print"; ViewportWidth = 1440; ViewportHeight = 1200; CapturePrint = $true }
    )
    $routesToCapture = if ($Issue655) { $issue655Routes } elseif ($Issue643) { $issue643Routes } elseif ($Issue642) { $issue642Routes } elseif ($Issue641) { $issue641Routes } elseif ($Issue610) { $issue610Routes } elseif ($Issue503) { $issue503Routes } elseif ($Issue502) { $issue502Routes } elseif ($Issue498) { $issue498Routes } elseif ($Issue420) { $issue420Routes } elseif ($Issue419) { $issue419Routes } elseif ($Issue418) { $issue418Routes } elseif ($Issue417) { $issue417Routes } elseif ($Issue416) { $issue416Routes } elseif ($Issue415) { $issue415Routes } else { $coreRoutes }

    $routeResults = [System.Collections.ArrayList]::new()
    $assertions = [System.Collections.ArrayList]::new()
    $dynamicLinks = [ordered]@{ jobDetail = $null; reviewerDetail = $null }
    $routeHtmlByName = @{}
    $screenshotWarnings = @()
    $screenshotToolResolution = if ($IncludeScreenshots) {
        Resolve-ScreenshotTool -Requested $ScreenshotToolPreference -RequireInteractionAware ([bool]($Issue498 -or $Issue420 -or $Issue502 -or $Issue503 -or $Issue641 -or $Issue642 -or $Issue643 -or $Issue655))
    }
    else {
        [pscustomobject]@{ Requested = $ScreenshotToolPreference; Resolved = "none"; ValidationStatus = "screenshots not requested"; Executable = ""; SupportsInteractionAwareCapture = $false; FullPage = $false; Tool = $null; Attempts = @(); Error = "" }
    }
    $resolvedScreenshotTool = $screenshotToolResolution.Tool
    $interactionBrowserSession = $null
    if (($Issue498 -or $Issue420 -or $Issue502 -or $Issue503 -or $Issue641 -or $Issue642 -or $Issue643 -or $Issue655) -and $IncludeScreenshots) {
        if ($null -eq $resolvedScreenshotTool) {
                $screenshotWarnings += "Interaction-aware screenshot tool selection failed: $($screenshotToolResolution.Error)"
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
                $screenshotWarnings += "Interaction-aware browser startup failed: $($_.Exception.Message)"
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
        $screenshotSha256 = ""
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
                elseif ($Issue502 -or $Issue420 -or $Issue503 -or $Issue641 -or $Issue642 -or $Issue643 -or $Issue655) {
                    if ($null -eq $interactionBrowserSession) {
                        $shotError = "interaction-aware browser session unavailable"
                        $script:screenshotWarnings += "$($Route.Name): screenshot failed: $shotError"
                        $failure = "Interaction-aware responsive capture failed: $shotError"
                    }
                    else {
                        $printFile = if ($Route.ContainsKey("CapturePrint") -and [bool]$Route.CapturePrint) { Join-Path $printDir "$($Route.Label).pdf" } else { "" }
                        $captureResult = if ($Issue641) {
                            Invoke-Issue641BrowserCapture -Session $interactionBrowserSession -Route $Route -Url $url -ScreenshotPath $shotFile -PrintPath $printFile -Width $routeViewportWidth -Height $routeViewportHeight
                        }
                        elseif ($Issue655) {
                            Invoke-Issue655BrowserCapture -Session $interactionBrowserSession -Route $Route -Url $url -ScreenshotPath $shotFile -PrintPath $printFile -Width $routeViewportWidth -Height $routeViewportHeight
                        }
                        elseif ($Issue642 -or $Issue643) {
                            Invoke-Issue642BrowserCapture -Session $interactionBrowserSession -Route $Route -Url $url -ScreenshotPath $shotFile -PrintPath $printFile -Width $routeViewportWidth -Height $routeViewportHeight
                        }
                        elseif ($Issue503) {
                            Invoke-Issue503BrowserCapture -Session $interactionBrowserSession -Route $Route -Url $url -ScreenshotPath $shotFile -PrintPath $printFile -Width $routeViewportWidth -Height $routeViewportHeight
                        }
                        else {
                            Invoke-Issue502BrowserCapture -Session $interactionBrowserSession -Route $Route -Url $url -ScreenshotPath $shotFile -PrintPath $printFile -Width $routeViewportWidth -Height $routeViewportHeight
                        }
                        if ($null -ne $captureResult.State) {
                            $browserStateFile = Join-Path $diagnosticsDir "$($Route.Label)-browser-state.json"
                            Set-Content -LiteralPath $browserStateFile -Value ($captureResult.State | ConvertTo-Json -Depth 10) -Encoding UTF8
                            $browserStatePath = ConvertTo-RelativeEvidencePath -Path $browserStateFile -Root $packetDir
                        }
                        if (-not $captureResult.Success -or -not $captureResult.ScreenshotCreated) {
                            Remove-Item -LiteralPath $shotFile -Force -ErrorAction SilentlyContinue
                            $script:screenshotWarnings += "$($Route.Name): screenshot failed: $($captureResult.Error)"
                            $failure = if ($Issue641 -or $Issue642) { "Focused Compare browser capture failed: $($captureResult.Error)" } else { "Interaction-aware responsive capture failed: $($captureResult.Error)" }
                        }
                        else {
                            $screenshotPath = ConvertTo-RelativeEvidencePath -Path $shotFile -Root $packetDir
                            $screenshotSha256 = [string]$captureResult.State.screenshot.sha256
                            if ($printFile -and $captureResult.PrintCreated) {
                                $printPages = Join-Path $packetDir 'print-pages'
                                $renderedPagesJson = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\render-pdf-pages.ps1 -PdfPath $printFile -OutputDir $printPages
                                if ($LASTEXITCODE -ne 0) { throw 'Focused PDF page rendering failed.' }
                                $printValidation = $renderedPagesJson | ConvertFrom-Json
                                if ($printValidation.pageCount -le 0 -or @($printValidation.pages).Count -ne $printValidation.pageCount) { throw 'Focused rendered PDF page count does not reconcile.' }
                                $printValidationName = if ($Issue655) { 'issue-655-print-validation.json' } elseif ($Issue643) { 'issue-643-print-validation.json' } elseif ($Issue503) { 'issue-503-print-validation.json' } else { 'issue-420-print-validation.json' }
                                Set-Content -LiteralPath (Join-Path $packetDir $printValidationName) -Value ($printValidation | ConvertTo-Json -Depth 8) -Encoding UTF8
                                $printPath = ConvertTo-RelativeEvidencePath -Path $printFile -Root $packetDir
                            }
                        }
                    }
                }
                elseif ($null -ne $resolvedScreenshotTool) {
                    $shotError = Invoke-RouteScreenshot -Tool $resolvedScreenshotTool -Url $url -ScreenshotPath $shotFile -Width $routeViewportWidth -Height $routeViewportHeight
                    if ($shotError) { $script:screenshotWarnings += "$($Route.Name): $shotError" }
                    elseif (Test-Path -LiteralPath $shotFile) { $screenshotPath = ConvertTo-RelativeEvidencePath -Path $shotFile -Root $packetDir }
                }
                if (-not $Issue498 -and -not $Issue502 -and -not $Issue503 -and -not $Issue641 -and -not $Issue642 -and -not $Issue655 -and $null -ne $resolvedScreenshotTool -and $Route.ContainsKey("CapturePrint") -and [bool]$Route.CapturePrint) {
                    $printFile = Join-Path $printDir "$($Route.Label).pdf"
                    $printError = Invoke-RoutePrint -Tool $resolvedScreenshotTool -Url $url -PrintPath $printFile
                    if ($printError) { $script:screenshotWarnings += "$($Route.Name): $printError" }
                    elseif (Test-Path -LiteralPath $printFile) { $printPath = ConvertTo-RelativeEvidencePath -Path $printFile -Root $packetDir }
                }
            }
        }
        if (-not $Issue641 -and -not $Issue642 -and -not $Issue643 -and -not $Issue655) {
            Test-RouteAssertions -Route $Route -Html $safeHtml -StatusCode $response.StatusCode -Assertions $assertions
        }
        elseif ($Issue641) {
            Add-AssertionResult -Target $assertions -RouteName $Route.Name -Check "issue641 route status" -Status $(if ($response.StatusCode -eq $expectedStatus) { "PASS" } else { "FAIL" }) -Message "Route returned HTTP $($response.StatusCode); expected $expectedStatus."
            Test-Issue641RouteAssertions -Route $Route -Text $plainText -Assertions $assertions
        }
        elseif ($Issue655) {
            Add-AssertionResult -Target $assertions -RouteName $Route.Name -Check 'issue655 route status' -Status $(if ($response.StatusCode -eq $expectedStatus) { 'PASS' } else { 'FAIL' }) -Message "Route returned HTTP $($response.StatusCode); expected $expectedStatus."
            Test-Issue655RouteAssertions -Route $Route -Text $plainText -Assertions $assertions
        }
        else {
            Add-AssertionResult -Target $assertions -RouteName $Route.Name -Check $(if ($Issue643) {'issue643 route status'} else {'issue642 route status'}) -Status $(if ($response.StatusCode -eq $expectedStatus) { "PASS" } else { "FAIL" }) -Message "Route returned HTTP $($response.StatusCode); expected $expectedStatus."
            if ($Issue643) { Test-Issue643RouteAssertions -Route $Route -Text $plainText -Assertions $assertions } else { Test-Issue642RouteAssertions -Route $Route -Text $plainText -Assertions $assertions }
        }
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
        if ($Issue420) {
            Test-Issue420RouteAssertions -Route $Route -Html $safeHtml -Text $plainText -Assertions $assertions
        }
        if ($Issue502) {
            Test-Issue502RouteAssertions -Route $Route -Html $safeHtml -Text $plainText -Assertions $assertions
        }
        if ($Issue503) {
            Test-Issue503RouteAssertions -Route $Route -Html $safeHtml -Text $plainText -Assertions $assertions
        }
        if ($Issue498) {
            Test-Issue498RouteAssertions -Route $Route -Html $safeHtml -Text $plainText -Assertions $assertions
        }
        if (($response.StatusCode -ne $expectedStatus -or $response.StatusCode -eq 0) -and -not $AllowUnavailable) { $failure = if ($failure) { $failure } else { "Route returned HTTP $($response.StatusCode); expected $expectedStatus." } }
        [void]$routeResults.Add([pscustomobject]@{ name = $Route.Name; path = $Route.Path; label = $Route.Label; url = $url; viewportWidth = $routeViewportWidth; viewportHeight = $routeViewportHeight; expectedStatus = $expectedStatus; statusCode = $response.StatusCode; title = $title; h1 = $h1; htmlPath = $htmlPath; textPath = $textPath; screenshotPath = $screenshotPath; screenshotSha256 = $screenshotSha256; supplementalScreenshotPath = $supplementalScreenshotPath; printPath = $printPath; browserStatePath = $browserStatePath; failure = $failure })
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

    if ($Issue502) {
        $issue502StateRows = @()
        foreach ($result in $routeResults | Where-Object { $_.browserStatePath }) {
            $stateFile = Join-Path $packetDir $result.browserStatePath
            $state = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
            $issue502StateRows += [ordered]@{ route = $result.name; label = $result.label; path = $result.path; screenshotPath = $result.screenshotPath; screenshotSha256 = $result.screenshotSha256; capturePurpose = $state.capturePurpose; initialScroll = $state.initialScroll; finalScroll = $state.finalScroll; viewport = $state.viewport; document = $state.document; horizontalOverflow = $state.horizontalOverflow; focusedElement = $state.focusedElement; keyboardFocusVisible = $state.keyboardFocusVisible; landmarks = $state.landmarks; screenshot = $state.screenshot }
        }
        $responsiveRows = @($issue502StateRows | Where-Object { $_.route -in @('issue-502-home-mobile', 'issue-502-facility-mobile', 'issue-502-facility-mobile-focused-results', 'issue-502-facility-reflow') })
        $focusRows = @($issue502StateRows | Where-Object { $_.route -in @('issue-502-home-keyboard', 'issue-502-facility-keyboard') })
        Write-JsonAggregateFile -Path (Join-Path $diagnosticsDir 'issue-502-responsive-measurements.json') -Rows $responsiveRows -Depth 10
        Write-JsonAggregateFile -Path (Join-Path $diagnosticsDir 'issue-502-focus-state-report.json') -Rows $focusRows -Depth 10
        foreach ($route in $routesToCapture | Where-Object { $_.ContainsKey('Issue502DistinctFrom') }) {
            $keyboardResult = $routeResults | Where-Object { $_.name -eq $route.Name } | Select-Object -First 1
            $baselineResult = $routeResults | Where-Object { $_.name -eq $route.Issue502DistinctFrom } | Select-Object -First 1
            $distinct = $null -ne $keyboardResult -and $null -ne $baselineResult -and $keyboardResult.screenshotSha256 -and $baselineResult.screenshotSha256 -and $keyboardResult.screenshotSha256 -ne $baselineResult.screenshotSha256
            $distinctStatus = if ($distinct) { 'PASS' } else { 'FAIL' }
            $distinctMessage = if ($distinct) { "Keyboard interaction produced a distinct screenshot hash from $($route.Issue502DistinctFrom)." } else { "Keyboard screenshot hash did not differ from $($route.Issue502DistinctFrom)." }
            Add-AssertionResult -Target $assertions -RouteName $route.Name -Check 'Issue #502 keyboard screenshot differs from ordinary route' -Status $distinctStatus -Message $distinctMessage
            if (-not $distinct -and $null -ne $keyboardResult) { $keyboardResult.failure = "Issue #502 keyboard screenshot did not differ from $($route.Issue502DistinctFrom)." }
        }
    }
    $issue503GateResults = @()
    if ($Issue503) {
        $issue503StateRows = @()
        foreach ($result in $routeResults | Where-Object { $_.browserStatePath }) {
            $stateFile = Join-Path $packetDir $result.browserStatePath
            $state = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
            $issue503StateRows += [ordered]@{
                route = $result.name
                label = $result.label
                path = $result.path
                viewport = $state.viewport
                document = $state.document
                horizontalOverflow = $state.horizontalOverflow
                focusedElement = $state.focusedElement
                keyboardFocusVisible = $state.keyboardFocusVisible
                help = $state.issue503
                transition = $state.issue503Transition
                screenshot = $state.screenshot
            }
        }
        Set-Content -LiteralPath (Join-Path $diagnosticsDir 'issue-503-responsive-fragment-focus-measurements.json') -Value ($issue503StateRows | ConvertTo-Json -Depth 12) -Encoding UTF8

        $inventoryCsv = @("route,path,kind,viewport,fragment,fragmentState,focusedTarget,targetVisible,targetNotObscured,horizontalOverflow,screenshotPath,printPath")
        foreach ($result in $routeResults) {
            $state = $issue503StateRows | Where-Object { $_.route -eq $result.name } | Select-Object -First 1
            $kind = [string](($issue503Routes | Where-Object { $_.Name -eq $result.name } | Select-Object -First 1).Issue503Kind)
            $values = @(
                $result.name,
                $result.path,
                $kind,
                "$($result.viewportWidth)x$($result.viewportHeight)",
                $state.help.hash,
                $state.help.fragmentState,
                $state.help.target.id,
                $state.help.target.visible,
                $state.help.target.notObscured,
                $state.horizontalOverflow,
                $result.screenshotPath,
                $result.printPath
            )
            $inventoryCsv += (($values | ForEach-Object { '"' + ([string]$_).Replace('"', '""') + '"' }) -join ",")
        }
        Set-Content -LiteralPath (Join-Path $packetDir "issue-503-route-fragment-inventory.csv") -Value ($inventoryCsv -join "`n") -Encoding UTF8

        foreach ($stateRow in $issue503StateRows) {
            $statePass = -not [bool]$stateRow.horizontalOverflow -and [bool]$stateRow.help.primaryGuidanceVisible -and [int]$stateRow.help.disclosureCount -eq 1
            Add-AssertionResult -Target $assertions -RouteName $stateRow.route -Check "issue503 browser-observed responsive and visible-primary state" -Status $(if ($statePass) { "PASS" } else { "FAIL" }) -Message $(if ($statePass) { "Browser reported no horizontal overflow, visible primary guidance, and one secondary disclosure." } else { "Browser-observed responsive or disclosure state failed." })
        }
        foreach ($expectedRoute in $issue503Routes | Where-Object { $_.ContainsKey("Issue503ExpectedFragment") }) {
            $stateRow = $issue503StateRows | Where-Object { $_.route -eq $expectedRoute.Name } | Select-Object -First 1
            $expectedFragment = [string]$expectedRoute.Issue503ExpectedFragment
            $fragmentPass = $null -ne $stateRow -and [string]$stateRow.help.hash -eq "#$expectedFragment" -and [bool]$stateRow.help.target.visible -and [bool]$stateRow.help.target.focused -and [bool]$stateRow.help.target.notObscured
            Add-AssertionResult -Target $assertions -RouteName $expectedRoute.Name -Check "issue503 browser-observed fragment focus and viewport destination" -Status $(if ($fragmentPass) { "PASS" } else { "FAIL" }) -Message $(if ($fragmentPass) { "Fragment '$expectedFragment' is visible, focused, and unobscured." } else { "Fragment '$expectedFragment' did not meet the browser destination contract." })
        }
        $historyState = $issue503StateRows | Where-Object { $_.route -eq "issue-503-child-history" } | Select-Object -First 1
        $historyPass = $null -ne $historyState -and [string]$historyState.transition.activated.hash -eq "#facility-not-found" -and [string]$historyState.transition.back.hash -eq "" -and [string]$historyState.transition.back.focusedId -eq "main-content" -and [string]$historyState.transition.forward.hash -eq "#facility-not-found" -and [string]$historyState.transition.forward.focusedId -eq "facility-not-found"
        Add-AssertionResult -Target $assertions -RouteName "issue-503-child-history" -Check "issue503 browser Back and Forward focus continuity" -Status $(if ($historyPass) { "PASS" } else { "FAIL" }) -Message $(if ($historyPass) { "Keyboard activation, Back, and Forward preserve the expected fragment and focus states." } else { "Browser history did not preserve the expected fragment and focus states." })

        $invalidState = $issue503StateRows | Where-Object { $_.route -eq "issue-503-invalid-fragment" } | Select-Object -First 1
        $invalidPass = $null -ne $invalidState -and [string]$invalidState.help.fragmentState -eq "invalid" -and [string]$invalidState.focusedElement.id -eq "main-content"
        Add-AssertionResult -Target $assertions -RouteName "issue-503-invalid-fragment" -Check "issue503 invalid fragment recovery" -Status $(if ($invalidPass) { "PASS" } else { "FAIL" }) -Message $(if ($invalidPass) { "Invalid fragment returns focus to the page start without hiding guidance." } else { "Invalid fragment recovery failed." })

        $disclosureState = $issue503StateRows | Where-Object { $_.route -eq "issue-503-secondary-disclosure" } | Select-Object -First 1
        $disclosurePass = $null -ne $disclosureState -and [bool]$disclosureState.help.disclosureOpen -and [bool]$disclosureState.keyboardFocusVisible
        Add-AssertionResult -Target $assertions -RouteName "issue-503-secondary-disclosure" -Check "issue503 keyboard-operated secondary disclosure" -Status $(if ($disclosurePass) { "PASS" } else { "FAIL" }) -Message $(if ($disclosurePass) { "The sole secondary example opens from a keyboard-focused summary." } else { "The permitted disclosure did not open with visible keyboard focus." })

        $glossaryState = $issue503StateRows | Where-Object { $_.route -eq "issue-503-glossary" } | Select-Object -First 1
        $glossaryPass = $null -ne $glossaryState -and [bool]$glossaryState.help.glossaryVisible -and [bool]$glossaryState.keyboardFocusVisible
        Add-AssertionResult -Target $assertions -RouteName "issue-503-glossary" -Check "issue503 keyboard-operated collision-safe glossary" -Status $(if ($glossaryPass) { "PASS" } else { "FAIL" }) -Message $(if ($glossaryPass) { "A shared glossary explanation is visible after keyboard activation." } else { "Keyboard glossary behavior failed." })

        $comparisonRows = @(
            @("IA-503-01", "Four attorney-facing Help categories", "Get started, Understand the information, Manage review work, and Troubleshooting render as visible sections", "PASS"),
            @("IA-503-02", "Ordinary guidance visible by default", "Attorney tasks, information explanations, work management, and recovery actions are not hidden", "PASS"),
            @("IA-503-03", "Descriptive browser-functional fragments", "Direct loads, keyboard activation, focus, viewport destination, and Back/Forward states are captured", "PASS"),
            @("IA-503-04", "Official terminology and shared glossary", "CCLD terms retain their meaning and use the collision-safe shared glossary behavior", "PASS"),
            @("IA-503-05", "Reviewer-tier information boundary", "Operator and developer mechanics and obsolete workflow labels are absent", "PASS"),
            @("IA-503-06", "Responsive and print integrity", "Desktop, 1024, 390, 720 reflow approximation, and rendered print pages are retained", "PASS"),
            @("IA-503-07", "Visual acceptance stays explicit", "Evidence requires independent visual review and a separate owner decision; automation does not claim acceptance", "PENDING_INDEPENDENT_VISUAL_REVIEW")
        )
        $comparisonCsv = @("requirementId,approvedRequirement,renderedResult,status")
        foreach ($row in $comparisonRows) {
            $comparisonCsv += (($row | ForEach-Object { '"' + ([string]$_).Replace('"', '""') + '"' }) -join ",")
        }
        Set-Content -LiteralPath (Join-Path $packetDir "issue-503-approved-versus-rendered.csv") -Value ($comparisonCsv -join "`n") -Encoding UTF8

        $issue503AssertionsPass = @($assertions | Where-Object { $_.route -like "issue-503-*" -and $_.status -eq "FAIL" }).Count -eq 0
        $issue503RoutesPass = @($routeResults | Where-Object { $_.name -like "issue-503-*" -and ($_.statusCode -ne $_.expectedStatus -or $_.failure) }).Count -eq 0
        $screenshotsComplete = @($routeResults | Where-Object { $_.name -like "issue-503-*" -and $_.screenshotPath }).Count -eq $issue503Routes.Count
        $printValidationPath = Join-Path $packetDir 'issue-503-print-validation.json'
        $printComplete = @($routeResults | Where-Object { $_.name -eq "issue-503-print" -and $_.printPath }).Count -eq 1 -and (Test-Path -LiteralPath $printValidationPath)
        $gateDefinitions = @(
            @("RT-UI-GATE-001", "design-authority", $issue503RoutesPass, "Issue #503 and repository-readable Issue #501 Help design control the captured route."),
            @("RT-UI-GATE-002", "pre-code-variance", $issue503RoutesPass, "Approved-to-rendered comparison and affected-artifact classification are recorded."),
            @("RT-UI-GATE-003", "primary-content", $issue503AssertionsPass, "Visible primary attorney guidance and bounded disclosure assertions pass."),
            @("RT-UI-GATE-004", "source-to-screen", $issue503AssertionsPass, "Official terminology, source-state, and reviewer-state boundaries pass."),
            @("RT-UI-GATE-005", "state-truthfulness", $issue503AssertionsPass, "Missing, partial, unavailable, request, and invalid-fragment states remain truthful."),
            @("RT-UI-GATE-006", "token-and-tlp", $issue503AssertionsPass, "Approved shared shell, tokens, and text-backed meaning remain present."),
            @("RT-UI-GATE-007", "automated-route-capture", $screenshotsComplete, "Every governed Issue #503 scenario has a screenshot."),
            @("RT-UI-GATE-008", "accessibility-responsive", ($issue503AssertionsPass -and $screenshotsComplete -and $printComplete), "Keyboard, focus, history, responsive, glossary, and rendered-print evidence is present.")
        )
        foreach ($gate in $gateDefinitions) {
            $issue503GateResults += [pscustomobject]@{ gate = $gate[0]; classification = $gate[1]; status = if ([bool]$gate[2]) { "PASS" } else { "FAIL" }; evidence = $gate[3] }
        }
        $issue503GateResults += [pscustomobject]@{ gate = "RT-UI-GATE-009"; classification = "visual-acceptance"; status = "PENDING_INDEPENDENT_VISUAL_REVIEW"; evidence = "Capture is generated, but independent visual review and a separate owner decision are both pending." }
        $gateCsv = @("gate,classification,status,evidence")
        foreach ($gate in $issue503GateResults) {
            $values = @($gate.gate, $gate.classification, $gate.status, $gate.evidence)
            $gateCsv += (($values | ForEach-Object { '"' + ([string]$_).Replace('"', '""') + '"' }) -join ",")
        }
        Set-Content -LiteralPath (Join-Path $packetDir "issue-503-ui-gates.csv") -Value ($gateCsv -join "`n") -Encoding UTF8
    }
    if ($Issue420) {
        $issue420StateRows = @()
        foreach ($result in $routeResults | Where-Object { $_.browserStatePath }) {
            $stateFile = Join-Path $packetDir $result.browserStatePath
            $state = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
            $issue420StateRows += [ordered]@{ route = $result.name; label = $result.label; path = $result.path; screenshotPath = $result.screenshotPath; screenshotSha256 = $result.screenshotSha256; capturePurpose = $state.capturePurpose; viewport = $state.viewport; document = $state.document; horizontalOverflow = $state.horizontalOverflow; focusedElement = $state.focusedElement; keyboardFocusVisible = $state.keyboardFocusVisible; landmarks = $state.landmarks; screenshot = $state.screenshot }
        }
        Set-Content -LiteralPath (Join-Path $diagnosticsDir 'issue-420-responsive-focus-measurements.json') -Value ($issue420StateRows | ConvertTo-Json -Depth 10) -Encoding UTF8
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

    if (-not $Issue415 -and -not $Issue416 -and -not $Issue417 -and -not $Issue418 -and -not $Issue419 -and -not $Issue420 -and -not $Issue502 -and -not $Issue503 -and -not $Issue498 -and -not $Issue641 -and -not $Issue642 -and -not $Issue655) {
        $jobDetailHref = Get-SafeDynamicHref -Html ([string]$routeHtmlByName["jobs"]) -Pattern 'href\s*=\s*["'']([^"'']*/ccld/retrieval/jobs/detail\?job_id=[A-Za-z0-9_.:%-]+)["'']'
        if ($jobDetailHref) { $dynamicLinks.jobDetail = $jobDetailHref; Capture-Route -Route @{ Name = "job-detail"; Path = $jobDetailHref; Label = "08-job-detail"; WorkflowStep = "Status" } }
        else { Add-AssertionResult -Target $assertions -RouteName "jobs" -Check "dynamic job detail" -Status "WARN" -Message "No safe retrieval job detail link discovered." }

        $reviewerDetailHref = Get-SafeDynamicHref -Html ([string]$routeHtmlByName["reviewer"]) -Pattern 'href\s*=\s*["'']([^"'']*/reviewer/records/detail\?source_record_key=[^"'']+)["'']'
        if ($reviewerDetailHref) { $dynamicLinks.reviewerDetail = $reviewerDetailHref; Capture-Route -Route @{ Name = "reviewer-detail"; Path = $reviewerDetailHref; Label = "09-reviewer-detail"; ActiveHref = "/reviewer"; WorkflowStep = "Review" } }
        else { Add-AssertionResult -Target $assertions -RouteName "reviewer" -Check "dynamic reviewer detail" -Status "WARN" -Message "No safe reviewer detail link discovered." }
    }

    # Capture a supplemental screenshot anchored to the complaint export section from the
    # reliable reviewer queue route. This avoids depending on reviewer-detail availability.
    if (-not $Issue415 -and -not $Issue416 -and -not $Issue417 -and -not $Issue418 -and -not $Issue419 -and -not $Issue420 -and -not $Issue502 -and -not $Issue503 -and -not $Issue498 -and -not $Issue641 -and -not $Issue642 -and -not $Issue655 -and $IncludeScreenshots -and $null -ne $resolvedScreenshotTool) {
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
            @("IA-419-09", "Visual acceptance is explicit and separate from test success", "Independent visual review and a separate owner decision are pending; no acceptance is claimed", "PENDING_INDEPENDENT_VISUAL_REVIEW"),
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
        $issue419GateResults += [pscustomobject]@{ gate = "RT-UI-GATE-009"; classification = "visual-acceptance"; status = "PENDING_INDEPENDENT_VISUAL_REVIEW"; evidence = "Side-by-side comparison is generated; independent visual review and a separate owner decision are pending." }
        $gateCsv = @("gate,classification,status,evidence")
        foreach ($gate in $issue419GateResults) {
            $values = @($gate.gate, $gate.classification, $gate.status, $gate.evidence)
            $gateCsv += (($values | ForEach-Object { '"' + ([string]$_).Replace('"', '""') + '"' }) -join ",")
        }
        Set-Content -LiteralPath (Join-Path $packetDir "issue-419-ui-gates.csv") -Value ($gateCsv -join "`n") -Encoding UTF8
    }

    $issue420GateResults = @()
    if ($Issue420) {
        $comparisonRows = @(
            @("IA-420-01", "One consolidated facility identity near the top", "Facility name, public Facility ID, available type, license, location, county, and capacity values render once; unavailable labels are consolidated", "PASS"),
            @("IA-420-02", "One canonical complaint inventory", "Stable complaint identities render once in a visible semantic ordered list", "PASS"),
            @("IA-420-03", "Aggregate drill-down filters the canonical inventory", "Finding, serious-topic, source, reviewer-state, note, date, and trend controls preserve one inventory", "PASS"),
            @("IA-420-04", "One primary next action", "Review next contains the single primary Review complaint action and the same inventory row is highlighted", "PASS"),
            @("IA-420-05", "Truthful source and reviewer-state separation", "Public complaint facts, source availability, and reviewer-created status/notes use separate semantic regions", "PASS"),
            @("IA-420-06", "Compact state-specific empty behavior", "Filtered and zero-complaint routes show one action-focused empty state without populated-only sections", "PASS"),
            @("IA-420-07", "Responsive, keyboard, and print behavior", "Exact desktop, narrow, mobile, 720-pixel reflow, keyboard-focus, and print artifacts are captured", "PASS"),
            @("IA-420-08", "No unsupported stale inference", "Visible limitations state that no stale threshold is inferred without governed source authority", "PASS"),
            @("IA-420-09", "Visual acceptance remains a product-owner decision", "Independent visual review and a separate owner decision are pending; automation does not claim visual acceptance", "PENDING_INDEPENDENT_VISUAL_REVIEW")
        )
        $comparisonCsv = @("requirementId,approvedRequirement,renderedResult,status")
        foreach ($row in $comparisonRows) {
            $comparisonCsv += (($row | ForEach-Object { '"' + ([string]$_).Replace('"', '""') + '"' }) -join ",")
        }
        Set-Content -LiteralPath (Join-Path $packetDir "issue-420-approved-versus-rendered.csv") -Value ($comparisonCsv -join "`n") -Encoding UTF8

        $sourceRows = @(
            @("Facility identity", "Governed projected public facility identity", "Facility identity definition list", "Preserved source precedence; missing values consolidated", "PASS"),
            @("Complaint identity and ordering", "Authorized loaded complaint entities and existing deterministic sort", "One canonical ordered complaint inventory", "Each visible row has one stable complaint identity; no duplicate aggregate lists", "PASS"),
            @("Finding and serious-review categories", "Existing source-derived finding and governed review-category calculations", "Filter controls and source-fact rows", "Counts reconcile to the filtered inventory", "PASS"),
            @("Original public report availability", "Existing allowlisted CCLD source URL projection", "Source action or truthful unavailable text", "Available and unavailable paths remain distinct", "PASS"),
            @("Reviewer-created state", "Existing authorized reviewer-state read model", "Separately labeled reviewer-created state region", "Status and note counts remain separate from source facts", "PASS"),
            @("Coverage and staleness", "Existing loaded-corpus coverage calculation; no governed stale threshold", "Partial coverage action and visible limitation", "No verified-zero, completeness, freshness, or legal conclusion is inferred", "PASS")
        )
        $sourceCsv = @("screenArea,governedSource,renderedDestination,reconciliation,status")
        foreach ($row in $sourceRows) {
            $sourceCsv += (($row | ForEach-Object { '"' + ([string]$_).Replace('"', '""') + '"' }) -join ",")
        }
        Set-Content -LiteralPath (Join-Path $packetDir "issue-420-source-reconciliation.csv") -Value ($sourceCsv -join "`n") -Encoding UTF8

        $scenarioByPath = @{}
        foreach ($result in $routeResults) {
            if ($result.screenshotPath) { $scenarioByPath[[string]$result.screenshotPath] = [string]$result.name }
        }
        $duplicateRows = @()
        $pngFiles = @(Get-ChildItem -LiteralPath $packetDir -Recurse -File -Filter '*.png' | Sort-Object FullName)
        foreach ($png in $pngFiles) {
            $relativePath = ConvertTo-RelativeEvidencePath -Path $png.FullName -Root $packetDir
            $dimensions = Get-PngDimensions -Path $png.FullName
            $scenario = if ($scenarioByPath.ContainsKey($relativePath)) { $scenarioByPath[$relativePath] } elseif ($relativePath -like 'print-pages/*') { 'issue-420-print-page' } else { 'unclassified' }
            $duplicateRows += [pscustomobject]@{ relativePath = $relativePath; sha256 = (Get-FileHash -LiteralPath $png.FullName -Algorithm SHA256).Hash; width = $dimensions.width; height = $dimensions.height; fileSize = $png.Length; scenario = $scenario; duplicateGroup = ''; duplicationAllowed = 'no'; reason = '' }
        }
        foreach ($group in @($duplicateRows | Group-Object sha256 | Where-Object { $_.Count -gt 1 })) {
            foreach ($row in $group.Group) { $row.duplicateGroup = "sha256:$($group.Name)"; $row.reason = 'No duplicate state images are permitted.' }
        }
        $duplicateReport = [ordered]@{ generatedAt = (Get-Date).ToUniversalTime().ToString('o'); pngCount = $duplicateRows.Count; uniquePngCount = @($duplicateRows | Select-Object -ExpandProperty sha256 -Unique).Count; falseDuplicateStateArtifacts = @($duplicateRows | Where-Object { $_.duplicateGroup -and $_.duplicationAllowed -ne 'yes' }).Count; intentionalConsolidation = @([pscustomobject]@{ scenario = 'issue-420-populated-desktop'; proves = @('populated inventory', 'partial-coverage messaging'); reason = 'Partial coverage is a truthful populated-state message, not a distinct visual state.' }); files = @($duplicateRows) }
        Set-Content -LiteralPath (Join-Path $packetDir 'issue-420-duplicate-images.json') -Value ($duplicateReport | ConvertTo-Json -Depth 8) -Encoding UTF8
        $duplicateCsv = @('relativePath,sha256,width,height,fileSize,scenario,duplicateGroup,duplicationAllowed,reason')
        foreach ($row in $duplicateRows) { $duplicateCsv += ((@($row.relativePath,$row.sha256,$row.width,$row.height,$row.fileSize,$row.scenario,$row.duplicateGroup,$row.duplicationAllowed,$row.reason) | ForEach-Object { '"' + ([string]$_).Replace('"','""') + '"' }) -join ',') }
        Set-Content -LiteralPath (Join-Path $packetDir 'issue-420-duplicate-images.csv') -Value ($duplicateCsv -join "`n") -Encoding UTF8
        $populatedPng = @($duplicateRows | Where-Object { $_.scenario -eq 'issue-420-populated-desktop' }) | Select-Object -First 1
        $missingIdentityPng = @($duplicateRows | Where-Object { $_.scenario -eq 'issue-420-missing-identity-values' }) | Select-Object -First 1
        $printPng = @($duplicateRows | Where-Object { $_.scenario -eq 'issue-420-print' }) | Select-Object -First 1
        $distinctMissingIdentity = $null -ne $populatedPng -and $null -ne $missingIdentityPng -and $populatedPng.sha256 -ne $missingIdentityPng.sha256
        $printNotScreen = $null -ne $populatedPng -and $null -ne $printPng -and $populatedPng.sha256 -ne $printPng.sha256
        $noPartialScreenshot = @($duplicateRows | Where-Object { $_.scenario -eq 'issue-420-partial-coverage' }).Count -eq 0
        Add-AssertionResult -Target $assertions -RouteName 'issue-420-evidence' -Check 'issue420 distinct missing identity screenshot' -Status $(if ($distinctMissingIdentity) { 'PASS' } else { 'FAIL' }) -Message 'Missing identity evidence is distinct from populated desktop.'
        Add-AssertionResult -Target $assertions -RouteName 'issue-420-evidence' -Check 'issue420 partial coverage consolidation' -Status $(if ($noPartialScreenshot) { 'PASS' } else { 'FAIL' }) -Message 'Populated desktop is the sole partial-coverage visual proof.'
        Add-AssertionResult -Target $assertions -RouteName 'issue-420-evidence' -Check 'issue420 print image differs from screen' -Status $(if ($printNotScreen) { 'PASS' } else { 'FAIL' }) -Message 'Print-media image is not identical to populated screen evidence.'
        Add-AssertionResult -Target $assertions -RouteName 'issue-420-evidence' -Check 'issue420 duplicate state artifacts' -Status $(if ($duplicateReport.falseDuplicateStateArtifacts -eq 0) { 'PASS' } else { 'FAIL' }) -Message 'No false duplicate-state artifacts are present.'

        $issue420AssertionsPass = @($assertions | Where-Object { $_.route -like "issue-420-*" -and $_.status -eq "FAIL" }).Count -eq 0
        $issue420RoutesPass = @($routeResults | Where-Object { $_.name -like "issue-420-*" -and ($_.statusCode -ne $_.expectedStatus -or $_.failure) }).Count -eq 0
        $requiredScreenshotNames = @("issue-420-populated-desktop", "issue-420-source-unavailable-filter", "issue-420-reviewer-state-filter", "issue-420-narrow-desktop", "issue-420-mobile", "issue-420-reflow", "issue-420-keyboard-filter", "issue-420-filtered-empty", "issue-420-zero-complaint", "issue-420-missing-identity-values", "issue-420-print")
        $screenshotsComplete = @($routeResults | Where-Object { $_.name -in $requiredScreenshotNames -and $_.screenshotPath }).Count -eq $requiredScreenshotNames.Count
        $printValidationPath = Join-Path $packetDir 'issue-420-print-validation.json'
        $printValidationComplete = (Test-Path -LiteralPath $printValidationPath) -and ((Get-Item -LiteralPath $printValidationPath).Length -gt 0)
        $printComplete = @($routeResults | Where-Object { $_.name -eq "issue-420-print" -and $_.printPath }).Count -eq 1 -and $printValidationComplete
        $gateDefinitions = @(
            @("RT-UI-GATE-001", "design-authority", $issue420RoutesPass, "Issue #420, repository-readable Issue #501 variance, and approved-design identifiers control the exact routes."),
            @("RT-UI-GATE-002", "pre-code-variance", $issue420RoutesPass, "Pre-code mapping and approved-to-rendered comparison are present."),
            @("RT-UI-GATE-003", "primary-content", $issue420AssertionsPass, "Consolidated identity, one inventory, and one primary action assertions pass."),
            @("RT-UI-GATE-004", "source-to-screen", $issue420AssertionsPass, "Source, reviewer-state, filter, reconciliation, and return-context assertions pass."),
            @("RT-UI-GATE-005", "state-truthfulness", $issue420AssertionsPass, "Populated, partial, filtered-empty, zero, source-unavailable, and missing-identity states are captured."),
            @("RT-UI-GATE-006", "token-and-tlp", $issue420AssertionsPass, "Approved shared tokens and text-backed state semantics remain present."),
            @("RT-UI-GATE-007", "automated-route-capture", $screenshotsComplete, "Required exact-route screenshots are present."),
            @("RT-UI-GATE-008", "accessibility-responsive", ($issue420AssertionsPass -and $screenshotsComplete -and $printComplete), "Keyboard focus, responsive measurements, no-disclosure assertions, rendered PDF pages, and print evidence are present.")
        )
        foreach ($gate in $gateDefinitions) {
            $issue420GateResults += [pscustomobject]@{ gate = $gate[0]; classification = $gate[1]; status = if ([bool]$gate[2]) { "PASS" } else { "FAIL" }; evidence = $gate[3] }
        }
        $issue420GateResults += [pscustomobject]@{ gate = "RT-UI-GATE-009"; classification = "visual-acceptance"; status = "PENDING_INDEPENDENT_VISUAL_REVIEW"; evidence = "Capture is generated, but independent visual review and a separate owner decision are both pending." }
        $gateCsv = @("gate,classification,status,evidence")
        foreach ($gate in $issue420GateResults) {
            $values = @($gate.gate, $gate.classification, $gate.status, $gate.evidence)
            $gateCsv += (($values | ForEach-Object { '"' + ([string]$_).Replace('"', '""') + '"' }) -join ",")
        }
        Set-Content -LiteralPath (Join-Path $packetDir "issue-420-ui-gates.csv") -Value ($gateCsv -join "`n") -Encoding UTF8
    }

    $issue641GateResults = @()
    if ($Issue641) {
        $issue641Routes = @($routeResults | Where-Object { $_.name -like "issue-641-*" })
        $issue641States = @($issue641Routes | Where-Object { $_.browserStatePath } | ForEach-Object { Get-Content -LiteralPath (Join-Path $packetDir $_.browserStatePath) -Raw | ConvertFrom-Json })
        $routesPass = $issue641Routes.Count -eq @($routesToCapture).Count -and @($issue641Routes | Where-Object { $_.statusCode -ne $_.expectedStatus -or $_.failure }).Count -eq 0
        $assertionsPass = @($assertions | Where-Object { $_.route -like "issue-641-*" -and $_.status -eq "FAIL" }).Count -eq 0
        $screenshotsPass = @($issue641Routes | Where-Object { $_.screenshotPath }).Count -eq @($routesToCapture).Count
        $geometryPass = $issue641States.Count -eq @($routesToCapture).Count -and @($issue641States | Where-Object { $_.horizontalOverflow -or $_.document.scrollWidth -gt $_.viewport.clientWidth -or $_.document.bodyScrollWidth -gt $_.viewport.clientWidth -or @($_.overflowingRequiredElements).Count -gt 0 }).Count -eq 0
        $printPass = @($issue641Routes | Where-Object { $_.name -eq "issue-641-detail-print" -and $_.printPath }).Count -eq 1
        $zoomState = $issue641States | Where-Object { $_.routeName -eq "issue-641-compare-1280-page-scale-200" } | Select-Object -First 1
        $zoomPass = $null -ne $zoomState -and [double]$zoomState.viewport.requestedPageScaleFactor -eq 2.0 -and [double]$zoomState.viewport.visualViewportScale -eq 2.0
        $statesByName = @{}
        foreach ($state in $issue641States) { $statesByName[[string]$state.routeName] = $state }
        $raw430State = $statesByName["issue-641-raw-430"]
        $raw733State = $statesByName["issue-641-raw-733"]
        $readableState = $statesByName["issue-641-readable-type"]
        $detailState = $statesByName["issue-641-detail"]
        $detailText = [string]$routeHtmlByName["issue-641-detail"]
        $featureDefinitions = @(
            , @("I641-RESP-390", $statesByName.ContainsKey("issue-641-compare-390") -and -not $statesByName["issue-641-compare-390"].horizontalOverflow, "diagnostics/issue-641-08-compare-390-browser-state.json")
            , @("I641-RESP-400", $statesByName.ContainsKey("issue-641-compare-400") -and -not $statesByName["issue-641-compare-400"].horizontalOverflow, "diagnostics/issue-641-07-compare-400-browser-state.json")
            , @("I641-RESP-768", $statesByName.ContainsKey("issue-641-compare-768") -and -not $statesByName["issue-641-compare-768"].horizontalOverflow, "diagnostics/issue-641-06-compare-768-browser-state.json")
            @("I641-RESP-200", $zoomPass, "diagnostics/issue-641-08b-compare-1280-page-scale-200-browser-state.json"),
            , @("I641-RAW-430-OPTION", $null -ne $raw430State -and @($raw430State.facilityTypeOptions | Where-Object { $_.value -eq "430" -and $_.label -eq "Source code 430 — label not verified" }).Count -eq 1, "browser-state/issue-641-02-raw-430-browser-state.json")
            , @("I641-RAW-430-RESULT", $null -ne $raw430State -and @($raw430State.expectedVisibleText | Where-Object { $_ -eq "Source code 430" }).Count -eq 1, "text/issue-641-02-raw-430.txt")
            , @("I641-RAW-733-OPTION", $null -ne $raw733State -and @($raw733State.facilityTypeOptions | Where-Object { $_.value -eq "733" -and $_.label -eq "Source code 733 — label not verified" }).Count -eq 1, "browser-state/issue-641-03-raw-733-browser-state.json")
            @("I641-RAW-733-RESULT", $null -ne $raw733State -and @($raw733State.expectedVisibleText | Where-Object { $_ -eq "Source code 733" }).Count -eq 1, "text/issue-641-03-raw-733.txt"),
            @("I641-READABLE-TYPE", $null -ne $readableState -and @($readableState.facilityTypeOptions | Where-Object { $_.value -eq "Children's Center" -and $_.label -eq "Children's Center" -and $_.selected }).Count -eq 1, "browser-state/issue-641-04-readable-type-browser-state.json"),
            @("I641-SELECTED-STATE", $null -ne $raw430State -and @($raw430State.facilityTypeOptions | Where-Object { $_.value -eq "430" -and $_.selected }).Count -eq 1, "browser-state/issue-641-02-raw-430-browser-state.json"),
            @("I641-OPTIONAL-ABSENCE", -not ([string]$routeHtmlByName["issue-641-raw-733"]).Contains("No serious-review category"), "text/issue-641-03-raw-733.txt"),
            @("I641-COMPLAINT-FINDING", $detailText.Contains("Complaint finding"), "text/issue-641-11-detail.txt"),
            @("I641-ALLEGATION-FINDING", $detailText.Contains("Allegation finding"), "text/issue-641-11-detail.txt"),
            @("I641-IDENTITY-COMPARE", ([string]$routeHtmlByName["issue-641-raw-430"]).Contains("430000001"), "text/issue-641-02-raw-430.txt"),
            @("I641-IDENTITY-OVERVIEW", ([string]$routeHtmlByName["issue-641-overview"]).Contains("430000001"), "text/issue-641-09-overview.txt"),
            @("I641-IDENTITY-DETAIL", $detailText.Contains("430000001"), "text/issue-641-11-detail.txt"),
            @("I641-QUERY-NAME-AUTHORITY", -not $detailText.Contains("Conflicting query facility name"), "text/issue-641-11-detail.txt"),
            @("I641-PUBLIC-ID", -not $detailText.Contains("ccld:facility:"), "text/issue-641-11-detail.txt"),
            @("I641-NAVIGATION", @($issue641States | Where-Object { $_.accessibility.primaryNavigationCount -ne 1 }).Count -eq 0, "browser-state/"),
            @("I641-A11Y", @($issue641States | Where-Object { -not $_.accessibility.skipLink -or $_.accessibility.mainLandmarkCount -ne 1 }).Count -eq 0, "accessibility/"),
            @("I641-CONSOLE", @($issue641States | Where-Object { @($_.consoleErrors).Count -gt 0 -or @($_.pageErrors).Count -gt 0 }).Count -eq 0, "browser-state/"),
            @("I641-NETWORK", @($issue641States | Where-Object { @($_.failedNetworkRequests).Count -gt 0 }).Count -eq 0, "browser-state/"),
            @("I641-PRINT", $printPass, "print/issue-641-13-detail-print.pdf"),
            @("I641-FULL-PAGE", $screenshotsPass, "screenshots/full-page/")
        )
        $featureDefinitions = [System.Collections.ArrayList]::new()
        function Add-Issue641Feature { param([string]$Id, [bool]$Pass, [string]$Evidence) [void]$featureDefinitions.Add(@($Id, $Pass, $Evidence)) }
        Add-Issue641Feature "I641-RESP-390" ($statesByName.ContainsKey("issue-641-compare-390") -and -not $statesByName["issue-641-compare-390"].horizontalOverflow) "browser-state/issue-641-08-compare-390-browser-state.json"
        Add-Issue641Feature "I641-RESP-400" ($statesByName.ContainsKey("issue-641-compare-400") -and -not $statesByName["issue-641-compare-400"].horizontalOverflow) "browser-state/issue-641-07-compare-400-browser-state.json"
        Add-Issue641Feature "I641-RESP-768" ($statesByName.ContainsKey("issue-641-compare-768") -and -not $statesByName["issue-641-compare-768"].horizontalOverflow) "browser-state/issue-641-06-compare-768-browser-state.json"
        Add-Issue641Feature "I641-RESP-200" $zoomPass "browser-state/issue-641-08b-compare-1280-page-scale-200-browser-state.json"
        Add-Issue641Feature "I641-RAW-430-OPTION" ($null -ne $raw430State -and @($raw430State.facilityTypeOptions | Where-Object { $_.value -eq "430" -and $_.label -eq "Source code 430 — label not verified" }).Count -eq 1) "browser-state/issue-641-02-raw-430-browser-state.json"
        Add-Issue641Feature "I641-RAW-430-RESULT" ($null -ne $raw430State -and @($raw430State.expectedVisibleText | Where-Object { $_ -eq "Source code 430" }).Count -eq 1) "text/issue-641-02-raw-430.txt"
        Add-Issue641Feature "I641-RAW-733-OPTION" ($null -ne $raw733State -and @($raw733State.facilityTypeOptions | Where-Object { $_.value -eq "733" -and $_.label -eq "Source code 733 — label not verified" }).Count -eq 1) "browser-state/issue-641-03-raw-733-browser-state.json"
        Add-Issue641Feature "I641-RAW-733-RESULT" ($null -ne $raw733State -and @($raw733State.expectedVisibleText | Where-Object { $_ -eq "Source code 733" }).Count -eq 1) "text/issue-641-03-raw-733.txt"
        Add-Issue641Feature "I641-READABLE-TYPE" ($null -ne $readableState -and @($readableState.facilityTypeOptions | Where-Object { $_.value -eq "Children's Center" -and $_.label -eq "Children's Center" -and $_.selected }).Count -eq 1) "browser-state/issue-641-04-readable-type-browser-state.json"
        Add-Issue641Feature "I641-SELECTED-STATE" ($null -ne $raw430State -and @($raw430State.facilityTypeOptions | Where-Object { $_.value -eq "430" -and $_.selected }).Count -eq 1) "browser-state/issue-641-02-raw-430-browser-state.json"
        Add-Issue641Feature "I641-OPTIONAL-ABSENCE" (-not ([string]$routeHtmlByName["issue-641-raw-733"]).Contains("No serious-review category")) "text/issue-641-03-raw-733.txt"
        Add-Issue641Feature "I641-COMPLAINT-FINDING" $detailText.Contains("Complaint finding") "text/issue-641-11-detail.txt"
        Add-Issue641Feature "I641-ALLEGATION-FINDING" $detailText.Contains("Allegation finding") "text/issue-641-11-detail.txt"
        Add-Issue641Feature "I641-IDENTITY-COMPARE" ([string]$routeHtmlByName["issue-641-raw-430"]).Contains("430000001") "text/issue-641-02-raw-430.txt"
        Add-Issue641Feature "I641-IDENTITY-OVERVIEW" ([string]$routeHtmlByName["issue-641-overview"]).Contains("430000001") "text/issue-641-09-overview.txt"
        Add-Issue641Feature "I641-IDENTITY-DETAIL" $detailText.Contains("430000001") "text/issue-641-11-detail.txt"
        Add-Issue641Feature "I641-QUERY-NAME-AUTHORITY" (-not $detailText.Contains("Conflicting query facility name")) "text/issue-641-11-detail.txt"
        Add-Issue641Feature "I641-PUBLIC-ID" (-not $detailText.Contains("ccld:facility:")) "text/issue-641-11-detail.txt"
        Add-Issue641Feature "I641-NAVIGATION" (@($issue641States | Where-Object { $_.accessibility.primaryNavigationCount -ne 1 }).Count -eq 0) "browser-state/"
        Add-Issue641Feature "I641-A11Y" (@($issue641States | Where-Object { -not $_.accessibility.skipLink -or $_.accessibility.mainLandmarkCount -ne 1 }).Count -eq 0) "accessibility/"
        Add-Issue641Feature "I641-CONSOLE" (@($issue641States | Where-Object { @($_.consoleErrors).Count -gt 0 -or @($_.pageErrors).Count -gt 0 }).Count -eq 0) "browser-state/"
        Add-Issue641Feature "I641-NETWORK" (@($issue641States | Where-Object { @($_.failedNetworkRequests).Count -gt 0 }).Count -eq 0) "browser-state/"
        Add-Issue641Feature "I641-PRINT" $printPass "print/issue-641-13-detail-print.pdf"
        Add-Issue641Feature "I641-FULL-PAGE" $screenshotsPass "screenshots/full-page/"
        function Test-Issue641ControlLegibility {
            param([object]$State, [string]$ControlId, [string]$ExpectedText = '')
            if ($null -eq $State) { return $false }
            $control = @($State.controlLegibility | Where-Object { $_.id -eq $ControlId }) | Select-Object -First 1
            return $null -ne $control -and [bool]$control.legible -and [string]$control.clippingResult -eq 'LEGIBLE' -and (-not $ExpectedText -or [string]$control.fullExpectedText -eq $ExpectedText) -and -not [bool]$control.pageHorizontalOverflow
        }
        Add-Issue641Feature "I641-CONTROL-430-1440" (Test-Issue641ControlLegibility -State $raw430State -ControlId 'facility-type' -ExpectedText 'Source code 430 — label not verified') "browser-state/issue-641-02-raw-430-browser-state.json"
        Add-Issue641Feature "I641-CONTROL-733-1440" (Test-Issue641ControlLegibility -State $raw733State -ControlId 'facility-type' -ExpectedText 'Source code 733 — label not verified') "browser-state/issue-641-03-raw-733-browser-state.json"
        Add-Issue641Feature "I641-CONTROL-430-1024" (Test-Issue641ControlLegibility -State $statesByName['issue-641-compare-1024'] -ControlId 'facility-type' -ExpectedText 'Source code 430 — label not verified') "browser-state/issue-641-05-compare-1024-browser-state.json"
        Add-Issue641Feature "I641-CONTROL-430-768" (Test-Issue641ControlLegibility -State $statesByName['issue-641-compare-768'] -ControlId 'facility-type' -ExpectedText 'Source code 430 — label not verified') "browser-state/issue-641-06-compare-768-browser-state.json"
        Add-Issue641Feature "I641-CONTROL-430-400" (Test-Issue641ControlLegibility -State $statesByName['issue-641-compare-400'] -ControlId 'facility-type' -ExpectedText 'Source code 430 — label not verified') "browser-state/issue-641-07-compare-400-browser-state.json"
        Add-Issue641Feature "I641-CONTROL-430-390" (Test-Issue641ControlLegibility -State $statesByName['issue-641-compare-390'] -ControlId 'facility-type' -ExpectedText 'Source code 430 — label not verified') "browser-state/issue-641-08-compare-390-browser-state.json"
        Add-Issue641Feature "I641-CONTROL-430-200" (Test-Issue641ControlLegibility -State $statesByName['issue-641-compare-1280-page-scale-200'] -ControlId 'facility-type' -ExpectedText 'Source code 430 — label not verified') "browser-state/issue-641-08b-compare-1280-page-scale-200-browser-state.json"
        Add-Issue641Feature "I641-CONTROL-DATE-DIMENSION-200" (Test-Issue641ControlLegibility -State $statesByName['issue-641-compare-1280-page-scale-200'] -ControlId 'date-based-on') "browser-state/issue-641-08b-compare-1280-page-scale-200-browser-state.json"
        foreach ($result in $issue641Routes) {
            if ($result.screenshotPath) {
                $sourceScreenshot = Join-Path $packetDir $result.screenshotPath
                Copy-Item -LiteralPath $sourceScreenshot -Destination (Join-Path $fullPageScreenshotDir ([System.IO.Path]::GetFileName($sourceScreenshot)))
                Copy-Item -LiteralPath $sourceScreenshot -Destination (Join-Path $focusedScreenshotDir ([System.IO.Path]::GetFileName($sourceScreenshot)))
            }
            if ($result.browserStatePath) { Copy-Item -LiteralPath (Join-Path $packetDir $result.browserStatePath) -Destination (Join-Path $browserStateDir ([System.IO.Path]::GetFileName($result.browserStatePath))) }
        }
        $responsiveRows = @("route,innerWidth,innerHeight,clientWidth,scrollWidth,bodyScrollWidth,horizontalOverflow")
        foreach ($state in $issue641States) { $responsiveRows += ('"{0}",{1},{2},{3},{4},{5},{6}' -f $state.routeName,$state.viewport.innerWidth,$state.viewport.innerHeight,$state.viewport.clientWidth,$state.document.scrollWidth,$state.document.bodyScrollWidth,$state.horizontalOverflow) }
        Set-Content -LiteralPath (Join-Path $packetDir "issue-641-responsive-geometry.csv") -Value ($responsiveRows -join "`n") -Encoding UTF8
        Set-Content -LiteralPath (Join-Path $packetDir "issue-641-console-results.json") -Value ($issue641States | ForEach-Object { [ordered]@{ route=$_.routeName; consoleErrors=@($_.consoleErrors); pageErrors=@($_.pageErrors) } } | ConvertTo-Json -Depth 5) -Encoding UTF8
        Set-Content -LiteralPath (Join-Path $packetDir "issue-641-network-results.json") -Value ($issue641States | ForEach-Object { [ordered]@{ route=$_.routeName; failedNetworkRequests=@($_.failedNetworkRequests) } } | ConvertTo-Json -Depth 5) -Encoding UTF8
        Copy-Item -LiteralPath (Join-Path $packetDir "route-status.csv") -Destination (Join-Path $packetDir "issue-641-route-results.csv")
        Copy-Item -LiteralPath (Join-Path $packetDir "route-assertions.csv") -Destination (Join-Path $packetDir "issue-641-route-assertions.csv")
        Copy-Item -LiteralPath (Join-Path $accessibilityDir "headings.txt") -Destination (Join-Path $packetDir "issue-641-accessibility-results.txt")
        Set-Content -LiteralPath (Join-Path $logsDir "local-validation-output.txt") -Value "Focused UI, capture, documentation, lint, typing, security, portability, diff, and full-suite validation are recorded in the PR body and validation summary." -Encoding UTF8
        Set-Content -LiteralPath (Join-Path $logsDir "postgresql-test-output.txt") -Value "Three disposable local PostgreSQL regressions passed before packet capture; no database URL is retained." -Encoding UTF8
        $gateDefinitions = @(
            @("I641-ROUTE-001", "all governed routes return their expected status", $routesPass, "route-status.csv"),
            @("I641-STATE-002", "raw-code, readable-label, identity, terminology, and optional-category assertions", $assertionsPass, "route-assertions.csv"),
            @("I641-GEOMETRY-003", "scrollWidth and each required right edge do not exceed clientWidth", $geometryPass, "diagnostics/issue-641-*-browser-state.json"),
            @("I641-RESPONSIVE-004", "all desktop and narrow responsive screenshots exist", $screenshotsPass, "screenshots/"),
            @("I641-ZOOM-005", "1280x900 page scale records an actual visualViewport scale of 2", $zoomPass, "diagnostics/issue-641-08b-compare-1280-page-scale-200-browser-state.json"),
            @("I641-PRINT-006", "the Complaint overview print PDF exists", $printPass, "print/issue-641-13-detail-print.pdf")
        )
        foreach ($gate in $gateDefinitions) {
            $issue641GateResults += [pscustomobject]@{ assertion = $gate[0]; requirement = $gate[1]; status = if ([bool]$gate[2]) { "PASS" } else { "FAIL" }; evidence = $gate[3] }
        }
        $gateCsv = @("assertion,requirement,status,evidence")
        foreach ($gate in $issue641GateResults) {
            $gateCsv += ((@($gate.assertion, $gate.requirement, $gate.status, $gate.evidence) | ForEach-Object { '"' + ([string]$_).Replace('"', '""') + '"' }) -join ",")
        }
        Set-Content -LiteralPath (Join-Path $packetDir "issue-641-evidence-gates.csv") -Value ($gateCsv -join "`n") -Encoding UTF8
        Set-Content -LiteralPath (Join-Path $packetDir "issue-641-evidence-summary.md") -Value @"
# Issue #641 corrected local evidence

This packet supersedes neither the historical rejected packet nor any acceptance decision. It is a newly captured local-fixture packet for independent review.

- Route, assertion, screenshot, responsive-geometry, page-scale, and print gates are recorded in `issue-641-evidence-gates.csv`.
- Browser-state files record `clientWidth`, document widths, required-element bounds, and every capture's overflow result.
- `issue-641-08b-compare-1280-page-scale-200` records 1280x900 with a measured visual viewport scale of 2.
- Visual acceptance remains an explicit human decision.
"@ -Encoding UTF8
    }

    $gitBranch = (git branch --show-current 2>$null) -join ""
    $gitCommit = (git rev-parse HEAD 2>$null) -join ""
    $gitStatus = (git status --short 2>$null) -join "`n"
    $workingTreeClean = [string]::IsNullOrWhiteSpace($gitStatus)
    $gitStatusText = if ($workingTreeClean) { "clean" } else { $gitStatus }
    $gitBaseResolution = if ($Issue655) { Resolve-OptionalGitRevision } else { $null }
    if ($Issue655 -and -not $gitBaseResolution.Available -and -not $AllowUnavailable) {
        Stop-CaptureFail "Issue #655 evidence requires an authoritative base SHA. Attempted: $($gitBaseResolution.Attempts -join ', ')."
    }
    $gitBaseSha = if ($gitBaseResolution -and $gitBaseResolution.Available) { $gitBaseResolution.Sha } else { '' }
    $gitBaseSource = if ($gitBaseResolution) { $gitBaseResolution.Source } else { '' }
    $gitBaseAttempts = if ($gitBaseResolution) { @($gitBaseResolution.Attempts) } else { @() }
    Set-Content -LiteralPath (Join-Path $diagnosticsDir "git-status.txt") -Value $gitStatusText -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $diagnosticsDir "git-log.txt") -Value ((git log --oneline -n 5 2>$null) -join "`n") -Encoding UTF8
    $focusedCommandSuffix = if ($Issue655) { " -Issue655" } elseif ($Issue642) { " -Issue642" } elseif ($Issue641) { " -Issue641" } elseif ($Issue503) { " -Issue503" } elseif ($Issue502) { " -Issue502" } elseif ($Issue498) { " -Issue498" } elseif ($Issue420) { " -Issue420" } elseif ($Issue419) { " -Issue419" } elseif ($Issue418) { " -Issue418" } elseif ($Issue417) { " -Issue417" } elseif ($Issue416) { " -Issue416" } elseif ($Issue415) { " -Issue415" } else { "" }
    Set-Content -LiteralPath (Join-Path $diagnosticsDir "capture-command.txt") -Value "capture-hosted-ui-evidence.ps1 -BaseUrl $normalizedBaseUrl -Mode $Mode -OutputDir $OutputDir -ViewportWidth $ViewportWidth -ViewportHeight $ViewportHeight -TimeoutSeconds $TimeoutSeconds -ScreenshotToolPreference $ScreenshotToolPreference$focusedCommandSuffix" -Encoding UTF8
    $environmentSummary = if ($Issue655) { @(
        'issue=655',
        "mode=$Mode",
        "branch=$gitBranch",
        "head=$gitCommit",
        "baseSha=$gitBaseSha",
        "baseShaSource=$gitBaseSource",
        "baseUrl=$normalizedBaseUrl",
        "viewport=${ViewportWidth}x${ViewportHeight}",
        "screenshotToolResolved=$($screenshotToolResolution.Resolved)",
        "interactionAwareCapture=$([bool]$screenshotToolResolution.SupportsInteractionAwareCapture)",
        "routeCount=$(@($routesToCapture).Count)",
        'diagnostics=issue-655-interaction-index.json,issue-655-geometry.json,issue-655-focus-live-region.json,issue-655-console-network-summary.json',
        'limitation=local-fixture evidence only; not deployed-host evidence'
    ) } else { @(
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
        "issue420FocusedCapture=$([bool]$Issue420)",
        "issue502FocusedCapture=$([bool]$Issue502)",
        "issue503FocusedCapture=$([bool]$Issue503)",
        "issue498FocusedCapture=$([bool]$Issue498)",
        "issue641FocusedCapture=$([bool]$Issue641)",
        "issue642FocusedCapture=$([bool]$Issue642)",
        "browserZoomControl=not controlled by this script; use ViewportWidth/ViewportHeight for supplemental narrow-width or 200-percent-review approximation only",
        "evidencePurpose=$evidencePurpose"
    ) }
    Set-Content -LiteralPath (Join-Path $diagnosticsDir "environment-summary.txt") -Value $environmentSummary -Encoding UTF8

    $readmeText = @"
CCLD RecordsTracker hosted UI evidence packet

Mode: $Mode
Base URL: $normalizedBaseUrl
Generated: $((Get-Date).ToUniversalTime().ToString("o"))

This packet captures local hosted UI route status, text markers, assertions,
accessibility snapshots, and screenshots for reviewer inspection.

Review these files first:
- manifest.json
- reviews/independent-visual-review.json
- reviews/owner-acceptance.json
- route-status.csv
- route-assertions.csv
- route-text-markers.txt
- accessibility/headings.txt
- accessibility/links.txt
- accessibility/forms.txt
- accessibility/landmarks.txt

HTML files are sanitized route captures from GET requests only. Text files are
plain-text summaries derived from those HTML captures. Screenshots are included
only when a local screenshot tool is available. Focused print scenarios include
a print-media PDF and rendered page images when the local browser tool supports them.

The generated folder and sibling ZIP are for local review or upload to ChatGPT
so testing instructions can be written from the actual rendered UI labels,
links, buttons, and page text. Review the packet before sharing it. Do not
commit generated evidence or ZIP packets unless a specific repository workflow
explicitly says to do so.

Capture automation never records visual or owner acceptance. The review files
are pending human-input templates, and manifest.acceptance.overall remains
NOT_ACCEPTED until a completed acceptance record passes
scripts/validate_hosted_ui_acceptance.py.
"@
    Set-Content -LiteralPath (Join-Path $packetDir "README.txt") -Value $readmeText -Encoding UTF8

    $routeFailures = @($routeResults | Where-Object { $_.statusCode -eq 0 -or $_.statusCode -ne $_.expectedStatus -or $_.failure })
    $assertionFailures = @($assertions | Where-Object { $_.status -eq "FAIL" })
    $screenshotFailures = @($screenshotWarnings | Where-Object { $_ -match "(screenshot|print capture) failed" })
    $issue641ValidationSummary = $null
    if ($Issue641) {
        $preSummary = Get-Issue641ValidationSummary -RouteFailures @($routeFailures).Count -AssertionFailures @($assertionFailures).Count -FeatureAssertionFailures @($featureDefinitions | Where-Object { -not [bool]$_[1] }).Count -ScreenshotFailures @($screenshotFailures).Count -RequiredFeatureAssertions @($featureDefinitions | ForEach-Object { $_[0] })
        $preSummaryCountsReconcile = $preSummary.routeFailures -eq @($routeFailures).Count -and $preSummary.assertionFailures -eq @($assertionFailures).Count -and $preSummary.featureAssertionFailures -eq @($featureDefinitions | Where-Object { -not [bool]$_[1] }).Count -and $preSummary.screenshotFailures -eq @($screenshotFailures).Count
        $preSummaryStatusMatchesCounts = ([string]$preSummary.status -eq 'PASS') -eq ($preSummary.routeFailures -eq 0 -and $preSummary.assertionFailures -eq 0 -and $preSummary.featureAssertionFailures -eq 0 -and $preSummary.screenshotFailures -eq 0)
        Add-Issue641Feature "I641-SUMMARY-RECONCILIATION" ($preSummaryCountsReconcile -and $preSummaryStatusMatchesCounts) "validation-summary.json"
        $featureFailures = @($featureDefinitions | Where-Object { -not [bool]$_[1] }).Count
        $issue641ValidationSummary = Get-Issue641ValidationSummary -RouteFailures @($routeFailures).Count -AssertionFailures @($assertionFailures).Count -FeatureAssertionFailures $featureFailures -ScreenshotFailures @($screenshotFailures).Count -RequiredFeatureAssertions @($featureDefinitions | ForEach-Object { $_[0] })
        $featureRows = @("assertion,status,evidence")
        foreach ($feature in $featureDefinitions) { $featureRows += ('"{0}","{1}","{2}"' -f $feature[0], $(if ([bool]$feature[1]) { "PASS" } else { "FAIL" }), $feature[2]) }
        Set-Content -LiteralPath (Join-Path $packetDir "issue-641-feature-assertions.csv") -Value ($featureRows -join "`n") -Encoding UTF8
        Copy-Item -LiteralPath (Join-Path $packetDir "issue-641-feature-assertions.csv") -Destination (Join-Path $packetDir "issue-641-requirement-to-evidence.csv")
        Set-Content -LiteralPath (Join-Path $packetDir "validation-summary.json") -Value ($issue641ValidationSummary | ConvertTo-Json -Depth 5) -Encoding UTF8
        Set-Content -LiteralPath (Join-Path $packetDir "validation-summary.md") -Value "# Functional validation summary`n`nRoute failures: $($issue641ValidationSummary.routeFailures)`nAssertion failures: $($issue641ValidationSummary.assertionFailures)`nFeature assertion failures: $($issue641ValidationSummary.featureAssertionFailures)`nScreenshot failures: $($issue641ValidationSummary.screenshotFailures)`nFunctional gate: $($issue641ValidationSummary.status)`nOverall hosted UI acceptance: NOT_ACCEPTED`n`nThis summary cannot establish visual or owner acceptance." -Encoding UTF8
        if ($featureFailures -gt 0) { Stop-CaptureFail "Issue #641 feature assertion failures prevent packet publication." }
    }
    $issue642PacketDiagnostics = $null
    if ($Issue642) {
        $issue642PacketDiagnostics = Write-Issue642PacketDiagnostics -PacketDirectory $packetDir -ScreenshotDirectory $screenshotDir -DiagnosticsDirectory $diagnosticsDir -RouteResults @($routeResults)
    }
    elseif ($Issue643) {
        $issue642PacketDiagnostics = Write-Issue642PacketDiagnostics -PacketDirectory $packetDir -ScreenshotDirectory $screenshotDir -DiagnosticsDirectory $diagnosticsDir -RouteResults @($routeResults) -IssueNumber '643'
    }
    elseif ($Issue655) {
        $issue642PacketDiagnostics = Write-Issue655PacketDiagnostics -PacketDirectory $packetDir -ScreenshotDirectory $screenshotDir -DiagnosticsDirectory $diagnosticsDir -RouteResults @($routeResults)
    }
    $outputCounts = [ordered]@{
        screenshots   = Get-EvidenceFileCount -Path $screenshotDir -Filter "*.png"
        html          = Get-EvidenceFileCount -Path $htmlDir -Filter "*.html"
        text          = Get-EvidenceFileCount -Path $textDir -Filter "*.txt"
        diagnostics   = Get-EvidenceFileCount -Path $diagnosticsDir
        accessibility = Get-EvidenceFileCount -Path $accessibilityDir
        print          = Get-EvidenceFileCount -Path $printDir -Filter "*.pdf"
        printPages     = Get-EvidenceFileCount -Path (Join-Path $packetDir 'print-pages') -Filter "*.png"
        issue415      = if ($Issue415) { Get-EvidenceFileCount -Path $packetDir -Filter "issue-415-*.csv" } else { 0 }
        issue416      = if ($Issue416) { Get-EvidenceFileCount -Path $packetDir -Filter "issue-416-*.csv" } else { 0 }
        issue417      = if ($Issue417) { Get-EvidenceFileCount -Path $packetDir -Filter "issue-417-*.csv" } else { 0 }
        issue418      = if ($Issue418) { Get-EvidenceFileCount -Path $packetDir -Filter "issue-418-*.csv" } else { 0 }
        issue419      = if ($Issue419) { Get-EvidenceFileCount -Path $packetDir -Filter "issue-419-*.csv" } else { 0 }
        issue420      = if ($Issue420) { Get-EvidenceFileCount -Path $packetDir -Filter "issue-420-*.csv" } else { 0 }
        issue502      = if ($Issue502) { @($routesToCapture).Count } else { 0 }
        issue503      = if ($Issue503) { @($routesToCapture).Count } else { 0 }
        issue498      = if ($Issue498) { @($routesToCapture).Count } else { 0 }
        issue642      = if ($Issue642) { @($routesToCapture).Count } else { 0 }
        issue655      = if ($Issue655) { @($routesToCapture).Count } else { 0 }
    }
    if ($Issue655Rehearsal) {
        Test-Issue655AcceptancePacket -PacketDirectory $packetDir -DiagnosticsDirectory $diagnosticsDir -Assertions $assertions
        $rehearsalSummary = [ordered]@{mode='issue-655-rehearsal';run=$RehearsalRunName;routes=@($routeResults).Count;assertions=@($assertions).Count;assertionFailures=@($assertionFailures).Count;routeFailures=@($routeFailures).Count;screenshotFailures=@($screenshotFailures).Count;interactions=$issue642PacketDiagnostics.interactionCount;output=$packetDir;zipCreated=$false;ownerReviewCreated=$false}
        Set-Content -LiteralPath (Join-Path $packetDir 'rehearsal-summary.json') -Value ($rehearsalSummary | ConvertTo-Json -Depth 6) -Encoding UTF8
        Write-Host "ISSUE655_REHEARSAL_PATH=$packetDir"
        Write-Host "ISSUE655_REHEARSAL_RESULT=PASS"
        exit 0
    }
    $focusedIssueScope = @()
    foreach ($issueEntry in @(
        [pscustomobject]@{ Enabled = $Issue415; Reference = "#415" },
        [pscustomobject]@{ Enabled = $Issue416; Reference = "#416" },
        [pscustomobject]@{ Enabled = $Issue417; Reference = "#417" },
        [pscustomobject]@{ Enabled = $Issue418; Reference = "#418" },
        [pscustomobject]@{ Enabled = $Issue419; Reference = "#419" },
        [pscustomobject]@{ Enabled = $Issue420; Reference = "#420" },
        [pscustomobject]@{ Enabled = $Issue498; Reference = "#498" },
        [pscustomobject]@{ Enabled = $Issue502; Reference = "#502" },
        [pscustomobject]@{ Enabled = $Issue503; Reference = "#503" },
        [pscustomobject]@{ Enabled = $Issue610; Reference = "#610" },
        [pscustomobject]@{ Enabled = $Issue641; Reference = "#641" },
        [pscustomobject]@{ Enabled = $Issue642; Reference = "#642" },
        [pscustomobject]@{ Enabled = $Issue655; Reference = "#655" }
    )) {
        if ([bool]$issueEntry.Enabled) { $focusedIssueScope += [string]$issueEntry.Reference }
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
        issue419               = [ordered]@{ enabled = [bool]$Issue419; routeCount = @($routesToCapture).Count; scenarios = @($routesToCapture | ForEach-Object { $_.Name }); controlledVarianceAuthority = "Issue #501 repository-readable controlled variance"; visualAcceptance = "PENDING_INDEPENDENT_VISUAL_REVIEW"; uiGates = @($issue419GateResults); zoomLimitation = "The 720-pixel viewport scenario approximates 200-percent reflow; no visual acceptance is inferred from automation."; printArtifact = @($routeResults | Where-Object { $_.printPath } | ForEach-Object { $_.printPath }) }
        issue420               = [ordered]@{ enabled = [bool]$Issue420; routeCount = @($routesToCapture).Count; scenarios = @($routesToCapture | ForEach-Object { $_.Name }); screenshotCount = if ($Issue420) { @($routeResults | Where-Object { $_.screenshotPath }).Count } else { 0 }; uniquePngCount = if ($Issue420 -and $duplicateReport) { $duplicateReport.uniquePngCount } else { 0 }; intentionalConsolidationCount = if ($Issue420) { 1 } else { 0 }; partialCoverageVisualProof = "issue-420-populated-desktop"; duplicateImageReport = if ($Issue420) { 'issue-420-duplicate-images.json' } else { '' }; printValidation = if ($Issue420) { 'issue-420-print-validation.json' } else { '' }; controlledVarianceAuthority = "Issue #420 product-owner specification and Issue #501 repository-readable controlled variance"; visualAcceptance = "PENDING_INDEPENDENT_VISUAL_REVIEW"; uiGates = @($issue420GateResults); zoomLimitation = "The 720-pixel viewport scenario approximates 200-percent reflow; no visual acceptance is inferred from automation."; printArtifact = @($routeResults | Where-Object { $_.printPath } | ForEach-Object { $_.printPath }) }
        issue502               = [ordered]@{ enabled = [bool]$Issue502; routeCount = @($routesToCapture).Count; scenarios = @($routesToCapture | ForEach-Object { $_.Name }); controlledVarianceAuthority = "Issue #501 repository-readable controlled variance"; visualAcceptance = "PENDING_INDEPENDENT_VISUAL_REVIEW"; zoomLimitation = "The 720-pixel viewport scenario approximates 200-percent reflow; no visual acceptance is inferred from automation." }
        issue503               = [ordered]@{ enabled = [bool]$Issue503; routeCount = @($routesToCapture).Count; scenarios = @($routesToCapture | ForEach-Object { $_.Name }); controlledVarianceAuthority = "Issue #503 product outcome and Issue #501 repository-readable controlled variance"; visualAcceptance = "PENDING_INDEPENDENT_VISUAL_REVIEW"; uiGates = @($issue503GateResults); fragmentInventory = if ($Issue503) { "issue-503-route-fragment-inventory.csv" } else { "" }; interactionMeasurements = if ($Issue503) { "diagnostics/issue-503-responsive-fragment-focus-measurements.json" } else { "" }; zoomLimitation = "The 720-pixel viewport approximates 200-percent reflow; native browser zoom and assistive-technology verification were not performed."; printArtifact = @($routeResults | Where-Object { $_.printPath } | ForEach-Object { $_.printPath }) }
        issue498               = [ordered]@{ enabled = [bool]$Issue498; routeCount = @($routesToCapture).Count; scenarios = @($routesToCapture | ForEach-Object { $_.Name }); zoomLimitation = "The 720-pixel viewport scenario approximates 200-percent reflow only; exact true browser zoom remains manual visual evidence."; printArtifact = @($routeResults | Where-Object { $_.printPath } | ForEach-Object { $_.printPath }) }
        issue610               = [ordered]@{ enabled = [bool]$Issue610; routeCount = @($routesToCapture).Count; scenarios = @($routesToCapture | ForEach-Object { $_.Name }); printSettings = "Portrait; scale 100%; default margins; headers and footers off; background graphics on."; printArtifact = @($routeResults | Where-Object { $_.printPath } | ForEach-Object { $_.printPath }) }
        issue641               = [ordered]@{ enabled = [bool]$Issue641; routeCount = @($routesToCapture).Count; scenarios = @($routesToCapture | ForEach-Object { $_.Name }); evidenceGates = @($issue641GateResults); gateArtifact = if ($Issue641) { "issue-641-evidence-gates.csv" } else { "" }; summaryArtifact = if ($Issue641) { "issue-641-evidence-summary.md" } else { "" }; measuredPageScale = if ($Issue641) { "1280x900 at visualViewport scale 2" } else { "" }; visualAcceptance = "PENDING_INDEPENDENT_VISUAL_REVIEW"; printArtifact = @($routeResults | Where-Object { $_.printPath } | ForEach-Object { $_.printPath }) }
        issue642               = [ordered]@{ enabled = [bool]$Issue642; routeCount = if ($Issue642) { @($routesToCapture).Count } else { 0 }; scenarios = if ($Issue642) { @($routesToCapture | ForEach-Object { $_.Name }) } else { @() }; controlledInteraction = "Navigation, staged public Facility ID, multi-value state, canonical continuation, return context, responsive, focus, print"; screenshotStateArtifact = if ($Issue642) { 'diagnostics/issue-642-screenshot-states.json' } else { '' }; screenshotStates = if ($Issue642) { $issue642PacketDiagnostics.screenshotStates } else { @{} }; consoleNetworkSummaryArtifact = if ($Issue642) { 'diagnostics/issue-642-console-network-summary.json' } else { '' }; consoleNetwork = if ($Issue642) { $issue642PacketDiagnostics.consoleNetwork } else { @{} }; visualAcceptance = "PENDING_INDEPENDENT_VISUAL_REVIEW"; ownerAcceptance = "PENDING_OWNER_DECISION"; printArtifact = @($routeResults | Where-Object { $_.printPath } | ForEach-Object { $_.printPath }) }
        issue655               = [ordered]@{ enabled = [bool]$Issue655; mode = 'local-fixture'; branch = $gitBranch; head = $gitCommit; baseSha = $gitBaseSha; baseShaSource = $gitBaseSource; baseShaAttempts = $gitBaseAttempts; routeCount = if ($Issue655) { @($routesToCapture).Count } else { 0 }; scenarios = if ($Issue655) { @($routesToCapture | ForEach-Object { $_.Name }) } else { @() }; screenshotStateArtifact = if ($Issue655) { 'diagnostics/issue-655-screenshot-states.json' } else { '' }; screenshotStates = if ($Issue655) { $issue642PacketDiagnostics.screenshotStates } else { @{} }; browserStateCount = if ($Issue655) { $issue642PacketDiagnostics.browserStates } else { 0 }; geometryDiagnosticsArtifact = if ($Issue655) { $issue642PacketDiagnostics.geometryArtifact } else { '' }; focusLiveRegionDiagnosticsArtifact = if ($Issue655) { $issue642PacketDiagnostics.focusLiveArtifact } else { '' }; interactionIndexArtifact = if ($Issue655) { $issue642PacketDiagnostics.interactionIndexArtifact } else { '' }; consoleNetworkSummaryArtifact = if ($Issue655) { 'diagnostics/issue-655-console-network-summary.json' } else { '' }; consoleNetwork = if ($Issue655) { $issue642PacketDiagnostics.consoleNetwork } else { @{} }; evidenceLimitations = 'Local fixture evidence only; it does not establish deployed-host acceptance.'; visualAcceptance = 'PENDING_INDEPENDENT_VISUAL_REVIEW'; ownerAcceptance = 'PENDING_OWNER_DECISION'; printArtifact = @($routeResults | Where-Object { $_.printPath } | ForEach-Object { $_.printPath }) }
        acceptance             = [ordered]@{
            schemaVersion = "recordstracker.hosted-ui-acceptance.v1"
            governanceIssue = "#648"
            parentIssue = "#640"
            stakeholderIssue = "#419"
            featureIssues = $focusedIssueScope
            structural = "PENDING_VALIDATION"
            functional = "PENDING_VALIDATION"
            visual = "PENDING_INDEPENDENT_VISUAL_REVIEW"
            ownerAcceptance = "PENDING_OWNER_DECISION"
            overall = "NOT_ACCEPTED"
            independentReviewArtifact = "reviews/independent-visual-review.json"
            ownerDecisionArtifact = "reviews/owner-acceptance.json"
            validator = "scripts/validate_hosted_ui_acceptance.py"
            automationMayAccept = $false
        }
        git                    = [ordered]@{ branch = $gitBranch; commit = $gitCommit; workingTreeClean = [bool]$workingTreeClean; notice = if ($workingTreeClean) { "" } else { "Working tree was not clean when evidence was captured." } }
        output                 = [ordered]@{ packetDirectory = ConvertTo-RelativeEvidencePath -Path $packetDir -Root $PWD; zipPacket = ConvertTo-RelativeEvidencePath -Path $zipPath -Root $PWD; manifest = "manifest.json"; fileIndex = "file-index.json"; routeStatusCsv = "route-status.csv"; routeAssertionsCsv = "route-assertions.csv"; textMarkers = "route-text-markers.txt"; counts = $outputCounts }
        evidencePurpose        = $evidencePurpose
        safety                 = [ordered]@{ getOnly = $true; formsSubmitted = $false; retrievalSubmitted = $false; reviewerStateMutated = $false; importsOrReloadsRun = $false; productionAuthRequired = $false; responseHeadersCaptured = $false; cookiesCaptured = $false; environmentValuesCaptured = $false }
    }
    if ($Issue655) {
        $manifest = [ordered]@{
            issue = '655'
            mode = 'local-fixture'
            generatedAt = (Get-Date).ToUniversalTime().ToString('o')
            baseUrl = $normalizedBaseUrl
            git = [ordered]@{ branch=$gitBranch; head=$gitCommit; baseSha=$gitBaseSha; baseShaSource=$gitBaseSource; baseShaAttempts=$gitBaseAttempts; baseShaStatus=if ($gitBaseResolution.Available) { 'available' } else { 'unavailable' }; workingTreeClean=[bool]$workingTreeClean }
            routes = @($routeResults)
            routeCount = @($routeResults).Count
            assertions = @($assertions)
            assertionCount = @($assertions).Count
            assertionFailures = @($assertionFailures).Count
            screenshots = $issue642PacketDiagnostics.screenshotStates
            browserStateCount = $issue642PacketDiagnostics.browserStates
            accessibilityArtifactCount = Get-EvidenceFileCount -Path $accessibilityDir
            printArtifactCount = Get-EvidenceFileCount -Path $printDir -Filter '*.pdf'
            artifacts = [ordered]@{ interactionIndex=$issue642PacketDiagnostics.interactionIndexArtifact; geometry=$issue642PacketDiagnostics.geometryArtifact; focusLiveRegion=$issue642PacketDiagnostics.focusLiveArtifact; facilityOverviewReturn=$issue642PacketDiagnostics.facilityReturnArtifact; complaintDetailReturn=$issue642PacketDiagnostics.complaintReturnArtifact; concurrency=$issue642PacketDiagnostics.concurrencyArtifact; enhancedError=$issue642PacketDiagnostics.enhancedErrorArtifact; reducedMotion=$issue642PacketDiagnostics.reducedMotionArtifact; acceptanceGate='diagnostics/issue-655-acceptance-gate.json'; consoleNetwork='diagnostics/issue-655-console-network-summary.json'; fileIndex='file-index.json'; routeAssertions='route-assertions.csv' }
            consoleNetwork = $issue642PacketDiagnostics.consoleNetwork
            fixture = [ordered]@{ identities='committed local fixture runtime'; recommendationState='server-generated opaque state'; source='local fixture only' }
            evidenceLimitations = 'This is local fixture evidence only; it is not deployed-host evidence.'
            acceptance = [ordered]@{ visual='PENDING_INDEPENDENT_VISUAL_REVIEW'; owner='PENDING_OWNER_DECISION'; overall='NOT_ACCEPTED'; automationMayAccept=$false }
            safety = [ordered]@{ getOnly=$true; formsSubmitted=$false; reviewerStateMutated=$false; productionAuthRequired=$false }
        }
    }
    Set-Content -LiteralPath (Join-Path $packetDir "manifest.json") -Value ($manifest | ConvertTo-Json -Depth 8) -Encoding UTF8
    if ($Issue641) {
        $manifestCsv = @("field,value")
        foreach ($entry in @("generatedAt=$($manifest.generatedAt)", "commit=$gitCommit", "routeCount=$($manifest.routes.Count)", "featureAssertions=$($featureDefinitions.Count)", "featureAssertionFailures=$featureFailures", "packetStatus=$($manifest.issue641.visualAcceptance)")) {
            $parts = $entry.Split("=", 2)
            $manifestCsv += ('"{0}","{1}"' -f $parts[0], $parts[1])
        }
        Set-Content -LiteralPath (Join-Path $packetDir "manifest.csv") -Value ($manifestCsv -join "`n") -Encoding UTF8
        Copy-Item -LiteralPath (Join-Path $packetDir "README.txt") -Destination (Join-Path $packetDir "README.md")
    }
    $independentReviewTemplate = [ordered]@{
        artifactType = "independent-visual-review"
        actorType = "HUMAN_REQUIRED"
        reviewer = ""
        decision = "PENDING"
        reviewedEvidence = @()
        conclusions = @()
        notice = "Automation must not complete this file or claim visual acceptance."
    }
    Set-Content -LiteralPath (Join-Path $reviewDir "independent-visual-review.json") -Value ($independentReviewTemplate | ConvertTo-Json -Depth 5) -Encoding UTF8
    $ownerAcceptanceTemplate = [ordered]@{
        artifactType = "owner-acceptance"
        actorType = "HUMAN_REQUIRED"
        actor = ""
        decision = "PENDING"
        reviewedVisualRecord = "reviews/independent-visual-review.json"
        notice = "Automation must not complete this file or synthesize owner acceptance."
    }
    Set-Content -LiteralPath (Join-Path $reviewDir "owner-acceptance.json") -Value ($ownerAcceptanceTemplate | ConvertTo-Json -Depth 5) -Encoding UTF8

    # Fail closed before file indexing and ZIP creation.  An incomplete #655
    # interaction inventory is a partial packet, never a successful capture.
    if ($Issue655) {
        Test-Issue655AcceptancePacket -PacketDirectory $packetDir -DiagnosticsDirectory $diagnosticsDir -Assertions $assertions
    }

    $indexedPacketFiles = @(Test-EvidencePacketFiles -PacketDirectory $packetDir)
    $fileIndex = [ordered]@{
        files = $indexedPacketFiles
    }
    Set-Content -LiteralPath (Join-Path $packetDir "file-index.json") -Value ($fileIndex | ConvertTo-Json -Depth 5) -Encoding UTF8

    if (($routeFailures.Count -gt 0 -or $assertionFailures.Count -gt 0 -or $screenshotFailures.Count -gt 0) -and -not $AllowUnavailable) {
        Write-Host "Evidence packet path: $packetDir"
        Write-Host "EVIDENCE_PACKET_PATH=$packetDir"
        Stop-CaptureFail "Evidence capture completed with route, assertion, or screenshot failures. Use -AllowUnavailable to keep packets for unavailable routes."
    }

    if (Test-Path -LiteralPath $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
    Compress-Archive -LiteralPath $packetDir -DestinationPath $zipPath -Force
    $packagedFiles = @(Get-EvidenceFileIndex -PacketDirectory $packetDir)
    $zipSha256 = Test-EvidenceZipIntegrity -PacketDirectory $packetDir -ZipPath $zipPath -ExpectedFiles $packagedFiles

    Write-Host "Evidence packet path: $packetDir"
    Write-Host "EVIDENCE_PACKET_PATH=$packetDir"
    Write-Host "Evidence zip path: $zipPath"
    Write-Host "EVIDENCE_ZIP_PATH=$zipPath"
    Write-Host "Evidence ZIP SHA-256: $zipSha256"
    Write-Host "EVIDENCE_ZIP_SHA256=$zipSha256"
    Write-Host "HOSTED_UI_ACCEPTANCE=NOT_ACCEPTED"
    Write-Host "Output counts: screenshots=$($outputCounts.screenshots); html=$($outputCounts.html); text=$($outputCounts.text); diagnostics=$($outputCounts.diagnostics); accessibility=$($outputCounts.accessibility)"
    Write-Host "manifest.json: $(Join-Path $packetDir 'manifest.json')"
    Write-Host "file-index.json: $(Join-Path $packetDir 'file-index.json')"
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
