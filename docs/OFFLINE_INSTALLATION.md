# Offline Installation

CompanyAI Local Edition Beta is prepared for delivery from a USB flash drive or external SSD and permanent operation from the workstation internal SSD.

## Prerequisites

- Windows with WSL2 support.
- Ubuntu WSL distribution.
- Docker Desktop with WSL integration.
- Port `8080` available on localhost.
- Recommended minimum: 8 GB RAM and enough free SSD space for database growth and backups.

The installer does not silently install Docker Desktop or change virtualization settings.

## Package Build

Create a delivery directory:

```bash
scripts/local/build-package.sh 0.1.0-beta
```

The package includes Docker image archives, Compose files, lifecycle scripts, Windows wrappers, documentation, a version manifest and checksums. It excludes Git history, `.env.local`, provider credentials, `node_modules` and generated secrets.

## Installation Preparation

On the target workstation, copy the package to the internal SSD before running CompanyAI. Do not run business data permanently from an ordinary USB flash drive.

Run:

```powershell
installer\windows\Install-CompanyAI.ps1
```

Then generate local secrets in `.env.local` before starting.

## Dashboard

After startup, open:

```text
http://localhost:8080
```

LAN access is disabled by default.
