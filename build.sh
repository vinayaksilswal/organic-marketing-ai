#!/usr/bin/env bash
# exit on error
set -o errexit

export PRISMA_CLIENT_ENGINE_TYPE="binary"
export PRISMA_CLI_QUERY_ENGINE_TYPE="binary"

pip install --no-cache-dir -r requirements.txt

# 1. Dynamically locate site-packages/prisma inside .venv
PRISMA_DIR=$(python -c "import os, prisma; print(os.path.dirname(prisma.__file__))")
echo "Target Prisma directory inside .venv: $PRISMA_DIR"

# 2. Tell Prisma CLI to fetch binaries directly into site-packages/prisma
export PRISMA_BINARY_CACHE_DIR="$PRISMA_DIR"

echo "Fetching Prisma binaries natively..."
prisma py fetch

# 3. Ensure the exact binary filename expected by Prisma Python exists and is executable
python -c "
import os, sys, glob, shutil, prisma
prisma_dir = os.path.dirname(prisma.__file__)

engines = glob.glob(os.path.join(prisma_dir, '**', '*query-engine*'), recursive=True) + \
          glob.glob(os.path.expanduser('~/.cache/**/*query-engine*'), recursive=True) + \
          glob.glob('/tmp/**/*query-engine*', recursive=True)

print('Discovered query engines:', engines)

if engines:
    target = os.path.join(prisma_dir, 'prisma-query-engine-debian-openssl-3.0.x')
    print(f'Copying {engines[0]} -> {target}')
    shutil.copyfile(engines[0], target)
    os.chmod(target, 0o755)
    print('ENGINE SUCCESSFULLY VERIFIED AND PLACED AT:', target)
else:
    print('ERROR: No query engine binary found after prisma py fetch!')
    sys.exit(1)
"

prisma generate --schema=schema_py.prisma
prisma db push --schema=schema_py.prisma

echo "Build complete! Prisma binary secured inside .venv"

