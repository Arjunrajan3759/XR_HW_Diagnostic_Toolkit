<# .SYNOPSIS Creates a Python 3.11 environment and installs pinned toolkit packages.
.EXAMPLE .\scripts\setup_windows.ps1 -Camera -Recording -Dev
#>
[CmdletBinding()]
param([switch]$Camera,[switch]$Recording,[switch]$Dev)
. (Join-Path $PSScriptRoot 'common.ps1')
Start-ToolkitLog 'setup'
try {
    Push-Location $RepoRoot
    if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot '.venv'))) {
        $launcher = Get-Command py -ErrorAction SilentlyContinue
        if ($launcher) {
            Invoke-ToolkitNative -Executable $launcher.Source -Arguments @('-3.11','-m','venv',(Join-Path $RepoRoot '.venv'))
        } else {
            $candidate = Get-Command python -ErrorAction SilentlyContinue
            if (-not $candidate) { throw 'Install 64-bit Python 3.11 from python.org, including the Python launcher.' }
            Invoke-ToolkitNative -Executable $candidate.Source -Arguments @('-c','import sys; assert sys.version_info[:2] == (3,11)')
            if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 is required. Install it alongside other versions.' }
            Invoke-ToolkitNative -Executable $candidate.Source -Arguments @('-m','venv',(Join-Path $RepoRoot '.venv'))
        }
        if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
    } else { Write-Host 'Preserving existing .venv.' }
    Require-Python
    $groups = @('requirements.txt')
    if ($Camera) { $groups += 'requirements-camera.txt' }
    if ($Recording) { $groups += 'requirements-recording.txt' }
    if ($Dev) { $groups += 'requirements-dev.txt' }
    $installArgs = @('-m','pip','install')
    foreach ($group in $groups) { $installArgs += @('-r',(Join-Path $RepoRoot $group)) }
    Invoke-ToolkitNative -Executable $Python -Arguments $installArgs
    if ($LASTEXITCODE -ne 0) { throw 'Package installation failed. Check network, Python architecture, and pip output.' }
    Invoke-ToolkitNative -Executable $Python -Arguments @('-m','pip','check')
    if ($LASTEXITCODE -ne 0) { throw 'Dependency conflict; see pip check output.' }
    try { $pio = Find-PlatformIO; Invoke-ToolkitNative -Executable $pio -Arguments @('--version') } catch { Write-Warning $_; $missingPio = $true }
    Invoke-ToolkitNative -Executable $Python -Arguments @('-m','xrdiag','doctor')
    if ($LASTEXITCODE -ne 0) { throw 'Environment doctor failed.' }
    if ($missingPio) { Write-Warning 'Host setup complete; firmware builds BLOCKED until PlatformIO is installed.'; exit 2 }
    Write-Host 'Setup complete. Devices are not required for software simulation.'
} catch { Write-Error $_; exit 1 } finally { Pop-Location; Stop-Transcript | Out-Null }
