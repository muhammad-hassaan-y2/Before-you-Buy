from byb_common.contracts import (
    FitPlacement,
    FitReport,
    Obstacle,
    ProductGeometry,
    ProductProfile,
    SimulationCompleted,
)

PROFILE = ProductProfile(
    name="Linen three-seater sofa",
    category="sofa",
    geometry=ProductGeometry(width_cm=220, depth_cm=95, height_cm=85, clearance_cm=60),
)


def test_health(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["database"] == "up"


def test_needs_link_or_file(client):
    response = client.post("/api/v1/simulations", data={"room_width_m": 4, "room_depth_m": 3, "room_height_m": 2.4})
    assert response.status_code == 400


def test_rejects_impossible_room(client):
    response = client.post("/api/v1/simulations", data={"link": "https://example.com/sofa", "room_width_m": 400})
    assert response.status_code == 422


def test_dispatches_then_records_result(client, dispatcher):
    accepted = client.post(
        "/api/v1/simulations",
        data={"link": "https://example.com/sofa", "room_width_m": 4.5, "room_depth_m": 3.5, "room_height_m": 2.5},
    )
    assert accepted.status_code == 202
    simulation_id = accepted.json()["id"]
    assert accepted.json()["status"] == "cataloguing"
    assert dispatcher.messages[0].product_link == "https://example.com/sofa"

    detail = client.get(f"/api/v1/simulations/{simulation_id}")
    assert detail.json()["status"] == "cataloguing"
    assert detail.json()["fit_report"] is None

    fit = FitReport(
        room_area_m2=15.75,
        usable_area_m2=15.4,
        placements=[FitPlacement(label="centred on the back wall", ring=[(0, 0), (2.2, 0), (2.2, 0.95)], area_m2=4.5, footprint_m2=2.09, fits=True)],
        conflicts=[],
        coverage_pct=13.6,
        verdict="fits",
    )
    callback = client.post(
        "/api/v1/internal/results",
        json=SimulationCompleted(simulation_id=simulation_id, status="completed", profile=PROFILE, fit=fit).model_dump(),
        headers={"x-byb-token": "wrong"},
    )
    assert callback.status_code == 403

    callback = client.post(
        "/api/v1/internal/results",
        json=SimulationCompleted(simulation_id=simulation_id, status="completed", profile=PROFILE, fit=fit).model_dump(),
        headers={"x-byb-token": "test-token"},
    )
    assert callback.status_code == 204

    finished = client.get(f"/api/v1/simulations/{simulation_id}").json()
    assert finished["status"] == "completed"
    assert finished["fit_report"]["verdict"] == "fits"
    assert finished["product_profile"]["name"] == "Linen three-seater sofa"
    assert len(client.get("/api/v1/simulations").json()) == 1


def test_unknown_simulation(client):
    assert client.get("/api/v1/simulations/deadbeef").status_code == 404


def test_worker_that_beats_the_response_is_not_reverted(client, dispatcher):
    """The direct-HTTP dispatch awaits the whole chain, so a callback can land
    while POST /simulations is still suspended. That callback must win."""
    from byb_gateway import database, models

    async def finish_fast(message):
        with database.SessionLocal() as session:
            row = session.get(models.Simulation, message.simulation_id)
            row.status = "completed"
            session.commit()

    dispatcher.start = finish_fast
    accepted = client.post(
        "/api/v1/simulations",
        data={"link": "https://example.com/sofa", "room_width_m": 4.5, "room_depth_m": 3.5, "room_height_m": 2.5},
    )
    assert accepted.status_code == 202
    assert client.get(f"/api/v1/simulations/{accepted.json()['id']}").json()["status"] == "completed"


def queue(client, **form) -> str:
    response = client.post(
        "/api/v1/simulations",
        data={"link": "https://example.com/sofa", "room_width_m": 4.0, "room_depth_m": 3.5, "room_height_m": 2.4, **form},
    )
    return response.json()["id"]


def test_workers_advance_the_stage(client):
    simulation_id = queue(client)
    for stage in ("enriching", "measuring", "fitting"):
        reported = client.post(
            "/api/v1/internal/progress",
            json={"simulation_id": simulation_id, "status": stage},
            headers={"x-byb-token": "test-token"},
        )
        assert reported.status_code == 204
        assert client.get(f"/api/v1/simulations/{simulation_id}").json()["status"] == stage


def test_progress_never_resurrects_a_settled_simulation(client):
    simulation_id = queue(client)
    client.post(
        "/api/v1/internal/progress",
        json={"simulation_id": simulation_id, "status": "completed"},
        headers={"x-byb-token": "test-token"},
    )
    client.post(
        "/api/v1/internal/progress",
        json={"simulation_id": simulation_id, "status": "enriching"},
        headers={"x-byb-token": "test-token"},
    )
    assert client.get(f"/api/v1/simulations/{simulation_id}").json()["status"] == "completed"


def test_progress_requires_the_internal_token(client):
    simulation_id = queue(client)
    refused = client.post(
        "/api/v1/internal/progress", json={"simulation_id": simulation_id, "status": "fitting"}
    )
    assert refused.status_code == 403


def test_progress_rejects_unknown_simulation(client):
    response = client.post(
        "/api/v1/internal/progress",
        json={"simulation_id": "deadbeefcafe1234", "status": "fitting"},
        headers={"x-byb-token": "test-token"},
    )
    assert response.status_code == 404


def test_candidate_is_persisted_alongside_the_profile(client):
    from byb_common.contracts import CatalogCandidate

    simulation_id = queue(client)
    candidate = CatalogCandidate(
        sku="BCK-101",
        name="Billy bookcase",
        brand="Billy",
        category="bookcase",
        geometry=ProductGeometry(width_cm=80, depth_cm=28, height_cm=202),
        score=0.9,
    )
    fit = FitReport(room_area_m2=14.0, usable_area_m2=13.6, placements=[], conflicts=[], coverage_pct=0.0, verdict="fits")
    client.post(
        "/api/v1/internal/results",
        json=SimulationCompleted(
            simulation_id=simulation_id, status="completed", profile=PROFILE, candidate=candidate, fit=fit
        ).model_dump(),
        headers={"x-byb-token": "test-token"},
    )

    detail = client.get(f"/api/v1/simulations/{simulation_id}").json()
    assert detail["catalog_candidate"]["sku"] == "BCK-101"
    assert detail["catalog_candidate"]["geometry"]["height_cm"] == 202


def test_room_scan_survives_a_later_callback_without_one(client):
    from byb_common.contracts import RoomScan

    simulation_id = queue(client)
    scan = RoomScan(
        width_m=3.72,
        depth_m=2.95,
        height_m=2.4,
        obstacles=[Obstacle(label="object 1 (photo)", ring=[(0.2, 0.2), (1.2, 0.2), (1.2, 0.9), (0.2, 0.9), (0.2, 0.2)])],
        measured=True,
        method="photo",
        confidence=0.61,
    )
    fit = FitReport(room_area_m2=11.0, usable_area_m2=10.0, placements=[], conflicts=[], coverage_pct=12.0, verdict="fits")
    headers = {"x-byb-token": "test-token"}

    client.post(
        "/api/v1/internal/results",
        json=SimulationCompleted(simulation_id=simulation_id, status="completed", profile=PROFILE, scan=scan, fit=fit).model_dump(),
        headers=headers,
    )
    detail = client.get(f"/api/v1/simulations/{simulation_id}").json()
    assert detail["room_scan"]["method"] == "photo"
    assert detail["room_scan"]["obstacles"][0]["label"] == "object 1 (photo)"

    # A worker reporting only a profile (a failed run, say) must not erase the scan.
    client.post(
        "/api/v1/internal/results",
        json=SimulationCompleted(simulation_id=simulation_id, status="completed", profile=PROFILE).model_dump(),
        headers=headers,
    )
    assert client.get(f"/api/v1/simulations/{simulation_id}").json()["room_scan"]["measured"] is True


class StubResponse:
    def __init__(self, payload, status_code=200):
        self._payload, self.status_code = payload, status_code

    def raise_for_status(self):
        if self.status_code != 200:
            import httpx

            raise httpx.ConnectError("catalog-service is down")

    def json(self):
        return self._payload


class StubHttp:
    def __init__(self, response):
        self._response = response
        self.url = None

    async def get(self, url, headers=None, timeout=None):
        self.url = url
        return self._response


def test_catalog_is_proxied_for_the_browser(client):
    rows = [{"sku": "BCK-101", "name": "Billy bookcase", "category": "bookcase", "geometry": {"width_cm": 80}}]
    client.app.state.http = StubHttp(StubResponse(rows))

    response = client.get("/api/v1/catalog")
    assert response.status_code == 200
    assert response.json()[0]["sku"] == "BCK-101"
    assert response.json()[0]["geometry"]["width_cm"] == 80
    assert client.app.state.http.url.endswith("/api/v1/catalog")


def test_catalog_passthrough_degrades_to_502(client):
    client.app.state.http = StubHttp(StubResponse(None, status_code=500))
    assert client.get("/api/v1/catalog").status_code == 502
