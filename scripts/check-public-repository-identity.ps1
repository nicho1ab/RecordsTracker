[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$Rules = @(
    @{
        Label = 'personal email'
        Pattern = '(?i)andrew@andrewnichols\.com'
    },
    @{
        Label = 'institutional email'
        Pattern = '(?i)abn@the user's institution\.edu'
    },
    @{
        Label = 'stakeholder organization domain'
        Pattern = '(?i)external stakeholder organization\.org'
    },
    @{
        Label = 'stakeholder personal name'
        Pattern = '(?i)(?<![A-Za-z0-9])external stakeholder(?![A-Za-z0-9])'
    },
    @{
        Label = 'employer acronym'
        Pattern = '(?i)(?<![A-Za-z0-9])the user's employer(?![A-Za-z0-9])'
    },
    @{
        Label = 'institution acronym'
        Pattern = '(?i)(?<![A-Za-z0-9])the user's institution(?![A-Za-z0-9])'
    },
    @{
        Label = 'private test hostname'
        Pattern = '(?i)test\.recordtracker\.xyz'
    },
    @{
        Label = 'private hostname'
        Pattern = '(?i)(?<![A-Za-z0-9.])recordtracker\.xyz(?![A-Za-z0-9.])'
    }
)

$TrackedFiles = @(
    git ls-files |
    Where-Object {
        $_ -and
        (Test-Path -LiteralPath $_ -PathType Leaf)
    }
)

$Findings = New-Object System.Collections.Generic.List[string]

foreach ($File in $TrackedFiles) {
    $LineNumber = 0

    foreach ($Line in Get-Content -LiteralPath $File -ErrorAction SilentlyContinue) {
        $LineNumber++

        foreach ($Rule in $Rules) {
            if ($Line -match $Rule.Pattern) {
                $Finding = '{0}`t{1}:{2}:{3}' -f `
                    $Rule.Label,
                    $File,
                    $LineNumber,
                    $Line

                [void]$Findings.Add($Finding)
            }
        }
    }
}

if ($Findings.Count -gt 0) {
    Write-Host 'Prohibited public-repository identity information was found:'

    foreach ($Finding in $Findings) {
        Write-Host $Finding
    }

    exit 1
}

Write-Host 'Public repository identity check passed.'
exit 0