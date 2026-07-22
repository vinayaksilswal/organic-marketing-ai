#!/usr/bin/env bash
# =============================================================================
# Organic Marketing AI — Render Build Script
# =============================================================================
set -o errexit

echo "=== Organic Marketing AI Build ==="

# Install Python dependencies (including SQLAlchemy & asyncpg)
pip install --no-cache-dir -r requirements.txt

# Create dummy prisma binary in virtualenv bin directory so legacy Render Dashboard Build Commands succeed
VENV_BIN="$(dirname $(which python))"
cat << 'EOF' > "$VENV_BIN/prisma"
#!/bin/bash
echo "Prisma CLI replaced with pure Python SQLAlchemy 2.0 Async ORM + asyncpg."
exit 0
EOF
chmod +x "$VENV_BIN/prisma"

echo "=== Build Complete ==="
