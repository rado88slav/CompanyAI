# Windows Installer Plan

CompanyAI Local Edition is prepared for a future Windows installer, but this repository does not yet ship an `.exe` installer.

## Future PowerShell Wrappers

- `Install-CompanyAI.ps1`: verify prerequisites, copy files to the install directory, generate `.env.local`, create Docker volumes and start the runtime.
- `Start-CompanyAI.ps1`: call `scripts/local/start.sh`.
- `Stop-CompanyAI.ps1`: call `scripts/local/stop.sh`.
- `Backup-CompanyAI.ps1`: call future backup tooling.
- `Restore-CompanyAI.ps1`: call future restore tooling with explicit confirmation.
- `Diagnose-CompanyAI.ps1`: call `scripts/local/diagnose.sh`.
- `Uninstall-CompanyAI.ps1`: stop containers and remove application files. Data removal must require a separate explicit destructive confirmation.

## Expected Folders

Future installer-managed layout:

```text
C:\Program Files\CompanyAI\
C:\ProgramData\CompanyAI\
  data\
  backups\
  logs\
  config\
```

## Permissions

Administrator privileges may be required for installing Docker Desktop, writing to `Program Files`, configuring firewall rules or creating Start Menu entries.

Starting, stopping, status checks, diagnostics and normal use should not require administrator privileges once Docker Desktop is installed and the user has Docker access.

## First Run

The installer must not create an insecure default administrator. It should generate local secrets once, store only necessary hashes or encrypted values and use the existing secure administrator creation workflow or a future first-run setup flow that closes permanently after the first administrator exists.

## LAN Access

LAN access is disabled by default because the local runtime binds to `127.0.0.1`. A future wrapper may intentionally set `LOCAL_APP_BIND_ADDRESS=0.0.0.0` after clear user confirmation and firewall checks.
