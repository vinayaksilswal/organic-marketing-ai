#!/usr/bin/env bash
# =============================================================================
# Organic Marketing AI — Render Build Script
# =============================================================================
set -o errexit

echo "=== Organic Marketing AI Build ==="

# Force Prisma binary engine
export PRISMA_CLIENT_ENGINE_TYPE="binary"
export PRISMA_CLI_QUERY_ENGINE_TYPE="binary"

# Install Python dependencies
pip install --no-cache-dir -r requirements.txt

# Fetch the Prisma engine binary
echo "Fetching Prisma query engine binaries..."
python -m prisma py fetch || echo "Warning: prisma py fetch warning"

# Generate the Prisma Python client
echo "Generating Prisma client..."
python -m prisma generate --schema=schema_py.prisma

# Populate exact paths expected by Prisma v5.17 on Render
python -c "
import os, shutil, prisma

prisma_dir = os.path.dirname(prisma.__file__)
engine_name = 'prisma-query-engine-debian-openssl-3.0.x'

# Recursively locate any downloaded query engine file
found_binary = None
for root_dir in ['/opt/render/.cache', os.path.expanduser('~/.cache'), '/tmp', prisma_dir, '.']:
    if os.path.exists(root_dir):
        for root, dirs, files in os.walk(root_dir):
            for file in files:
                if 'query-engine' in file and not file.endswith(('.gz', '.py', '.pyc', '.json', '.lock')):
                    found_binary = os.path.join(root, file)
                    break
            if found_binary:
                break
    if found_binary:
        break

if found_binary:
    os.chmod(found_binary, 0o755)
    print(f'Found Prisma engine binary at: {found_binary}')

    # Exact target locations expected by Prisma v5.17 on Render
    cache_target_dir = '/opt/render/.cache/prisma-python/binaries/5.17.0/393aa359c9ad4a4bb28630fb5613f9c281cde053'
    os.makedirs(cache_target_dir, exist_ok=True)

    exact_targets = [
        f'/opt/render/project/src/{engine_name}',
        os.path.join(cache_target_dir, engine_name),
        engine_name,
        f'query-engine-debian-openssl-3.0.x',
        os.path.join(prisma_dir, engine_name),
    ]

    for target in exact_targets:
        try:
            parent = os.path.dirname(target)
            if parent:
                os.makedirs(parent, exist_ok=True)
            shutil.copy2(found_binary, target)
            os.chmod(target, 0o755)
            print(f'✓ Placed Prisma engine at: {target}')
        except Exception as e:
            print(f'Warning placing {target}: {e}')
else:
    print('WARNING: Engine binary not found in search paths!')
"

# Push schema to database
echo "Pushing database schema..."
python -m prisma db push --schema=schema_py.prisma --accept-data-loss || echo "Warning: db push warning"

echo "=== Build Complete ==="
