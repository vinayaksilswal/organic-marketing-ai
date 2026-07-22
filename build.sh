#!/usr/bin/env bash
# exit on error
set -o errexit

pip install --no-cache-dir -r requirements.txt
prisma generate --schema=schema_py.prisma
prisma db push --schema=schema_py.prisma

echo "Finding the engine downloaded by Prisma in the system cache..."
ENGINE_PATH=$(find ~/.cache /opt/render/.cache -type f -name "*query-engine-debian-openssl-3.0.x" 2>/dev/null | head -n 1)

if [ -n "$ENGINE_PATH" ]; then
    echo "Found engine at $ENGINE_PATH"
    mkdir -p /opt/render/project/src/prisma_engine_binary
    mv "$ENGINE_PATH" /opt/render/project/src/prisma_engine_binary/prisma-query-engine-debian-openssl-3.0.x
    chmod +x /opt/render/project/src/prisma_engine_binary/prisma-query-engine-debian-openssl-3.0.x
    echo "Engine successfully moved to project root directory to survive cache wipe!"
else
    echo "ERROR: Engine not found in cache dir!"
    exit 1
fi

