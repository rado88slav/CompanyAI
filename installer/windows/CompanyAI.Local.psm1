Set-StrictMode -Version Latest

function Get-CompanyAIRoot {
    $scriptPath = $PSScriptRoot
    $candidate = Resolve-Path (Join-Path $scriptPath "../..")
    return $candidate.Path
}

function Invoke-CompanyAIBash {
    param(
        [Parameter(Mandatory = $true)][string]$Script,
        [string[]]$Arguments = @()
    )

    $root = Get-CompanyAIRoot
    $wslRoot = (wsl.exe wslpath -a "$root").Trim()
    if (-not $wslRoot) {
        throw "Unable to resolve CompanyAI path in WSL. Ensure WSL2 is installed."
    }

    $bashArgs = @("cd '$wslRoot' && '$wslRoot/$Script'")
    foreach ($argument in $Arguments) {
        $escaped = $argument.Replace("'", "'\''")
        $bashArgs[0] += " '$escaped'"
    }

    wsl.exe bash -lc $bashArgs[0]
    if ($LASTEXITCODE -ne 0) {
        throw "CompanyAI command failed: $Script"
    }
}
