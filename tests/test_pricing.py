"""The year-based price: it is the payout rule replayed, its guardrail and its proof."""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import insert, select

from api import accounts, burn, calculator, place_days, readings, store
from api.main import SINGAPORE, app
from api.models import Tariff
from tests.test_api import (  # noqa: F401  (client is a fixture)
    ADMIN,
    MAP_STATIC,
    MAXWELL,
    SELLER,
    buy_body,
    client,
    default_tariff,
)
from tests.test_underwriting import decide, sign_in_as_insurer

PRODUCTS = [product["key"] for product in default_tariff()["products"]]


def centre_quote(client, centre: str = MAXWELL, product: str = "cooked_food") -> dict:
    return client.post("/api/quote", json={"product": product, "centre": centre}).json()


def tier(quote: dict, key: str = "tier_2") -> dict:
    return next(t for t in quote["tiers"] if t["tier"] == key)


@pytest.mark.parametrize("product", PRODUCTS)
def test_a_tier_offered_never_costs_more_than_half_its_limit(client, product):
    quotes = client.get("/api/map/quotes", params={"product": product}).json()
    for quote in [*quotes["centres"].values(), *quotes["quotes"].values()]:
        for t in quote["tiers"]:
            assert t["offered"] == (
                t["yearly_premium_sgd"] <= 0.5 * t["max_payout_per_year_sgd"]
            )
            assert (t["not_offered_reason"] is None) == t["offered"]
            assert t["expected_paid_days"] <= t["max_payout_per_year_sgd"] / t["daily_payout_sgd"]


def replay_by_the_payout_rule(
    tariff, sites, centre: dict, product_key: str
) -> tuple[list, dict]:
    """Each year's loss-days at a centre, worked out day by day through api/readings.py, plus
    the assumed days of a hazard with no history (a closure order)."""
    table = burn.load_day_table()
    product = calculator.find(tariff.products, product_key, "product")
    factor = calculator.product_factor(product)
    where = readings.history_place(centre["region"], centre["lat"], centre["lng"], sites)
    rule = readings.station_rule(tariff)
    _, fed = place_days.feed_days(table)
    fed_by_hazard = dict(zip(readings.HAZARDS, fed, strict=True))
    hazards = {h.key: h for h in tariff.hazards if h.key in readings.HAZARDS}
    days, losses = sorted(table), defaultdict(list)
    for at, day in enumerate(days):
        found = readings.day_readings_at(table[day], where, rule)
        for key, hazard in hazards.items():
            severity = float(calculator.severities(hazard, np.array([found[key]]))[0])
            fed_today = bool(fed_by_hazard[key][at])
            losses[key].append(calculator.hazard_loss(hazard, severity, factor) * fed_today)
    average = {
        key: calculator.DAYS_PER_YEAR * statistics.fmean(
            loss for loss, fed_today in zip(values, fed_by_hazard[key], strict=True) if fed_today
        )
        for key, values in losses.items()
    }
    by_year: dict[int, list[float]] = defaultdict(list)
    for at, day in enumerate(days):
        day_loss = 1 - np.prod([1 - losses[key][at] for key in hazards])
        waiting = sum(
            average[key] / calculator.DAYS_PER_YEAR
            for key in hazards if not fed_by_hazard[key][at]
        )
        by_year[int(day[:4])].append(day_loss + waiting)
    assumed = sum(
        h.assumed_days_per_year * calculator.hazard_loss(h, h.bands[-1].severity, factor)
        for h in tariff.hazards if h.assumed_days_per_year is not None
    )
    years = [
        sum(days) * calculator.DAYS_PER_YEAR / len(days) + assumed for days in by_year.values()
    ]
    return years, average


def test_the_price_is_the_replay_average_to_the_cent(client):
    tariff = store.latest(client.app.state.db).tariff
    centre = next(c for c in MAP_STATIC["hawker_centres"] if c["name"] == MAXWELL)
    years, average = replay_by_the_payout_rule(
        tariff, client.app.state.sites, centre, "cooked_food"
    )
    shown = centre_quote(client)
    assert years[0] > 0 and len(years) == 13
    for t in shown["tiers"]:
        limit_days = t["max_payout_per_year_sgd"] / t["daily_payout_sgd"]
        expected_sgd = statistics.fmean(min(y, limit_days) for y in years) * t["daily_payout_sgd"]
        steps = {step["key"]: step["amount_sgd"] for step in t["build_up"]}
        assert steps["expected_payouts"] == round(expected_sgd, 2)
    for key, days in average.items():
        assert shown["loss_day_parts"][key] == round(days, 2)
    assert shown["loss_day_parts"]["closure"] == 2


def test_each_tiers_shares_add_up_to_one():
    for row in default_tariff()["tiers"]:
        assert sum(row["premium_shares"].values()) == pytest.approx(1)


def test_a_tiers_shares_must_add_up_to_one():
    body = default_tariff()
    body["tiers"][0]["premium_shares"]["profit"] = 0.2
    with pytest.raises(ValidationError, match="must add up to 1"):
        Tariff.model_validate(body)


def test_the_parts_are_each_tiers_shares_of_the_premium_and_add_up(client):
    shares = {row["key"]: row["premium_shares"] for row in default_tariff()["tiers"]}
    assert shares["tier_2"] == {
        "expected_payouts": 0.60, "reinsurance": 0.06, "management": 0.10,
        "distribution": 0.15, "profit": 0.09,
    }
    for t in centre_quote(client)["tiers"]:
        steps = {step["key"]: step["amount_sgd"] for step in t["build_up"]}
        assert list(steps) == [
            "expected_payouts", "reinsurance", "management", "distribution", "profit", "gst",
        ]
        assert round(sum(steps.values()), 2) == t["yearly_premium_sgd"]
        before_gst = t["yearly_premium_sgd"] / 1.09
        for key, share in shares[t["tier"]].items():
            assert steps[key] == pytest.approx(share * before_gst, abs=0.01)
        # GST takes the cents the five rounded parts leave over.
        assert steps["gst"] == pytest.approx(0.09 * before_gst, abs=0.03)
        assert t["price_per_day_sgd"] == round(t["yearly_premium_sgd"] / 365, 2)
        multiple = t["max_payout_per_year_sgd"] / t["yearly_premium_sgd"]
        assert t["cover_multiple"] == round(multiple, 1)
        assert t["cost_per_sgd_of_daily_cover"] == round(
            t["yearly_premium_sgd"] / t["daily_payout_sgd"], 2
        )


def test_higher_tiers_are_better_value_at_maxwell(client):
    tiers = centre_quote(client)["tiers"]
    multiples = [t["cover_multiple"] for t in tiers]
    paybacks = [t["proof"]["payback_share"] for t in tiers]
    costs = [t["cost_per_sgd_of_daily_cover"] for t in tiers]
    assert multiples == sorted(multiples) and multiples[0] < multiples[-1]
    assert paybacks == sorted(paybacks) and paybacks[0] < paybacks[-1]
    assert costs == sorted(costs, reverse=True)
    assert [t["best_value"] for t in tiers] == [False, False, False, True]


def save_tariff(client, body: dict) -> None:
    saved = client.get("/api/admin/tariff", auth=ADMIN).json()
    change = {"based_on_version": saved["version"], "tariff": body}
    assert client.put("/api/admin/tariff", json=change, auth=ADMIN).status_code == 200


def test_tier_2_keeps_its_price_apart_from_the_longer_limit(client):
    shown = tier(centre_quote(client))
    body = default_tariff()
    for row in body["tiers"][:2]:
        row["max_paid_days_per_year"] = 30
    save_tariff(client, body)
    at_30_days = tier(centre_quote(client))
    for row in body["tiers"]:
        del row["premium_shares"]
    save_tariff(client, body)
    on_the_loads = tier(centre_quote(client))
    assert at_30_days["yearly_premium_sgd"] == on_the_loads["yearly_premium_sgd"]
    assert shown["weekly_premium_sgd"] == 58.05
    assert at_30_days["weekly_premium_sgd"] == 58.05
    assert shown["expected_paid_days"] >= at_30_days["expected_paid_days"]


def test_an_old_tariff_without_premium_shares_prices_on_the_loads_as_before(client):
    body = default_tariff()
    for row in body["tiers"]:
        del row["premium_shares"]
    saved = client.get("/api/admin/tariff", auth=ADMIN).json()
    change = {"based_on_version": saved["version"], "tariff": body}
    assert client.put("/api/admin/tariff", json=change, auth=ADMIN).status_code == 200
    for t in centre_quote(client)["tiers"]:
        steps = {step["key"]: step["amount_sgd"] for step in t["build_up"]}
        risk_cost = steps["expected_payouts"]
        # expected_payouts is rounded to the cent before the loads multiply it by 1.82.
        assert t["yearly_premium_sgd"] == pytest.approx(risk_cost * 1.25 / 0.75 * 1.09, abs=0.02)
        before_gst = t["yearly_premium_sgd"] - steps["gst"]
        shares = {key: amount / before_gst for key, amount in steps.items() if key != "gst"}
        assert shares == pytest.approx({
            "expected_payouts": 0.60, "reinsurance": 0.06, "management": 0.10,
            "distribution": 0.15, "profit": 0.09,
        }, abs=0.0005)


def test_a_2015_haze_year_stays_under_the_limit_at_the_median_centre(client):
    centres = client.get("/api/map/quotes").json()["centres"]
    by_price = sorted(centres.values(), key=lambda quote: tier(quote)["yearly_premium_sgd"])
    median = by_price[len(by_price) // 2]
    for t in median["tiers"]:
        assert 0 < t["proof"]["haze_2015_like_sgd"] < t["max_payout_per_year_sgd"]


def test_no_centre_reads_a_heat_station_on_hold(client):
    centres = client.get("/api/map/quotes").json()["centres"]
    read = {
        station
        for quote in centres.values()
        for risk in quote["local_risks"] if risk["hazard"] == "heat"
        for station in risk["stations"]
    }
    assert read and not read & {"S142", "S128"}


def test_a_centre_whose_nearest_heat_station_is_on_hold_reads_the_next_one(client):
    centre, held_station = centre_nearest_a_held_heat_station(client)
    place = client.app.state.centres_by_name[centre]
    where = readings.history_place(
        place["region"], place["lat"], place["lng"], client.app.state.sites
    )
    rule = readings.station_rule(store.latest(client.app.state.db).tariff)
    next_one = next(s for s, _ in where.heat_stations if s not in rule.heat_on_hold)
    assert readings.stations_used(where, "heat", rule) == [next_one] != [held_station]
    heat = next(r for r in centre_quote(client, centre)["local_risks"] if r["hazard"] == "heat")
    assert heat["stations"] == [next_one]


def test_the_proof_at_maxwell_is_the_burn_replay(client):
    shown = tier(centre_quote(client))
    proof = shown["proof"]
    replay = client.get("/api/map/burn", params={"centre": MAXWELL, "tier": "tier_2"}).json()
    years = replay["years"]
    full = years[:-1]
    assert proof["years_replayed"] == len(years) == 10
    assert proof["years_paid"] == sum(year["paid_sgd"] > 0 for year in years)
    assert proof["payout_days_per_year"] == pytest.approx(
        statistics.fmean(year["payout_days"] for year in full), abs=0.05
    )
    assert proof["typical_year_paid_sgd"] == pytest.approx(
        statistics.median(year["paid_sgd"] for year in full), abs=0.02
    )
    assert proof["paid_2026_sgd"] == pytest.approx(years[-1]["paid_sgd"], abs=0.02)
    assert replay["weekly_premium_sgd"] == shown["weekly_premium_sgd"]
    assert proof["payback_share"] == pytest.approx(0.6 / 1.09, abs=0.001)


def test_the_file_and_an_on_demand_read_give_the_same_replay(client):
    days: place_days.PlaceDays = client.app.state.place_days
    tariff = store.latest(client.app.state.db).tariff
    centre = next(c for c in MAP_STATIC["hawker_centres"] if c["name"] == MAXWELL)
    rule = readings.station_rule(tariff)
    assert rule == days.rule
    from_file = days.replay(rule, centre["region"], centre["lat"], centre["lng"])
    where = readings.history_place(centre["region"], centre["lat"], centre["lng"], days.sites)
    on_demand = place_days.read_place(burn.load_day_table(), days.days, where, rule)
    for at, hazard in enumerate(readings.HAZARDS):
        assert np.array_equal(from_file.readings[hazard], on_demand[at])


def centre_nearest_a_held_heat_station(client) -> tuple[str, str]:
    held = readings.station_rule(store.latest(client.app.state.db).tariff).heat_on_hold
    for centre in MAP_STATIC["hawker_centres"]:
        where = readings.history_place(
            centre["region"], centre["lat"], centre["lng"], client.app.state.sites
        )
        nearest, _ = where.heat_stations[0]
        if nearest in held:
            return centre["name"], nearest
    pytest.fail("No centre has S142 or S128 as its nearest WBGT station")


def test_a_tariff_with_another_station_rule_is_read_on_demand(client):
    centre, held_station = centre_nearest_a_held_heat_station(client)
    before = centre_quote(client, centre)
    saved = client.get("/api/admin/tariff", auth=ADMIN).json()
    heat = next(hazard for hazard in saved["tariff"]["hazards"] if hazard["key"] == "heat")
    heat["stations_on_hold"] = []
    change = {"based_on_version": saved["version"], "tariff": saved["tariff"]}
    assert client.put("/api/admin/tariff", json=change, auth=ADMIN).status_code == 200
    after = centre_quote(client, centre)
    stations = {risk["hazard"]: risk["stations"] for risk in after["local_risks"]}
    assert stations["heat"] == [held_station]
    assert after["loss_day_parts"]["heat"] != before["loss_day_parts"]["heat"]
    assert after["loss_day_parts"]["haze"] == before["loss_day_parts"]["haze"]
    assert client.app.state.place_days.read_on_demand


def hide_every_tier(client) -> None:
    """Set the share so low that no tier is offered anywhere."""
    saved = client.get("/api/admin/tariff", auth=ADMIN).json()
    saved["tariff"]["pricing"]["refer_above_limit_share"] = 0.01
    change = {"based_on_version": saved["version"], "tariff": saved["tariff"]}
    assert client.put("/api/admin/tariff", json=change, auth=ADMIN).status_code == 200


def past_price_referral(client, tier_key: str, product: str = "cooked_food") -> int:
    """A change of tier referred to an underwriter for its price, as the dashboard saved one
    before a tier priced too high for its place was hidden instead. Returns its application id."""
    shown = tier(centre_quote(client, product=product), tier_key)
    applications = accounts.applications
    with client.app.state.db.begin() as db:
        old = db.execute(
            select(applications).order_by(applications.c.id.desc())
        ).mappings().first()
        copy = {key: value for key, value in old.items() if key != "id"}
        copy.update(tier=tier_key, status="referred", payment_method=None, payment_ref=None)
        new_id = db.execute(
            insert(applications).values(**copy).returning(applications.c.id)
        ).scalar_one()
        for table in (accounts.application_details, accounts.application_profile):
            row = db.execute(
                select(table).where(table.c.application_id == old["id"])
            ).mappings().one()
            db.execute(insert(table).values(**{**row, "application_id": new_id}))
        db.execute(insert(accounts.application_referrals).values(
            application_id=new_id, reason=f"{shown['label']} costs a lot here, so an underwriter "
            "must approve it", product=product, weekly_premium_sgd=shown["weekly_premium_sgd"],
        ))
    return new_id


def test_a_tier_not_offered_is_refused_by_the_buy_flow_before_anything_is_saved(client):
    hide_every_tier(client)
    shown = tier(centre_quote(client))
    assert shown["offered"] is False
    assert "Tier 2 is not offered here" in shown["not_offered_reason"]
    response = client.post("/api/buy", json=buy_body())
    assert response.status_code == 409
    assert response.json()["detail"] == shown["not_offered_reason"]
    login = {"email": buy_body()["email"], "password": buy_body()["password"]}
    assert client.post("/api/auth/login", json=login).status_code == 401
    without_cover = buy_body(add_safeday=False, tier=None, payment_method=None)
    assert client.post("/api/buy", json=without_cover).status_code == 200


def test_a_tier_not_offered_is_refused_from_the_dashboard_and_the_cover_stays(client):
    assert client.post("/api/buy", json=buy_body()).status_code == 200
    hide_every_tier(client)
    response = client.post("/api/policies", json={"tier": "tier_4", **SELLER})
    assert response.status_code == 409
    assert response.json()["detail"].startswith("Tier 4 is not offered here.")
    assert "weather history" in response.json()["detail"]
    [policy] = client.get("/api/policies").json()
    assert policy["tier"] == "tier_2"
    client.post("/api/auth/logout")
    sign_in_as_insurer(client)
    assert client.get("/api/insurer/applications").json()["waiting"] == []


def test_a_past_price_referral_still_waits_for_and_follows_the_underwriter(client):
    assert client.post("/api/buy", json=buy_body()).status_code == 200
    referral_id = past_price_referral(client, "tier_4")
    assert client.post("/api/policies", json={"tier": "tier_1", **SELLER}).status_code == 409
    client.post("/api/auth/logout")
    sign_in_as_insurer(client)
    [waiting] = client.get("/api/insurer/applications").json()["waiting"]
    assert waiting["id"] == referral_id and "underwriter" in waiting["referral_reason"]
    approved = decide(client, referral_id, "approve").json()
    assert approved["policy"]["tier"] == "tier_4"
    [policy] = client.get("/api/policies").json()
    assert policy["tier"] == "tier_2" and policy["tier_change"]["tier"] == "tier_4"


TIERS_BEFORE_YEARLY_PRICE = ((10, 20), (15, 40), (20, 70), (30, 100))
SHIPPED_DAILY_AMOUNTS = [35, 195, 630, 1355]


def old_main_tariff() -> dict:
    """The default tariff as it was before the yearly price."""
    body = default_tariff()
    for field in ("distribution_expense_ratio", "refer_above_limit_share"):
        del body["pricing"][field]
    for hazard in body["hazards"]:
        hazard.pop("stations_on_hold", None)
        if hazard["key"] == "closure":
            hazard["assumed_days_per_year"] = 0
    for row, (days, daily) in zip(body["tiers"], TIERS_BEFORE_YEARLY_PRICE, strict=True):
        row["max_paid_days_per_year"] = days
        row["daily_payout_sgd"] = daily
        del row["premium_shares"]
    return body


def start_with(tmp_path, monkeypatch, body: dict) -> None:
    database_url = f"sqlite:///{tmp_path / 'tariff.db'}"
    with store.connect(database_url).begin() as db:
        db.execute(insert(store.tariff_versions).values(
            saved_at=datetime.now(UTC), saved_by="insurer", body=body
        ))
    monkeypatch.setenv("ADMIN_USERNAME", ADMIN[0])
    monkeypatch.setenv("ADMIN_PASSWORD", ADMIN[1])
    monkeypatch.setenv("DATABASE_URL", database_url)


def test_an_old_tariff_with_running_costs_under_15_percent_keeps_the_desks_edits(
    tmp_path, monkeypatch
):
    old = old_main_tariff()
    old["pricing"]["expense_ratio"] = 0.12
    old["tiers"][3]["daily_payout_sgd"] = 150
    start_with(tmp_path, monkeypatch, old)
    with TestClient(app) as client:
        saved = client.get("/api/admin/tariff", auth=ADMIN).json()
    # The shipped tiers' new amounts would pass Tier 4's 150, so every tier is kept.
    assert [t["daily_payout_sgd"] for t in saved["tariff"]["tiers"]] == [20, 40, 70, 150]
    assert saved["tariff"]["pricing"]["expense_ratio"] == 0.12
    assert saved["tariff"]["pricing"]["distribution_expense_ratio"] == 0.12


def test_an_old_tariff_migrates_tier_by_tier_and_hides_an_old_tier_only_at_its_limit(
    tmp_path, monkeypatch
):
    old = old_main_tariff()
    old["tiers"][0]["max_paid_days_per_year"] = 12
    start_with(tmp_path, monkeypatch, old)
    with TestClient(app) as client:
        tiers = client.get("/api/admin/tariff", auth=ADMIN).json()["tariff"]["tiers"]
        centres = client.get("/api/map/quotes").json()["centres"]
    assert [t["max_paid_days_per_year"] for t in tiers] == [12, 45, 45, 45]
    assert [t["daily_payout_sgd"] for t in tiers] == [20, *SHIPPED_DAILY_AMOUNTS[1:]]
    assert tiers[0]["premium_shares"] is None and tiers[1]["premium_shares"] is not None
    # Without premium shares only the floor applies: hidden where the premium reaches the limit.
    old_tier_1 = [tier(quote, "tier_1") for quote in centres.values()]
    assert any(t["yearly_premium_sgd"] > 0.5 * t["max_payout_per_year_sgd"] for t in old_tier_1)
    for t in old_tier_1:
        assert t["offered"] == (t["yearly_premium_sgd"] < t["max_payout_per_year_sgd"])


def test_an_approved_referral_starts_the_product_applied_for(client):
    assert client.post("/api/buy", json=buy_body()).status_code == 200
    shown = tier(centre_quote(client, product="flowers"), "tier_4")
    referral_id = past_price_referral(client, "tier_4", product="flowers")
    client.post("/api/auth/logout")
    sign_in_as_insurer(client)
    policy = decide(client, referral_id, "approve").json()["policy"]
    assert policy["product"] == "flowers"
    assert policy["weekly_premium_sgd"] == shown["weekly_premium_sgd"]


def test_a_declined_change_of_tier_leaves_the_cover_and_buying_open(client):
    assert client.post("/api/buy", json=buy_body()).status_code == 200
    application_id = past_price_referral(client, "tier_4")
    client.post("/api/auth/logout")
    sign_in_as_insurer(client)
    decide(client, application_id, "decline")
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"email": "tan@example.test", "password": "test-pass-123"})
    assert [p["tier"] for p in client.get("/api/policies").json()] == ["tier_2"]
    assert client.post("/api/policies", json={"tier": "tier_1", **SELLER}).status_code == 200


def test_a_change_of_tier_keeps_the_cover_in_force_until_its_waiting_period_ends(client):
    assert client.post("/api/buy", json=buy_body()).status_code == 200
    months_ago = datetime(2026, 6, 1, tzinfo=UTC)
    with client.app.state.db.begin() as db:
        db.execute(accounts.policies.update().values(started_at=months_ago))
    before = client.get("/api/policies").json()[0]
    application_id = past_price_referral(client, "tier_4")
    client.post("/api/auth/logout")
    sign_in_as_insurer(client)
    policy = decide(client, application_id, "approve").json()["policy"]
    assert policy["started_at"][:10] == before["started_at"][:10]
    starts_on = date.fromisoformat(policy["tier_starts_on"])
    assert starts_on == datetime.now(SINGAPORE).date() + timedelta(days=30)
    day_before = {"loss_date": (starts_on - timedelta(days=1)).isoformat(), "source": "manual",
                  "readings": {"closure": 1}}
    first_day = {**day_before, "loss_date": starts_on.isoformat()}
    for run in (day_before, first_day):
        assert client.post("/api/insurer/payout-runs", json=run).status_code == 200
    paid = {p["loss_date"]: p["amount_sgd"] for p in client.get("/api/payouts").json()}
    assert paid == {day_before["loss_date"]: 195.0, first_day["loss_date"]: 1355.0}
    [after] = client.get("/api/policies").json()
    assert (after["id"], after["tier"], after["started_at"]) == (
        before["id"], "tier_2", before["started_at"]
    )
    assert after["tier_change"]["tier"] == "tier_4"


def test_a_day_before_the_switch_paid_after_it_is_paid_on_the_old_terms(client):
    assert client.post("/api/buy", json=buy_body()).status_code == 200
    with client.app.state.db.begin() as db:
        db.execute(accounts.policies.update().values(started_at=datetime(2026, 6, 1, tzinfo=UTC)))
    application_id = past_price_referral(client, "tier_4")
    client.post("/api/auth/logout")
    sign_in_as_insurer(client)
    decide(client, application_id, "approve")
    today = datetime.now(SINGAPORE).date()
    with client.app.state.db.begin() as db:
        db.execute(accounts.policy_tier_changes.update().values(starts_on=today))
    closed = {"source": "manual", "readings": {"closure": 1}}
    for day in (today, today - timedelta(days=1)):
        run = {**closed, "loss_date": day.isoformat()}
        assert client.post("/api/insurer/payout-runs", json=run).status_code == 200
    paid = {p["loss_date"]: (p["tier"], p["amount_sgd"]) for p in client.get("/api/payouts").json()}
    assert paid == {
        (today - timedelta(days=1)).isoformat(): ("tier_2", 195.0),
        today.isoformat(): ("tier_4", 1355.0),
    }
    [policy] = client.get("/api/policies").json()
    assert (policy["tier"], policy["tier_change"]) == ("tier_4", None)


def test_a_tariff_saved_before_the_yearly_price_gains_the_limit_and_the_stations_on_hold(
    tmp_path, monkeypatch
):
    database_url = f"sqlite:///{tmp_path / 'tariff.db'}"
    old = old_main_tariff()
    with store.connect(database_url).begin() as db:
        db.execute(insert(store.tariff_versions).values(
            saved_at=datetime.now(UTC), saved_by="admin", body=old
        ))
    monkeypatch.setenv("ADMIN_USERNAME", ADMIN[0])
    monkeypatch.setenv("ADMIN_PASSWORD", ADMIN[1])
    monkeypatch.setenv("DATABASE_URL", database_url)
    with TestClient(app) as client:
        saved = client.get("/api/admin/tariff", auth=ADMIN).json()
    with TestClient(app) as client:
        again = client.get("/api/admin/tariff", auth=ADMIN).json()
    assert (saved["version"], saved["saved_by"]) == (2, "default: yearly limits, stations on hold")
    assert again["version"] == 2
    tiers = saved["tariff"]["tiers"]
    assert [t["max_paid_days_per_year"] for t in tiers] == [45, 45, 45, 45]
    assert [t["daily_payout_sgd"] for t in tiers] == SHIPPED_DAILY_AMOUNTS
    shipped = [t["premium_shares"] for t in default_tariff()["tiers"]]
    assert [t["premium_shares"] for t in tiers] == shipped
    hazards = {h["key"]: h for h in saved["tariff"]["hazards"]}
    assert hazards["heat"]["stations_on_hold"] == ["S142", "S128"]
    assert hazards["closure"]["assumed_days_per_year"] == 2
    assert saved["tariff"]["pricing"]["refer_above_limit_share"] == 0.5


def test_a_tariff_desk_limit_is_kept(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'tariff.db'}"
    old = default_tariff()
    del old["pricing"]["refer_above_limit_share"]
    for row, days in zip(old["tiers"], (12, 15, 20, 30), strict=True):
        row["max_paid_days_per_year"] = days
    with store.connect(database_url).begin() as db:
        db.execute(insert(store.tariff_versions).values(
            saved_at=datetime.now(UTC), saved_by="admin", body=old
        ))
    monkeypatch.setenv("ADMIN_USERNAME", ADMIN[0])
    monkeypatch.setenv("ADMIN_PASSWORD", ADMIN[1])
    monkeypatch.setenv("DATABASE_URL", database_url)
    with TestClient(app) as client:
        saved = client.get("/api/admin/tariff", auth=ADMIN).json()
    assert [t["max_paid_days_per_year"] for t in saved["tariff"]["tiers"]] == [12, 15, 20, 30]


def test_places_read_on_demand_are_kept_up_to_a_limit(client, monkeypatch):
    days: place_days.PlaceDays = client.app.state.place_days
    monkeypatch.setattr(place_days, "ON_DEMAND_PLACES_KEPT", 2)
    rule = days.rule
    for step in range(4):
        days.replay(rule, "central", 1.35 + step * 1e-4, 103.85)
    assert len(days.read_on_demand) == 2
    newest = place_days.place_key("central", 1.35 + 3e-4, 103.85)
    assert (rule, newest) in days.read_on_demand
