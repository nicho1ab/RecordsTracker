<#
.SYNOPSIS
Summarizes safe QNAP pilot hosted route evidence.
.DESCRIPTION
Runs bounded GET-only checks against the expected hosted CCLD route surface and
prints a concise evidence summary. This script does not mutate data, run
imports, run retrieval, submit feedback, call live CCLD, call GitHub, print
response bodies, print secrets, print raw artifact contents, print raw server
paths, or make public-source completeness or legal conclusions.
.PARAMETER BaseUrl
Hosted app base URL. Defaults to http://127.0.0.1:8000.
.PARAMETER TimeoutSeconds
Per-route request timeout in seconds. Defaults to 10.
.PARAMETER AllowUnavailable
Return success when the app is unreachable. Intended only for documentation and
static validation contexts where no server is running.
.EXAMPLE
.\scripts\summarize-qnap-pilot-route-evidence.ps1 -BaseUrl http://<host-name-or-ip>:8000
.EXAMPLE
.\scripts\summarize-qnap-pilot-route-evidence.ps1 -AllowUnavailable
.NOTES
Run after starting the hosted app and after the QNAP verifier passes.
#>
param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [ValidateRange(1, 120)]
    [int]$TimeoutSeconds = 10,
    [switch]$AllowUnavailable
)

$ErrorActionPreference = "Stop"
$failureCount = 0
$warningCount = 0

$forbiddenMarkers = @(
    "provider_subject",
    "provider-subject",
    "provider_issuer",
    "provider-issuer",
    "client_secret",
    "client-secret",
    "raw provider claims",
    "raw_provider_claims",
    "connection string",
    "connection_string",
    "set-cookie",
    "cookie=",
    "authorization:",
    "bearer ",
    "github_pat_",
    "ghp_"
)

$routes = @(
    @{ Path = "/"; AllowedStatus = @(200); RequiredText = @("CCLD Records Review"); Expected = "hosted app shell" },
    @{ Path = "/health"; AllowedStatus = @(200); RequiredText = @('"status": "ok"'); Expected = "health OK" },
    @{ Path = "/auth/status"; AllowedStatus = @(200); RequiredText = @("auth"); Expected = "safe auth status" },
    @{ Path = "/feedback"; AllowedStatus = @(200); RequiredText = @("Tester feedback"); Expected = "feedback form or safe unconfigured state" },
    @{ Path = "/ccld/facilities"; AllowedStatus = @(200, 401, 503); RequiredText = @(); Expected = "facility lookup, protected, or setup-required state" },
    @{ Path = "/ccld/records/request"; AllowedStatus = @(200, 401, 503); RequiredText = @(); Expected = "request page, protected, or setup-required state" },
    @{ Path = "/ccld/retrieval/jobs"; AllowedStatus = @(200, 401, 503); RequiredText = @(); Expected = "retrieval history, protected, or setup-required state" },
    @{ Path = "/ccld/retrieval/jobs/detail?job_id=missing-job"; AllowedStatus = @(400, 401, 404, 503); RequiredText = @(); Expected = "safe missing-job detail state" },
    @{ Path = "/ccld/help"; AllowedStatus = @(200); RequiredText = @("How CCLD review works"); Expected = "public CCLD help" },
    @{ Path = "/reviewer"; AllowedStatus = @(200, 401, 503); RequiredText = @(); Expected = "reviewer UI, protected, or setup-required state" }
)

function Write-EvidencePass {
    param([string]$Message)
    Write-Host "[PASS] $Message"
}

function Write-EvidenceWarn {
    param([string]$Message)
    $script:warningCount += 1
    Write-Warning $Message
}

function Write-EvidenceFail {
    param([string]$Message)
    $script:failureCount += 1
    Write-Host "[FAIL] $Message"
}

function Invoke-RouteEvidenceCheck {
    param([hashtable]$Route)

    $base = $BaseUrl.TrimEnd("/")
    $url = "$base$($Route.Path)"
    try {
        $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec $TimeoutSeconds -ErrorAction Stop
        $status = [int]$response.StatusCode
        $content = [string]$response.Content
    }
    catch {
        if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
            $status = [int]$_.Exception.Response.StatusCode
            $content = [string]$_.ErrorDetails.Message
            try {
                if ($_.Exception.Response.Content -and $_.Exception.Response.Content.ReadAsStringAsync) {
                    $content = $_.Exception.Response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
                }
                elseif ($_.Exception.Response.GetResponseStream) {
                    $reader = [System.IO.StreamReader]::new($_.Exception.Response.GetResponseStream())
                    $content = $reader.ReadToEnd()
                    $reader.Dispose()
                }
            }
            catch {
                $content = [string]$_.ErrorDetails.Message
            }
        }
        else {
            if ($AllowUnavailable) {
                Write-EvidenceWarn "Route $($Route.Path) unavailable at $base; no response body printed."
                return
            }
            Write-EvidenceFail "Route $($Route.Path) could not be reached at $base."
            return
        }
    }

    if ($Route.AllowedStatus -notcontains $status) {
        Write-EvidenceFail "Route $($Route.Path) returned HTTP $status; expected one of $($Route.AllowedStatus -join ', ')."
        return
    }

    foreach ($marker in $Route.RequiredText) {
        if (-not $content.Contains($marker)) {
            Write-EvidenceFail "Route $($Route.Path) returned HTTP $status but did not include expected safe marker '$marker'."
            return
        }
    }

    $lowerContent = $content.ToLowerInvariant()
    foreach ($marker in $forbiddenMarkers) {
        if ($lowerContent.Contains($marker)) {
            Write-EvidenceFail "Route $($Route.Path) returned forbidden private marker '$marker'. Response body was not printed."
            return
        }
    }

    Write-EvidencePass "Route $($Route.Path) returned HTTP $status ($($Route.Expected))."
}

Write-Host "QNAP pilot route evidence summary"
Write-Host "Base URL: $($BaseUrl.TrimEnd('/'))"
Write-Host "GET-only: yes. POSTs, imports, retrieval execution, reviewer-created writes, and feedback submission are not performed."
Write-Host "External calls: no live CCLD calls and no GitHub calls are made by this evidence command."
Write-Host "Safe output: response bodies, secrets, raw artifacts, raw source narrative, raw server paths, cookies, provider subjects, provider issuers, and connection strings are not printed."
Write-Host "Conclusion boundary: no public-source completeness, legal, facility-wide, harm, abuse, neglect, or liability conclusion."

foreach ($route in $routes) {
    Invoke-RouteEvidenceCheck -Route $route
}

Write-Host "Response bodies printed: no."
Write-Host "Raw artifact contents printed: no."
Write-Host "Raw server-specific paths printed: no."
Write-Host "Secrets printed: no."

if ($failureCount -gt 0) {
    Write-Host "Route evidence completed with $failureCount readiness failure(s) and $warningCount warning(s)."
    exit 1
}

Write-Host "Route evidence completed with $warningCount warning(s) and no readiness failures."
exit 0