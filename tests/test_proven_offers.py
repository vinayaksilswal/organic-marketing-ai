"""The proven-offer bridge from paid results to organic captions."""

from types import SimpleNamespace

import pytest

from services.proven_offers import (
    MEASURED,
    for_profile,
    measured_for,
    normalise,
    to_caption_guidance,
)


def _profile(name="", proven=None):
    return SimpleNamespace(name=name, provenOffers=proven)


class TestNormalise:
    def test_rejects_non_lists(self):
        for junk in (None, "", {}, 5, "product"):
            assert normalise(junk) == []

    def test_drops_entries_with_no_product(self):
        assert normalise([{"problem": "x"}, {"product": "  "}]) == []

    def test_keeps_the_fields_captions_use(self):
        out = normalise([{
            "product": "Thing", "problem": "P", "proof": "R",
            "offer": "O", "audience": "A", "best_format": "F",
        }])
        assert out == [{
            "product": "Thing", "problem": "P", "proof": "R",
            "offer": "O", "audience": "A", "best_format": "F",
        }]

    def test_survives_a_junk_entry_beside_a_good_one(self):
        out = normalise(["nonsense", {"product": "Thing"}, 42])
        assert len(out) == 1 and out[0]["product"] == "Thing"

    def test_truncates_rather_than_letting_a_field_run_away(self):
        out = normalise([{"product": "x" * 999, "best_format": "y" * 999}])
        assert len(out[0]["product"]) == 120
        # Long enough to say "images beat video by 3-4x", which is the part
        # that actually changes what gets written.
        assert len(out[0]["best_format"]) == 120


class TestGuidance:
    def test_silent_when_there_is_nothing_proven(self):
        assert to_caption_guidance(None) == ""
        assert to_caption_guidance([]) == ""

    def test_names_the_product_and_the_problem(self):
        text = to_caption_guidance(MEASURED["Lumively"])
        assert "Sank Magic Book" in text
        assert "handwriting" in text

    def test_carries_the_offer_when_one_converted(self):
        assert "Buy 1 Get 1 Free" in to_caption_guidance(MEASURED["MyCart4U"])

    def test_omits_the_offer_line_when_there_is_no_offer(self):
        text = to_caption_guidance(MEASURED["Lumively"])
        assert "the offer that converted" not in text

    def test_forbids_copying_the_ad_wording(self):
        # An organic feed that repeats ad copy reads as a billboard, and the
        # reader never opted in. This instruction is the whole reason the
        # service passes angles rather than the creative body text.
        text = to_caption_guidance(MEASURED["MyCart4U"])
        assert "do not copy the advertising wording" in text

    def test_caps_at_three_products(self):
        many = [{"product": f"P{i}"} for i in range(9)]
        text = to_caption_guidance(many)
        assert "P2" in text and "P3" not in text


class TestLookup:
    def test_matches_a_business_by_name_ignoring_case(self):
        assert measured_for(_profile("lumively"))
        assert measured_for(_profile("  MyCart4U  "))

    def test_unknown_business_gets_nothing_invented(self):
        assert measured_for(_profile("HollyVerse")) == []
        assert for_profile(_profile("HollyVerse")) == []

    def test_stored_offers_win_over_the_measured_table(self):
        p = _profile("Lumively", [{"product": "Something newer"}])
        assert for_profile(p)[0]["product"] == "Something newer"

    def test_falls_back_to_measured_when_nothing_is_stored_yet(self):
        p = _profile("Lumively", None)
        assert "Sank Magic Book" in for_profile(p)[0]["product"]

    def test_empty_stored_value_does_not_shadow_the_fallback(self):
        # A business whose column was written as [] must not lose its known
        # offers -- that would silently drop the evidence the captions need.
        assert for_profile(_profile("MyCart4U", []))

    def test_profile_without_the_column_does_not_explode(self):
        assert for_profile(SimpleNamespace(name="Lumively")) != []
