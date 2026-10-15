from typing import Any

PROFILE: dict[str, Any] = {
    "name": "Ektorp 3-seat sofa",
    "category": "sofa",
    "source": "catalog",
    "confidence": 0.72,
    "geometry": {"width_cm": 218, "depth_cm": 95, "height_cm": 85, "clearance_cm": 90},
}


def scan(**overrides) -> dict[str, Any]:
    base = {
        "simulation_id": "cafe1234deadbeef",
        "profile": PROFILE,
        "candidate": None,
        "scan": {"width_m": 4.0, "depth_m": 3.0, "height_m": 2.5, "obstacles": [], "measured": False, "method": "declared"},
    }
    return base | overrides


def test_fit_reports_the_stage_then_hands_on_to_scene(client, transport):
    report = client.post("/v1/fit", json=scan()).json()
    assert report["verdict"] in {"fits", "tight"}
    assert report["room_area_m2"] == 12.0

    stage, handed_on = transport.calls
    assert (stage[0], stage[1]) == ("api-gateway", "/api/v1/internal/progress")
    assert stage[2] == {"simulation_id": "cafe1234deadbeef", "status": "fitting"}
    assert (handed_on[0], handed_on[1]) == ("scene-service", "/v1/render")
    assert handed_on[2]["scan"]["method"] == "declared"
    assert handed_on[2]["fit"]["placements"][0]["centre_x_m"] > 0


def test_the_scanned_room_is_the_room_that_gets_measured(client, transport):
    body = scan(scan={"width_m": 2.0, "depth_m": 1.0, "height_m": 2.5, "obstacles": [], "measured": True, "method": "photo"})
    report = client.post("/v1/fit", json=body).json()
    assert report["verdict"] == "too_large"
    assert report["room_area_m2"] == 2.0
    assert transport.calls[-1][2]["fit"]["verdict"] == "too_large"


def test_photo_obstacles_are_reasons_in_the_report(client):
    ring = [[1.25, 2.15], [2.75, 2.15], [2.75, 2.95], [1.25, 2.95], [1.25, 2.15]]
    body = scan(
        scan={
            "width_m": 4.0,
            "depth_m": 3.0,
            "height_m": 2.5,
            "measured": True,
            "method": "photo",
            "obstacles": [{"label": "object 1 (photo)", "ring": ring, "height_m": 0.6, "source": "photo"}],
        }
    )
    report = client.post("/v1/fit", json=body).json()
    assert report["obstacles"][0]["label"] == "object 1 (photo)"
    assert any("object 1 (photo)" in conflict for conflict in report["conflicts"])


def test_a_missing_profile_fails_the_simulation(client, transport):
    report = client.post("/v1/fit", json=scan(profile=None)).json()
    assert report is None
    assert transport.calls[-1][2]["status"] == "failed"
    assert "no product profile" in transport.calls[-1][2]["error"]


def test_events_route_accepts_a_cloud_envelope(client, transport):
    envelope = {"id": "1", "type": "com.dapr.event.sent", "data": scan()}
    assert client.post("/events", json=envelope).json() == {"status": "SUCCESS"}
    assert transport.calls[-1][:2] == ("scene-service", "/v1/render")


def test_dapr_handshake_admits_the_scanned_topic(client):
    assert client.get("/dapr/subscribe").json() == [
        {"pubsubname": "byb-pubsub", "topic": "simulation.room_scanned", "route": "/events"}
    ]
