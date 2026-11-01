<# .SYNOPSIS Validates checksums then creates a handoff ZIP.
.EXAMPLE .\scripts\package_results.ps1 -ResultsFolder 'results\run folder' -IncludeRaw
#>
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$ResultsFolder,[switch]$IncludeRaw)
. (Join-Path $PSScriptRoot 'common.ps1')
Start-ToolkitLog 'package'
try {
    Push-Location $RepoRoot
    Require-Python
    $runArgs = @('-m','xrdiag','package',$ResultsFolder)
    if ($IncludeRaw) { $runArgs += '--include-raw' }
    Invoke-ToolkitNative -Executable $Python -Arguments $runArgs
    exit $LASTEXITCODE
} catch { Write-Error $_; exit 1 } finally { Pop-Location; Stop-Transcript | Out-Null }
