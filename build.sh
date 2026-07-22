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

# Remove any Windows/invalid binaries that might have been committed
python -c "
import os, glob
for root, dirs, files in os.walk('.'):
    for f in files:
        if 'query-engine' in f:
            p = os.path.join(root, f)
            try:
                with open(p, 'rb') as fp:
                    header = fp.read(4)
                if header != b'\x7fELF':
                    print(f'Removing non-Linux query-engine artifact: {p}')
                    os.remove(p)
            except Exception:
                pass
"

# Fetch genuine Linux binary from Prisma CDN
echo "Fetching Prisma query engine binaries..."
python -m prisma py fetch

# Generate the Prisma Python client
echo "Generating Prisma client..."
python -m prisma generate --schema=schema_py.prisma

# Verify and place the ELF binary
python -c "
import os, shutil, prisma

prisma_dir = os.path.dirname(prisma.__file__)
engine_name = 'prisma-query-engine-debian-openssl-3.0.x'

def is_valid_elf(p):
    if not os.path.isfile(p):
        return False
    try:
        with open(p, 'rb') as f:
            return f.read(4) == b'\x7fELF'
    except Exception:
        return False

# Find genuine Linux ELF engine
found_binary = None
for root_dir in ['/opt/render/.cache', os.path.expanduser('~/.cache'), prisma_dir, '/tmp']:
    if os.path.exists(root_dir):
        for root, dirs, files in os.walk(root_dir):
            for file in files:
                if 'query-engine' in file and not file.endswith(('.gz', '.py', '.pyc', '.json', '.lock')):
                    full_p = os.path.join(root, file)
                    if is_valid_elf(full_p):
                        found_binary = full_p
                        break
            if found_binary:
                break
    if found_binary:
        break

if found_binary:
    os.chmod(found_binary, 0o777)
    print(f'Verified valid Linux ELF binary at: {found_binary}')

    target_dir = '/opt/render/.cache/prisma-python/binaries/5.17.0/393aa359c9ad4a4bb28630fb5613f9c281cde053'
    os.makedirs(target_dir, exist_ok=True)

    targets = [
        f'/opt/render/project/src/{engine_name}',
        os.path.join(target_dir, engine_name),
        os.path.join(prisma_dir, engine_name),
    ]

    for target in targets:
        try:
            parent = os.path.dirname(target)
            if parent:
                os.makedirs(parent, exist_ok=True)
            shutil.copy2(found_binary, target)
            os.chmod(target, 0o777)
            print(f'✓ Placed valid ELF binary at: {target}')
        except Exception as e:
            print(f'Warning placing {target}: {e}')
else:
    print('WARNING: Could not find valid ELF binary after fetch!')
"

# Push schema to database
echo "Pushing database schema..."
python -m prisma db push --schema=schema_py.prisma --accept-data-loss || echo "Warning: db push warning"

echo "=== Build Complete ==="
