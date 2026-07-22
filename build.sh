#!/usr/bin/env bash
# exit on error
set -o errexit

# Tell Prisma where to store the engine during the build so it survives the Render cache wipe!
export PRISMA_BINARY_CACHE_DIR="$(pwd)/.venv/prisma_engine"
export PRISMA_CLIENT_ENGINE_TYPE=binary
export PRISMA_CLI_QUERY_ENGINE_TYPE=binary

pip install --no-cache-dir -r requirements.txt

# This will now natively download the engines to .venv/prisma_engine
prisma generate --schema=schema_py.prisma
prisma db push --schema=schema_py.prisma

echo "Build complete! Engine safely placed in $PRISMA_BINARY_CACHE_DIR"
