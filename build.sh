#!/usr/bin/env bash
# exit on error
set -o errexit

export PRISMA_BINARY_CACHE_DIR=$(pwd)/.prisma_cache
export PRISMA_CLIENT_ENGINE_TYPE=binary
export PRISMA_CLI_QUERY_ENGINE_TYPE=binary
pip install --no-cache-dir -r requirements.txt
prisma generate --schema=schema_py.prisma
prisma db push --schema=schema_py.prisma

# Fix Prisma Engine Missing Error on Render
# Prisma CLI downloads the engine to node_modules inside the cache dir,
# but Prisma Python strictly looks for a specific filename directly in the project root or cache dir root.
echo "Locating downloaded Prisma query engine..."
engine_path=$(find .prisma_cache -type f -name "*query-engine-debian-openssl*" | head -n 1)

if [ -n "$engine_path" ]; then
    echo "Found Prisma Engine at: $engine_path"
    cp "$engine_path" ./prisma-query-engine-debian-openssl-3.0.x
    cp "$engine_path" .prisma_cache/prisma-query-engine-debian-openssl-3.0.x
    chmod +x ./prisma-query-engine-debian-openssl-3.0.x
    chmod +x .prisma_cache/prisma-query-engine-debian-openssl-3.0.x
    echo "Engine successfully copied to Prisma Python's expected fallback locations!"
else
    echo "WARNING: Could not find query engine in .prisma_cache!"
    # Try fetching it natively via python just in case
    prisma py fetch
fi
