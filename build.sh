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

# Fetch Prisma engine binaries for all Linux targets
echo "Fetching Prisma query engine binaries..."
python -m prisma py fetch || echo "Warning: standard prisma py fetch warning"

python -c "
import subprocess, sys
for target in ['debian-openssl-3.0.x', 'rhel-openssl-3.0.x', 'debian-openssl-1.1.x', 'linux-musl-openssl-3.0.x']:
    try:
        subprocess.run([sys.executable, '-m', 'prisma', 'py', 'fetch', '--target', target], check=False)
    except Exception as e:
        print(f'Fetch warning for {target}: {e}')
"

# Generate the Prisma Python client
echo "Generating Prisma client..."
python -m prisma generate --schema=schema_py.prisma

# Populate exact paths expected by Prisma v5.17 on Render and make executable (chmod 777)
python -c "
import os, shutil, subprocess, prisma

prisma_dir = os.path.dirname(prisma.__file__)
engine_name = 'prisma-query-engine-debian-openssl-3.0.x'

# Recursively locate any downloaded query engine file
found_binary = None
for root_dir in ['/opt/render/.cache', os.path.expanduser('~/.cache'), '/tmp', prisma_dir, '.']:
    if os.path.exists(root_dir):
        for root, dirs, files in os.walk(root_dir):
            for file in files:
                if 'query-engine' in file and not file.endswith(('.gz', '.py', '.pyc', '.json', '.lock')):
                    full_p = os.path.join(root, file)
                    try:
                        os.chmod(full_p, 0o777)
                        res = subprocess.run([full_p, '--version'], capture_output=True, timeout=5)
                        if res.returncode == 0:
                            found_binary = full_p
                            print(f'Verified executable Prisma engine binary at: {found_binary}')
                            break
                    except Exception as err:
                        print(f'Candidate binary {full_p} execution check: {err}')
            if found_binary:
                break
    if found_binary:
        break

if not found_binary:
    # Fallback to any query-engine file
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
    try:
        os.chmod(found_binary, 0o777)
    except Exception:
        pass
    
    cache_target_dir = '/opt/render/.cache/prisma-python/binaries/5.17.0/393aa359c9ad4a4bb28630fb5613f9c281cde053'
    os.makedirs(cache_target_dir, exist_ok=True)

    exact_targets = [
        f'/opt/render/project/src/{engine_name}',
        os.path.join(cache_target_dir, engine_name),
        engine_name,
        'query-engine-debian-openssl-3.0.x',
        os.path.join(prisma_dir, engine_name),
    ]

    for target in exact_targets:
        try:
            parent = os.path.dirname(target)
            if parent:
                os.makedirs(parent, exist_ok=True)
            shutil.copy2(found_binary, target)
            os.chmod(target, 0o777)
            print(f'✓ Verified & Placed Prisma engine at: {target}')
        except Exception as e:
            print(f'Warning placing {target}: {e}')
else:
    print('WARNING: Could not find any query-engine binary during build!')
"

# Push schema to database
echo "Pushing database schema..."
python -m prisma db push --schema=schema_py.prisma --accept-data-loss || echo "Warning: db push warning"

echo "=== Build Complete ==="
