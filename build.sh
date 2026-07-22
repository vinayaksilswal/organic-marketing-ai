#!/usr/bin/env bash
# exit on error
set -o errexit

export PRISMA_CLIENT_ENGINE_TYPE=binary
export PRISMA_CLI_QUERY_ENGINE_TYPE=binary
pip install --no-cache-dir -r requirements.txt
prisma generate --schema=schema_py.prisma
prisma db push --schema=schema_py.prisma

# Force fetch binaries natively
prisma py fetch || true

echo "Aggressively searching for downloaded Prisma engines across the entire server..."
find /opt/render/project/src /opt/render/.cache -type f -name "*query-engine*debian*" 2>/dev/null > found_engines.txt || true
echo "Found engines:"
cat found_engines.txt

engine_path=$(head -n 1 found_engines.txt)
if [ -n "$engine_path" ]; then
    echo "Copying $engine_path to $(pwd)/prisma-query-engine-debian-openssl-3.0.x"
    cp "$engine_path" ./prisma-query-engine-debian-openssl-3.0.x
    chmod +x ./prisma-query-engine-debian-openssl-3.0.x
    echo "Successfully placed engine in expected path!"
else
    echo "CRITICAL: Could not find any Prisma engines!"
fi
