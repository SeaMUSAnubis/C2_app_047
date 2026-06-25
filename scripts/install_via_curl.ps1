# Install the UEBA agent on Windows from a GitHub release (or any HTTPS
# artifact host). Designed for the iwr | iex pattern:
#
#   iwr https://github.com/vespionage/ueba-endpoint-monitoring/releases/latest/download/install.ps1 -useb | iex
#
# Or with parameters:
#   iwr .../install.ps1 -useb | iex; Install-UebaAgent -ServerUrl ... -EnrollmentToken ...
#
# It will:
#   1. Detect arch (x86_64).
#   2. Download agent-windows-x86_64.exe + SHA256SUMS to temp.
#   3. Verify SHA256 (required).
#   4. Install to C:\Program Files\UEBA Agent\agent.exe.
#   5. Register a scheduled task.
#   6. Optionally enroll (if -EnrollmentToken given) and start.

[CmdletBinding()]
param(
    [string]$ReleaseUrl = $env:UEBA_RELEASE_URL,
    [string]$Version = $env:UEBA_VERSION,
    [string]$InstallDir = $env:UEBA_INSTALL_DIR,
    [string]$StateDir = $env:UEBA_STATE_DIR,
    [switch]$NoStart,
    [switch]$NoService,
    [string]$ServerUrl,
    [string]$EnrollmentToken,
    [string]$DeviceId,
    [string]$AssignedUserId
)

$ErrorActionPreference = "Stop"

# --- Defaults ----------------------------------------------------------------

if (-not $ReleaseUrl) { $ReleaseUrl = "https://github.com/vespionage/ueba-endpoint-monitoring/releases/latest/download" }
if (-not $Version)     { $Version = "latest" }
if (-not $InstallDir)  { $InstallDir = "$env:ProgramFiles\UEBA Agent" }
if (-not $StateDir)    { $StateDir = "$env:ProgramData\UEBA Agent" }
$LogDir = Join-Path $StateDir "Logs"
$BinaryName = "agent-windows-x86_64.exe"

# --- Pre-flight --------------------------------------------------------------

$current = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($current)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "[install] ERROR: must run as Administrator (use 'iwr | iex' from an elevated PowerShell, or wrap in Start-Process -Verb RunAs)"
}

function Log($m) { Write-Host "[install] $m" }
function Die($m) { Write-Error "[install] ERROR: $m"; exit 1 }

if ($Version -ne "latest") {
    $ReleaseUrl = $ReleaseUrl -replace "/releases/latest/download$", "/releases/download/v$($Version.TrimStart('v'))"
}
Log "Release URL: $ReleaseUrl"
Log "Version:     $Version"

# --- Download + verify -------------------------------------------------------

$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("ueba-agent-" + [System.Guid]::NewGuid().ToString("N").Substring(0, 8))
New-Item -ItemType Directory -Path $tmp -Force | Out-Null

try {
    Log "Downloading SHA256SUMS"
    Invoke-WebRequest -UseBasicParsing -Uri "$ReleaseUrl/SHA256SUMS" -OutFile "$tmp\SHA256SUMS" -ErrorAction Stop

    Log "Downloading $BinaryName"
    Invoke-WebRequest -UseBasicParsing -Uri "$ReleaseUrl/$BinaryName" -OutFile "$tmp\$BinaryName" -ErrorAction Stop

    # Verify SHA256.
    $expectedLine = Select-String -Path "$tmp\SHA256SUMS" -Pattern ("\s" + [regex]::Escape($BinaryName) + "$")
    if (-not $expectedLine) {
        Die "$BinaryName not found in SHA256SUMS — wrong release artifact?"
    }
    $expected = ($expectedLine -split '\s+')[0].Trim().ToLower()
    $actual = (Get-FileHash -Path "$tmp\$BinaryName" -Algorithm SHA256).Hash.ToLower()
    if ($expected -ne $actual) {
        if ($env:UEBA_SKIP_VERIFY -eq "1") {
            Log "WARN: SHA256 mismatch (expected=$($expected.Substring(0,16))... actual=$($actual.Substring(0,16))...) — UEBA_SKIP_VERIFY=1, continuing"
        } else {
            Die "SHA256 mismatch! expected=$expected actual=$actual — refusing to install. Set UEBA_SKIP_VERIFY=1 to override."
        }
    }
    Log "SHA256 verified: $($actual.Substring(0,16))..."

    # --- Install binary --------------------------------------------------------

    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    New-Item -ItemType Directory -Path $StateDir -Force | Out-Null
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

    Copy-Item -Path "$tmp\$BinaryName" -Destination (Join-Path $InstallDir "agent.exe") -Force
    Log "Installed binary to $InstallDir\agent.exe"

    # --- Optional: enroll ------------------------------------------------------

    if ($EnrollmentToken -and $ServerUrl) {
        Log "Enrolling with $ServerUrl"
        $args = @(
            "enroll",
            "--server-url", $ServerUrl,
            "--enrollment-token", $EnrollmentToken,
            "--state-path", (Join-Path $StateDir "state.json")
        )
        if ($DeviceId)        { $args += @("--device-id", $DeviceId) }
        if ($AssignedUserId)  { $args += @("--assigned-user-id", $AssignedUserId) }
        $agentExe = Join-Path $InstallDir "agent.exe"
        try {
            & $agentExe @args
            Log "Enrolled. state.json written."
        } catch {
            Log "WARN: enroll failed (token may be expired). Run manually:"
            Log "  $agentExe enroll --server-url ... --enrollment-token ... --state-path $StateDir\state.json"
        }
    }

    # --- Register scheduled task ----------------------------------------------

    if (-not $NoService) {
        $taskName = "UEBA Agent"
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

        $agentExe = Join-Path $InstallDir "agent.exe"
        $argList = @(
            "run"
            "--state-path", (Join-Path $StateDir "state.json")
            "--buffer-path", (Join-Path $StateDir "buffer.db")
            "--log-path", (Join-Path $LogDir "agent.log")
        )

        $action = New-ScheduledTaskAction -Execute $agentExe -Argument ($argList -join ' ') -WorkingDirectory $StateDir
        $trigger = New-ScheduledTaskTrigger -AtStartup
        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
            -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) `
            -ExecutionTimeLimit (New-TimeSpan -Hours 0)
        $principal2 = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

        Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
            -Settings $settings -Principal $principal2 -Description "UEBA Endpoint Agent" | Out-Null

        if (-not $NoStart) {
            Start-ScheduledTask -TaskName $taskName
            Log "Service started. Verify: Get-ScheduledTask -TaskName '$taskName' | Get-ScheduledTaskInfo"
        }
    }
} finally {
    Remove-Item -Path $tmp -Recurse -Force -ErrorAction SilentlyContinue
}

@"
============================================================
  UEBA Endpoint Agent installed (binary, no pip needed).
============================================================

Binary path  : $InstallDir\agent.exe
State path   : $StateDir\state.json
Buffer DB    : $StateDir\buffer.db
Logs         : $LogDir\agent.log
Version      : $Version
Source       : $ReleaseUrl

Update to a newer version later:
  & "$InstallDir\agent.exe" update

Uninstall:
  & "$InstallDir\agent.exe" update --uninstall
============================================================
"@
