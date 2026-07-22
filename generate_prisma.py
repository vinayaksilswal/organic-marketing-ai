import os
import re
import sys

source_path = "../prisma/schema.prisma"
target_path = "schema_py.prisma"

if not os.path.exists(source_path):
    print(f"Warning: {source_path} not found.")
    if os.path.exists(target_path):
        print(f"{target_path} already exists, skipping generation.")
        sys.exit(0)
    else:
        # Create minimal valid schema_py.prisma if absent
        with open(target_path, "w") as f:
            f.write("""
datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

generator py {
  provider = "prisma-client-py"
}

model User {
  id String @id @default(uuid())
}
""")
        print(f"Created placeholder {target_path}")
        sys.exit(0)

with open(source_path, "r") as f:
    content = f.read()

if "url =" not in content and "url  =" not in content:
    content = content.replace(
        'provider = "postgresql"',
        'provider = "postgresql"\n  url      = env("DATABASE_URL")'
    )

content = re.sub(r'generator client\s*\{[^}]+\}', '', content)

python_generator = """
generator py {
  provider             = "prisma-client-py"
  recursive_type_depth = 5
}
"""
if "generator py" not in content:
    content += python_generator

with open(target_path, "w") as f:
    f.write(content)

print("Created schema_py.prisma cleanly.")
