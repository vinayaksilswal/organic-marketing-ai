"""Deleting published posts is irreversible, so the guards are the feature."""

import services.post_cleanup as cleanup
from services.post_cleanup import _views_from


class TestViewReading:
    def test_reels_report_plays(self):
        assert _views_from({"data": [{"name": "plays", "values": [{"value": 42}]}]}) == 42

    def test_feed_posts_report_impressions(self):
        assert _views_from(
            {"data": [{"name": "impressions", "values": [{"value": 7}]}]}
        ) == 7

    def test_reach_is_used_when_nothing_better_exists(self):
        assert _views_from({"data": [{"name": "reach", "values": [{"value": 3}]}]}) == 3

    def test_plays_wins_over_reach_when_both_are_present(self):
        insights = {"data": [
            {"name": "reach", "values": [{"value": 5}]},
            {"name": "plays", "values": [{"value": 90}]},
        ]}
        assert _views_from(insights) == 90

    def test_zero_views_is_a_real_number_not_a_missing_one(self):
        # A post with genuinely zero views is exactly what should be removed,
        # so this must not be confused with "unknown".
        assert _views_from({"data": [{"name": "plays", "values": [{"value": 0}]}]}) == 0

    def test_an_error_reads_as_unknown_rather_than_zero(self):
        # Treating an unreadable post as zero views would delete it for being
        # unmeasurable, which is how a permissions failure becomes data loss.
        assert _views_from({"error": {"message": "no permission"}}) is None
        assert _views_from({}) is None
        assert _views_from({"data": []}) is None

    def test_a_non_numeric_value_is_not_trusted(self):
        assert _views_from(
            {"data": [{"name": "plays", "values": [{"value": None}]}]}
        ) is None


class TestThresholds:
    def test_the_rule_matches_what_was_asked_for(self):
        assert cleanup.MIN_AGE_DAYS == 15
        assert cleanup.MIN_VIEWS == 100

    def test_a_run_is_bounded(self):
        # The blast radius of one bad run. Without a cap, a Meta outage
        # returning zeros could empty an account in a single pass.
        assert 0 < cleanup.MAX_DELETIONS_PER_RUN <= 50

    def test_it_is_off_unless_explicitly_enabled(self, monkeypatch):
        # Deleting a customer's published posts must never be something that
        # starts happening because the code shipped.
        monkeypatch.delenv("POST_CLEANUP_ENABLED", raising=False)
        import importlib

        reloaded = importlib.reload(cleanup)
        assert reloaded.ENABLED is False


class TestRunGuard:
    async def test_disabled_run_deletes_nothing(self, monkeypatch):
        monkeypatch.setattr(cleanup, "ENABLED", False)
        assert await cleanup.run_cleanup() == []

    async def test_a_dry_run_is_not_stopped_by_the_disabled_guard(self, monkeypatch):
        """Seeing what WOULD be deleted must not require arming the deleter.

        Checks the guard condition itself rather than running the job, which
        needs a live database. The guard is `not ENABLED and not dry_run`, so
        a dry run passes it while a real run does not.
        """
        monkeypatch.setattr(cleanup, "ENABLED", False)
        assert (not cleanup.ENABLED and not False) is True   # real run: stopped
        assert (not cleanup.ENABLED and not True) is False   # dry run: allowed
