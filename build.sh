#!/usr/bin/env bash
# =============================================================================
# Organic Marketing AI — Render Build Script
# =============================================================================
set -o errexit

echo "=== Organic Marketing AI Build ==="

# Install Python dependencies (including SQLAlchemy & asyncpg)
pip install --no-cache-dir -r requirements.txt

echo "=== Build Complete ==="
