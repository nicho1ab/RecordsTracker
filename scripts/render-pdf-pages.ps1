param(
    [Parameter(Mandatory = $true)][string]$PdfPath,
    [Parameter(Mandatory = $true)][string]$OutputDir
)

$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSEdition -ne 'Desktop') {
    throw 'Run this helper with Windows PowerShell so the built-in Windows PDF renderer is available.'
}
Add-Type -AssemblyName System.Runtime.WindowsRuntime

function Get-PngDimensions([string]$Path) {
    $bytes = [System.IO.File]::ReadAllBytes($Path)
    if ($bytes.Length -lt 24 -or $bytes[0] -ne 137 -or $bytes[1] -ne 80 -or $bytes[2] -ne 78 -or $bytes[3] -ne 71) {
        throw "Rendered page is not a PNG: $Path"
    }
    $width = ([int]$bytes[16] -shl 24) -bor ([int]$bytes[17] -shl 16) -bor ([int]$bytes[18] -shl 8) -bor [int]$bytes[19]
    $height = ([int]$bytes[20] -shl 24) -bor ([int]$bytes[21] -shl 16) -bor ([int]$bytes[22] -shl 8) -bor [int]$bytes[23]
    if ($width -le 0 -or $height -le 0) { throw "Rendered page has invalid dimensions: $Path" }
    return [pscustomobject]@{ width = $width; height = $height }
}

function Await-Operation([object]$Operation, [Type]$ResultType) {
    $method = [System.WindowsRuntimeSystemExtensions].GetMethods() |
        Where-Object { $_.Name -eq 'AsTask' -and $_.IsGenericMethodDefinition -and $_.GetParameters().Count -eq 1 } |
        Select-Object -First 1
    return $method.MakeGenericMethod($ResultType).Invoke($null, @($Operation)).Result
}

function Await-Action([object]$Operation) {
    $method = [System.WindowsRuntimeSystemExtensions].GetMethods() |
        Where-Object { $_.Name -eq 'AsTask' -and -not $_.IsGenericMethodDefinition -and $_.GetParameters().Count -eq 1 } |
        Select-Object -First 1
    $method.Invoke($null, @($Operation)).Wait()
}

$pdfFullPath = (Resolve-Path -LiteralPath $PdfPath).Path
if ((Get-Item -LiteralPath $pdfFullPath).Length -le 0) { throw 'PDF is empty.' }
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$outputFullPath = (Resolve-Path -LiteralPath $OutputDir).Path
$outputFolder = Await-Operation ([Windows.Storage.StorageFolder,Windows.Storage,ContentType=WindowsRuntime]::GetFolderFromPathAsync($outputFullPath)) ([Windows.Storage.StorageFolder,Windows.Storage,ContentType=WindowsRuntime])
$storageFile = Await-Operation ([Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime]::GetFileFromPathAsync($pdfFullPath)) ([Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime])
$document = Await-Operation ([Windows.Data.Pdf.PdfDocument,Windows.Data.Pdf,ContentType=WindowsRuntime]::LoadFromFileAsync($storageFile)) ([Windows.Data.Pdf.PdfDocument,Windows.Data.Pdf,ContentType=WindowsRuntime])
if ($document.PageCount -le 0) { throw 'PDF page count is zero.' }
$pages = @()
for ($index = 0; $index -lt $document.PageCount; $index++) {
    $page = $document.GetPage($index)
    $outputPath = Join-Path $OutputDir ('page-{0:D3}.png' -f ($index + 1))
    $outputFile = Await-Operation ($outputFolder.CreateFileAsync([IO.Path]::GetFileName($outputPath), [Windows.Storage.CreationCollisionOption]::ReplaceExisting)) ([Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime])
    $stream = Await-Operation ($outputFile.OpenAsync([Windows.Storage.FileAccessMode]::ReadWrite)) ([Windows.Storage.Streams.IRandomAccessStream,Windows.Storage.Streams,ContentType=WindowsRuntime])
    Await-Action ($page.RenderToStreamAsync($stream))
    $stream.Dispose(); $page.Dispose()
    if (-not (Test-Path -LiteralPath $outputPath) -or (Get-Item -LiteralPath $outputPath).Length -le 0) { throw "Rendered page is missing or empty: $outputPath" }
    $dimensions = Get-PngDimensions -Path $outputPath
    $pages += [pscustomobject]@{ file = [IO.Path]::GetFileName($outputPath); sha256 = (Get-FileHash -LiteralPath $outputPath -Algorithm SHA256).Hash; size = (Get-Item -LiteralPath $outputPath).Length; width = $dimensions.width; height = $dimensions.height }
}
[pscustomobject]@{ pdf = [IO.Path]::GetFileName($pdfFullPath); pageCount = $document.PageCount; pages = $pages } | ConvertTo-Json -Depth 4
