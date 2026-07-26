Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Import-Module (Join-Path $PSScriptRoot "CompanyAI.Local.psm1") -Force
Invoke-CompanyAIBash -Script "scripts/local/restart.sh"
