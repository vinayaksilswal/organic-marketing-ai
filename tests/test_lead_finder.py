"""Leads: the people in your comments who were trying to buy.

The value of this screen is entirely in its precision. A tool that calls "🔥"
a sales lead wastes an afternoon and never gets opened again; one that misses
"how much?" costs an actual customer. So the tests here are mostly about what
it must NOT flag.

Every lead carries the phrase that flagged it, so a wrong match is visibly
wrong rather than an opaque verdict the customer has to take on faith.
"""

import pytest

from services import lead_finder as lf


# =============================================================================
# What counts as somebody trying to buy
# =============================================================================

@pytest.mark.parametrize("text,kind", [
    ("How much?", "price"),
    ("how much is this", "price"),
    ("What's the price?", "price"),
    ("kitna hai bhai", "price"),
    ("Whats the cost for 3", "price"),
    ("₹ for this?", "price"),
    ("How do I buy this", "buy"),
    ("where can i get one", "buy"),
    ("Can I order 2", "buy"),
    ("Is this available", "availability"),
    ("do you have it in stock", "availability"),
    ("Do you ship to Delhi", "availability"),
    ("DM me please", "contact"),
    ("whatsapp number?", "contact"),
    ("Interested!", "interest"),
    ("I need this", "interest"),
])
def test_buying_intent_is_recognised(text, kind):
    got = lf.classify(text)
    assert got is not None, f"missed: {text!r}"
    assert got["kind"] == kind, f"{text!r} -> {got['kind']}, expected {kind}"


@pytest.mark.parametrize("text", [
    "🔥🔥🔥",
    "love this",
    "Amazing work!!",
    "congrats 👏",
    "beautiful",
    "first",
    "",
    "   ",
    "❤️",
    "Great content, keep it up",
])
def test_appreciation_is_not_a_lead(text):
    """The failure that kills the feature. Flagging these buries the one
    comment that mattered under forty that did not."""
    assert lf.classify(text) is None, f"falsely flagged: {text!r}"


def test_the_phrase_that_flagged_it_is_returned():
    """A verdict the customer cannot check is a verdict they cannot trust."""
    got = lf.classify("Hey, how much for two of these?")
    assert got["matched"].lower() == "how much"


def test_price_outranks_a_generic_question():
    """Both patterns match. The one worth money has to win, because the list
    is sorted by it."""
    got = lf.classify("how much is it? do you deliver?")
    assert got["kind"] == "price"


def test_a_bare_question_still_surfaces_but_ranks_last():
    got = lf.classify("does this work for small teams?")
    assert got["kind"] == "question"
    assert lf._PRIORITY["question"] > lf._PRIORITY["price"]


# =============================================================================
# Scanning accounts
# =============================================================================

def _account(comments, handle="mybiz"):
    return [{
        "platform": "instagram",
        "handle": handle,
        "posts": [{
            "permalink": "https://instagram.com/p/abc",
            "caption": "New batch is up",
            "comments_list": comments,
        }],
    }]


def test_a_buying_question_becomes_a_lead():
    out = lf.from_accounts(_account([
        {"username": "asha", "text": "how much?", "timestamp": "2026-08-20T10:00:00+0000"},
    ]))
    assert out["total"] == 1
    lead = out["leads"][0]
    assert lead["who"] == "asha"
    assert lead["kind"] == "price"
    assert lead["answered"] is False
    assert lead["postPermalink"].endswith("/abc")


def test_our_own_comments_are_not_leads():
    """The business replying to itself is not a customer."""
    out = lf.from_accounts(_account([
        {"username": "mybiz", "text": "how much? DM us", "timestamp": "x"},
    ]))
    assert out["total"] == 0


def test_a_question_we_already_answered_is_marked_answered():
    """Graph nests replies as {'data': [...]}. Reading it as a list marks
    every lead unanswered and sends the customer back to people they have
    already helped."""
    out = lf.from_accounts(_account([
        {
            "username": "asha", "text": "how much?", "timestamp": "x",
            "replies": {"data": [{"username": "mybiz", "text": "₹499, DM sent"}]},
        },
    ]))
    assert out["leads"][0]["answered"] is True
    assert out["unanswered"] == 0


def test_a_reply_from_someone_else_does_not_count_as_answered():
    out = lf.from_accounts(_account([
        {
            "username": "asha", "text": "how much?", "timestamp": "x",
            "replies": {"data": [{"username": "randomguy", "text": "same question"}]},
        },
    ]))
    assert out["leads"][0]["answered"] is False


def test_unanswered_buying_questions_sort_to_the_top():
    """The order is the product. Whoever is closest to paying and still
    waiting goes first."""
    out = lf.from_accounts(_account([
        {"username": "a", "text": "does it work offline?", "timestamp": "x"},
        {"username": "b", "text": "how much?", "timestamp": "x",
         "replies": {"data": [{"username": "mybiz", "text": "answered"}]}},
        {"username": "c", "text": "where can i buy", "timestamp": "x"},
    ]))
    kinds = [(l["kind"], l["answered"]) for l in out["leads"]]
    assert kinds[0] == ("buy", False), kinds
    assert kinds[-1][1] is True, "an answered lead is not last"


def test_an_account_with_no_comments_says_so_rather_than_looking_broken():
    out = lf.from_accounts(_account([]))
    assert out["total"] == 0
    assert "no comments" in out["summary"].lower()


def test_comments_with_nothing_to_act_on_are_reported_as_read():
    """'We read 40 comments and none were leads' is a useful answer. A blank
    screen is not."""
    out = lf.from_accounts(_account([
        {"username": "x", "text": "🔥", "timestamp": "t"},
        {"username": "y", "text": "love it", "timestamp": "t"},
    ]))
    assert out["commentsScanned"] == 2
    assert out["total"] == 0
    assert "2 comments" in out["summary"]


def test_the_summary_counts_who_is_still_waiting():
    out = lf.from_accounts(_account([
        {"username": "a", "text": "how much?", "timestamp": "t"},
        {"username": "b", "text": "is it available?", "timestamp": "t"},
    ]))
    assert "2 of 2" in out["summary"] or "2 " in out["summary"]
    assert out["unanswered"] == 2


def test_nothing_explodes_on_missing_fields():
    """Graph omits keys constantly."""
    out = lf.from_accounts([
        {"platform": "instagram", "handle": None, "posts": [{"comments_list": [{}]}]},
        {"platform": "instagram"},
        {},
    ])
    assert out["total"] == 0


def test_direct_messages_are_not_read():
    """A tool that quietly read DMs after being connected for publishing would
    deserve to lose the customer. The permission is not requested and the code
    must not start using it without that being a decision."""
    import pathlib

    src = pathlib.Path(lf.__file__).read_text(encoding="utf-8")
    assert "instagram_manage_messages" not in src.replace(
        "It does not read direct messages. That needs instagram_manage_messages,", ""
    )
    assert "/conversations" not in src
