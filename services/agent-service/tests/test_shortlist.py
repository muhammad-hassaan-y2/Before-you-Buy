from byb_agent.shortlist import listing_url, rank, score, to_candidate


def test_a_matching_category_outranks_a_stray_word(rows):
    ranked = rank(rows, category="sofa", price_band=None, must_haves=[], limit=5)
    assert all(row["category"] == "sofa" for row, _ in ranked)
    assert ranked[0][0]["sku"] in {"SOF-002", "SOF-001"}


def test_the_roomie_option_is_tested_first(rows):
    """A thing that can plausibly fit should be simulated before a thing that cannot."""
    ranked = rank(rows, category="sofa", price_band=None, must_haves=[], limit=3, room=(2.0, 2.0))
    assert ranked[0][0]["sku"] == "SOF-002"


def test_the_price_band_acts_as_a_filter_not_a_wall(rows):
    ranked = rank(rows, category="sofa", price_band="$$", must_haves=[], limit=3)
    assert any(row["price_band"] == "$$" for row, _ in ranked)


def test_must_haves_nudge_the_order(rows):
    with_linens = score(rows[0], "sofa", None, ["linen"])
    without = score(rows[2], "sofa", None, ["linen"])
    assert with_linens > without


def test_a_wider_search_never_invents_a_product(rows):
    ranked = rank(rows, category="wardrobe", price_band=None, must_haves=[], limit=5)
    assert ranked == [] or all(row["category"] == "wardrobe" for row, _ in ranked)


def test_the_listing_url_carries_the_words_the_catalog_reads():
    row = {"sku": "SOF-001", "name": "Linen three-seater sofa", "category": "sofa", "brand": "linen", "material": "linen"}
    link = listing_url(row)
    assert link.startswith("https://shop.example.com/p/")
    assert "sofa" in link and "linen" in link


def test_a_candidate_is_a_contract_not_a_dict(rows):
    candidate = to_candidate(rows[0], 0.8)
    assert candidate.sku == "SOF-001"
    assert candidate.geometry.width_cm == 220
    assert candidate.score == 0.8
    assert candidate.parts, "the 3D scene needs parts, not one box"
