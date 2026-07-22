#!/usr/bin/env bash
# exit on error
set -o errexit

export PRISMA_CLIENT_ENGINE_TYPE="binary"
export PRISMA_CLI_QUERY_ENGINE_TYPE="binary"

pip install --no-cache-dir -r requirements.txt

echo "Locating Prisma package inside .venv and fetching query engine..."
python -c "
import os, sys, shutil, glob
import prisma
from prisma.binaries import fetch_binaries

prisma_dir = os.path.dirname(prisma.__file__)
print('Prisma package directory inside .venv:', prisma_dir)

fetch_binaries(prisma_dir)

found = [f for f in glob.glob(os.path.join(prisma_dir, '**', '*query-engine*'), recursive=True) if 'node_modules' not in f] + \
        [f for f in glob.glob(os.path.expanduser('~/.cache/**/*query-engine*'), recursive=True) if 'node_modules' not in f]

if found:
    src_engine = found[0]
    target_engine = os.path.join(prisma_dir, 'prisma-query-engine-debian-openssl-3.0.x')
    print(f'Copying engine from {src_engine} to {target_engine}')
    shutil.copy(src_engine, target_engine)
    os.chmod(target_engine, 0o755)
    print('Engine placed successfully inside .venv!')
else:
    print('WARNING: Could not locate engine file via glob')
"

prisma generate --schema=schema_py.prisma
prisma db push --schema=schema_py.prisma

echo "Build complete! Prisma engine stored safely in .venv"

