"""Every endpoint the interface calls has to exist.

VideoStudio fetched /marketing/products for months. There has never been such
a route -- products live on the ecommerce router -- so every workspace load
fired a 404 and the product picker silently stayed empty. An e-commerce
customer could only ever generate a creative about their business in general
and never about a specific item, and nothing anywhere said so: the fetch
failed, the catch logged to a console nobody had open, and the select rendered
with no options.

That is the shape of this whole class of bug. It cannot be caught by reading
either side alone, because both sides are individually correct -- the frontend
asks for a sensible path, the backend offers a sensible path, and they are
different paths.

So this compares the two. It is a spelling check between the interface and the
API, and it would have caught that one the day it was written.
"""

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend" / "src"
API_PREFIX = "/api/v1"


def _normalise(path: str) -> str:
    """A path with every interpolation reduced to one placeholder."""
    path = re.sub(r"\$\{[^}]+\}", "{x}", path)
    path = path.split("?")[0].rstrip("/")
    return path


@pytest.fixture(scope="module")
def registered() -> set[str]:
    from fastapi.testclient import TestClient

    import main

    with TestClient(main.app, raise_server_exceptions=False):
        schema = main.app.openapi()

    out = set()
    for raw in schema.get("paths", {}):
        if raw.startswith(API_PREFIX):
            out.add(re.sub(r"\{[^}]+\}", "{x}", raw[len(API_PREFIX):]).rstrip("/"))
    return out


@pytest.fixture(scope="module")
def called() -> set[str]:
    out = set()
    for f in FRONTEND.rglob("*.jsx"):
        for m in re.finditer(r"\$\{API_BASE\}(/[A-Za-z0-9_\-/\$\{\}\.]*)", f.read_text(encoding="utf-8")):
            path = _normalise(m.group(1))
            if not path:
                continue
            # A trailing interpolation with no slash before it is a query
            # string appended to the path, not a path segment.
            path = re.sub(r"(?<!/)\{x\}$", "", path).rstrip("/")
            out.add(path)
    return out


def test_the_route_table_was_actually_read(registered):
    """app.routes does not expose included routers in this FastAPI version --
    walking it returns two entries and makes the comparison below vacuous. The
    OpenAPI schema is the honest source."""
    assert len(registered) > 50, f"only {len(registered)} routes found; the schema was not read"


def test_the_frontend_was_actually_read(called):
    assert len(called) > 30, f"only {len(called)} calls found; the scan missed the source"


def test_every_called_endpoint_exists(registered, called):
    missing = sorted(c for c in called if c not in registered)
    assert not missing, (
        "the interface calls endpoints that are not registered — these 404 at "
        "runtime and fail silently:\n  " + "\n  ".join(missing)
    )
