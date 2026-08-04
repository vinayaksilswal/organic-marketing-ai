"""One customer must never reach another customer's workspace.

Before this guard existed, `verify_user` proved who was calling and nothing
proved the workspace in X-Workspace-Id belonged to them. Row-level security
did not help: it scopes queries to whatever workspace it is handed, so naming
someone else's simply scoped the query to their data.

Twenty workspace-scoped endpoints relied on nothing but the header being
present -- including GET /media, DELETE /media/{id}, POST /run-automation and
POST /posts/manual. Any signed-up account could read another customer's
catalog, delete their assets, or publish to their social accounts.

This platform is about to be sold to strangers from a landing page, which is
exactly the condition under which that stops being theoretical.
"""

import inspect
import re
from pathlib import Path

import pytest

ROUTERS = Path(__file__).resolve().parent.parent / "routers"

# Routers that take a workspace from the request and must therefore prove the
# caller owns it.
WORKSPACE_ROUTERS = [
    "marketing.py", "api.py", "creative_api.py", "team.py",
    "user_api.py", "video.py", "ecommerce.py",
]


@pytest.mark.parametrize("filename", WORKSPACE_ROUTERS)
def test_every_workspace_router_verifies_access(filename):
    """Enforced at the router, not per endpoint, so the next endpoint someone
    adds is covered without anyone remembering to cover it."""
    src = (ROUTERS / filename).read_text(encoding="utf-8")
    routers = re.findall(r"APIRouter\((.*?)\n\)", src, re.S)
    guarded = [r for r in routers if "verify_workspace_access" in r]
    authed = [r for r in routers if "verify_user" in r]
    assert authed, f"{filename} has no authenticated router at all"
    assert len(guarded) == len(authed), (
        f"{filename} has {len(authed)} authenticated router(s) but only "
        f"{len(guarded)} that verify workspace access"
    )


def test_the_guard_allows_the_owner():
    from routers.auth import verify_workspace_access

    src = inspect.getsource(verify_workspace_access)
    assert "profile.userId == user_id" in src


def test_the_guard_allows_accepted_team_members():
    """A team member is a legitimate user of a workspace they do not own.
    Refusing them would break the feature while fixing the hole."""
    from routers.auth import verify_workspace_access

    src = inspect.getsource(verify_workspace_access)
    assert "TeamMember" in src
    assert 'TeamMember.status == "ACCEPTED"' in src, (
        "a pending or revoked invite must not grant access"
    )


def test_a_missing_workspace_and_a_foreign_one_are_indistinguishable():
    """Different answers would let someone enumerate which workspace ids
    exist, which is a slower version of the same leak."""
    from routers.auth import verify_workspace_access

    src = inspect.getsource(verify_workspace_access)
    codes = re.findall(r"status_code=(\d+)", src)
    assert set(codes) == {"404"}, (
        f"the guard answers with {set(codes)}; a 403 for 'not yours' and a 404 "
        f"for 'no such workspace' reveals which ids are real"
    )


def test_a_request_without_a_workspace_is_not_blocked():
    """Many endpoints legitimately have no workspace. Rejecting those would
    take the whole API down rather than securing it."""
    from routers.auth import verify_workspace_access

    src = inspect.getsource(verify_workspace_access)
    assert "if not workspace_id:" in src and "return None" in src


def test_the_refusal_is_logged():
    """A cross-tenant attempt is a security event, not a routine 404."""
    from routers.auth import verify_workspace_access

    src = inspect.getsource(verify_workspace_access)
    assert "Blocked cross-tenant access" in src


def test_guard_runs_before_the_endpoint_body():
    """A dependency that ran after the handler would be decoration. FastAPI
    resolves router-level dependencies before dispatching."""
    import routers.marketing as m

    deps = [d.dependency.__name__ for d in m.router.dependencies]
    assert "verify_workspace_access" in deps
    assert "verify_user" in deps
