import pytest
from datetime import datetime, timedelta, timezone
from services.scheduler import is_post_due, utc_now

def test_scheduler_utc_now():
    now = utc_now()
    assert now.tzinfo == timezone.utc
    assert isinstance(now, datetime)

def test_is_post_due():
    # 2 hours interval with 15 min loop (grace = 7.5 min = 0.125h)
    assert is_post_due(hours_since_last=2.0, interval_hours=2.0, loop_minutes=15) is True
    assert is_post_due(hours_since_last=1.9, interval_hours=2.0, loop_minutes=15) is True
    assert is_post_due(hours_since_last=1.5, interval_hours=2.0, loop_minutes=15) is False
