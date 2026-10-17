"""The dropship terms a storefront quotes, and the listing link they hang on."""

from byb_catalog.commerce import (
    BAND_RETAIL_EUR,
    FREIGHT_VOLUME_M3,
    SUPPLIERS,
    lead_days,
    product_url,
    retail_eur,
    supplier_for,
    terms_for,
    volume_m3,
)
from byb_catalog.matching import candidate_for
from byb_catalog.skus import CATALOG


def test_every_product_url_resolves_back_to_its_own_sku():
    """A product page starts a simulation by pasting its own listing link.

    That only works if the catalog reads the link as the SKU it came from, so this is checked for
    every shelf rather than for one tidy example - the near neighbours (two Kivik sofas, two Pax
    wardrobes) are exactly where a slug would otherwise blur.
    """
    for item in CATALOG:
        url = product_url(item)
        matched = candidate_for(url)
        assert matched is not None, f"nothing matched {url}"
        assert matched.sku == item.sku, f"{url} read as {matched.sku}, not {item.sku}"


def test_retail_sits_in_its_band_and_moves_with_the_box():
    for item in CATALOG:
        base = BAND_RETAIL_EUR[item.price_band]
        assert base * 0.7 <= retail_eur(item) <= base * 1.5
        assert str(int(retail_eur(item))).endswith("9"), f"{item.sku} lists an odd price: {retail_eur(item)}"


def test_the_shop_keeps_a_margin_and_says_which_one():
    for item in CATALOG:
        terms = terms_for(item)
        assert 0 < terms["cost_eur"] < terms["retail_eur"], item.sku
        assert terms["margin_eur"] == round(terms["retail_eur"] - terms["cost_eur"], 2)
        assert 20 <= terms["margin_pct"] <= 70
        assert terms["product_url"] == product_url(item)
        assert terms["basis"], "a derived number has to say it was derived"


def test_a_bigger_box_leads_longer_than_a_parcel():
    """Freight is not decoration: the pallet threshold is what adds the days."""
    small = next(item for item in CATALOG if volume_m3(item) < FREIGHT_VOLUME_M3)
    big = next(item for item in CATALOG if volume_m3(item) >= FREIGHT_VOLUME_M3)
    assert terms_for(small)["freight"] == "parcel"
    assert terms_for(big)["freight"] == "pallet"
    assert lead_days(big) >= lead_days(small)


def test_the_same_sku_always_shows_the_same_workshop():
    names = {name for name, _ in SUPPLIERS}
    for item in CATALOG:
        assert supplier_for(item) == supplier_for(item)
        assert supplier_for(item)["name"] in names


def test_browse_rows_carry_their_terms(client):
    rows = client.get("/api/v1/catalog").json()
    assert rows, "the storefront has nothing to show without a catalog"
    for row in rows:
        assert {"commerce", "geometry", "price_band"} <= set(row)
        assert row["commerce"]["retail_eur"] > 0


def test_one_shelf_answers_and_an_unknown_one_does_not(client):
    sku = CATALOG[0].sku
    body = client.get(f"/api/v1/catalog/{sku}").json()
    assert body["sku"] == sku and body["commerce"]["product_url"].startswith("https://")
    assert client.get("/api/v1/catalog/NOPE-999").status_code == 404
