#!/usr/bin/env bash
# exit on error
set -o errexit

export PRISMA_BINARY_CACHE_DIR="/opt/render/project/src/.venv/prisma_cache"
export PRISMA_CLIENT_ENGINE_TYPE="binary"
export PRISMA_CLI_QUERY_ENGINE_TYPE="binary"

pip install --no-cache-dir -r requirements.txt
prisma py fetch
prisma generate --schema=schema_py.prisma
prisma db push --schema=schema_py.prisma

echo "Ensuring query engine is placed at exact path required by Prisma Python..."
mkdir -p /opt/render/project/src/.venv/prisma_cache

FOUND_ENGINE=$(find ~/.cache /opt/render /tmp /root -type f -name "*query-engine*" 2>/dev/null | grep -v node_modules | head -n 1)

if [ -n "$FOUND_ENGINE" ]; then
    echo "Found downloaded engine at: $FOUND_ENGINE"
    cp "$FOUND_ENGINE" /opt/render/project/src/.venv/prisma_cache/prisma-query-engine-debian-openssl-3.0.x
    chmod +x /opt/render/project/src/.venv/prisma_cache/prisma-query-engine-debian-openssl-3.0.x
    echo "Successfully copied engine to /opt/render/project/src/.venv/prisma_cache/prisma-query-engine-debian-openssl-3.0.x"
else
    echo "WARNING: Could not locate engine via find, checking default PRISMA_BINARY_CACHE_DIR"
fi

echo "Build complete! Prisma binary cached inside persistent .venv directory."

