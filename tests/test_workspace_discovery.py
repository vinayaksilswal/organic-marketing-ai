"""A stale workspace id must not lock a user out of their own account.

The client keeps the active workspace in localStorage, which every account
signing in on that browser shares. A second user inherits the first user's
workspace id and attaches it to every request. The tenant guard correctly
refuses it -- including on the one call that would have corrected the stale
value, listing the user's own workspaces.

Observed in production: surendra.prasad@gmail.com signed in and received 404
on /businesses, /marketing/media, /video/config and /ecommerce/products, over
and over, because each request carried a workspace belonging to a different
account. Nothing in the app could recover; the only escape was clearing site
data.

Creating a business had the same shape from the other end. A new account owns
no workspace, so requiring one in order to make one is circular.
"""

import inspect
from pathlib import Path

import pytest

from routers.auth import _USER_SCOPED_PATHS, verify_workspace_access

FRONTEND = Path(__file__).resolve().parent.parent / "frontend" / "src"


def test_listing_workspaces_is_not_workspace_scoped():
    """This is the call that breaks the deadlock. If it is guarded, a stale id
    is unrecoverable from inside the app."""
    assert "/api/v1/businesses" in _USER_SCOPED_PATHS


def test_creating_a_business_does_not_require_owning_one():
    """POST and GET share the path; a new account must be able to reach it."""
    assert "/api/v1/businesses" in _USER_SCOPED_PATHS


def test_identity_and_billing_are_reachable_without_a_workspace():
    """A user whose only workspace was deleted still has to see their plan."""
    assert "/api/v1/users/me" in _USER_SCOPED_PATHS
    assert "/api/v1/billing/me" in _USER_SCOPED_PATHS


def test_a_single_workspace_stays_guarded():
    """The exemption is for discovery, not for anything taking an id. If
    /businesses/{id} were exempt the original hole would be back."""
    assert not any(p.endswith("{id}") or p.endswith("{workspace_id}")
                   for p in _USER_SCOPED_PATHS)
    assert "/api/v1/marketing/media" not in _USER_SCOPED_PATHS
    assert "/api/v1/marketing/run-automation" not in _USER_SCOPED_PATHS


def test_the_exemption_is_matched_exactly_not_by_prefix():
    """A prefix match on "/api/v1/businesses" would also exempt
    "/api/v1/businesses/<someone-elses-id>"."""
    src = inspect.getsource(verify_workspace_access)
    assert "in _USER_SCOPED_PATHS" in src
    assert "startswith" not in src.split("_USER_SCOPED_PATHS")[1][:200]


def test_the_exempted_handlers_filter_by_user_themselves():
    """Exempting an endpoint only removes the header check. If the handler
    did not scope by user_id, this would be a real hole rather than a fix."""
    import routers.user_api as user_api

    src = inspect.getsource(user_api.get_user_businesses)
    assert "BusinessProfile.userId == user_id" in src


# ── the client half ──────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def workspace_context() -> str:
    path = FRONTEND / "components" / "WorkspaceContext.jsx"
    if not path.exists():
        pytest.skip("frontend source not present")
    return path.read_text(encoding="utf-8")


def test_the_workspace_list_is_fetched_without_a_workspace_header(workspace_context):
    assert "'X-Workspace-Id': ''" in workspace_context, (
        "listing workspaces still asserts which one is current"
    )


def test_an_unusable_workspace_id_is_dropped(workspace_context):
    """Keeping it means every later request repeats the same refusal."""
    assert "Clearing unusable active workspace" in workspace_context
    catch = workspace_context[workspace_context.index("catch (err)"):]
    assert "setActiveWorkspace(null)" in catch


def test_an_empty_header_is_omitted_rather_than_sent_blank():
    """An empty string would be forwarded and the server would try to resolve
    it, which fails the same way as a stale one."""
    config = (FRONTEND / "config.js").read_text(encoding="utf-8")
    assert "delete headers['X-Workspace-Id']" in config
