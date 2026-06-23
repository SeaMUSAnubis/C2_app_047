# Install the UEBA endpoint agent on Windows.
#
# This script:
#   1. Validates it's run as Administrator.
#   2. Insterts Python (if missing) via winget OR uses existing Python.
#   3. Installs the agent into a venv at C:\Program Files\UEBA Agent.
#   4. Registers a Windows Task Scheduler entry to start the agent at boot.
#      (Task Scheduler is the recommended approach for non-Service apps on
#      Windows 10/11; NSSM is a fallback if you need a real Windows service.)
#   5. Prints next steps.
#
# Usage (from elevated PowerShell):
#   .\scripts\install_agent.ps1
#
# After install:
#   # 1. Enroll (one-time):
#   & "C:\Program Files\UEBA Agent\venv\Scripts\agent.exe" enroll `
#       --server-url https://ueba.corp.example `
#       --enrollment-token o47enr_xxxxxxxx `
#       --state-path "C:\ProgramData\UEBA Agent\state.json"
#
#   # 2. The scheduled task will start the agent automatically at next boot.
#      To start now:
#   Start-ScheduledTask -TaskName "UEBA Agent"
#
#   # 3. Verify:
#   Get-ScheduledTask -TaskName "UEBA Agent" | Get-ScheduledTaskInfo
#   Get-EventLog -LogName Application -Source "UEBA Agent" -Newest 20

[CmdletBinding()]
param(
    [string]$InstallPrefix = "$env:ProgramFiles\UEBA Agent",
    [string]$StateDir = "$env:ProgramData\UEBA Agent",
    [string]$LogDir = "$env:ProgramData\UEBA Agent\Logs",
    [string]$PythonBin = "python",
    [switch]$UseNssm = $false
)

$ErrorActionPreference = "Stop"

# --- Helpers ---------------------------------------------------------------

function Write-Info { param([string]$m) Write-Host "[install-agent] $m" }
function Die        { param([string]$m) Write-Error "[install-agent] ERROR: $m"; exit 1 }

function Test-Administrator {
    $current = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($current)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-Python {
    param([string]$bin)
    try {
        & $bin -Version 2>&1 | Out-Null
        return $true
    } catch {
        return $false
    }
}

# --- Pre-flight ------------------------------------------------------------

if (-not (Test-Administrator)) {
    Die "must run as Administrator (right-click PowerShell → 'Run as administrator')"
}

if (-not (Test-Python $PythonBin)) {
    Write-Info "Python not found at '$PythonBin'. Attempting install via winget..."
    try {
        winget install --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
    } catch {
        Die "winget install failed. Install Python 3.10+ manually from https://python.org and re-run."
    }
    $PythonBin = "python"
    if (-not (Test-Python $PythonBin)) {
        Die "Python still not found after winget install. Aborting."
    }
}

$pyVersion = & $PythonBin -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Write-Info "Using Python $pyVersion"

# --- Install ----------------------------------------------------------------

Write-Info "Creating $InstallPrefix"
New-Item -ItemType Directory -Path $InstallPrefix -Force | Out-Null

Write-Info "Creating venv at $InstallPrefix\venv"
& $PythonBin -m venv "$InstallPrefix\venv"

$venvPip = "$InstallPrefix\venv\Scripts\pip.exe"
$venvAgent = "$InstallPrefix\venv\Scripts\agent.exe"

Write-Info "Upgrading pip"
& $venvPip install --quiet --upgrade pip wheel

# Prefer local source install.
$repoDir = (Resolve-Path "$PSScriptRoot\..").Path
if (Test-Path "$repoDir\pyproject.toml") {
    Write-Info "Installing from local source ($repoDir)"
    & $venvPip install --quiet "$repoDir"
} else {
    Write-Info "Installing ueba-agent from PyPI"
    & $venvPip install --quiet "ueba-agent"
}

# --- Runtime dirs -----------------------------------------------------------

Write-Info "Creating state dir $StateDir"
New-Item -ItemType Directory -Path $StateDir -Force | Out-Null
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

# Restrict access to admins + SYSTEM.
try {
    $acl = Get-Acl $StateDir
    $acl.SetAccessRuleProtection($true, $false)
    Set-Acl $StateDir $acl
} catch {
    Write-Info "Could not harden ACL on $StateDir (continuing): $_"
}

# --- Scheduled task ---------------------------------------------------------

$taskName = "UEBA Agent"
$taskDescription = "UEBA Endpoint Agent — collects employee activity and streams to the central UEBA backend."

# Build the command line. Quoting matters: PowerShell will properly escape
# the args when writing the task XML.
$exePath = "$InstallPrefix\venv\Scripts\agent.exe"
$argList = @(
    "run"
    "--state-path", "$StateDir\state.json"
    "--buffer-path", "$StateDir\buffer.db"
    "--log-path", "$LogDir\agent.log"
)

# Remove any pre-existing task.
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

Write-Info "Registering scheduled task '$taskName' (run as SYSTEM, on boot)"

$action = New-ScheduledTaskAction -Execute $exePath -Argument ($argList -join ' ') -WorkingDirectory $StateDir
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0)  # unlimited
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Description $taskDescription |
    Out-Null

# --- Next steps -------------------------------------------------------------

@"
============================================================
  UEBA Endpoint Agent installed.
============================================================

Next steps (open an elevated PowerShell):

  1. Enroll with a one-time token from the admin UI:

       & "$venvAgent" enroll `
           --server-url https://YOUR-SERVER `
           --enrollment-token o47enr_xxxxxxxx `
           --state-path "$StateDir\state.json"

  2. Start the scheduled task (it also runs at next boot):

       Start-ScheduledTask -TaskName "$taskName"

  3. Verify:

       Get-ScheduledTask -TaskName "$taskName" | Get-ScheduledTaskInfo
       Get-EventLog -LogName Application -Source "UEBA Agent" -Newest 20

Install prefix : $InstallPrefix
State dir      : $StateDir
Log dir        : $LogDir
============================================================
"@
