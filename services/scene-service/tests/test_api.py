def test_render_reports_the_stage_then_the_result(client, transport, fitted):
    scene = client.post("/v1/render", json=fitted).json()
    assert scene["room_width_m"] == 4.0
    assert len(scene["placements"]) == 3

    stage, result = transport.calls
    assert (stage[0], stage[1]) == ("api-gateway", "/api/v1/internal/progress")
    assert stage[2] == {"simulation_id": "cafe1234deadbeef", "status": "rendering"}
    assert (result[0], result[1]) == ("api-gateway", "/api/v1/internal/results")
    assert result[2]["status"] == "completed"


def test_the_final_callback_closes_the_simulation_with_a_model(client, transport, fitted):
    client.post("/v1/render", json=fitted)
    payload = transport.calls[-1][2]
    assert payload["scene"]["cameras"][0]["label"] == "overview"
    assert payload["gltf"]["asset"]["version"] == "2.0"
    assert payload["fit"]["verdict"] == "fits"
    assert payload["scan"]["method"] == "photo"
    assert payload["profile"]["name"] == "Ektorp 3-seat sofa"


def test_the_catalog_candidate_survives_the_last_hop(client, transport, fitted):
    fitted["candidate"] = {
        "sku": "EK-3S-01",
        "name": "Ektorp 3-seat sofa",
        "brand": "IKEA",
        "category": "sofa",
        "geometry": {"width_cm": 218, "depth_cm": 95, "height_cm": 85, "clearance_cm": 90},
        "score": 0.81,
        "source": "catalog",
    }
    client.post("/v1/render", json=fitted)
    assert transport.calls[-1][2]["candidate"]["sku"] == "EK-3S-01"


def test_a_message_without_a_fit_report_fails_instead_of_stalling(client, transport, fitted):
    scene = client.post("/v1/render", json=fitted | {"fit": None}).json()
    assert scene["status"] == "failed"
    assert "fit report" in scene["error"]
    assert transport.calls[-1][2]["status"] == "failed"


def test_events_route_accepts_a_cloud_envelope(client, transport, fitted):
    envelope = {"id": "1", "type": "com.dapr.event.sent", "data": fitted}
    assert client.post("/events", json=envelope).json() == {"status": "SUCCESS"}
    assert transport.calls[-1][1] == "/api/v1/internal/results"


def test_dapr_handshake_admits_the_fitted_topic(client):
    assert client.get("/dapr/subscribe").json() == [
        {"pubsubname": "byb-pubsub", "topic": "simulation.fitted", "route": "/events"}
    ]


def test_healthz_names_the_transport(client):
    assert client.get("/healthz").json()["transport"] == "http"
