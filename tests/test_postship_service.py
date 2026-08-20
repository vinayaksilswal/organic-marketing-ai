import pytest
from services.postship_service import generate_postship_bundle


@pytest.mark.asyncio
async def test_generate_postship_bundle_from_text():
    input_text = "Fixed the render race, shipped writing styles today."
    bundle = await generate_postship_bundle(
        input_text=input_text,
        business_name="BuildLog",
        industry="DevTools SaaS",
    )

    assert "x_post" in bundle
    assert "linkedin_post" in bundle
    assert "reddit_post" in bundle

    # Check X post structure
    x = bundle["x_post"]
    assert "content" in x
    assert len(x["content"]) > 10
    assert "metrics_estimate" in x

    # Check LinkedIn post structure
    li = bundle["linkedin_post"]
    assert "content" in li
    assert len(li["content"]) > 15
    assert "metrics_estimate" in li

    # Check Reddit post structure
    rd = bundle["reddit_post"]
    assert "title" in rd
    assert "body" in rd
    assert "subreddit" in rd
    assert rd["subreddit"].startswith("r/")


@pytest.mark.asyncio
async def test_generate_postship_bundle_from_url():
    bundle = await generate_postship_bundle(
        input_text="Check out our new AI organic social marketing platform",
        url="https://github.com",
        business_name="Organiflo",
        industry="Marketing AI",
    )

    assert bundle["x_post"]["content"] is not None
    assert bundle["linkedin_post"]["content"] is not None
    assert bundle["reddit_post"]["title"] is not None
