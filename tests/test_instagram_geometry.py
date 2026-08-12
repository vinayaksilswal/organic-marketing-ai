"""Images outside Instagram's aspect ratio window are cropped, not lost."""

from services.instagram_geometry import (
    already_normalised,
    is_cloudinary_image,
    publishable_url,
    publishable_urls,
)

CLOUDINARY = (
    "https://res.cloudinary.com/qpojfnua/image/upload/v1785824093/"
    "tenants/a9f955ac-c4d2-4646-b9b0-68e5118bd0ef/media/fa4faa5b.jpg"
)
VIDEO = (
    "https://res.cloudinary.com/qpojfnua/image/upload/v1785824093/"
    "tenants/a9f955ac/media/clip.mp4"
)


class TestRewriting:
    def test_a_cloudinary_image_gains_the_conditional_transform(self):
        out = publishable_url(CLOUDINARY)
        assert "if_ar_lt_0.8/c_fill,ar_4:5,g_auto/if_end" in out
        assert "if_ar_gt_1.91/c_fill,ar_1.91,g_auto/if_end" in out

    def test_the_original_path_survives_intact(self):
        # A rewrite that loses the public id returns a 404 for every post.
        out = publishable_url(CLOUDINARY)
        assert out.endswith("media/fa4faa5b.jpg")
        assert "v1785824093" in out
        assert "tenants/a9f955ac-c4d2-4646-b9b0-68e5118bd0ef" in out

    def test_it_is_conditional_not_unconditional(self):
        # An already-valid square image must come back byte-identical from
        # Cloudinary, which is what `if_` buys. Applying c_fill unconditionally
        # would re-crop assets that post fine today.
        assert "if_ar_lt_0.8" in publishable_url(CLOUDINARY)

    def test_applying_it_twice_changes_nothing(self):
        once = publishable_url(CLOUDINARY)
        assert publishable_url(once) == once
        assert already_normalised(once)


class TestPassThrough:
    def test_a_non_cloudinary_url_is_untouched(self):
        for url in (
            "https://example.com/photo.jpg",
            "https://cdn.shopify.com/x/product.jpg",
            "/api/v1/media/abc123",
        ):
            assert publishable_url(url) == url

    def test_junk_input_never_raises(self):
        # A post going out with the original URL is today's behaviour; a post
        # not going out because this raised would be a regression.
        for junk in (None, "", 5, {}, []):
            assert publishable_url(junk) == junk

    def test_videos_are_left_alone(self):
        # Reels accept far taller shapes than feed images. Cropping a vertical
        # video to 4:5 would break the format that currently works.
        assert publishable_urls([VIDEO]) == [VIDEO]

    def test_is_cloudinary_image_rejects_other_hosts(self):
        assert is_cloudinary_image(CLOUDINARY)
        assert not is_cloudinary_image("https://example.com/image/upload/x.jpg")
        assert not is_cloudinary_image("")


class TestWholePost:
    def test_a_mixed_post_rewrites_only_the_images(self):
        out = publishable_urls([CLOUDINARY, VIDEO, "https://example.com/a.jpg"])
        assert "if_ar_lt_0.8" in out[0]
        assert out[1] == VIDEO
        assert out[2] == "https://example.com/a.jpg"

    def test_order_is_preserved(self):
        # Carousel slide order is the user's explicit choice; reordering here
        # would silently rearrange their post.
        urls = [CLOUDINARY, VIDEO, CLOUDINARY.replace("fa4faa5b", "second")]
        out = publishable_urls(urls)
        assert len(out) == 3
        assert out[1] == VIDEO
        assert "second" in out[2]

    def test_empty_and_none_are_safe(self):
        assert publishable_urls([]) == []
        assert publishable_urls(None) == []
