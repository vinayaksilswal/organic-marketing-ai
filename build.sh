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

# Find downloaded binary and place a copy in prisma package bin folder
python -c "
import os, glob, shutil, prisma
prisma_dir = os.path.dirname(prisma.__file__)
bin_dir = os.path.join(prisma_dir, 'bin')
os.makedirs(bin_dir, exist_ok=True)

# Search recursively for downloaded engine
for search_base in [os.path.expanduser('~/.cache'), '/root/.cache', '/tmp', prisma_dir]:
    if os.path.exists(search_base):
        for root, dirs, files in os.walk(search_base):
            for file in files:
                if 'query-engine' in file and not file.endswith(('.gz', '.py', '.pyc', '.json', '.lock')):
                    src = os.path.join(root, file)
                    os.chmod(src, 0o755)
                    # Copy to prisma bin folder as query-engine
                    dest = os.path.join(bin_dir, file)
                    shutil.copy2(src, dest)
                    print(f'Copied Prisma engine to: {dest}')
                    os.environ['PRISMA_QUERY_ENGINE_BINARY'] = dest
"

# Push schema to database
echo "Pushing database schema..."
python -m prisma db push --schema=schema_py.prisma --accept-data-loss || echo "Warning: db push warning"

echo "=== Build Complete ==="
