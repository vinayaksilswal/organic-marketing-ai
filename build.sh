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
echo "Downloading Prisma query engine natively..."
prisma py fetch

echo "Locating downloaded Prisma query engine aggressively..."
engine_path=$(find /opt/render/project/src /opt/render/.cache -type f -name "*query-engine-debian-openssl*" -print -quit 2>/dev/null)

if [ -n "$engine_path" ]; then
    echo "Found Prisma Engine at: $engine_path"
    cp "$engine_path" ./prisma-query-engine-debian-openssl-3.0.x
    chmod +x ./prisma-query-engine-debian-openssl-3.0.x
    echo "Engine successfully copied to Prisma Python's expected fallback locations!"
else
    echo "CRITICAL WARNING: Could not find query engine anywhere in /opt/render!"
fi
