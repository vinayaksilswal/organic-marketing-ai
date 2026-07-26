#!/usr/bin/env bash
# =============================================================================
# Organic Marketing AI — Render Build Script
# =============================================================================
set -o errexit

echo "=== Organic Marketing AI Build ==="

# Install Python dependencies
pip install --no-cache-dir -r requirements.txt

# Run Alembic Migrations
echo "=== Running Alembic Migrations ==="
alembic upgrade head

echo "=== Build Complete ==="
