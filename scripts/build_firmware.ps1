<# .SYNOPSIS Builds diagnostic firmware without touching hardware. #>
[CmdletBinding()]
param()
. (Join-Path $PSScriptRoot 'common.ps1')
Start-ToolkitLog 'build'
try {
    $pio = Find-PlatformIO
    Invoke-ToolkitNative -Executable $pio -Arguments @('run','-d',(Join-Path $RepoRoot 'firmware\xiao_esp32c6_diagnostics'))
    exit $LASTEXITCODE
} catch { Write-Error $_; exit 1 } finally { Stop-Transcript | Out-Null }
