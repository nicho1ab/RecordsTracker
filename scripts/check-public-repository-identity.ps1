[CmdletBinding()]
param(
    [string]$TermsFile = (Join-Path (Split-Path -Parent $PSScriptRoot) '.private\prohibited-terms.txt')
)

$ErrorActionPreference = 'Stop'

$Terms = New-Object System.Collections.Generic.List[string]

$EnvironmentTerms = [Environment]::GetEnvironmentVariable('CCLD_PROHIBITED_TERMS')
if (-not [string]::IsNullOrWhiteSpace($EnvironmentTerms)) {
    foreach ($Term in ($EnvironmentTerms -split '\|')) {
        if (-not [string]::IsNullOrWhiteSpace($Term)) { [void]$Terms.Add($Term.Trim()) }
    }
}
elseif (Test-Path -LiteralPath $TermsFile -PathType Leaf) {
    foreach ($Term in Get-Content -LiteralPath $TermsFile) {
        if (-not [string]::IsNullOrWhiteSpace($Term) -and -not $Term.TrimStart().StartsWith('#')) { [void]$Terms.Add($Term.Trim()) }
    }
}
else {
    throw "No prohibited-terms source was found. Create the ignored file $TermsFile or set CCLD_PROHIBITED_TERMS using pipe-separated values."
}

if ($Terms.Count -eq 0) { throw 'No prohibited terms were supplied.' }

$TrackedFiles = @(git ls-files | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) })
$Findings = New-Object System.Collections.Generic.List[string]

$LineNumber = 0
foreach ($File in $TrackedFiles) {
    $LineNumber = 0
    foreach ($Line in Get-Content -LiteralPath $File -ErrorAction SilentlyContinue) {
        $LineNumber++
        foreach ($Term in $Terms) {
            $Escaped = [regex]::Escape($Term)
            if ($Term -match '^[A-Za-z0-9_-]+$') { $Pattern = '(?i)(?<![A-Za-z0-9])' + $Escaped + '(?![A-Za-z0-9])' } else { $Pattern = '(?i)' + $Escaped }
            if ($Line -match $Pattern) { [void]$Findings.Add(('{0}:{1}: prohibited term found' -f $File,$LineNumber)) }
        }
    }
}

if ($Findings.Count -gt 0) {
    Write-Host 'Prohibited public-repository identity information was found:'
    $Findings | Sort-Object -Unique | ForEach-Object { Write-Host $_ }
    exit 1
}

Write-Host 'Public repository identity check passed.'
exit 0