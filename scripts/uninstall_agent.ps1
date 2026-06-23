# Uninstall the UEBA endpoint agent on Windows.
#
# - Unregisters the scheduled task
# - Removes the install prefix
# - Optionally removes state + log directories

[CmdletBinding()]
param(
    [string]$InstallPrefix = "$env:ProgramFiles\UEBA Agent",
    [string]$StateDir = "$env:ProgramData\UEBA Agent"
)

$ErrorActionPreference = "Stop"

$current = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($current)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "must run as Administrator"; exit 1
}

$taskName = "UEBA Agent"
if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    Write-Host "[uninstall] unregistering scheduled task '$taskName'"
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

if (Test-Path $InstallPrefix) {
    Write-Host "[uninstall] removing $InstallPrefix"
    Remove-Item -Path $InstallPrefix -Recurse -Force
}

if (Test-Path $StateDir) {
    $ans = Read-Host "[uninstall] remove $StateDir (state + buffer + logs)? [y/N]"
    if ($ans -match '^[Yy]$') {
        Write-Host "[uninstall] removing $StateDir"
        Remove-Item -Path $StateDir -Recurse -Force
    } else {
        Write-Host "[uninstall] keeping $StateDir"
    }
}

Write-Host "[uninstall] done."
