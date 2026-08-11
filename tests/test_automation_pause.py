"""Pausing a business holds its automation without destroying anything.

Every alternative a user would otherwise reach for loses something:
disconnecting the social account drops the access token, deleting the
workspace drops the catalog, and setting a 24-hour interval still posts.
A rebrand, an incident or a holiday needs a switch, not a demolition.
"""

import inspect
from pathlib import Path

import pytest

from database import BusinessProfile

FRONTEND = Path(__file__).resolve().parent.parent / "frontend" / "src"


def test_the_column_defaults_to_running():
    """A migration that paused live accounts would be silent, and would look
    exactly like the automation being broken."""
    col = BusinessProfile.__table__.columns["automationPaused"]
    assert col.default.arg is False
    assert not col.nullable, "a null would be neither paused nor running"


def test_the_migration_defaults_existing_rows_to_running():
    migration = (
        Path(__file__).resolve().parent.parent
        / "alembic" / "versions" / "020_automation_paused.py"
    ).read_text(encoding="utf-8")
    assert "DEFAULT FALSE" in migration
    assert "NOT NULL" in migration
    assert "IF NOT EXISTS" in migration, "re-running the migration must be safe"


def test_the_loop_skips_a_paused_workspace():
    import services.scheduler as sched

    src = inspect.getsource(sched.execute_marketing_loop)
    assert "if paused:" in src
    assert '"{name}: paused"' in src or "paused" in src


def test_pausing_is_checked_before_any_expensive_work():
    """A paused workspace should not spend an LLM call on brand analysis or a
    database round trip on the due check."""
    import services.scheduler as sched

    src = inspect.getsource(sched.execute_marketing_loop)
    paused_at = src.index("if paused:")
    brand_at = src.index("generate_brand_context")
    due_at = src.index("posts_in_last_24h")
    assert paused_at < brand_at
    assert paused_at < due_at


def test_a_paused_cycle_says_so_rather_than_skipping_silently():
    """Every silent skip in this loop has cost hours to diagnose."""
    import services.scheduler as sched

    src = inspect.getsource(sched.execute_marketing_loop)
    assert "outcomes.append(f\"{name}: paused\")" in src


def test_the_api_accepts_and_returns_the_flag():
    import routers.user_api as user_api

    src = inspect.getsource(user_api)
    assert "automationPaused: Optional[bool] = None" in src, (
        "the update model cannot carry the flag"
    )
    assert src.count('"automationPaused"') >= 2, (
        "the flag is not returned, so the UI cannot show its own state"
    )


def test_only_the_owner_can_pause_a_workspace():
    import routers.user_api as user_api

    src = inspect.getsource(user_api.update_business)
    assert "bp.userId != user_id" in src


# ── the button ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def workspaces_jsx() -> str:
    path = FRONTEND / "pages" / "dashboard" / "Workspaces.jsx"
    if not path.exists():
        pytest.skip("frontend source not present")
    return path.read_text(encoding="utf-8")


def test_the_card_has_a_pause_control(workspaces_jsx):
    assert "toggleAutomation" in workspaces_jsx
    assert "automationPaused: next" in workspaces_jsx


def test_the_control_reflects_the_current_state(workspaces_jsx):
    """A button that always says "Pause" gives no way to tell whether it
    worked."""
    assert "bp.automationPaused ? 'Resume' : 'Pause'" in workspaces_jsx


def test_a_paused_business_is_obvious_without_reading_the_button(workspaces_jsx):
    assert "Automation paused" in workspaces_jsx


def test_the_list_is_refreshed_after_toggling(workspaces_jsx):
    """Otherwise the card keeps showing the old state until a manual reload,
    which reads as the click having failed."""
    handler = workspaces_jsx[workspaces_jsx.index("const toggleAutomation"):]
    handler = handler[: handler.index("const openEditModal")]
    assert "refreshWorkspaces()" in handler
