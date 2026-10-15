from byb_common.contracts import FitPlacement, FitReport, ProductGeometry, ProductProfile, SimulationCompleted

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
    assert accepted.json()["status"] == "enriching"
    assert dispatcher.messages[0].product_link == "https://example.com/sofa"

    detail = client.get(f"/api/v1/simulations/{simulation_id}")
    assert detail.json()["status"] == "enriching"
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
