#!/usr/bin/env bash
# =============================================================================
# Organic Marketing AI — Render Build Script
# =============================================================================
set -o errexit

echo "=== Organic Marketing AI Build ==="

# Install Python dependencies
pip install --no-cache-dir -r requirements.txt

# Run Database Migrations
echo "=== Running Database Migrations ==="
python migrate_db.py

echo "=== Build Complete ==="
