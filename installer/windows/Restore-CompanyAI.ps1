Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
param(
    [Parameter(Mandatory = $true)][string]$BackupDirectory,
    [Parameter(Mandatory = $true)][string]$Confirmation
)
Import-Module (Join-Path $PSScriptRoot "CompanyAI.Local.psm1") -Force
$wslBackup = (wsl.exe wslpath -a "$BackupDirectory").Trim()
Invoke-CompanyAIBash -Script "scripts/local/restore.sh" -Arguments @($wslBackup, $Confirmation)
