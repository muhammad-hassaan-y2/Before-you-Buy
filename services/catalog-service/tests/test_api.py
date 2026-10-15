BILLY = "https://www.ikea.com/gb/p/billy-bookcase-white-b652fa01/"


def request_body(simulation_id: str = "deadbeefcafe1234", link: str | None = BILLY, notes: str | None = None) -> dict:
    return {
        "simulation_id": simulation_id,
        "room_width_m": 4.0,
        "room_depth_m": 3.5,
        "room_height_m": 2.4,
        "product_link": link,
        "shopper_notes": notes,
    }


def test_health_reports_the_catalog_size(client):
    body = client.get("/healthz").json()
    assert body["status"] == "ok"
    assert int(body["skus"]) > 30
    assert body["transport"] == "http"


def test_sidecar_handshake_announces_its_topic(client):
    """daprd drops every event unless the app confirms this subscription."""
    subscriptions = client.get("/dapr/subscribe").json()
    assert subscriptions == [{"pubsubname": "byb-pubsub", "topic": "simulation.requested", "route": "/events"}]


def test_billy_link_becomes_a_candidate_and_moves_on(client, transport):
    body = client.post("/v1/catalogue", json=request_body()).json()

    assert body["candidate"]["sku"] == "BCK-101"
    assert body["candidate"]["geometry"]["width_cm"] == 80
    assert body["simulation_id"] == "deadbeefcafe1234"

    hops = [(app_id, method) for app_id, method, _ in transport.calls]
    assert ("api-gateway", "/api/v1/internal/progress") in hops
    assert ("inference-service", "/v1/enrich") in hops


def test_forwarded_payload_keeps_the_room_and_image(client, transport):
    payload = request_body(notes="narrow shelf for the study")
    payload["image_key"] = "abc-room.png"
    client.post("/v1/catalogue", json=payload)

    _, _, forwarded = transport.calls[-1]
    assert forwarded["room_width_m"] == 4.0
    assert forwarded["image_key"] == "abc-room.png"
    assert forwarded["shopper_notes"] == "narrow shelf for the study"


def test_no_match_still_continues_the_chain(client, transport):
    body = client.post("/v1/catalogue", json=request_body(link="https://example.com/p/qqq-zzz", notes=None)).json()

    assert body["candidate"] is None
    assert transport.calls[-1][:2] == ("inference-service", "/v1/enrich")


def test_cloudevent_envelope_from_dapr(client, transport):
    response = client.post("/events", json={"data": request_body(simulation_id="cafe1234deadbeef")})

    assert response.json() == {"status": "SUCCESS"}
    assert transport.calls[-1][1] == "/v1/enrich"


def test_catalog_browse_exposes_geometry(client):
    rows = client.get("/api/v1/catalog").json()
    assert len(rows) > 30
    assert {"sku", "name", "category", "geometry"} <= set(rows[0])
    assert rows[0]["geometry"]["height_cm"] > 0
