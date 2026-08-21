"""A request body must be read from the request body.

This shipped to production and stayed there:

    POST /api/v1/auth/forgot-password
    {"detail": [{"loc": ["query", "data"], "msg": "Field required"}]}

Password reset was impossible for every customer, and /openapi.json returned
500, so /docs was gone too.

The cause was a combination, which is why nothing caught it. routers/auth.py
had `from __future__ import annotations`, so every annotation became a string.
`forgot_password` is wrapped by @limiter.limit, and a wrapper's __globals__
belong to slowapi, not to auth.py. FastAPI resolved "ForgotPasswordRequest"
against the wrong module, found nothing, gave up on treating it as a model and
classified it as a QUERY parameter.

It reproduced only under the pinned pydantic (2.11.5). A newer pydantic on a
developer machine resolved it and hid the whole thing, so "works locally" was
true and meaningless.

These tests are about the class of bug, not the one endpoint.
"""

import inspect
import typing

import pytest
from fastapi.routing import APIRoute
from pydantic import BaseModel

import main


@pytest.fixture(scope="module", autouse=True)
def started_app():
    """The routers are attached during lifespan startup, not at import.

    Without this the route list is empty and every test here passes while
    checking nothing -- which is precisely how the original bug survived.
    """
    from fastapi.testclient import TestClient

    with TestClient(main.app, raise_server_exceptions=False):
        yield


def _routes():
    """Every APIRoute in the app, including the nested ones.

    Two shapes have to be handled, because the pinned FastAPI and the newer
    one on this machine differ here. The pinned version flattens included
    routes straight into app.routes; the newer one wraps each include in an
    _IncludedRouter that keeps them behind `original_router`.

    A non-recursive walk sees twelve routes out of several hundred and misses
    every router where a body model could go astray -- including the auth
    router this test exists for. Hence the floor assertion below: a walk that
    quietly finds nothing is worse than no test at all.
    """
    found: list[APIRoute] = []
    seen: set[int] = set()

    def walk(container):
        if id(container) in seen:
            return
        seen.add(id(container))
        for route in getattr(container, "routes", []):
            if isinstance(route, APIRoute):
                found.append(route)
                continue
            # A nested router, under whichever name this version uses for it.
            for attr in ("original_router", "routes", "app"):
                child = getattr(route, attr, None)
                if child is not None and hasattr(child, "routes"):
                    walk(child)
                    break
            else:
                if hasattr(route, "routes"):
                    walk(route)

    walk(main.app)
    assert len(found) > 50, f"only {len(found)} routes found; the walk missed most of the app"
    return found


def test_the_openapi_schema_builds():
    """A schema that raises means /docs is a 500 and every generated client is
    broken. This alone would have caught the outage."""
    schema = main.app.openapi()
    assert schema["paths"], "no paths in the generated schema"


def test_no_endpoint_reads_a_model_from_the_query_string():
    """The exact production symptom, generalised to every route.

    A Pydantic model is never a query parameter. If one is classified as such,
    FastAPI failed to resolve the annotation and the endpoint cannot receive
    its payload at all.
    """
    broken = []
    for route in _routes():
        for param in route.dependant.query_params:
            annotation = param.field_info.annotation
            if isinstance(annotation, type) and issubclass(annotation, BaseModel):
                broken.append(f"{route.path} reads {param.name} from the query string")
    assert not broken, "\n".join(broken)


def test_every_declared_model_parameter_is_actually_bound_to_the_body():
    """The other half: the model resolved, but is it wired to the body?"""
    broken = []
    for route in _routes():
        endpoint = route.endpoint
        # Resolve against the module the function was WRITTEN in. Unwrapping
        # matters: the decorated function is what carries the real globals.
        target = inspect.unwrap(endpoint)
        try:
            hints = typing.get_type_hints(target)
        except Exception as e:
            broken.append(f"{route.path}: annotations do not resolve ({e})")
            continue

        # The return annotation is not a request body. A GET that declares
        # `-> SomeResponse` is correct and must not be flagged.
        parameters = {k: v for k, v in hints.items() if k != "return"}
        takes_a_model = any(
            isinstance(h, type) and issubclass(h, BaseModel) for h in parameters.values()
        )
        if takes_a_model and route.body_field is None:
            broken.append(
                f"{route.path} declares a model but has no body field; "
                f"its payload cannot arrive"
            )
    assert not broken, "\n".join(broken)


def test_the_endpoint_that_actually_broke():
    """Named explicitly so the regression is unmistakable in a failure list."""
    route = next(
        (r for r in _routes() if r.path.endswith("/auth/forgot-password")), None
    )
    assert route is not None, "the forgot-password route disappeared"
    assert route.body_field is not None, "forgot-password is not reading a body"
    assert not [p.name for p in route.dependant.query_params], (
        "forgot-password grew a query parameter again"
    )


def test_rate_limiting_is_still_on_the_endpoint_that_needs_it():
    """The fix must not have been achieved by deleting the protection.

    This endpoint mails an address the caller supplies. Unthrottled, it floods
    somebody else's inbox and burns the sending quota.
    """
    import routers.auth as auth

    src = inspect.getsource(auth)
    assert "@limiter.limit" in src, "the rate limit was removed rather than fixed"


def test_the_module_does_not_reintroduce_deferred_annotations():
    """The one-line change that caused it. A future import here re-breaks the
    endpoint silently, and only on the pinned pydantic."""
    import pathlib

    src = (
        pathlib.Path(__file__).resolve().parent.parent / "routers" / "auth.py"
    ).read_text(encoding="utf-8")
    # Statements only. The module explains this hazard in a comment, and
    # matching prose would make the test trip over the warning about itself.
    statements = [
        line for line in src.splitlines() if not line.lstrip().startswith("#")
    ]
    assert "from __future__ import annotations" not in chr(10).join(statements), (
        "auth.py defers annotations again; forgot-password will read its body "
        "as a query parameter under the pinned pydantic"
    )
