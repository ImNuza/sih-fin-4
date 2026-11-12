"""Saved tariffs. Every save adds a version, so each change keeps its time and author.

DATABASE_URL picks the database: Postgres on the server, a SQLite file on a laptop.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Engine,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    insert,
    select,
)

from api.models import SavedTariff, Tariff

metadata = MetaData()
tariff_versions = Table(
    "tariff_versions",
    metadata,
    Column("version", Integer, primary_key=True, autoincrement=True),
    Column("saved_at", DateTime(timezone=True), nullable=False),
    Column("saved_by", String, nullable=False),
    Column("body", JSON, nullable=False),
)


def connect(database_url: str) -> Engine:
    engine = create_engine(database_url, pool_pre_ping=True)
    metadata.create_all(engine)
    return engine


def latest(engine: Engine) -> SavedTariff | None:
    newest_first = tariff_versions.c.version.desc()
    with engine.connect() as db:
        row = db.execute(select(tariff_versions).order_by(newest_first).limit(1)).first()
    if row is None:
        return None
    # SQLite drops the time zone. Every time is saved in UTC, so put it back.
    saved_at = row.saved_at if row.saved_at.tzinfo else row.saved_at.replace(tzinfo=UTC)
    return SavedTariff(
        version=row.version,
        saved_at=saved_at,
        saved_by=row.saved_by,
        tariff=Tariff.model_validate(row.body),
    )


def save(engine: Engine, tariff: Tariff, saved_by: str) -> SavedTariff:
    saved_at = datetime.now(UTC)
    new_row = insert(tariff_versions).values(
        saved_at=saved_at, saved_by=saved_by, body=tariff.model_dump(mode="json")
    )
    with engine.begin() as db:
        version = db.execute(new_row.returning(tariff_versions.c.version)).scalar_one()
    return SavedTariff(version=version, saved_at=saved_at, saved_by=saved_by, tariff=tariff)
