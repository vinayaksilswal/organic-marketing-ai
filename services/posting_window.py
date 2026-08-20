"""When a workspace is allowed to post, as opposed to when it is due.

The interval answers "has enough time passed". It cannot answer "is this a
sensible moment", and on a fixed interval the answer drifts through the whole
clock: a 4-hour cadence starting at 20:58 posts at 02:58 and 08:58, so a shop
whose customers are asleep gets a third of its output at three in the morning.
Two live workspaces show exactly that pattern.

So a workspace can also say WHEN. Days of the week, and an hour range, in its
own timezone -- because "post between 9 and 6" means nothing without knowing
whose 9 and whose 6.

COMPOSITION
-----------
The window never causes a post. It only ever withholds one. The interval still
decides due-ness, and both must agree:

    due (interval) AND allowed (window) -> post

That ordering matters. A window that forced posts would fire every workspace
at 09:00 sharp, which is the most obviously automated thing an account can do.

DEFAULTS
--------
Everything null means "no restriction", which is what every existing workspace
has and must keep having. A scheduling feature that silently narrows when an
account may post is a feature that silently stops it posting.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, Tuple

from loguru import logger

try:  # Python 3.9+
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - not reachable on supported runtimes
    ZoneInfo = None  # type: ignore

# Monday is 0, matching datetime.weekday(). Stored as ints rather than names so
# the value never depends on a locale.
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
ALL_DAYS = list(range(7))

DEFAULT_TIMEZONE = "UTC"


def _tz(name: Optional[str]):
    """The workspace's timezone, falling back to UTC rather than raising.

    A bad timezone string must not stop an account posting. Withholding every
    post because a settings field is malformed is a far worse failure than
    posting on the wrong clock.
    """
    if not name or ZoneInfo is None:
        return timezone.utc
    try:
        return ZoneInfo(name)
    except Exception:
        logger.warning(f"Unknown posting timezone {name!r}; using UTC")
        return timezone.utc


def normalise_days(raw: Any) -> Optional[list[int]]:
    """A stored day list, cleaned. None means every day."""
    if raw is None:
        return None
    if not isinstance(raw, (list, tuple, set)):
        return None
    days = sorted({int(d) for d in raw if isinstance(d, (int, float)) and 0 <= int(d) <= 6})
    # Empty means the customer deselected everything. Treated as no
    # restriction rather than as "never post", because a UI that can reach a
    # state where nothing ever publishes -- silently -- is a UI that will.
    if not days or len(days) == 7:
        return None
    return days


def _hour_bounds(start: Any, end: Any) -> Optional[Tuple[int, int]]:
    try:
        s, e = int(start), int(end)
    except (TypeError, ValueError):
        return None
    if not (0 <= s <= 23 and 0 <= e <= 23) or s == e:
        return None
    return s, e


def within_window(
    profile: Any, now: Optional[datetime] = None
) -> Tuple[bool, str]:
    """(allowed, reason). Reason is for the log, not the customer."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    local = now.astimezone(_tz(getattr(profile, "postingTimezone", None)))

    days = normalise_days(getattr(profile, "postingDays", None))
    if days is not None and local.weekday() not in days:
        allowed = ", ".join(DAY_NAMES[d] for d in days)
        return False, f"{DAY_NAMES[local.weekday()]} is outside the posting days ({allowed})"

    bounds = _hour_bounds(
        getattr(profile, "postingStartHour", None),
        getattr(profile, "postingEndHour", None),
    )
    if bounds is None:
        return True, "any hour"

    start, end = bounds
    hour = local.hour
    if start < end:
        ok = start <= hour < end
    else:
        # An overnight window, 22:00-06:00. Wrapping midnight is the normal
        # case for nightlife, delivery and anything selling to another
        # timezone, so it is supported rather than rejected as invalid.
        ok = hour >= start or hour < end

    if ok:
        return True, f"{hour:02d}:00 local is inside {start:02d}-{end:02d}"
    return False, f"{hour:02d}:00 local is outside {start:02d}-{end:02d}"


def describe(profile: Any) -> str:
    """One line for the dashboard, in the customer's own terms."""
    days = normalise_days(getattr(profile, "postingDays", None))
    bounds = _hour_bounds(
        getattr(profile, "postingStartHour", None),
        getattr(profile, "postingEndHour", None),
    )
    tzname = getattr(profile, "postingTimezone", None) or DEFAULT_TIMEZONE

    day_part = "Every day" if days is None else ", ".join(DAY_NAMES[d] for d in days)
    if bounds is None:
        return f"{day_part}, any time ({tzname})"
    return f"{day_part}, {bounds[0]:02d}:00-{bounds[1]:02d}:00 ({tzname})"
