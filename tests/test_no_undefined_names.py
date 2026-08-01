"""Catch names used but never imported.

Twice in one session a module referenced a name that did not exist in it —
AsyncSessionLocal in routers/marketing.py, then asyncio in
services/video_outro.py. Both imported cleanly, both passed the test suite, and
both only failed when the code path actually ran in production.

pyflakes finds this statically in under a second, which is cheaper than a
deploy and a user hitting it.
"""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# Every module that serves a request or runs in a worker. A NameError here is a
# 500 in production rather than an import error at boot, because the offending
# line may sit inside a rarely-taken branch.
CRITICAL = [
    "routers",
    "services",
    "prompt_engine",
    "main.py",
    "worker.py",
    "database.py",
]


def _pyflakes(target: Path):
    return subprocess.run(
        [sys.executable, "-m", "pyflakes", str(target)],
        capture_output=True, text=True, cwd=ROOT,
    )


@pytest.mark.parametrize("target", CRITICAL)
def test_no_undefined_names(target):
    path = ROOT / target
    if not path.exists():
        pytest.skip(f"{target} not present")

    result = _pyflakes(path)
    if "No module named pyflakes" in (result.stderr or ""):
        pytest.skip("pyflakes not installed")

    # Unused imports are noise; an undefined name is a production 500.
    undefined = [
        line for line in (result.stdout or "").splitlines()
        if "undefined name" in line
    ]
    assert not undefined, (
        "Names used but never imported — these raise NameError at runtime:\n  "
        + "\n  ".join(undefined)
    )
