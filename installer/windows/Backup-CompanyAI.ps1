Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
param([string]$Destination = "")
Import-Module (Join-Path $PSScriptRoot "CompanyAI.Local.psm1") -Force
if ($Destination) {
    $wslDestination = (wsl.exe wslpath -a "$Destination").Trim()
    Invoke-CompanyAIBash -Script "scripts/local/backup.sh" -Arguments @($wslDestination)
} else {
    Invoke-CompanyAIBash -Script "scripts/local/backup.sh"
}
