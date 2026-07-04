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
.EXAMPLE
.\scripts\capture-hosted-ui-evidence.ps1 -BaseUrl http://127.0.0.1:8003 -Mode live
.EXAMPLE
.\scripts\capture-hosted-ui-evidence.ps1 -BaseUrl http://127.0.0.1:8010 -Mode fixture
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

    [switch]$AllowUnavailable
)

$ErrorActionPreference = "Stop"

$evidencePurpose = "Local hosted UI review evidence for route status, text markers, assertions, accessibility snapshots, and screenshots."
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
        "home" = @("Start a Facility Complaint Review", "Review path")
        "facility" = @("Find a facility", "Find the facility/license number")
        "facility-priority" = @("Facility review priority", "Facilities grouped by review cue priority")
        "facility-intelligence" = @("Facility review intelligence", "Facilities by review-priority indicator")
        "facility-hub" = @("Facility review hub", "Facility-directory details")
        "request-records" = @("Request Records", "Which facility should be reviewed?")
        "jobs" = @("Job diagnostics", "Track Request Records jobs")
        "reviewer" = @("Complaint records ready for review", "Worklist")
        "substantiated-triage" = @("substantiated complaint triage", "Source-derived finding")
        "packet-preview-empty" = @("Review packet preview", "No facility/date packet context was supplied.")
        "packet-preview-context" = @("Review packet preview", "Packet preparation preview")
        "packet-draft-empty" = @("Attorney Review Packet Draft", "No facility/date packet context was supplied.")
        "packet-draft-context" = @("Attorney Review Packet Draft", "Packet scope")
        "feedback" = @("Report an issue", "Report a review issue")
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
    $packetName = "$timestamp-$Mode"
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
        @{ Name = "substantiated-triage"; Path = "/reviewer/records/substantiated"; Label = "05-substantiated-triage"; ActiveHref = "/reviewer"; WorkflowStep = "Review" },
        @{ Name = "matrix-export"; Path = "/reviewer/records/matrix.csv?facility_number=157806098&start_date=2022-08-01&end_date=2022-08-31&request_context_origin=manual_entry"; Label = "05-matrix-export" },
        @{ Name = "packet-preview-empty"; Path = "/reviewer/packet/preview"; Label = "06-packet-preview-empty"; ActiveHref = "/reviewer"; WorkflowStep = "Review" },
        @{ Name = "packet-preview-context"; Path = "/reviewer/packet/preview?facility_number=157806098&start_date=2022-08-01&end_date=2022-08-31&request_context_origin=manual_entry"; Label = "06-packet-preview-context"; ActiveHref = "/reviewer"; WorkflowStep = "Review" },
        @{ Name = "packet-draft-empty"; Path = "/reviewer/packet/draft"; Label = "07-packet-draft-empty"; ActiveHref = "/reviewer"; WorkflowStep = "Review" },
        @{ Name = "packet-draft-context"; Path = "/reviewer/packet/draft?facility_number=157806098&start_date=2022-08-01&end_date=2022-08-31&request_context_origin=manual_entry"; Label = "08-packet-draft-context"; ActiveHref = "/reviewer"; WorkflowStep = "Review" },
        @{ Name = "feedback"; Path = "/feedback"; Label = "09-feedback"; ActiveHref = "/feedback"; WorkflowStep = "Report" },
        @{ Name = "help"; Path = "/ccld/help"; Label = "10-help"; ActiveHref = "/ccld/help" }
    )

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
        if (($response.StatusCode -ge 400 -or $response.StatusCode -eq 0) -and -not $AllowUnavailable) { $failure = if ($failure) { $failure } else { "Route returned HTTP $($response.StatusCode)." } }
        [void]$routeResults.Add([pscustomobject]@{ name = $Route.Name; path = $Route.Path; label = $Route.Label; url = $url; statusCode = $response.StatusCode; title = $title; h1 = $h1; htmlPath = $htmlPath; textPath = $textPath; screenshotPath = $screenshotPath; failure = $failure })
        $routeHtmlByName[$Route.Name] = $safeHtml
    }

    foreach ($route in $coreRoutes) { Capture-Route -Route $route }

    $jobDetailHref = Get-SafeDynamicHref -Html ([string]$routeHtmlByName["jobs"]) -Pattern 'href\s*=\s*["'']([^"'']*/ccld/retrieval/jobs/detail\?job_id=[A-Za-z0-9_.:%-]+)["'']'
    if ($jobDetailHref) { $dynamicLinks.jobDetail = $jobDetailHref; Capture-Route -Route @{ Name = "job-detail"; Path = $jobDetailHref; Label = "08-job-detail"; ActiveHref = "/ccld/retrieval/jobs"; WorkflowStep = "Status" } }
    else { Add-AssertionResult -Target $assertions -RouteName "jobs" -Check "dynamic job detail" -Status "WARN" -Message "No safe retrieval job detail link discovered." }

    $reviewerDetailHref = Get-SafeDynamicHref -Html ([string]$routeHtmlByName["reviewer"]) -Pattern 'href\s*=\s*["'']([^"'']*/reviewer/records/detail\?source_record_key=[^"'']+)["'']'
    if ($reviewerDetailHref) { $dynamicLinks.reviewerDetail = $reviewerDetailHref; Capture-Route -Route @{ Name = "reviewer-detail"; Path = $reviewerDetailHref; Label = "09-reviewer-detail"; ActiveHref = "/reviewer"; WorkflowStep = "Review" } }
    else { Add-AssertionResult -Target $assertions -RouteName "reviewer" -Check "dynamic reviewer detail" -Status "WARN" -Message "No safe reviewer detail link discovered." }

    # Capture a supplemental screenshot anchored to the complaint export section from the
    # reliable reviewer queue route. This avoids depending on reviewer-detail availability.
    if ($IncludeScreenshots -and $null -ne $screenshotTool) {
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

    $gitBranch = (git branch --show-current 2>$null) -join ""
    $gitCommit = (git rev-parse HEAD 2>$null) -join ""
    $gitStatus = (git status --short 2>$null) -join "`n"
    $workingTreeClean = [string]::IsNullOrWhiteSpace($gitStatus)
    $gitStatusText = if ($workingTreeClean) { "clean" } else { $gitStatus }
    Set-Content -LiteralPath (Join-Path $diagnosticsDir "git-status.txt") -Value $gitStatusText -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $diagnosticsDir "git-log.txt") -Value ((git log --oneline -n 5 2>$null) -join "`n") -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $diagnosticsDir "capture-command.txt") -Value "capture-hosted-ui-evidence.ps1 -BaseUrl $normalizedBaseUrl -Mode $Mode -OutputDir $OutputDir -ViewportWidth $ViewportWidth -ViewportHeight $ViewportHeight -TimeoutSeconds $TimeoutSeconds" -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $diagnosticsDir "environment-summary.txt") -Value @(
        "mode=$Mode",
        "baseUrl=$normalizedBaseUrl",
        "viewport=${ViewportWidth}x${ViewportHeight}",
        "screenshotsRequested=$IncludeScreenshots",
        "screenshotTool=$(if ($screenshotTool) { $screenshotTool.Name } else { 'none' })",
        "fullPageScreenshots=$(if ($screenshotTool) { $screenshotTool.FullPage } else { $false })",
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
