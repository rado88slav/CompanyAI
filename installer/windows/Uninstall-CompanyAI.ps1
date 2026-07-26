Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
param([string]$Confirmation = "")
Import-Module (Join-Path $PSScriptRoot "CompanyAI.Local.psm1") -Force
if ($Confirmation -ne "REMOVE_CONTAINERS_KEEP_DATA") {
    throw "Use -Confirmation REMOVE_CONTAINERS_KEEP_DATA to remove containers. Business data volumes are never deleted by this wrapper."
}
Invoke-CompanyAIBash -Script "scripts/local/uninstall.sh"
