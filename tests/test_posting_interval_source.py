"""One field decides how often a business posts.

The interval was stored twice: BusinessProfile.postIntervalHours, which the
scheduler reads, and MarketingState.postIntervalHours, which the Social
Scheduler page read and wrote. They drifted -- two workspaces set to 4 hours
in Businesses -> Edit reported 2 hours on the scheduler page, so the settings
screen was describing a cadence the automation had never agreed to.

These pin the rule: the profile is authoritative, the mirror follows it, and
a workspace with nowhere to publish says so instead of silently doing nothing.
"""

import inspect

import pytest


def test_the_scheduler_reads_the_profile():
    """If this moves to MarketingState, the settings page becomes a lie again."""
    import services.scheduler as sched

    src = inspect.getsource(sched.execute_marketing_loop)
    assert "profile.postIntervalHours" in src, (
        "the loop no longer reads the interval from the BusinessProfile"
    )
    assert "MarketingState" not in src, (
        "the loop must not take the interval from the mirror copy"
    )


def test_settings_reports_the_profile_interval():
    import routers.marketing as m

    src = inspect.getsource(m.get_marketing_settings)
    assert "profile.postIntervalHours" in src
    assert "state.postIntervalHours" not in src, (
        "settings is reading the mirror again, which is what drifted"
    )


def test_updating_the_interval_writes_the_profile():
    import routers.marketing as m

    src = inspect.getsource(m.update_interval)
    assert "profile.postIntervalHours = data.intervalHours" in src, (
        "the interval endpoint must write the field the scheduler reads"
    )


def test_business_edit_mirrors_into_marketing_state():
    """Either screen may set it; both must leave the same number behind."""
    from services.onboarding_service import OnboardingService

    src = inspect.getsource(OnboardingService.update_business_profile)
    assert "MarketingState" in src and "postIntervalHours" in src, (
        "editing a business no longer keeps the mirror in step"
    )


def test_settings_explains_a_workspace_that_cannot_publish():
    """251 finished clips and zero posts, with nothing anywhere saying why,
    is the failure this prevents."""
    import routers.marketing as m

    src = inspect.getsource(m.get_marketing_settings)
    assert "socialConnected" in src
    assert "blockedReason" in src


def test_the_loop_skips_and_names_an_unconnected_workspace():
    import services.scheduler as sched

    src = inspect.getsource(sched.execute_marketing_loop)
    assert "SocialConnection" in src, (
        "the loop should check there is somewhere to publish"
    )
    assert "no connected social" in src.lower()


@pytest.mark.parametrize("interval", [1, 2, 4, 8, 12, 24])
def test_a_new_business_inherits_a_working_default(interval):
    """A business created today has no MarketingState row at all. The loop must
    still find an interval for it, or new workspaces never post."""
    from database import BusinessProfile

    column = BusinessProfile.__table__.columns["postIntervalHours"]
    assert column.default is not None, "new businesses would have no interval"
    assert column.default.arg == 2
    assert not column.nullable, "a null interval would skip the workspace forever"
