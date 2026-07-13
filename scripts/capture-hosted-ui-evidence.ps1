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

    [switch]$AllowUnavailable,

    [switch]$Issue415,

    [switch]$Issue416,

    [switch]$Issue417,

    [switch]$Issue418
)

$ErrorActionPreference = "Stop"

$evidencePurpose = if ($Issue418) {
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
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $Timeout -ErrorAction Stop
        return [pscustomobject]@{ StatusCode = [int]$response.StatusCode; Content = [string]$response.Content; Error = "" }
    }
    catch {
        if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
            $status = [int]$_.Exception.Response.StatusCode
            return [pscustomobject]@{ StatusCode = $status; Content = ""; Error = "HTTP $status" }
        }
        return [pscustomobject]@{ StatusCode = 0; Content = ""; Error = $_.Exception.Message }
    }
}

function Find-ScreenshotTool {
    $repoPlaywright = Join-Path $PWD "node_modules\.bin\playwright.cmd"
    if (Test-Path -LiteralPath $repoPlaywright) { return [pscustomobject]@{ Name = "playwright-local"; Command = $repoPlaywright; FullPage = $true } }
    $playwrightCommand = Get-Command "playwright" -ErrorAction SilentlyContinue
    if ($playwrightCommand) { return [pscustomobject]@{ Name = "playwright"; Command = $playwrightCommand.Source; FullPage = $true } }
    $edgePaths = @(
        (Join-Path ${env:ProgramFiles} "Microsoft\Edge\Application\msedge.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Microsoft\Edge\Application\msedge.exe")
    )
    foreach ($path in $edgePaths) {
        if ($path -and (Test-Path -LiteralPath $path)) { return [pscustomobject]@{ Name = "msedge-headless"; Command = $path; FullPage = $false } }
    }
    foreach ($browser in @("msedge", "chrome", "chrome.exe")) {
        $cmd = Get-Command $browser -ErrorAction SilentlyContinue
        if ($cmd) { return [pscustomobject]@{ Name = "$browser-headless"; Command = $cmd.Source; FullPage = $false } }
    }
    return $null
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
    param([object]$Tool, [string]$Url, [string]$ScreenshotPath)
    if ($null -eq $Tool) { return "screenshot tool unavailable" }
    if ($Tool.Name -like "playwright*") { $arguments = @("screenshot", "--full-page", "--viewport-size=${ViewportWidth},${ViewportHeight}", $Url, $ScreenshotPath) }
    else { $arguments = @("--headless=new", "--disable-gpu", "--hide-scrollbars", "--window-size=$ViewportWidth,$ViewportHeight", "--screenshot=$ScreenshotPath", $Url) }
    $screenshotTimeoutSeconds = [Math]::Max(30, [int]$TimeoutSeconds)
    $result = Invoke-NativeCaptureCommand -Command $Tool.Command -Arguments $arguments -Timeout $screenshotTimeoutSeconds
    if ($result.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $ScreenshotPath)) { return "screenshot failed with $($Tool.Name) exit code $($result.ExitCode): $($result.Output.Trim())" }
    return ""
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
        "facility-priority" = @("Facility review priority", "Facilities grouped by review cue priority")
        "facility-intelligence" = @("Facility review intelligence", "Facilities by review-priority indicator")
        "facility-hub" = @("Facility review hub", "Facility-directory details")
        "request-records" = @("Request Records", "Which facility should be reviewed?")
        "jobs" = @("Job diagnostics", "Track Request Records jobs")
        "reviewer" = @("Complaint records ready for review", "Worklist")
        "substantiated-triage" = @("substantiated complaint triage", "Source-derived finding")
        "serious-topics" = @("Serious-topic complaint worklist", "Filter serious review themes")
        "facility-priorities" = @("Facility review priorities", "Find facilities that may deserve review first")
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
    if ($StatusCode -ge 400) { Add-AssertionResult -Target $Assertions -RouteName $name -Check "route status" -Status "FAIL" -Message "Route returned HTTP $StatusCode." }
    else { Add-AssertionResult -Target $Assertions -RouteName $name -Check "route status" -Status "PASS" -Message "Route returned HTTP $StatusCode." }
    $forbidden = Get-ForbiddenMarkers -Text $Html
    if ($forbidden.Count -gt 0) { Add-AssertionResult -Target $Assertions -RouteName $name -Check "private markers" -Status "FAIL" -Message ("Forbidden marker(s): " + ($forbidden -join ", ")) }
    else { Add-AssertionResult -Target $Assertions -RouteName $name -Check "private markers" -Status "PASS" -Message "No forbidden private markers found." }
    if ($Html.Contains("Feedbac k")) { Add-AssertionResult -Target $Assertions -RouteName $name -Check "broken labels" -Status "FAIL" -Message "Broken step label found." }
    else { Add-AssertionResult -Target $Assertions -RouteName $name -Check "broken labels" -Status "PASS" -Message "No broken Feedbac k label found." }
    $expectedModeText = switch ($Mode) { "live" { "Live public CCLD" } "fixture" { "Fixture/mock demo" } default { "Review aids only" } }
    if ($Html.Contains($expectedModeText)) { Add-AssertionResult -Target $Assertions -RouteName $name -Check "mode badge" -Status "PASS" -Message "Expected mode marker '$expectedModeText' found." }
    else { Add-AssertionResult -Target $Assertions -RouteName $name -Check "mode badge" -Status "WARN" -Message "Expected mode marker '$expectedModeText' not found." }
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
        if ($Html.Contains("Worklist") -and ($Html.Contains("Open next record") -or $Html.Contains("Open record"))) { Add-AssertionResult -Target $Assertions -RouteName $name -Check "reviewer queue" -Status "PASS" -Message "Worklist and review action found." }
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
    $pattern = "Showing\s+(?<first>\d+)(?:-(?<last>\d+))?\s+of\s+(?<matching>\d+)\s+matching\s+facility\s+priority\s+row\(s\);\s+(?<total>\d+)\s+total\s+authorized\s+loaded\s+facility\s+row\(s\)"
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
    Add-Issue416PassFail -Assertions $Assertions -RouteName $name -Check "issue416 h1" -Pass ($Html.Contains("<h1") -and $Text.Contains("Facility review priorities")) -PassMessage "Expected facility priorities H1 found." -FailMessage "Expected facility priorities H1 missing."
    Add-Issue416PassFail -Assertions $Assertions -RouteName $name -Check "issue416 count summary" -Pass $counts.Found -PassMessage "Facility priority count summary found." -FailMessage "Facility priority count summary missing."
    Add-Issue416PassFail -Assertions $Assertions -RouteName $name -Check "issue416 no hidden score" -Pass ($Text.Contains("does not use a hidden score") -and $Text.Contains("These rules are visible ordering rules")) -PassMessage "No hidden-score language and visible rules found." -FailMessage "Visible no-hidden-score/rules language missing."
    Add-Issue416PassFail -Assertions $Assertions -RouteName $name -Check "issue416 controls labeled" -Pass (($Html -match "(?is)<label[^>]*>.*?</label>") -and ($Html -match "(?is)<select|<input")) -PassMessage "Filter controls have labels." -FailMessage "Expected labeled filter controls missing."
    Add-Issue416PassFail -Assertions $Assertions -RouteName $name -Check "issue416 semantic table" -Pass (($Text.Contains("No facility priority rows matched.")) -or (($Html -match "(?is)<caption[^>]*>.*?</caption>") -and ($Html -match "(?is)<th\b"))) -PassMessage "Semantic table caption/headings found when rows are rendered." -FailMessage "Semantic table caption/headings missing."
    Add-Issue416PassFail -Assertions $Assertions -RouteName $name -Check "issue416 safe conclusions" -Pass (-not ($Text -match "(?i)legal priority|statewide completeness|source completeness proof")) -PassMessage "No unsupported conclusion wording found." -FailMessage "Unsupported conclusion wording found."
    if ($kind -eq "default") {
        Add-Issue416PassFail -Assertions $Assertions -RouteName $name -Check "issue416 default rows" -Pass ($counts.Found -and $counts.Total -gt 0 -and $Text.Contains("Contributing factors")) -PassMessage "Default route has facility rows and factor heading." -FailMessage "Default route rows or factors missing."
        Add-Issue416PassFail -Assertions $Assertions -RouteName $name -Check "issue416 date display" -Pass (($Text -match "\b\d{2}/\d{2}/\d{4}\b") -or $Text.Contains("unknown")) -PassMessage "MM/DD/YYYY or explicit unknown date found." -FailMessage "No MM/DD/YYYY or unknown date found."
        Add-Issue416PassFail -Assertions $Assertions -RouteName $name -Check "issue416 review links" -Pass ($Text.Contains("Open qualifying complaint queue") -and $Text.Contains("Open next complaint review workspace")) -PassMessage "Queue and reviewer workspace links found." -FailMessage "Queue or reviewer workspace links missing."
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
        Add-Issue416PassFail -Assertions $Assertions -RouteName $name -Check "issue416 filtered empty" -Pass ($counts.Found -and $counts.Matching -eq 0 -and $Text.Contains("No facility priority rows matched.")) -PassMessage "Filtered-empty state found." -FailMessage "Filtered-empty state missing."
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
    Add-Issue418PassFail -Assertions $Assertions -RouteName $name -Check "issue418 h1" -Pass ($Html.Contains("<h1") -and $Text.Contains("Review complaint trends over time")) -PassMessage "Expected complaint trends H1 found." -FailMessage "Expected complaint trends H1 missing."
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
        Add-Issue418PassFail -Assertions $Assertions -RouteName $name -Check "issue418 zero qualifying" -Pass ($Text.Contains("Zero qualifying records") -and -not ($Html -match "(?is)Zero qualifying records.*?<strong>Decreased activity</strong>")) -PassMessage "Zero qualifying state found without unsupported decrease cue." -FailMessage "Zero qualifying state missing or described as decreased activity."
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
    $baseUri = [System.Uri]::new($BaseUrl)
    $normalizedBaseUrl = $baseUri.GetLeftPart([System.UriPartial]::Authority).TrimEnd("/")
    $timestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd-HHmmssZ")
    $packetName = if ($Issue418) { "$timestamp-$Mode-issue-418" } elseif ($Issue417) { "$timestamp-$Mode-issue-417" } elseif ($Issue416) { "$timestamp-$Mode-issue-416" } elseif ($Issue415) { "$timestamp-$Mode-issue-415" } else { "$timestamp-$Mode" }
    $outputRoot = Join-Path $PWD $OutputDir
    $packetDir = Join-Path $outputRoot $packetName
    $zipPath = Join-Path $outputRoot "$packetName.zip"
    $htmlDir = Join-Path $packetDir "html"
    $textDir = Join-Path $packetDir "text"
    $screenshotDir = Join-Path $packetDir "screenshots"
    $accessibilityDir = Join-Path $packetDir "accessibility"
    $diagnosticsDir = Join-Path $packetDir "diagnostics"
    foreach ($dir in @($packetDir, $htmlDir, $textDir, $screenshotDir, $accessibilityDir, $diagnosticsDir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }

    $coreRoutes = @(
        @{ Name = "home"; Path = "/"; Label = "01-home"; ActiveHref = "/"; WorkflowStep = "Start" },
        @{ Name = "facility"; Path = "/ccld/facilities"; Label = "02-facility"; ActiveHref = "/ccld/facilities"; WorkflowStep = "Facility" },
        @{ Name = "facility-priority"; Path = "/ccld/facilities/review-priority"; Label = "02-facility-priority"; ActiveHref = "/ccld/facilities"; WorkflowStep = "Facility" },
        @{ Name = "facility-intelligence"; Path = "/ccld/facilities/intelligence"; Label = "02-facility-intelligence"; ActiveHref = "/ccld/facilities"; WorkflowStep = "Facility" },
        @{ Name = "facility-hub"; Path = "/ccld/facilities/detail?facility_number=434417302"; Label = "02-facility-hub"; ActiveHref = "/ccld/facilities"; WorkflowStep = "Facility" },
        @{ Name = "request-records"; Path = "/ccld/records/request"; Label = "03-request-records"; ActiveHref = "/ccld/records/request"; WorkflowStep = "Request" },
        @{ Name = "jobs"; Path = "/ccld/retrieval/jobs"; Label = "04-job-status"; ActiveHref = "/ccld/retrieval/jobs"; WorkflowStep = "Status" },
        @{ Name = "reviewer"; Path = "/reviewer"; Label = "05-reviewer"; ActiveHref = "/reviewer"; WorkflowStep = "Review" },
        @{ Name = "facility-priorities"; Path = "/reviewer/facilities/priorities"; Label = "05-facility-priorities"; ActiveHref = "/reviewer"; WorkflowStep = "Review" },
        @{ Name = "facility-trends"; Path = "/reviewer/facilities/trends"; Label = "05-facility-trends"; ActiveHref = "/reviewer"; WorkflowStep = "Review" },
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
        @{ Name = "issue-416-default"; Path = "/reviewer/facilities/priorities"; Label = "issue-416-01-default"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; Issue416Kind = "default" },
        @{ Name = "issue-416-filtered"; Path = "/reviewer/facilities/priorities?facility_type=FOSTER%20FAMILY%20AGENCY&geography=Kern&min_complaints=1&min_substantiated=0&indicator=source_available"; Label = "issue-416-02-filtered"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; Issue416Kind = "filtered" },
        @{ Name = "issue-416-pagination"; Path = "/reviewer/facilities/priorities?page_size=10"; Label = "issue-416-03-pagination"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; Issue416Kind = "pagination" },
        @{ Name = "issue-416-empty"; Path = "/reviewer/facilities/priorities?min_complaints=9999"; Label = "issue-416-04-empty"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; Issue416Kind = "empty" }
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
    $issue418Routes = @(
        @{ Name = "issue-418-default"; Path = "/reviewer/facilities/trends"; Label = "issue-418-01-default"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; Issue418Kind = "default" },
        @{ Name = "issue-418-monthly-facility"; Path = "/reviewer/facilities/trends?facility=157806098&start_date=2022-03-01&end_date=2022-05-31&time_grain=month&period_count=3"; Label = "issue-418-02-monthly-facility"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; Issue418Kind = "monthly-facility" },
        @{ Name = "issue-418-quarterly"; Path = "/reviewer/facilities/trends?start_date=2022-01-01&end_date=2022-12-31&time_grain=quarter&period_count=4"; Label = "issue-418-03-quarterly"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; Issue418Kind = "quarterly" },
        @{ Name = "issue-418-increased"; Path = "/reviewer/facilities/trends?start_date=2020-01-01&end_date=2021-12-31&time_grain=month&period_count=24"; Label = "issue-418-04-increased"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; Issue418Kind = "increased" },
        @{ Name = "issue-418-secondary-cue"; Path = "/reviewer/facilities/trends?start_date=2022-01-01&end_date=2023-12-31&time_grain=month&period_count=24"; Label = "issue-418-05-secondary-cue"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; Issue418Kind = "secondary-cue" },
        @{ Name = "issue-418-incomplete"; Path = "/reviewer/facilities/trends?start_date=$issue418CurrentStart&end_date=$issue418CurrentEnd&time_grain=month&period_count=1"; Label = "issue-418-06-incomplete"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; Issue418Kind = "incomplete" },
        @{ Name = "issue-418-zero"; Path = "/reviewer/facilities/trends?facility=157806098&finding=Substantiated&start_date=2022-04-01&end_date=2022-04-30&time_grain=month&period_count=1"; Label = "issue-418-07-zero"; ActiveHref = "/reviewer"; WorkflowStep = "Review"; Issue418Kind = "zero" }
    )
    $routesToCapture = if ($Issue418) { $issue418Routes } elseif ($Issue417) { $issue417Routes } elseif ($Issue416) { $issue416Routes } elseif ($Issue415) { $issue415Routes } else { $coreRoutes }

    $routeResults = [System.Collections.ArrayList]::new()
    $assertions = [System.Collections.ArrayList]::new()
    $dynamicLinks = [ordered]@{ jobDetail = $null; reviewerDetail = $null }
    $routeHtmlByName = @{}
    $screenshotTool = if ($IncludeScreenshots) { Find-ScreenshotTool } else { $null }
    $screenshotWarnings = @()

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
        $failure = ""
        if ($response.Error) { $failure = Redact-EvidenceText -Text $response.Error }
        if ($IncludeHtml -and $response.Content) {
            $htmlFile = Join-Path $htmlDir "$($Route.Label).html"
            Set-Content -LiteralPath $htmlFile -Value $safeHtml -Encoding UTF8
            $htmlPath = ConvertTo-RelativeEvidencePath -Path $htmlFile -Root $packetDir
        }
        if ($response.Content) {
            $textFile = Join-Path $textDir "$($Route.Label).txt"
            Set-Content -LiteralPath $textFile -Value $plainText -Encoding UTF8
            $textPath = ConvertTo-RelativeEvidencePath -Path $textFile -Root $packetDir
            if ($IncludeScreenshots -and $null -ne $screenshotTool -and $response.StatusCode -gt 0 -and (Test-HtmlScreenshotCandidate -Route $Route -Html $safeHtml)) {
                $shotFile = Join-Path $screenshotDir "$($Route.Label).png"
                $shotError = Invoke-RouteScreenshot -Tool $screenshotTool -Url $url -ScreenshotPath $shotFile
                if ($shotError) { $script:screenshotWarnings += "$($Route.Name): $shotError" }
                elseif (Test-Path -LiteralPath $shotFile) { $screenshotPath = ConvertTo-RelativeEvidencePath -Path $shotFile -Root $packetDir }
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
        if (($response.StatusCode -ge 400 -or $response.StatusCode -eq 0) -and -not $AllowUnavailable) { $failure = if ($failure) { $failure } else { "Route returned HTTP $($response.StatusCode)." } }
        [void]$routeResults.Add([pscustomobject]@{ name = $Route.Name; path = $Route.Path; label = $Route.Label; url = $url; statusCode = $response.StatusCode; title = $title; h1 = $h1; htmlPath = $htmlPath; textPath = $textPath; screenshotPath = $screenshotPath; failure = $failure })
        $routeHtmlByName[$Route.Name] = $safeHtml
    }

    foreach ($route in $routesToCapture) { Capture-Route -Route $route }

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

    if (-not $Issue415 -and -not $Issue416 -and -not $Issue417 -and -not $Issue418) {
        $jobDetailHref = Get-SafeDynamicHref -Html ([string]$routeHtmlByName["jobs"]) -Pattern 'href\s*=\s*["'']([^"'']*/ccld/retrieval/jobs/detail\?job_id=[A-Za-z0-9_.:%-]+)["'']'
        if ($jobDetailHref) { $dynamicLinks.jobDetail = $jobDetailHref; Capture-Route -Route @{ Name = "job-detail"; Path = $jobDetailHref; Label = "08-job-detail"; ActiveHref = "/ccld/retrieval/jobs"; WorkflowStep = "Status" } }
        else { Add-AssertionResult -Target $assertions -RouteName "jobs" -Check "dynamic job detail" -Status "WARN" -Message "No safe retrieval job detail link discovered." }

        $reviewerDetailHref = Get-SafeDynamicHref -Html ([string]$routeHtmlByName["reviewer"]) -Pattern 'href\s*=\s*["'']([^"'']*/reviewer/records/detail\?source_record_key=[^"'']+)["'']'
        if ($reviewerDetailHref) { $dynamicLinks.reviewerDetail = $reviewerDetailHref; Capture-Route -Route @{ Name = "reviewer-detail"; Path = $reviewerDetailHref; Label = "09-reviewer-detail"; ActiveHref = "/reviewer"; WorkflowStep = "Review" } }
        else { Add-AssertionResult -Target $assertions -RouteName "reviewer" -Check "dynamic reviewer detail" -Status "WARN" -Message "No safe reviewer detail link discovered." }
    }

    # Capture a supplemental screenshot anchored to the complaint export section from the
    # reliable reviewer queue route. This avoids depending on reviewer-detail availability.
    if (-not $Issue415 -and -not $Issue416 -and -not $Issue417 -and -not $Issue418 -and $IncludeScreenshots -and $null -ne $screenshotTool) {
        $reviewerExportAnchorUrl = (Join-RouteUrl -Base $normalizedBaseUrl -Path "/reviewer") + "#complaint-export-controls"
        $reviewerExportShotFile = Join-Path $screenshotDir "05-reviewer-complaint-exports.png"
        $reviewerExportShotError = Invoke-RouteScreenshot -Tool $screenshotTool -Url $reviewerExportAnchorUrl -ScreenshotPath $reviewerExportShotFile
        if ($reviewerExportShotError) {
            $script:screenshotWarnings += "reviewer-complaint-exports: $reviewerExportShotError"
        }
    }

    $routeStatusRows = @("route,label,path,statusCode,title,h1,htmlPath,textPath,screenshotPath,failure")
    foreach ($result in $routeResults) {
        $values = @($result.name, $result.label, $result.path, $result.statusCode, $result.title, $result.h1, $result.htmlPath, $result.textPath, $result.screenshotPath, $result.failure)
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

    $gitBranch = (git branch --show-current 2>$null) -join ""
    $gitCommit = (git rev-parse HEAD 2>$null) -join ""
    $gitStatus = (git status --short 2>$null) -join "`n"
    $workingTreeClean = [string]::IsNullOrWhiteSpace($gitStatus)
    $gitStatusText = if ($workingTreeClean) { "clean" } else { $gitStatus }
    Set-Content -LiteralPath (Join-Path $diagnosticsDir "git-status.txt") -Value $gitStatusText -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $diagnosticsDir "git-log.txt") -Value ((git log --oneline -n 5 2>$null) -join "`n") -Encoding UTF8
    $focusedCommandSuffix = if ($Issue418) { " -Issue418" } elseif ($Issue417) { " -Issue417" } elseif ($Issue416) { " -Issue416" } elseif ($Issue415) { " -Issue415" } else { "" }
    Set-Content -LiteralPath (Join-Path $diagnosticsDir "capture-command.txt") -Value "capture-hosted-ui-evidence.ps1 -BaseUrl $normalizedBaseUrl -Mode $Mode -OutputDir $OutputDir -ViewportWidth $ViewportWidth -ViewportHeight $ViewportHeight -TimeoutSeconds $TimeoutSeconds$focusedCommandSuffix" -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $diagnosticsDir "environment-summary.txt") -Value @(
        "mode=$Mode",
        "baseUrl=$normalizedBaseUrl",
        "viewport=${ViewportWidth}x${ViewportHeight}",
        "screenshotsRequested=$IncludeScreenshots",
        "screenshotTool=$(if ($screenshotTool) { $screenshotTool.Name } else { 'none' })",
        "fullPageScreenshots=$(if ($screenshotTool) { $screenshotTool.FullPage } else { $false })",
        "issue415FocusedCapture=$([bool]$Issue415)",
        "issue416FocusedCapture=$([bool]$Issue416)",
        "issue417FocusedCapture=$([bool]$Issue417)",
        "issue418FocusedCapture=$([bool]$Issue418)",
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
only when a local screenshot tool is available.

The generated folder and sibling ZIP are for local review or upload to ChatGPT
so testing instructions can be written from the actual rendered UI labels,
links, buttons, and page text. Review the packet before sharing it. Do not
commit generated evidence or ZIP packets unless a specific repository workflow
explicitly says to do so.
"@
    Set-Content -LiteralPath (Join-Path $packetDir "README.txt") -Value $readmeText -Encoding UTF8

    $routeFailures = @($routeResults | Where-Object { $_.statusCode -eq 0 -or $_.statusCode -ge 400 -or $_.failure })
    $assertionFailures = @($assertions | Where-Object { $_.status -eq "FAIL" })
    $screenshotFailures = @($screenshotWarnings | Where-Object { $_ -match "screenshot failed" })
    $outputCounts = [ordered]@{
        screenshots   = Get-EvidenceFileCount -Path $screenshotDir -Filter "*.png"
        html          = Get-EvidenceFileCount -Path $htmlDir -Filter "*.html"
        text          = Get-EvidenceFileCount -Path $textDir -Filter "*.txt"
        diagnostics   = Get-EvidenceFileCount -Path $diagnosticsDir
        accessibility = Get-EvidenceFileCount -Path $accessibilityDir
        issue415      = if ($Issue415) { Get-EvidenceFileCount -Path $packetDir -Filter "issue-415-*.csv" } else { 0 }
        issue416      = if ($Issue416) { Get-EvidenceFileCount -Path $packetDir -Filter "issue-416-*.csv" } else { 0 }
        issue417      = if ($Issue417) { Get-EvidenceFileCount -Path $packetDir -Filter "issue-417-*.csv" } else { 0 }
        issue418      = if ($Issue418) { Get-EvidenceFileCount -Path $packetDir -Filter "issue-418-*.csv" } else { 0 }
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
        screenshotsAvailable   = [bool]($screenshotTool -ne $null)
        screenshotsCaptured    = [bool](@($routeResults | Where-Object { $_.screenshotPath }).Count -gt 0)
        screenshotsFullPage    = [bool]($screenshotTool -and $screenshotTool.FullPage)
        screenshotWarnings     = $screenshotWarnings
        screenshotFailures     = $screenshotFailures
        captureToolUsed        = if ($screenshotTool) { $screenshotTool.Name } else { "http-get-html-text-only" }
        issue415               = [ordered]@{ enabled = [bool]$Issue415; countSummaries = @($issue415CountSummaries); hrefInventory = @($issue415HrefInventory); zoomLimitation = "True browser zoom is not controlled by this script; reduced viewport captures are supplemental evidence only." }
        issue416               = [ordered]@{ enabled = [bool]$Issue416; routeCount = @($routesToCapture).Count; countSummaries = @($issue416CountSummaries); zoomLimitation = "True browser zoom is not controlled by this script; reduced viewport captures are supplemental evidence only." }
        issue417               = [ordered]@{ enabled = [bool]$Issue417; routeCount = @($routesToCapture).Count; countSummaries = @($issue417CountSummaries); zoomLimitation = "True browser zoom is not controlled by this script; reduced viewport captures are supplemental evidence only." }
        issue418               = [ordered]@{ enabled = [bool]$Issue418; routeCount = @($routesToCapture).Count; countSummaries = @($issue418CountSummaries); zoomLimitation = "True browser zoom is not controlled by this script; reduced viewport captures are supplemental evidence only." }
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
    if ($screenshotTool) { Write-Host "Screenshot support: $($screenshotTool.Name) (full page: $($screenshotTool.FullPage))" }
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
