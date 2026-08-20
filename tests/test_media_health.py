"""A dead asset is retired; a flaky one is left alone.

_is_postable asks whether a row looks publishable — active, has a URL, is an
image or video. It cannot ask whether the URL still resolves, so a Media row
pointing at a deleted file passes every check, gets scheduled, and fails at
Meta with the error landing on the delivery log rather than on the asset that
caused it.

The dangerous half of fixing that is over-reach. Emptying a customer's catalog
because of a network blip is a far worse failure than the one being fixed, and
irreversible in practice — nobody remembers which assets were fine yesterday.
So only 404 and 410 retire anything.
"""

import inspect

import pytest

from services import media_health as mh


def test_only_definitive_gone_statuses_retire_an_asset():
    assert mh.DEAD_STATUSES == {404, 410}


@pytest.mark.parametrize("status", [408, 429, 500, 502, 503, 504])
def test_transient_failures_never_retire_an_asset(status):
    """These all mean 'ask again later'. Treating them as death empties a
    catalog over a bad minute."""
    assert status not in mh.DEAD_STATUSES


def test_an_unreachable_url_is_counted_not_retired():
    """A timeout returns None, and None must not be read as gone."""
    src = inspect.getsource(mh.sweep)
    assert "if status is None:" in src
    assert "unreachable += 1" in src
    none_branch = src.index("if status is None:")
    retire = src.index("dead += 1")
    assert none_branch < retire, "an unreachable probe falls through to retirement"


def test_head_falling_back_to_get_is_not_treated_as_death():
    """Some CDNs answer HEAD with 405 while serving the object fine."""
    src = inspect.getsource(mh._probe)
    assert "405" in src and "client.get" in src


def test_nothing_is_deleted():
    """Retiring is reversible; deleting is not, and the file may come back."""
    src = inspect.getsource(mh.sweep)
    assert "isActive = False" in src
    assert "delete(" not in src and "session.delete" not in src


def test_the_reason_is_recorded_where_the_user_will_see_it():
    src = inspect.getsource(mh.sweep)
    assert "generationError" in src
    assert "Re-upload" in src


def test_a_dry_run_changes_nothing():
    src = inspect.getsource(mh.sweep)
    assert "if not dry_run" in src
    commit = src.index("await session.commit()")
    guard = src.rindex("if not dry_run and dead:", 0, commit)
    assert guard < commit, "the commit is not behind the dry-run guard"


def test_only_real_media_is_probed():
    """The catalog also holds prompt-only rows with no URL — probing those
    would count failures that are not failures."""
    src = inspect.getsource(mh.sweep)
    assert 'startswith("http")' in src
    assert 'startswith(("image/", "video/"))' in src


def test_the_sweep_is_bounded():
    """An unbounded fan-out against one CDN gets rate limited, and rate limits
    look exactly like the transient failures this must not act on."""
    src = inspect.getsource(mh.sweep)
    assert "Semaphore" in src
    assert mh.CONCURRENCY <= 10
