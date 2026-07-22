#!/usr/bin/env bash
# exit on error
set -o errexit

export PRISMA_CLIENT_ENGINE_TYPE=binary
export PRISMA_CLI_QUERY_ENGINE_TYPE=binary

pip install --no-cache-dir -r requirements.txt
prisma generate --schema=schema_py.prisma
prisma db push --schema=schema_py.prisma

echo "Downloading Prisma engine directly for Render (debian-openssl-3.0.x)..."
PRISMA_COMMIT="393aa359c9ad4a4bb28630fb5613f9c281cde053"
mkdir -p .venv/prisma_engine
curl -L -s "https://binaries.prisma.sh/all_commits/${PRISMA_COMMIT}/debian-openssl-3.0.x/query-engine.gz" -o .venv/prisma_engine/query-engine.gz
gzip -d -f .venv/prisma_engine/query-engine.gz
mv .venv/prisma_engine/query-engine .venv/prisma_engine/prisma-query-engine-debian-openssl-3.0.x
chmod +x .venv/prisma_engine/prisma-query-engine-debian-openssl-3.0.x
echo "Successfully placed engine exactly where it is expected!"
