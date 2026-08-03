"""A bulk upload must land entirely in the business it started from.

authFetch reads the active workspace from localStorage at the moment each
request fires. A bulk upload is dozens of sequential requests over several
minutes, and localStorage is shared across tabs of the same origin -- so
switching business in another tab silently redirected every remaining batch.

One folder of 2793 files ended up split across five workspaces:

    1098 in quantcai
     417 in BollyVerse
      30 in Billionaire Goal777
       3 in Lumively
       3 in organic-marketing-ai

Nothing in the UI showed it happening. These guard the fix at the only place
that can enforce it -- the upload pinning its workspace for the whole run.
"""

from pathlib import Path

import pytest

CATALOG = Path(__file__).resolve().parent.parent / "frontend" / "src" / "pages" / "dashboard" / "MediaCatalog.jsx"
CONFIG = Path(__file__).resolve().parent.parent / "frontend" / "src" / "config.js"


@pytest.fixture(scope="module")
def catalog_source() -> str:
    if not CATALOG.exists():
        pytest.skip("frontend source not present")
    return CATALOG.read_text(encoding="utf-8")


def test_the_upload_pins_its_workspace(catalog_source):
    assert "const uploadWorkspaceId" in catalog_source, (
        "bulk upload no longer captures the workspace before it starts"
    )
    assert "pinnedWorkspace" in catalog_source


def test_every_batch_sends_the_pinned_workspace(catalog_source):
    """The header has to be on the request itself. Capturing the id and then
    not sending it is the same bug with extra steps."""
    start = catalog_source.index("media/bulk-upload")
    window = catalog_source[start:start + 320]
    assert "headers: pinnedWorkspace" in window, (
        "the bulk-upload request does not carry the pinned workspace header"
    )


def test_request_headers_override_the_ambient_workspace():
    """authFetch must merge caller headers AFTER the localStorage value, or
    pinning has no effect."""
    if not CONFIG.exists():
        pytest.skip("frontend config not present")
    src = CONFIG.read_text(encoding="utf-8")

    ambient = src.index("'X-Workspace-Id': activeWorkspaceId")
    caller = src.index("...(options.headers || {})")
    assert caller > ambient, (
        "caller-supplied headers are merged before the localStorage workspace, "
        "so an explicit X-Workspace-Id would be overwritten"
    )


def test_a_mid_upload_switch_is_reported(catalog_source):
    """The files go to the right place, but the catalog on screen is a
    different one -- which looks exactly like the upload having failed."""
    assert "switchedAway" in catalog_source
    assert "changed business while this was running" in catalog_source


def test_upload_refuses_without_a_workspace(catalog_source):
    """No workspace means the server picks one, which is how this started."""
    assert "Select a business before uploading" in catalog_source


def test_the_repair_script_identifies_files_by_folder():
    """The businessProfileId is the field that was wrong, so it cannot be used
    to decide where a file belongs. The folder prefix in the filename records
    the actual origin and the bug never touched it."""
    script = Path(__file__).resolve().parent.parent / "scripts" / "reassign_misfiled_media.py"
    if not script.exists():
        pytest.skip("repair script not present")
    src = script.read_text(encoding="utf-8")

    assert "_folder_of" in src
    assert "--undo" in src, "a bulk reassignment with no rollback is not repairable"
    assert "rollback" in src.lower()
