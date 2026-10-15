from byb_catalog.matching import best_match, candidate_for, slug_text, tokenize
from byb_catalog.settings import settings
from byb_catalog.skus import CATALOG, find


def test_catalog_is_internally_consistent():
    assert len({item.sku for item in CATALOG}) == len(CATALOG)
    for item in CATALOG:
        assert item.width_cm > 0 and item.depth_cm > 0 and item.height_cm > 0
        assert item.clearance_cm >= 0
        assert item.tokens()


def test_link_slug_is_readable():
    link = "https://www.ikea.com/gb/p/billy-bookcase-white-b652fa01/"
    assert set(slug_text(link).split()) >= {"billy", "bookcase", "white", "b652fa01"}
    assert "ikea" not in slug_text(link), "the host is not part of the product name"


def test_billy_link_resolves_to_the_bookcase():
    candidate = candidate_for("https://www.ikea.com/gb/p/billy-bookcase-white-b652fa01/", None)
    assert candidate is not None
    assert candidate.sku == "BCK-101"
    assert candidate.geometry.width_cm == 80
    assert candidate.score > settings.min_match_score


def test_notes_alone_can_pick_a_sectional():
    candidate = candidate_for(None, "corner sofa with chaise, needs to breathe")
    assert candidate is not None
    assert candidate.category == "sectional"


def test_three_seater_linen_sofa_prefers_the_linen_sku():
    candidate = candidate_for(None, "three seater linen sofa")
    assert candidate is not None
    assert candidate.category == "sofa"
    assert 200 <= candidate.geometry.width_cm <= 230


def test_king_bed_is_the_wide_one():
    candidate = candidate_for("https://example.com/p/tarva-king-bed-oak", None)
    assert candidate is not None
    assert candidate.sku == "BED-102"


def test_unrelated_text_reports_no_match():
    assert best_match("zzz qqq wvvv") is None
    assert candidate_for("https://example.com/", "asdfgh") is None


def test_every_match_carries_parts_for_the_engine():
    candidate = candidate_for(None, "oak extending dining table")
    assert candidate is not None
    assert candidate.parts, "the 3D engine needs at least one box"
    assert all(part.size_cm[0] > 0 for part in candidate.parts)


def test_tokenizer_drops_url_noise():
    words = tokenize("https://x.com/p/sofa-4-seat")
    assert "sofa" in words and "seat" in words
    assert "4" not in words and "p" not in words and "com" not in words


def test_find_is_case_insensitive():
    assert find("bck-101") is not None
    assert find("nope") is None
