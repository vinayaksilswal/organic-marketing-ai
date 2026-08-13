"""Every caption carries the business's own hashtag."""

from types import SimpleNamespace

from services.hashtag_engine import brand_tag, ensure_brand_tag


def _profile(name):
    return SimpleNamespace(name=name)


class TestBrandTag:
    def test_a_plain_name_becomes_a_tag(self):
        assert brand_tag(_profile("Lumively")) == "#Lumively"

    def test_spaces_are_removed_rather_than_breaking_the_tag(self):
        # "#Billionaire Goal777" would be read by Instagram as #Billionaire.
        assert brand_tag(_profile("Billionaire Goal777")) == "#BillionaireGoal777"

    def test_punctuation_is_stripped(self):
        assert brand_tag(_profile("MyCart4U!")) == "#MyCart4U"

    def test_a_nameless_business_gets_nothing_invented(self):
        assert brand_tag(_profile("")) is None
        assert brand_tag(SimpleNamespace()) is None

    def test_a_name_that_cannot_be_a_tag_returns_nothing(self):
        # All-digits is not searchable on Instagram.
        assert brand_tag(_profile("777")) is None


class TestEnsure:
    def test_it_is_appended_when_missing(self):
        out = ensure_brand_tag("A caption.\n\n#one #two", _profile("Lumively"))
        assert "#Lumively" in out

    def test_it_joins_the_existing_hashtag_line(self):
        # A second block of tags below the first looks like two captions
        # stapled together.
        out = ensure_brand_tag("A caption.\n\n#one #two", _profile("Lumively"))
        assert out.count("\n\n") == 1
        assert out.split("\n")[-1] == "#one #two #Lumively"

    def test_a_caption_with_no_tags_gets_its_own_line(self):
        out = ensure_brand_tag("Just words.", _profile("Lumively"))
        assert out == "Just words.\n\n#Lumively"

    def test_it_is_not_added_twice(self):
        caption = "A caption.\n\n#one #Lumively"
        assert ensure_brand_tag(caption, _profile("Lumively")) == caption

    def test_matching_ignores_case(self):
        # #lumively and #Lumively are the same tag to Instagram, so adding the
        # other spelling would put the same tag on the post twice.
        caption = "A caption.\n\n#lumively"
        assert ensure_brand_tag(caption, _profile("Lumively")) == caption

    def test_an_unusable_name_leaves_the_caption_alone(self):
        caption = "A caption.\n\n#one"
        assert ensure_brand_tag(caption, _profile("")) == caption

    def test_an_empty_caption_becomes_just_the_tag(self):
        assert ensure_brand_tag("", _profile("Lumively")) == "#Lumively"

    def test_trailing_whitespace_does_not_produce_a_gap(self):
        out = ensure_brand_tag("Words.\n\n#one   \n", _profile("Lumively"))
        assert out.endswith("#one #Lumively")
