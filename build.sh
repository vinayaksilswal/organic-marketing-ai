#!/usr/bin/env bash
# exit on error
set -o errexit

export PRISMA_CLIENT_ENGINE_TYPE="binary"
export PRISMA_CLI_QUERY_ENGINE_TYPE="binary"

pip install --no-cache-dir -r requirements.txt

echo "Generating Prisma client (downloads query engine)..."
prisma generate --schema=schema_py.prisma

echo "Copying query engine into persistent .venv site-packages/prisma directory..."
python -c "
import os, sys, shutil, glob
import prisma

prisma_dir = os.path.dirname(prisma.__file__)
print('Target Prisma package directory inside .venv:', prisma_dir)

# Find the query engine downloaded by prisma generate in system cache
found = glob.glob(os.path.expanduser('~/.cache/**/query-engine*'), recursive=True) + \
        glob.glob('/tmp/**/query-engine*', recursive=True) + \
        glob.glob('/opt/render/.cache/**/query-engine*', recursive=True)

print('Discovered engine candidates:', found)

if found:
    src_engine = found[0]
    target_engine = os.path.join(prisma_dir, 'prisma-query-engine-debian-openssl-3.0.x')
    print(f'Copying engine from {src_engine} to {target_engine}')
    shutil.copyfile(src_engine, target_engine)
    os.chmod(target_engine, 0o755)
    print('SUCCESSFULLY COPIED ENGINE TO:', target_engine)
else:
    print('ERROR: Could not locate query-engine binary in cache!')
    sys.exit(1)
"

prisma db push --schema=schema_py.prisma

echo "Build complete! Prisma query engine safely secured in .venv"

