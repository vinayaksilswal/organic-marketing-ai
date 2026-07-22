#!/usr/bin/env bash
# exit on error
set -o errexit

export PRISMA_BINARY_CACHE_DIR="/opt/render/project/src/.venv/prisma_engine"
export PRISMA_CLIENT_ENGINE_TYPE="binary"
export PRISMA_CLI_QUERY_ENGINE_TYPE="binary"

pip install --no-cache-dir -r requirements.txt
prisma generate --schema=schema_py.prisma
prisma db push --schema=schema_py.prisma

echo "Build complete! Prisma is initialized natively as a binary inside .venv cache."
