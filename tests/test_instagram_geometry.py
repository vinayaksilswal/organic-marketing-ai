"""Images outside Instagram's aspect ratio window are cropped, not lost.

The decision is made here in Python rather than by a Cloudinary conditional,
and the transformation names explicit pixels rather than a ratio. Both choices
came from live failures, and the tests below pin the specific shapes that broke
the first attempt.
"""

import struct

import pytest

from services.instagram_geometry import (
    LANDSCAPE,
    MAX_RATIO,
    MIN_RATIO,
    PORTRAIT,
    already_normalised,
    apply,
    dimensions,
    is_cloudinary_image,
    publishable_urls,
    transform_for,
)

CLOUDINARY = (
    "https://res.cloudinary.com/qpojfnua/image/upload/v1785824093/"
    "tenants/a9f955ac-c4d2-4646-b9b0-68e5118bd0ef/media/fa4faa5b.jpg"
)
VIDEO = (
    "https://res.cloudinary.com/qpojfnua/image/upload/v1785824093/"
    "tenants/a9f955ac/media/clip.mp4"
)


def _jpeg(width: int, height: int) -> bytes:
    """A minimal JPEG carrying just an SOF0 frame header."""
    return (
        b"\xff\xd8"
        + b"\xff\xc0" + struct.pack(">H", 17) + b"\x08"
        + struct.pack(">HH", height, width)
        + b"\x03" + b"\x00" * 9
    )


def _png(width: int, height: int) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + struct.pack(">II", width, height)


class TestMeasuring:
    def test_reads_jpeg_dimensions(self):
        assert dimensions(_jpeg(1440, 1920)) == (1440, 1920)

    def test_reads_png_dimensions(self):
        assert dimensions(_png(1080, 1350)) == (1080, 1350)

    def test_junk_measures_as_nothing_rather_than_guessing(self):
        for junk in (b"", b"not an image", b"\xff\xd8truncated"):
            assert dimensions(junk) is None


class TestDecision:
    def test_the_dominant_hollyverse_shape_is_corrected(self):
        # 1440x1920 = 0.750, the single most common asset in the catalog.
        assert transform_for(1440, 1920) == PORTRAIT

    def test_the_boundary_shape_that_defeated_the_cloudinary_conditional(self):
        # 1186x1483 = 0.7997. Genuinely rejected by Instagram, and left
        # untouched by `if_ar_lt_0.8` because Cloudinary rounded it to 0.80.
        assert transform_for(1186, 1483) == PORTRAIT

    def test_a_story_crop_is_corrected(self):
        assert transform_for(768, 1376) == PORTRAIT

    def test_a_very_wide_image_is_corrected(self):
        assert transform_for(3000, 1000) == LANDSCAPE

    def test_shapes_already_in_range_are_left_alone(self):
        # 1200x630 is 1.9048 and fits. 1200x628 -- the standard link-preview
        # size -- is 1.9108 and does NOT, which is exactly the kind of near-miss
        # this module exists to catch.
        for w, h in [(1080, 1350), (1080, 1080), (1440, 1788), (1200, 630)]:
            assert transform_for(w, h) is None, f"{w}x{h} should not be touched"
        assert transform_for(1200, 628) == LANDSCAPE

    def test_exactly_at_each_boundary_is_accepted(self):
        assert transform_for(800, 1000) is None      # exactly 0.8
        assert transform_for(1910, 1000) is None     # exactly 1.91

    def test_zero_dimensions_do_not_divide_by_zero(self):
        assert transform_for(0, 100) is None
        assert transform_for(100, 0) is None


class TestTransform:
    def test_the_target_is_explicit_pixels_not_a_ratio(self):
        # ar_4:5 let Cloudinary choose integers and it produced 1430x1788 --
        # 0.7998, back outside the window. Fixed pixels cannot do that.
        assert "w_1080" in PORTRAIT and "h_1350" in PORTRAIT
        assert "ar_" not in PORTRAIT

    def test_the_portrait_target_is_inside_the_window(self):
        assert MIN_RATIO <= 1080 / 1350 <= MAX_RATIO

    def test_the_landscape_target_is_inside_the_window(self):
        assert MIN_RATIO <= 1080 / 566 <= MAX_RATIO

    def test_applying_keeps_the_public_id_intact(self):
        out = apply(CLOUDINARY, PORTRAIT)
        assert out.endswith("media/fa4faa5b.jpg")
        assert "v1785824093" in out
        assert PORTRAIT in out

    def test_a_transformed_url_is_recognised_as_done(self):
        assert already_normalised(apply(CLOUDINARY, PORTRAIT))
        assert not already_normalised(CLOUDINARY)


class TestHosts:
    def test_only_cloudinary_urls_can_be_transformed(self):
        assert is_cloudinary_image(CLOUDINARY)
        assert not is_cloudinary_image("https://example.com/image/upload/x.jpg")
        assert not is_cloudinary_image("")
        assert not is_cloudinary_image(None)


class TestWholePost:
    @pytest.mark.asyncio
    async def test_videos_are_never_measured_or_cropped(self):
        # Reels accept far taller shapes. Cropping vertical video to 4:5 would
        # break the format that currently works, and measuring it would mean a
        # pointless request per post.
        assert await publishable_urls([VIDEO]) == [VIDEO]

    @pytest.mark.asyncio
    async def test_empty_input_is_safe(self):
        assert await publishable_urls([]) == []
        assert await publishable_urls(None) == []

    @pytest.mark.asyncio
    async def test_non_cloudinary_images_pass_through_without_a_request(self):
        # No network call should be needed to decide this, so it works offline.
        urls = ["https://example.com/a.jpg", "/api/v1/media/abc"]
        assert await publishable_urls(urls) == urls

    @pytest.mark.asyncio
    async def test_order_is_preserved(self):
        # Carousel slide order is the user's explicit choice.
        urls = [VIDEO, "https://example.com/a.jpg", "https://example.com/b.jpg"]
        assert await publishable_urls(urls) == urls
