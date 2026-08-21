"""TikTok is out of the product.

It is banned in India, which is where this platform is sold and where every
connected account is run from. A publishing path nobody can legally use is not
a dormant feature, it is a promise the interface makes and cannot keep -- and
"Send to TikTok Drafts" sat in the scheduler as a publishing mode a customer
could select.

The review queue behind that mode was a real feature and it stayed. Only the
branding went: holding a post for a one-tap sign-off is useful regardless of
which platform invented the idea.

This test exists because the removal touched eleven files, and a platform name
is exactly the kind of thing that returns in a copied block.
"""

import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent

SEARCH_DIRS = [
    ROOT / "services",
    ROOT / "routers",
    ROOT / "frontend" / "src",
]
SEARCH_FILES = [ROOT / "worker.py"]


def _sources():
    for d in SEARCH_DIRS:
        for f in d.rglob("*"):
            if f.suffix in (".py", ".jsx", ".js") and "node_modules" not in f.parts:
                yield f
    for f in SEARCH_FILES:
        if f.exists():
            yield f


def test_tiktok_is_not_referenced_anywhere_shipped():
    hits = []
    for f in _sources():
        text = f.read_text(encoding="utf-8", errors="ignore")
        for i, line in enumerate(text.split("\n"), 1):
            if "tiktok" in line.lower():
                hits.append(f"{f.relative_to(ROOT)}:{i}")
    assert not hits, (
        "TikTok is banned where this product is sold, so it must not appear in "
        "shipped code or copy:\n  " + "\n  ".join(hits)
    )


def test_the_service_module_is_gone():
    assert not (ROOT / "services" / "tiktok_service.py").exists()


def test_the_review_queue_survived_the_removal():
    """DRAFT_REVIEW was the useful half of that publishing mode. Holding a post
    for a one-tap sign-off is worth keeping whoever invented it."""
    marketing = (ROOT / "routers" / "marketing.py").read_text(encoding="utf-8")
    assert "DRAFT_REVIEW" in marketing

    scheduler = (ROOT / "frontend" / "src" / "pages" / "dashboard" / "SocialScheduler.jsx").read_text(encoding="utf-8")
    assert "DRAFT_REVIEW" in scheduler
    assert "Review Queue" in scheduler, "the mode lost its label along with its branding"


def test_the_worker_no_longer_imports_a_deleted_module():
    """A stale import of a deleted module is an ImportError at startup, which
    takes the whole worker with it."""
    worker = (ROOT / "worker.py").read_text(encoding="utf-8")
    assert "tiktok_service" not in worker
