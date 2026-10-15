"""Engine, session factory and the FastAPI DB dependency."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from byb_gateway.settings import settings


def _engine() -> Engine:
    kwargs = {"pool_pre_ping": True, "future": True}
    if settings.database_url.startswith("sqlite"):
        return create_engine(settings.database_url, connect_args={"check_same_thread": False}, **kwargs)
    return create_engine(settings.database_url, **kwargs)


engine = _engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


def _add_missing_columns() -> None:
    """Bring an existing database up to the current model by adding new columns.

    Postgres volumes outlive code changes, and `create_all` never alters a table it
    already created. This only ever adds nullable columns; renaming or removing a column
    needs a real migration tool, which this project does not have yet.
    """
    from byb_gateway import models

    inspector = inspect(engine)
    for table in models.Base.metadata.tables.values():
        if not inspector.has_table(table.name):
            continue
        existing = {column["name"] for column in inspector.get_columns(table.name)}
        missing = [column for column in table.columns if column.name not in existing]
        if not missing:
            continue
        with engine.begin() as connection:
            for column in missing:
                sql_type = column.type.compile(dialect=engine.dialect)
                connection.exec_driver_sql(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {sql_type}')


def init_db() -> None:
    from byb_gateway import models

    models.Base.metadata.create_all(engine)
    _add_missing_columns()


def get_db() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
