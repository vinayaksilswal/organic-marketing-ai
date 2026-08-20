"""The product does not tell customers what it is built on.

Which model writes a caption is an implementation detail and a moving target —
the fallback chain in services/ai_service.py already rotates through several
providers within one request. Naming any of them in the interface makes a
promise the next deploy may break.

"Free AI providers queue under load" was worse than a leak. It was in the one
place a customer stares at while waiting for the thing they are paying for,
and it told them the reason it is slow is that we did not pay for it. Nobody
pays $17 a month for a wrapper they have just been told is free.

The waiting message still says it may take a minute. That is honest and it is
useful. The reason why is ours.
"""

import pathlib
import re

import pytest

FRONTEND = pathlib.Path(__file__).resolve().parent.parent / "frontend" / "src"

# Provider and model names that must not reach the interface.
BANNED = [
    r"free\s+ai\b",
    # "free tier" on its own is the PRICING tier and is legitimate — the whole
    # funnel depends on saying it. Only the AI sense is banned.
    r"free\s+(model|provider)s?\b",
    r"free\s+ai\s+tier",
    r"openrouter",
    r"pollinations",
    r"nemotron",
    r"\bgemma\b",
    r"gpt-oss",
    r"anthropic",
    r"\bollama\b",
    r":free\b",
]


def _sources():
    for path in FRONTEND.rglob("*.js*"):
        if "node_modules" in path.parts:
            continue
        yield path, path.read_text(encoding="utf-8", errors="ignore")


@pytest.mark.parametrize("pattern", BANNED)
def test_no_provider_is_named_in_the_interface(pattern):
    offenders = []
    for path, text in _sources():
        for m in re.finditer(pattern, text, re.IGNORECASE):
            line = text[: m.start()].count("\n") + 1
            offenders.append(f"{path.name}:{line} -> {m.group(0)!r}")
    assert not offenders, (
        "the interface names an AI provider or tier:\n  " + "\n  ".join(offenders)
    )


def test_the_wait_is_still_explained():
    """Removing the reason must not remove the reassurance. An empty spinner
    with no expectation set is why people reload and generate twice."""
    studio = (FRONTEND / "pages" / "dashboard" / "VideoStudio.jsx").read_text(encoding="utf-8")
    assert "take up to a minute" in studio
    assert "leave this page" in studio
