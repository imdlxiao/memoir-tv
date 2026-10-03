# Author: donglixiao
# Register quiet startup after the current Windows user signs in. No administrator required.
param(
    [switch]$Disable,
    [switch]$NoStart
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$Launcher = Join-Path $PSScriptRoot 'start_background.py'
$RunKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$EntryName = 'memoir-tv'
$Existing = $null
if (Test-Path -LiteralPath $RunKey) {
    $Entry = (Get-ItemProperty -LiteralPath $RunKey).PSObject.Properties[$EntryName]
    if ($Entry) { $Existing = $Entry.Value }
}

if ($Disable) {
    if ($Existing -and -not $Existing.Contains($Launcher)) {
        throw 'The memoir-tv startup entry belongs to another checkout. Review it before removal.'
    }
    if ($Existing) { Remove-ItemProperty -LiteralPath $RunKey -Name $EntryName }
    Write-Output 'memoir-tv login startup disabled. The currently running server was left running.'
    exit 0
}

if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot 'config.local.json') -PathType Leaf)) {
    throw 'Create config.local.json before enabling startup.'
}
$PythonPath = (Get-Command python -CommandType Application | Select-Object -First 1).Source
$PythonWindowless = Join-Path (Split-Path -Parent $PythonPath) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $PythonWindowless -PathType Leaf)) {
    throw 'pythonw.exe was not found beside python.exe. Install Python for Windows first.'
}
$CommandLine = '"' + $PythonWindowless + '" "' + $Launcher + '"'
if ($CommandLine.Length -gt 260) { throw 'The startup command exceeds the Windows Run entry length limit.' }
if ($Existing -and $Existing -ne $CommandLine -and -not $Existing.Contains($Launcher)) {
    throw 'A different memoir-tv startup entry already exists. Review it before replacing it.'
}
if (-not (Test-Path -LiteralPath $RunKey)) { New-Item -Path $RunKey | Out-Null }
New-ItemProperty -LiteralPath $RunKey -Name $EntryName -Value $CommandLine -PropertyType String -Force | Out-Null
Write-Output ('Registered current-user login startup: ' + $CommandLine)
if (-not $NoStart) {
    Start-Process -FilePath $PythonWindowless -ArgumentList ('"' + $Launcher + '"') -WorkingDirectory $ProjectRoot -WindowStyle Hidden
    Write-Output 'Quiet startup requested. See .local/startup.log for the result.'
}
