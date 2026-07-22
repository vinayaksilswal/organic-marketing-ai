#!/usr/bin/env bash
# exit on error
set -o errexit

export PRISMA_CLIENT_ENGINE_TYPE=library
export PRISMA_CLI_QUERY_ENGINE_TYPE=library
pip install --no-cache-dir -r requirements.txt
prisma generate --schema=schema_py.prisma
prisma db push --schema=schema_py.prisma
