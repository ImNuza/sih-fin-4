"""Startup brings a tariff saved by an older release up to date, once, and keeps the desk's choices.

tests/data/tariff_before_yearly_price.json is the default tariff of the release before the
yearly price (main at a106ec9), which is what the hosted site has saved.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import insert, select

from api import store
from api.main import DEFAULT_TARIFF_PATH, bring_up_to_date
from api.models import Tariff

BEFORE_YEARLY_PRICE = Path(__file__).parent / "data" / "tariff_before_yearly_price.json"


def saved_engine(tmp_path, body: dict):
    engine = store.connect(f"sqlite:///{tmp_path / 'tariff.db'}")
    with engine.begin() as db:
        db.execute(insert(store.tariff_versions).values(
            saved_at=datetime.now(UTC), saved_by="default", body=body,
        ))
    return engine


def default() -> Tariff:
    return Tariff.model_validate_json(DEFAULT_TARIFF_PATH.read_text())


def versions(engine) -> list[str]:
    with engine.connect() as db:
        rows = db.execute(select(store.tariff_versions).order_by(store.tariff_versions.c.version))
        return [row.saved_by for row in rows]


def start(engine) -> Tariff:
    bring_up_to_date(engine, store.latest(engine), default())
    return store.latest(engine).tariff


def test_the_hosted_tariff_gets_the_limits_holds_and_haze_payout_in_one_version(tmp_path):
    engine = saved_engine(tmp_path, json.loads(BEFORE_YEARLY_PRICE.read_text()))
    tariff = start(engine)
    assert [tier.max_paid_days_per_year for tier in tariff.tiers] == [35, 35, 40, 45]
    assert all(tier.premium_shares is not None for tier in tariff.tiers)
    heat = next(hazard for hazard in tariff.hazards if hazard.key == "heat")
    assert heat.stations_on_hold == ["S142", "S128"]
    assert tariff.haze_bonus == default().haze_bonus
    assert versions(engine) == [
        "default", "default: yearly limits, stations on hold, severe haze payout",
    ]


def test_a_missing_product_does_not_stop_the_later_steps(tmp_path):
    body = json.loads(BEFORE_YEARLY_PRICE.read_text())
    body["products"] = body["products"][:-1]
    engine = saved_engine(tmp_path, body)
    tariff = start(engine)
    assert len(tariff.products) == len(default().products)
    assert [tier.max_paid_days_per_year for tier in tariff.tiers] == [35, 35, 40, 45]
    heat = next(hazard for hazard in tariff.hazards if hazard.key == "heat")
    assert heat.stations_on_hold == ["S142", "S128"]
    assert tariff.haze_bonus is not None


def test_a_second_start_saves_nothing(tmp_path):
    engine = saved_engine(tmp_path, json.loads(BEFORE_YEARLY_PRICE.read_text()))
    start(engine)
    start(engine)
    assert len(versions(engine)) == 2


def test_a_desk_that_took_the_haze_payout_off_sale_keeps_it_off(tmp_path):
    body = default().model_dump(mode="json")
    body["haze_bonus"] = None
    engine = saved_engine(tmp_path, body)
    assert start(engine).haze_bonus is None
    assert versions(engine) == ["default"]


def test_a_desk_that_cleared_the_stations_on_hold_keeps_them_cleared(tmp_path):
    body = default().model_dump(mode="json")
    for hazard in body["hazards"]:
        hazard["stations_on_hold"] = []
    engine = saved_engine(tmp_path, body)
    heat = next(hazard for hazard in start(engine).hazards if hazard.key == "heat")
    assert heat.stations_on_hold == []
