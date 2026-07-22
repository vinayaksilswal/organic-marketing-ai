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

# Copy engine to exact locations expected by Prisma v5.17 on Render
python -c "
import os, glob, shutil, prisma

prisma_dir = os.path.dirname(prisma.__file__)

# Find downloaded binary recursively
found = None
for search_base in [os.path.expanduser('~/.cache'), '/root/.cache', '/tmp', prisma_dir, '.']:
    if os.path.exists(search_base):
        for root, dirs, files in os.walk(search_base):
            for file in files:
                if 'query-engine' in file and not file.endswith(('.gz', '.py', '.pyc', '.json', '.lock')):
                    found = os.path.join(root, file)
                    break
            if found:
                break
    if found:
        break

if found:
    os.chmod(found, 0o755)
    print(f'Found Prisma engine binary at: {found}')
    
    # Target paths expected by Prisma on Render
    targets = [
        'prisma-query-engine-debian-openssl-3.0.x',
        'query-engine-debian-openssl-3.0.x',
        'prisma-query-engine-rhel-openssl-3.0.x',
        'query-engine-rhel-openssl-3.0.x',
        os.path.join(prisma_dir, 'prisma-query-engine-debian-openssl-3.0.x'),
        os.path.join(prisma_dir, 'bin', 'query-engine'),
    ]
    for target in targets:
        try:
            parent = os.path.dirname(target)
            if parent:
                os.makedirs(parent, exist_ok=True)
            shutil.copy2(found, target)
            os.chmod(target, 0o755)
            print(f'✓ Copied Prisma engine to: {target}')
        except Exception as e:
            print(f'Warning copying to {target}: {e}')
else:
    print('WARNING: No query engine binary found during build step!')
"

# Push schema to database
echo "Pushing database schema..."
python -m prisma db push --schema=schema_py.prisma --accept-data-loss || echo "Warning: db push warning"

echo "=== Build Complete ==="
