import sys
import subprocess
import os
import glob
import shutil

print("Fetching Prisma engine...")
os.environ["PRISMA_CLIENT_ENGINE_TYPE"] = "binary"
os.environ["PRISMA_CLI_QUERY_ENGINE_TYPE"] = "binary"

cache_dir = os.path.join(os.getcwd(), ".prisma_binaries")
os.environ["PRISMA_BINARY_CACHE_DIR"] = cache_dir

subprocess.run([sys.executable, "-m", "prisma", "py", "fetch"], check=True)

engines = []
for root, dirs, files in os.walk(cache_dir):
    for file in files:
        if "query-engine" in file:
            engines.append(os.path.join(root, file))

if not engines:
    # Fallback to home dir cache if PRISMA_BINARY_CACHE_DIR was ignored
    home = os.path.expanduser("~")
    for root, dirs, files in os.walk(os.path.join(home, ".cache", "prisma-python")):
        for file in files:
            if "query-engine" in file:
                engines.append(os.path.join(root, file))

if engines:
    engine_path = engines[0]
    expected_name = "prisma-" + os.path.basename(engine_path)
    
    # Store it in the venv so Render preserves it across build and run phases!
    venv_dir = os.environ.get("VIRTUAL_ENV", sys.prefix)
    bin_dir = os.path.join(venv_dir, "bin")
    if not os.path.exists(bin_dir):
        os.makedirs(bin_dir)
        
    final_path = os.path.join(bin_dir, expected_name)
    shutil.copy(engine_path, final_path)
    os.chmod(final_path, 0o755)
    print(f"Fixed Prisma path bug: Copied {engine_path} to {final_path}")
else:
    print("Could not find downloaded Prisma engine in cache directory.")
