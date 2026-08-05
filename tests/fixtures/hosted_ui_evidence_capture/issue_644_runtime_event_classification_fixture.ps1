param([Parameter(Mandatory)][string]$CaptureScriptPath)
$ErrorActionPreference='Stop'
. $CaptureScriptPath -LibraryOnly
function Get-Result { param([scriptblock]$Action) try { & $Action; 'not rejected' } catch { $_.Exception.Message } }
$beacon='https://static.cloudflareinsights.com/beacon.min.js?token=fixture'
$valid = New-RuntimeEventClassificationLedger -BrowserStates @([pscustomobject]@{routeName='compare';consoleErrors=@("Failed to load resource: $beacon");consoleWarnings=@();pageErrors=@();failedNetworkRequests=@($beacon)})
$zero = New-RuntimeEventClassificationLedger -BrowserStates @([pscustomobject]@{routeName='zero';consoleErrors=@();consoleWarnings=@();pageErrors=@();failedNetworkRequests=@()})
$unknown = Get-Result { New-RuntimeEventClassificationLedger -BrowserStates @([pscustomobject]@{routeName='compare';consoleErrors=@();consoleWarnings=@();pageErrors=@();failedNetworkRequests=@('https://example.invalid/x.js')}) }
$application = Get-Result { New-RuntimeEventClassificationLedger -BrowserStates @([pscustomobject]@{routeName='compare';consoleErrors=@('app failure');consoleWarnings=@();pageErrors=@();failedNetworkRequests=@('http://127.0.0.1:8010/app.js')}) }
$duplicate = Get-Result { $copy=$valid | ConvertTo-Json -Depth 10 | ConvertFrom-Json; $copy.consoleClassifications += $copy.consoleClassifications[0]; Test-RuntimeEventClassificationLedger -Ledger $copy }
$omitted = Get-Result { $copy=$valid | ConvertTo-Json -Depth 10 | ConvertFrom-Json; $copy.networkClassifications=@(); Test-RuntimeEventClassificationLedger -Ledger $copy }
$unobserved = Get-Result { $copy=$valid | ConvertTo-Json -Depth 10 | ConvertFrom-Json; $copy.networkClassifications[0].observedDetail='https://static.cloudflareinsights.com/beacon.min.js?unobserved'; Test-RuntimeEventClassificationLedger -Ledger $copy }
[ordered]@{valid=$valid;zero=$zero;unknown=$unknown;application=$application;duplicate=$duplicate;omitted=$omitted;unobserved=$unobserved}|ConvertTo-Json -Depth 10
