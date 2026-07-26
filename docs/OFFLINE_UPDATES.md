# Offline Updates

CompanyAI Local Edition updates are manual and package-based.

## Intended Flow

1. Verify package checksums.
2. Inspect version compatibility.
3. Create a pre-update backup.
4. Import Docker images from the package.
5. Stop affected services safely.
6. Run migrations.
7. Start services.
8. Run health checks.
9. Record update result and keep recovery instructions.

Automatic silent updates are intentionally not implemented.

## Recovery

Old images and backup assets should remain available until the new version is verified on the workstation.
