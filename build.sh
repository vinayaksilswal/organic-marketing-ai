#!/usr/bin/env bash
# exit on error
set -o errexit

export PRISMA_BINARY_CACHE_DIR="/opt/render/project/src/.venv/prisma_engine"
export PRISMA_CLIENT_ENGINE_TYPE="binary"
export PRISMA_CLI_QUERY_ENGINE_TYPE="binary"

pip install --no-cache-dir -r requirements.txt
prisma generate --schema=schema_py.prisma
prisma db push --schema=schema_py.prisma

echo "Moving Prisma engine to expected root directory..."
# Prisma downloads the engine into a deeply nested folder inside the cache dir.
# We find it and move it to the root of the cache dir, where main.py expects it.
ENGINE_PATH=$(find .venv/prisma_engine -type f -name "*query-engine-debian-openssl-3.0.x" | head -n 1)

if [ -n "$ENGINE_PATH" ]; then
    echo "Found engine at $ENGINE_PATH"
    mv "$ENGINE_PATH" /opt/render/project/src/.venv/prisma_engine/prisma-query-engine-debian-openssl-3.0.x
    chmod +x /opt/render/project/src/.venv/prisma_engine/prisma-query-engine-debian-openssl-3.0.x
    echo "Engine successfully moved to expected location!"
else
    echo "ERROR: Engine not found in cache dir!"
    exit 1
fi

