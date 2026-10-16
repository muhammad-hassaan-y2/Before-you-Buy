import cv2

MEASURED = {
    "simulation_id": "sim-000001",
    "room_width_m": 4.0,
    "room_depth_m": 3.0,
    "room_height_m": 2.4,
    "image_key": None,
    "profile": {
        "name": "Malsjelvi dining table",
        "category": "table",
        "geometry": {"width_cm": 152, "depth_cm": 94, "height_cm": 75, "clearance_cm": 75},
    },
}


def test_scan_without_a_photo_passes_the_declared_room_through(client, transport):
    body = client.post("/v1/scan", json=MEASURED).json()
    assert (body["width_m"], body["depth_m"], body["measured"], body["method"]) == (4.0, 3.0, False, "declared")

    stage, hop = transport.calls
    assert (stage[0], stage[1]) == ("api-gateway", "/api/v1/internal/progress")
    assert stage[2] == {"simulation_id": "sim-000001", "status": "scanning"}
    assert (hop[0], hop[1]) == ("geometry-service", "/v1/fit")
    assert hop[2]["scan"]["width_m"] == 4.0
    assert hop[2]["profile"]["name"] == "Malsjelvi dining table"
    assert hop[2]["candidate"] is None


def test_missing_upload_does_not_break_the_chain(client, uploads, transport):
    client.post("/v1/scan", json={**MEASURED, "image_key": "room/does-not-exist.jpg"})
    assert transport.calls[-1][2]["scan"]["method"] == "declared"


def test_photo_dimensions_reach_geometry(client, uploads, transport, draw_room):
    assert cv2.imwrite(str(uploads / "room.png"), draw_room())
    body = client.post("/v1/scan", json={**MEASURED, "image_key": "uploads/room.png"}).json()
    assert body["measured"] and body["method"] == "photo"
    assert transport.calls[-1][2]["scan"] == body


def test_events_route_forwards_and_reports_success(client, transport):
    envelope = {"id": "1", "type": "com.dapr.event.sent", "data": MEASURED}
    assert client.post("/events", json=envelope).json() == {"status": "SUCCESS"}
    assert transport.calls[-1][1] == "/v1/fit"


def test_dapr_handshake_admits_the_measured_topic_only(client):
    assert client.get("/dapr/subscribe").json() == [
        {"pubsubname": "byb-pubsub", "topic": "simulation.measured", "route": "/events"}
    ]


def test_health_reports_the_transport(client):
    body = client.get("/healthz").json()
    assert body["service"] == "vision-service"
    assert body["transport"] == "http"
