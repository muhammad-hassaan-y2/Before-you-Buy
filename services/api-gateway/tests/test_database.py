from sqlalchemy import inspect

from byb_gateway import database, models


def column_names() -> set[str]:
    return {column["name"] for column in inspect(database.engine).get_columns("simulation_results")}


def test_init_db_adds_a_column_the_old_database_is_missing():
    """A Postgres volume outlives the code that created it, and create_all never ALTERs."""
    with database.engine.begin() as connection:
        connection.exec_driver_sql('ALTER TABLE "simulation_results" DROP COLUMN "catalog_candidate"')
    assert "catalog_candidate" not in column_names()

    database.init_db()
    assert "catalog_candidate" in column_names()


def test_the_added_column_round_trips():
    with database.engine.begin() as connection:
        connection.exec_driver_sql('ALTER TABLE "simulation_results" DROP COLUMN "catalog_candidate"')
    database.init_db()

    with database.SessionLocal() as session:
        simulation = models.Simulation(product_link="https://example.com/billy", room_width_m=4.0)
        session.add(simulation)
        session.commit()
        session.add(
            models.SimulationResult(
                simulation_id=simulation.id,
                catalog_candidate={"sku": "BCK-101", "score": 0.9},
                fit_report={"verdict": "fits"},
            )
        )
        session.commit()

    with database.SessionLocal() as session:
        row = session.query(models.SimulationResult).one()
        assert row.catalog_candidate["sku"] == "BCK-101"
        assert row.fit_report["verdict"] == "fits"


def test_init_db_is_idempotent():
    database.init_db()
    before = column_names()
    database.init_db()
    assert column_names() == before
