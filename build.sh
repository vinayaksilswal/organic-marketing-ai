#!/usr/bin/env bash
# exit on error
set -o errexit

export PRISMA_CLIENT_ENGINE_TYPE="binary"
export PRISMA_CLI_QUERY_ENGINE_TYPE="binary"
export PRISMA_BINARY_CACHE_DIR="/opt/render/project/src/.prisma_cache"

pip install --no-cache-dir -r requirements.txt

echo "Fetching Prisma binaries directly using Python CLI..."
python -c "
import os
from prisma.binaries import fetch_binaries
target_dir = '/opt/render/project/src/.prisma_cache'
os.makedirs(target_dir, exist_ok=True)
fetch_binaries(target_dir)
print('Binaries fetched into', target_dir)
" || true

prisma py fetch || true

mkdir -p /opt/render/project/src/.prisma_cache
FOUND_ENGINE=$(find /opt/render/project/src/.prisma_cache ~/.cache /tmp -type f -name "*query-engine*" 2>/dev/null | grep -v node_modules | head -n 1 || true)

if [ -n "$FOUND_ENGINE" ]; then
    echo "Found downloaded engine at: $FOUND_ENGINE"
    cp "$FOUND_ENGINE" /opt/render/project/src/.prisma_cache/prisma-query-engine-debian-openssl-3.0.x
    chmod +x /opt/render/project/src/.prisma_cache/prisma-query-engine-debian-openssl-3.0.x
    echo "Successfully copied engine to /opt/render/project/src/.prisma_cache/prisma-query-engine-debian-openssl-3.0.x"
fi

prisma generate --schema=schema_py.prisma
prisma db push --schema=schema_py.prisma

echo "Build complete! Prisma binary stored in .prisma_cache"

