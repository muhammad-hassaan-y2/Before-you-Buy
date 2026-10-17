"""The shelf: a count derived from the SKU, and the only two things allowed to move it.

A storefront that shows stock has to be able to say where the number came from. These tests hold
that line - the count is reproducible, a claim is what changes it, one claim per key no matter how
often it is retried, and a bag the shop cannot supply is refused by the shelf rather than shipped
short.
"""

from byb_catalog import stock
from byb_catalog.skus import CATALOG

# Parcel freight and a shallow shelf depth, so a claim of a few units always has room to be tested.
SKU = "CHR-104"


def test_every_sku_has_a_shelf_row(client):
    rows = client.get("/api/v1/stock").json()
    assert {row["sku"] for row in rows} == {item.sku for item in CATALOG}
    assert all(row["available"] == max(row["on_hand"] - row["reserved"], 0) for row in rows)
    assert all(row["state"] in {"in_stock", "low", "backorder", "made_to_order"} for row in rows)


def test_a_count_is_the_skus_own_and_not_a_draw():
    item = next(row for row in CATALOG if row.sku == SKU)
    assert stock.on_hand_for(item) == stock.on_hand_for(item), "same SKU in, same count out"
    assert stock.stock_row(item)["basis"], "the storefront has to be able to say where a count came from"


def test_a_claim_moves_the_shelf_and_a_retry_of_the_same_key_moves_it_no_further(client):
    before = client.get(f"/api/v1/stock/{SKU}").json()
    key = "order:stock-test"
    body = {"key": key, "lines": [{"sku": SKU, "qty": 2}], "reason": "an order draft"}

    first = client.post("/api/v1/stock/claim", json=body)
    again = client.post("/api/v1/stock/claim", json=body)
    assert first.status_code == again.status_code == 200
    assert again.json()["at"] == first.json()["at"], "a retried claim is the same claim, not two"

    after = client.get(f"/api/v1/stock/{SKU}").json()
    assert after["reserved"] == before["reserved"] + 2
    assert after["available"] == before["available"] - 2

    assert client.post("/api/v1/stock/release", json={"key": key}).json()["released"] is True
    assert client.get(f"/api/v1/stock/{SKU}").json()["available"] == before["available"]


def test_the_shelf_refuses_more_than_it_has_rather_than_selling_short(client):
    on_hand = client.get(f"/api/v1/stock/{SKU}").json()["on_hand"]
    response = client.post(
        "/api/v1/stock/claim",
        json={"key": "order:greedy", "lines": [{"sku": SKU, "qty": on_hand + 1}], "reason": "overshoot"},
    )
    assert response.status_code == 409
    assert SKU in response.json()["detail"]
    assert client.get(f"/api/v1/stock/{SKU}").json()["reserved"] == 0, "a refused claim leaves nothing held"


def test_one_short_line_refuses_the_whole_claim(client):
    other = next(row.sku for row in CATALOG if row.sku != SKU)
    response = client.post(
        "/api/v1/stock/claim",
        json={"key": "order:mixed", "lines": [{"sku": SKU, "qty": 1}, {"sku": other, "qty": 9_999}], "reason": "a bag"},
    )
    assert response.status_code == 409
    assert client.get(f"/api/v1/stock/{SKU}").json()["reserved"] == 0


def test_the_shop_can_read_its_own_traffic_back(client):
    client.post("/api/v1/stock/claim", json={"key": "hold:feed", "lines": [{"sku": SKU, "qty": 1}], "reason": "a hold"})
    events = client.get("/api/v1/stock/events").json()
    assert events[0]["action"] == "claimed" and events[0]["key"] == "hold:feed"
    assert events[0]["at"] >= events[-1]["at"], "newest first"
    client.post("/api/v1/stock/release", json={"key": "hold:feed"})


def test_an_unknown_sku_is_answered_with_a_404(client):
    assert client.get("/api/v1/stock/NOPE-999").status_code == 404
    assert client.post("/api/v1/stock/claim", json={"key": "order:x", "lines": [{"sku": "NOPE-999", "qty": 1}]}).status_code == 404
    assert client.post("/api/v1/stock/claim", json={"lines": []}).status_code == 422


def test_a_made_to_order_piece_says_so_instead_of_claiming_a_zero():
    slow = next(item for item in CATALOG if stock.lead_days(item) >= stock.MADE_TO_ORDER_DAYS)
    row = stock.stock_row(slow)
    assert row["on_hand"] == 0 and row["state"] == "made_to_order"
    assert row["next_lot_in_days"] == row["lead_days"]
