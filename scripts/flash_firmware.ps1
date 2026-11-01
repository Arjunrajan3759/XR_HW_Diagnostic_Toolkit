<# .SYNOPSIS Flashes ONLY after explicit port selection, recovery confirmation and interactive approval.
.EXAMPLE .\scripts\flash_firmware.ps1 -Port COM7 -RecoveryImageConfirmed
#>
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Port,[switch]$RecoveryImageConfirmed)
. (Join-Path $PSScriptRoot 'common.ps1')
Start-ToolkitLog 'flash'
try {
    if (-not $RecoveryImageConfirmed) { throw 'First obtain a known-good recovery image or an approved complete flash backup. See README recovery procedure.' }
    $pio = Find-PlatformIO
    Write-Host "WARNING: This replaces firmware on explicitly selected device $Port. It may disrupt the glove."
    $answer = Read-Host "Type exactly FLASH $Port to approve"
    if ($answer -cne "FLASH $Port") { Write-Host 'Not approved; nothing flashed.'; exit 2 }
    Invoke-ToolkitNative -Executable $pio -Arguments @('run','-d',(Join-Path $RepoRoot 'firmware\xiao_esp32c6_diagnostics'),'-t','upload','--upload-port',$Port)
    exit $LASTEXITCODE
} catch { Write-Error $_; exit 1 } finally { Stop-Transcript | Out-Null }
