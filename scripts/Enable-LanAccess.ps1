# Author: donglixiao. Allow memoir-tv on the local subnet without disabling the firewall.
#Requires -RunAsAdministrator
$ErrorActionPreference = 'Stop'
$memoirPort = 8765
$memoirPython = (Get-Command python -CommandType Application).Source
$memoirInterface = Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -and $_.IPv4Address } | Select-Object -First 1
if (-not $memoirInterface) { throw 'No active IPv4 LAN interface was found.' }

# Windows explicit block rules override allow rules. Preserve Python's existing
# TCP block for every port except this app's port. Leave UDP rules untouched.
$memoirBlocks = @(Get-NetFirewallRule -Enabled True -Direction Inbound -Action Block | Where-Object {
    $memoirApplication = $_ | Get-NetFirewallApplicationFilter
    $memoirApplication.Program -ieq $memoirPython
} | ForEach-Object {
    $memoirFilter = $_ | Get-NetFirewallPortFilter
    if ($memoirFilter.Protocol -eq 'TCP' -and $memoirFilter.LocalPort -contains 'Any') {
        $memoirFilter
    }
})

$memoirRuleName = 'memoir-tv-LAN-TCP-8765'
$memoirParameters = @{
    Enabled = 'True'
    Direction = 'Inbound'
    Action = 'Allow'
    Profile = 'Any'
    Program = $memoirPython
    Protocol = 'TCP'
    LocalPort = $memoirPort
    RemoteAddress = 'LocalSubnet'
    InterfaceAlias = $memoirInterface.InterfaceAlias
}
if (Get-NetFirewallRule -Name $memoirRuleName -ErrorAction SilentlyContinue) {
    Set-NetFirewallRule -Name $memoirRuleName @memoirParameters
} else {
    New-NetFirewallRule -Name $memoirRuleName -DisplayName 'memoir-tv LAN (TCP 8765)' @memoirParameters | Out-Null
}
foreach ($memoirFilter in $memoirBlocks) {
    $memoirFilter | Set-NetFirewallPortFilter -LocalPort @('1-8764', '8766-65535')
}
Write-Host ('Ready: http://{0}:{1}/' -f $memoirInterface.IPv4Address[0].IPAddress, $memoirPort)
Write-Host 'Only the local subnet can use this rule. The firewall remains enabled.'
