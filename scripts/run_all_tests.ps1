<# .SYNOPSIS Runs software tests then available diagnostics; never flashes.
.EXAMPLE .\scripts\run_all_tests.ps1 -Simulated -Duration 2
#>
[CmdletBinding()]
param([switch]$Simulated,[string]$Port,[double]$Duration=2,[string]$Output='results')
. (Join-Path $PSScriptRoot 'common.ps1')
Start-ToolkitLog 'tests'
try {
    Push-Location $RepoRoot
    Require-Python
    Invoke-ToolkitNative -Executable $Python -Arguments @('-m','pytest','-q')
    if ($LASTEXITCODE -ne 0) { throw 'Software tests failed; diagnostics not started.' }
    $runArgs = @('-m','xrdiag','run-all','--duration',"$Duration",'--output',$Output)
    if ($Simulated) { $runArgs += @('--mode','simulated') }
    if ($Port) { $runArgs += @('--port',$Port) }
    Invoke-ToolkitNative -Executable $Python -Arguments $runArgs
    $resultCode=$LASTEXITCODE
    if ($resultCode -eq 2) { Write-Host 'BLOCKED prerequisites are listed in reports; no hardware success claimed.' }
    exit $resultCode
} catch { Write-Error $_; exit 1 } finally { Pop-Location; Stop-Transcript | Out-Null }
