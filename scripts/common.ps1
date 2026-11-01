# Shared helpers. Scripts never require activation or administrator privileges.
$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
$env:PYTHONUTF8 = '1'
function Require-Python {
    if (-not (Test-Path -LiteralPath $Python)) { throw 'Run scripts/setup_windows.ps1 first.' }
    Invoke-ToolkitNative -Executable $Python -Arguments @('-c',"import sys,struct; assert sys.version_info[:2] == (3,11), 'Python 3.11 required'; assert struct.calcsize('P') == 8, '64-bit Python required'")
    if ($LASTEXITCODE -ne 0) { throw 'Existing .venv must use Python 3.11; preserve it and resolve manually.' }
}
function Find-PlatformIO {
    foreach ($name in @('pio','platformio')) {
        $found = Get-Command $name -ErrorAction SilentlyContinue
        if ($found) { return $found.Source }
    }
    $candidate = Join-Path $env:USERPROFILE '.platformio\penv\Scripts\platformio.exe'
    if (Test-Path -LiteralPath $candidate) { return $candidate }
    throw 'PlatformIO missing. Install PlatformIO Core or the VS Code PlatformIO IDE extension, then restart PowerShell.'
}
function Start-ToolkitLog([string]$Name) {
    $logRoot = Join-Path $RepoRoot 'results\script_logs'
    New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
    $logId = [guid]::NewGuid().ToString('N')
    $script:NativeLog = Join-Path $logRoot ("{0}_{1}.native.txt" -f $Name,$logId)
    Start-Transcript -Path (Join-Path $logRoot ("{0}_{1}.txt" -f $Name,$logId)) | Out-Null
}
function Invoke-ToolkitNative {
    param([string]$Executable,[string[]]$Arguments)
    # Native stdout is not reliably included by Start-Transcript on Windows PowerShell.
    # Preserve it explicitly, including stderr, and retain the native exit code.
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $global:LASTEXITCODE = 1
        & $Executable @Arguments 2>&1 | ForEach-Object { $_.ToString() } | Tee-Object -FilePath $script:NativeLog -Append -ErrorAction Stop
        $global:LASTEXITCODE = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previousPreference }
}
