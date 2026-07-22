#!/usr/bin/env bash
# =============================================================================
# Organic Marketing AI — Render Build Script
# =============================================================================
# This script runs during Render's build phase. It installs dependencies,
# fetches the correct Prisma query engine binary for the host OS, generates
# the Prisma client, and pushes the database schema.
# =============================================================================
set -o errexit

echo "=== Organic Marketing AI Build ==="

# Force Prisma to use the binary engine (not Node-API/WASM)
export PRISMA_CLIENT_ENGINE_TYPE="binary"
export PRISMA_CLI_QUERY_ENGINE_TYPE="binary"

# Install Python dependencies
pip install --no-cache-dir -r requirements.txt

# Fetch the correct Prisma query engine for this OS
echo "Fetching Prisma query engine binaries..."
python -m prisma py fetch || echo "Warning: prisma py fetch returned non-zero (may already exist)"

# Generate the Prisma Python client from our schema
echo "Generating Prisma client..."
python -m prisma generate --schema=schema_py.prisma

# Push schema to the database (creates/alters tables)
echo "Pushing database schema..."
python -m prisma db push --schema=schema_py.prisma --accept-data-loss || echo "Warning: db push had issues"

# Verify the engine binary exists
echo "Verifying Prisma engine binary..."
python -c "
import prisma, os, glob
d = os.path.dirname(prisma.__file__)
bins = [f for f in glob.glob(os.path.join(d, '*query-engine*'))
        if os.path.isfile(f) and not f.endswith(('.gz','.py','.pyc'))]
if bins:
    print(f'Found Prisma engine: {bins[0]}')
else:
    print('WARNING: No Prisma engine binary found!')
    # Try one more time
    import subprocess, sys
    subprocess.run([sys.executable, '-m', 'prisma', 'py', 'fetch'], check=False)
"

echo "=== Build Complete ==="
