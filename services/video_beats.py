"""How a clip of a given length is divided, second by second.

Video models take a duration, and the prompts written for them almost never
say what happens WHEN. A model handed "a 30-second ad about a skincare brand"
spends its budget evenly across thirty seconds and produces thirty seconds of
nothing in particular. Handed "0-3s: a woman already mid-reaction, 3-11s: she
turns the jar to the light, 11-16s: ...", it has somewhere to put each frame.

So the prompt carries a beat sheet, and this module builds it.

THREE THINGS THAT DO NOT SCALE WITH LENGTH
------------------------------------------
The hook is always 3 seconds. It is the window in which a scroll is decided
and the point at which Instagram counts a view; a 30-second ad does not get a
nine-second hook because it is longer, it gets the same three and then has to
keep what it caught.

The outro is always 2 seconds. It is one still card with a name and an offer,
and holding it longer does not make anyone read it twice — it just taxes the
watch-time ratio, which is a ranking input.

Speech runs at about 2.5 words a second. Everything between those two is the
only part that grows.

WHY THE BODY IS SPLIT
--------------------
A single action stretched over twenty seconds is where these models drift:
the subject morphs, the room changes, the product becomes a different product.
Past roughly eight seconds a beat needs to become two. The splits below keep
every beat inside that window, which is also how a human editor would cut it.
"""

from __future__ import annotations

from typing import Any

# The scroll-stop window, and the end card. Neither scales with length.
HOOK_SECONDS = 3.0
OUTRO_SECONDS = 2.0

# What the generators accept today.
MIN_DURATION = 8
MAX_DURATION = 30
DEFAULT_DURATION = 10

# Natural speech, near enough for a word budget.
WORDS_PER_SECOND = 2.5

# Longer than this and a single beat starts to drift.
MAX_BEAT_SECONDS = 8.0


def clamp_duration(value: Any) -> int:
    """Whatever the client sent, turned into a length we can actually build."""
    try:
        seconds = int(round(float(value)))
    except (TypeError, ValueError):
        return DEFAULT_DURATION
    return max(MIN_DURATION, min(MAX_DURATION, seconds))


def _body_split(body_seconds: float) -> list[float]:
    """Divide the middle into beats no longer than one shot can hold."""
    if body_seconds <= 0:
        return []
    count = max(1, int(-(-body_seconds // MAX_BEAT_SECONDS)))  # ceil
    even = body_seconds / count
    return [even] * count


ROLES = [
    ("The turn", "the moment the problem becomes solvable — the product doing "
                 "the one thing it exists to do, filmed close"),
    ("The proof", "the result in the world: the thing working, the person "
                  "using it, the outcome visible rather than described"),
    ("The reason", "why it holds up — one concrete detail a sceptic would "
                   "want, shown rather than claimed"),
    ("The answer", "the single objection that stops this purchase, answered on "
                   "screen — the price, the effort, the risk, whichever one "
                   "this buyer actually raises"),
]


def build_beats(duration: int) -> list[dict]:
    """The full second-by-second plan for a clip of this length."""
    duration = clamp_duration(duration)
    body = max(0.0, duration - HOOK_SECONDS - OUTRO_SECONDS)

    beats: list[dict] = [{
        "name": "Hook",
        "start": 0.0,
        "end": HOOK_SECONDS,
        "seconds": HOOK_SECONDS,
        "intent": (
            "Open ALREADY IN MOTION on the first frame — someone mid-reaction, "
            "mid-reach, mid-expression. No establishing shot, no logo, no fade. "
            "The viewer must recognise their own problem before anything is "
            "claimed."
        ),
    }]

    cursor = HOOK_SECONDS
    splits = _body_split(body)
    for i, length in enumerate(splits):
        name, intent = ROLES[i] if i < len(ROLES) else (
            f"Beat {i + 1}", "one further concrete moment, same subject and room"
        )
        beats.append({
            "name": name,
            "start": round(cursor, 1),
            "end": round(cursor + length, 1),
            "seconds": round(length, 1),
            "intent": intent,
        })
        cursor += length

    beats.append({
        "name": "Outro",
        "start": round(cursor, 1),
        "end": float(duration),
        "seconds": OUTRO_SECONDS,
        "intent": (
            "Resolve onto the closing card: the brand name and the offer, held "
            "still. Nothing moves here — a call to action that moves gets "
            "scrolled past, one that stops gets read."
        ),
    })
    return beats


def word_budget(duration: int) -> int:
    """How many spoken words fit, leaving the outro card silent-ish."""
    duration = clamp_duration(duration)
    return int((duration - OUTRO_SECONDS * 0.5) * WORDS_PER_SECOND)


def beat_sheet(duration: int) -> str:
    """The beat plan as the block that goes into the video-model prompt.

    Written as instructions to the renderer, not as notes to a human: every
    line names a time range, what is in frame, and what is heard. Models
    follow an explicit clock far better than they follow a narrative.
    """
    beats = build_beats(duration)
    lines = [
        f"TIMED STRUCTURE — this clip is {clamp_duration(duration)} seconds. "
        f"Write the prompt so each range below is explicitly described, in order, "
        f"with its own VISUAL and its own SPOKEN words:",
        "",
    ]
    for b in beats:
        lines.append(
            f"  {b['start']:g}-{b['end']:g}s  {b['name'].upper()} "
            f"({b['seconds']:g}s) — {b['intent']}"
        )
    lines += [
        "",
        f"SPOKEN WORD BUDGET: about {word_budget(duration)} words across the whole "
        "clip, starting on the first frame with no pause before the first word. "
        "Write the actual words, verbatim, in double quotes — these models "
        "generate synchronised speech, so a description of the line produces "
        "silence and only the words themselves produce a voice.",
        "",
        "AUDIO: one short ambience clause plus one punctuating sound, named once "
        "for the whole clip.",
    ]
    return "\n".join(lines)


def summary(duration: int) -> dict:
    """Machine-readable plan, for the API and the dashboard."""
    duration = clamp_duration(duration)
    return {
        "durationSeconds": duration,
        "hookSeconds": HOOK_SECONDS,
        "outroSeconds": OUTRO_SECONDS,
        "wordBudget": word_budget(duration),
        "beats": build_beats(duration),
    }
