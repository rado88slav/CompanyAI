#!/usr/bin/env bash
# Description: Create the initial project structure and base files.

set -e

echo "======================================"
echo " Company AI - Project Setup"
echo "======================================"

echo ""
echo "Creating project structure..."

mkdir -p \
agent \
backend \
dashboard \
database \
docker \
docs \
config \
integrations \
scripts \
storage/uploads \
storage/exports \
storage/reports \
storage/backups \
storage/cache \
project-admin

touch \
README.md \
.env.example \
.gitignore \
docker-compose.yml

cat > README.md << 'EOF'
# Company AI

Local AI Operations Platform

Status: MVP
EOF

cat > .gitignore << 'EOF'
.env
__pycache__/
*.pyc
storage/cache/
storage/backups/
EOF

cat > .env.example << 'EOF'
PROJECT_NAME=company-ai
EOF

echo ""
echo "Project structure created successfully."
