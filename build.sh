#!/usr/bin/env bash
# exit on error
set -o errexit

export PRISMA_CLIENT_ENGINE_TYPE="binary"
export PRISMA_CLI_QUERY_ENGINE_TYPE="binary"

pip install --no-cache-dir -r requirements.txt

echo "Downloading official Prisma query engine (debian-openssl-3.0.x) directly into .venv..."
python -c "
import os, gzip, urllib.request, prisma

prisma_dir = os.path.dirname(prisma.__file__)
target_path = os.path.join(prisma_dir, 'prisma-query-engine-debian-openssl-3.0.x')

url = 'https://binaries.prisma.sh/all_commits/393aa359c9ad4a4bb28630fb5613f9c281cde053/debian-openssl-3.0.x/query-engine.gz'
gz_path = target_path + '.gz'

print('Fetching engine from:', url)
urllib.request.urlretrieve(url, gz_path)

with gzip.open(gz_path, 'rb') as f_in:
    with open(target_path, 'wb') as f_out:
        f_out.write(f_in.read())

if os.path.exists(gz_path):
    os.remove(gz_path)

os.chmod(target_path, 0o755)
print('SUCCESSFULLY INSTALLED ENGINE AT:', target_path)
"

prisma generate --schema=schema_py.prisma
prisma db push --schema=schema_py.prisma

echo "Build complete! Prisma engine secured in .venv"

