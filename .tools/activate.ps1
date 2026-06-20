$RepoRoot = Split-Path -Parent $PSScriptRoot
$Paths = @(
    (Join-Path $PSScriptRoot "bin"),
    "C:\Users\ivychi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python",
    "C:\Users\ivychi\util\nodejs"
)

$PathsToAdd = $Paths.Clone()
[array]::Reverse($PathsToAdd)

foreach ($Path in $PathsToAdd) {
    if ((Test-Path $Path) -and (($env:Path -split ";") -notcontains $Path)) {
        $env:Path = "$Path;$env:Path"
    }
}

Write-Host "WFERP local tools are active for this PowerShell session."
Write-Host "Repo: $RepoRoot"
