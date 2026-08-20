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


SEGMENT_SECONDS = 3.0

# A trailing stub shorter than this is folded into the segment before it. Two
# seconds is roughly the shortest span a video model treats as its own shot;
# below that it produces a flash rather than a beat.
MIN_TAIL_SECONDS = 2.0


def _segment_bounds(duration: int) -> list[tuple[float, float]]:
    """Cut the clip into three-second blocks, absorbing any short tail."""
    bounds, cursor = [], 0.0
    while cursor < duration:
        end = min(cursor + SEGMENT_SECONDS, float(duration))
        bounds.append((cursor, end))
        cursor = end

    if len(bounds) > 1:
        last_start, last_end = bounds[-1]
        if last_end - last_start < MIN_TAIL_SECONDS:
            prev_start, _ = bounds[-2]
            bounds[-2] = (prev_start, last_end)
            bounds.pop()
    return bounds


def _role_for(index: int, total: int) -> tuple[str, str]:
    """What this block is for. First stops the scroll, last asks for the click."""
    if index == 0:
        return "HOOK", (
            "Open ALREADY IN MOTION on the very first frame - someone "
            "mid-reaction, mid-reach, mid-expression. No establishing shot, no "
            "logo, no fade. The viewer must recognise their own problem before "
            "anything is claimed."
        )
    if index == total - 1:
        return "OUTRO / CTA", (
            "Resolve onto the closing card: the brand name and the offer, held "
            "still for the last two seconds. Nothing moves here - a call to "
            "action that moves gets scrolled past, one that stops gets read."
        )
    # Everything between carries the argument, in order.
    middles = [
        ("THE TURN", "the moment the problem becomes solvable - the product "
                     "doing the one thing it exists to do, filmed close"),
        ("THE PROOF", "the result in the world: the thing working, the person "
                      "using it, the outcome visible rather than described"),
        ("THE REASON", "why it holds up - one concrete detail a sceptic would "
                       "want, shown rather than claimed"),
        ("THE ANSWER", "the single objection that stops this purchase, "
                       "answered on screen"),
    ]
    name, intent = middles[(index - 1) % len(middles)]
    return name, intent


def build_beats(duration: int) -> list[dict]:
    """The clip in three-second blocks, each with its own job.

    Three seconds is the unit because it is the shortest span a viewer
    registers as a distinct shot and the longest one a video model holds
    without drifting. It also matches how the hook is judged: the first block
    IS the scroll decision.
    """
    duration = clamp_duration(duration)
    bounds = _segment_bounds(duration)
    total = len(bounds)

    beats = []
    for i, (start, end) in enumerate(bounds):
        name, intent = _role_for(i, total)
        beats.append({
            "index": i + 1,
            "name": name,
            "start": round(start, 1),
            "end": round(end, 1),
            "seconds": round(end - start, 1),
            "intent": intent,
            # Speech fitting this block, so a writer can see the budget per
            # segment rather than only for the clip.
            "words": max(1, int(round((end - start) * WORDS_PER_SECOND))),
        })
    return beats


def word_budget(duration: int) -> int:
    """How many spoken words fit, leaving the outro card silent-ish."""
    duration = clamp_duration(duration)
    return int((duration - OUTRO_SECONDS * 0.5) * WORDS_PER_SECOND)


def _clock(seconds: float) -> str:
    """0:03 rather than 3s. A timeline reads as a timeline."""
    m, sec = divmod(int(round(seconds)), 60)
    return f"{m}:{sec:02d}"


def beat_sheet(duration: int) -> str:
    """The block that tells the model exactly what to write, and how to lay it out.

    The layout is load-bearing rather than decorative. The person receiving
    this prompt has to read it, find the third block, change one line and
    paste it into a video tool -- so it is written as a timeline with fixed
    labels and hanging indents, not as a paragraph. A wall of prose is
    unreviewable, and an unreviewable prompt gets used unedited or not at all.
    """
    beats = build_beats(duration)
    total = clamp_duration(duration)

    lines = [
        f"WRITE THE PROMPT AS A {total}-SECOND TIMELINE, IN BLOCKS OF THREE SECONDS.",
        "",
        "Reproduce the structure below exactly, in this order, with these labels",
        "and this indentation. For every block write two lines:",
        "",
        "    VISUAL: one camera move, one subject, one action, and the light.",
        "    SCRIPT: the words spoken aloud in that block, verbatim, in quotes.",
        "",
        "Do not merge blocks. Do not add commentary between them. A block with",
        "nothing spoken still gets a SCRIPT line reading \"(silence)\".",
        "",
        "-" * 60,
        "",
    ]

    for b in beats:
        lines.append(f"{_clock(b['start'])}-{_clock(b['end'])}  {b['name']}  ({b['seconds']:g}s, about {b['words']} words)")
        lines.append(f"    {b['intent']}")
        lines.append("    VISUAL: <what the camera sees>")
        lines.append(f"    SCRIPT: \"<the words spoken in these {b['seconds']:g} seconds>\"")
        lines.append("")

    lines += [
        "-" * 60,
        "",
        f"SPOKEN BUDGET: about {word_budget(duration)} words across the whole clip, "
        "starting on the very first frame with no pause before the first word. "
        "Write the actual words -- these models generate synchronised speech, so "
        "a description of the line produces silence and only the words produce a "
        "voice.",
        "",
        "AUDIO: one ambience clause plus one punctuating sound, named once after "
        "the final block.",
        "",
        "CONTINUITY: the same subject, wardrobe, room and grade in every block. "
        "Name them once at the top and do not restate them per block -- repeating "
        "a description is how a model ends up rendering two different people.",
    ]
    return chr(10).join(lines)


def summary(duration: int) -> dict:
    """Machine-readable plan, for the API and the dashboard."""
    duration = clamp_duration(duration)
    return {
        "durationSeconds": duration,
        "hookSeconds": HOOK_SECONDS,
        "outroSeconds": OUTRO_SECONDS,
        "segmentSeconds": SEGMENT_SECONDS,
        "wordBudget": word_budget(duration),
        "beats": build_beats(duration),
    }
