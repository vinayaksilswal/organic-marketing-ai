"""The server's reason for refusing has to survive the trip to the screen.

FastAPI raises HTTPException with `detail`. main.py then has a global handler
that reshapes every one of them into {"success": false, "message": ...}. So
`body.detail` is populated in a unit test and undefined in production.

Fifteen call sites read only `detail`. Every one of them replaced the real
explanation with a generic fallback for every actual user:

    "Could not start the subscription"  instead of what PayPal said
    "Reset failed"                      instead of "that link has expired"
    "Generation failed"                 instead of the plan limit that was hit

This was invisible locally because the tests that exercise those endpoints
read the JSON directly, and invisible in review because reading `.detail` off
a FastAPI response is exactly what you would expect to be correct.
"""

import pathlib
import re

import pytest


ROOT = pathlib.Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend" / "src"
SOURCES = sorted(list(FRONTEND.rglob("*.jsx")) + list(FRONTEND.rglob("*.js")))

# `body.detail` on its own is the bug. These are the accepted ways to read an
# error: the shared helper, or an explicit fallback to the other field.
_BARE_DETAIL = re.compile(r"\.detail\b")


def test_the_frontend_was_actually_read():
    """Guards the sweep below: an empty file list passes it silently."""
    assert len(SOURCES) > 20, f"only found {len(SOURCES)} frontend sources"


def test_the_shared_helper_exists_and_reads_both_shapes():
    src = (FRONTEND / "config.js").read_text(encoding="utf-8")
    assert "export function apiError" in src
    assert "body?.message" in src and "body?.detail" in src, (
        "the helper must read the production shape and the FastAPI shape"
    )


def test_the_helper_handles_a_validation_error_list():
    """422s arrive as [{loc, msg}]. Rendering that object gives the user
    '[object Object]', which is worse than the generic fallback."""
    src = (FRONTEND / "config.js").read_text(encoding="utf-8")
    assert "Array.isArray" in src and "msg" in src


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_no_file_reads_detail_without_a_fallback(path):
    """Every `.detail` read must go through apiError, or name `.message` too."""
    src = path.read_text(encoding="utf-8")
    offenders = []

    for i, line in enumerate(src.splitlines(), 1):
        if not _BARE_DETAIL.search(line):
            continue
        # Prose, not code. The helper's own docstring explains this bug and
        # therefore names the field it is about.
        stripped = line.strip()
        if stripped.startswith(('*', '//', '/*')):
            continue
        # The CustomEvent carries its own `detail` — that is the DOM's field
        # name, nothing to do with the API envelope.
        if "CustomEvent" in line or "e.detail" in line or "event.detail" in line:
            continue
        # `.message` as a property read is the accepted alternative. Matching
        # the bare word is not: `setStatus({ message: data.detail })` contains
        # it as an object key, and an earlier version of this test skipped the
        # one line it most needed to catch.
        if "apiError" in line or re.search(r"[.?]\s*message", line):
            continue
        offenders.append(f"{path.name}:{i}: {line.strip()[:90]}")

    assert not offenders, (
        "these read the API's `detail`, which is undefined in production:\n"
        + "\n".join(offenders)
    )


def test_the_places_that_were_broken_now_use_the_helper():
    """Named explicitly, because these are the ones a user actually hits."""
    expected = {
        "pages/ResetPassword.jsx": "Reset failed",
        "pages/dashboard/Billing.jsx": "Could not start the subscription",
        "pages/dashboard/Support.jsx": "Could not send that.",
    }
    for rel, fallback in expected.items():
        src = (FRONTEND / rel).read_text(encoding="utf-8")
        # Called, not merely imported. The import survives a regression that
        # removes the call, so checking for the name alone proves nothing.
        assert "apiError(" in src, f"{rel} still does not call the helper"
        assert fallback in src, f"{rel} lost its fallback wording"


def test_the_global_handler_still_reshapes_errors():
    """The reason the helper is needed. If this ever changes back to plain
    FastAPI detail, the helper keeps working — but the comment explaining it
    would become wrong, and this test would say so."""
    src = (ROOT / "main.py").read_text(encoding="utf-8")
    assert '"success": False, "message": exc.detail' in src
