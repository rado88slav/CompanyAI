Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Import-Module (Join-Path $PSScriptRoot "CompanyAI.Local.psm1") -Force

Write-Host "CompanyAI Local Edition installer preparation"
Write-Host "Prerequisites: WSL2, Ubuntu distribution, Docker Desktop with WSL integration, 8GB RAM recommended, port 8080 free."
Invoke-CompanyAIBash -Script "scripts/local/install.sh"
