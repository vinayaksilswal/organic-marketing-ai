#!/usr/bin/env bash
# exit on error
set -o errexit

pip install --no-cache-dir -r requirements.txt
prisma generate --schema=schema_py.prisma
prisma db push --schema=schema_py.prisma

echo "Build complete! Prisma is initialized natively."
