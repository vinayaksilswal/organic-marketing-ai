"""One workspace failing must not stop every workspace after it.

Observed in production: two businesses posted on schedule and five never did,
and the only thing separating them was their position in the loop's iteration.
The cause was a single database session held open across the whole cycle.
Publishing a Reel uploads a video to Instagram and polls until it finishes --
minutes with the connection idle -- and Neon closes idle connections:

    InterfaceError: connection is closed
      SELECT count("Audience".id) ... WHERE businessProfileId = ...

From the fifth workspace onward every query ran on a dead connection, was
caught by the per-workspace handler, and was skipped. Every run. Permanently.

pool_pre_ping does not help: it validates a connection when it is checked out
of the pool, not one already held and then left idle.
"""

import inspect

import pytest

import services.scheduler as scheduler


@pytest.fixture(scope="module")
def loop_source() -> str:
    return inspect.getsource(scheduler.execute_marketing_loop)


def test_no_session_is_held_across_publishing(loop_source):
    """The publish is the slow part and the reason the connection died."""
    publish = loop_source.index("_execute_inline(workspace_id)")
    after_checks = loop_source.rindex("connection is None")
    assert "async with AsyncSessionLocal" not in loop_source[after_checks:publish], (
        "a database session is open while a workspace publishes, which is what "
        "left it idle long enough for the server to close it"
    )


def test_each_workspace_gets_its_own_session(loop_source):
    """Sharing one connection is what let a single failure cascade."""
    assert loop_source.count("AsyncSessionLocal()") >= 2, (
        "the loop still uses a single session for every workspace"
    )


def test_the_workspace_list_is_read_into_plain_values(loop_source):
    """Holding ORM instances past their session means every later attribute
    read is a lazy load on a connection that may be gone."""
    assert "workspaces = [" in loop_source
    assert "p.postIntervalHours or 2" in loop_source, (
        "the interval should be captured while the session is alive"
    )


def test_a_failing_workspace_does_not_stop_the_others(loop_source):
    assert "except Exception as workspace_err" in loop_source
    assert loop_source.rindex("continue") > loop_source.index("workspace_err")


def test_the_error_names_the_workspace(loop_source):
    """The original logged an id only, so a cascade looked like one failure
    rather than every workspace after a point."""
    assert "Error processing {name}" in loop_source


def test_brand_backfill_failure_does_not_block_posting(loop_source):
    """Brand analysis improves captions; it is not a precondition to publish."""
    brand = loop_source.index("generate_brand_context")
    publish = loop_source.index("_execute_inline(workspace_id)")
    assert brand < publish
    assert "posting continues with fallback captions" in loop_source
