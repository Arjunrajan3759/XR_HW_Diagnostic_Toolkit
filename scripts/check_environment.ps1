<# .SYNOPSIS Reports Python, PlatformIO and passively enumerated devices. #>
[CmdletBinding()]
param()
. (Join-Path $PSScriptRoot 'common.ps1')
Start-ToolkitLog 'environment'
try {
    Push-Location $RepoRoot
    Require-Python
    $pio = Find-PlatformIO
    Invoke-ToolkitNative -Executable $pio -Arguments @('--version')
    if ($LASTEXITCODE -ne 0) { throw 'PlatformIO version check failed.' }
    Invoke-ToolkitNative -Executable $Python -Arguments @('-m','xrdiag','doctor')
    exit $LASTEXITCODE
} catch { Write-Error $_; exit 1 } finally { Pop-Location; Stop-Transcript | Out-Null }
