"""The Payung assistant: every tool prices a place as POST /api/quote does, states the product
from the live tariff, and answers with no model at all.

No API key and no local model are seen (kyc.api_key and assistant.local_model_ready are stubbed),
so no test calls a real model. The model path runs once against a stand-in client.
"""

from __future__ import annotations

import json
from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from openai.types.chat import ChatCompletionMessage, ChatCompletionMessageToolCall
from openai.types.chat.chat_completion_message_tool_call import Function
from sqlalchemy import select
from starlette.requests import Request

from api import accounts, assistant, kyc, store
from api.main import app
from tests import test_api, test_premium_payments

MAXWELL = test_api.buy_body()["centre"]
SHOP_POSTCODE = "380123"
PRODUCT = "cooked_food"
PAST_DAY = "2025-06-02"
YEARLY_LIMIT_DAYS = 45


@pytest.fixture(autouse=True)
def no_model(monkeypatch):
    monkeypatch.setattr(kyc, "api_key", lambda key_name: None)
    monkeypatch.setattr(assistant, "local_model_ready", lambda: False)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'tariff.db'}")
    with TestClient(app) as client:
        yield client


class HazyLiveFeed:
    """Today's live feed, never fetched: PSI 150 in every region, no gauge or WBGT station."""

    def ensure_started(self) -> None:
        pass

    def read(self) -> dict:
        regions = app.state.regions
        return {"available": True, "fetched_at": "test",
                "haze": {region: {"max_today": 150} for region in regions}}


@pytest.fixture
def hazy_today(client, monkeypatch):
    monkeypatch.setattr(app.state, "live", HazyLiveFeed())


def context(user: accounts.Account | None = None, page: str = "site") -> assistant.Context:
    request = Request({"type": "http", "app": app, "headers": [], "method": "POST",
                       "path": "/api/assistant/chat"})
    return assistant.Context(request, store.latest(app.state.db).tariff, page, user)


def account(email: str) -> accounts.Account:
    with app.state.db.connect() as db:
        row = db.execute(select(accounts.users).where(accounts.users.c.email == email)).one()
    return accounts.account_from_row(row)


INSURER = accounts.Account(id=0, email="desk@example.test", name="Desk", role="insurer",
                           business_name=None, centre=None, region=None, product=None,
                           insurer="Income")


def quote(client, product: str = PRODUCT, **place) -> dict:
    response = client.post("/api/quote", json={"product": product, **place})
    assert response.status_code == 200, response.text
    return response.json()


def tier_of(priced: dict, tier: str = "tier_2") -> dict:
    return next(t for t in priced["tiers"] if t["tier"] == tier)


def assert_rows_are_the_quote(rows: list[dict], priced: dict) -> None:
    assert [row["tier"] for row in rows] == [t["tier"] for t in priced["tiers"]]
    for row, tier in zip(rows, priced["tiers"], strict=True):
        assert row["yearly_premium_sgd"] == tier["yearly_premium_sgd"]
        assert row["monthly_premium_sgd"] == round(tier["yearly_premium_sgd"] / 12, 2)
        assert row["weekly_billed_sgd"] == tier["weekly_premium_sgd"]
        assert row["pays_for_a_day_with_no_sales_sgd"] == tier["daily_payout_sgd"]
        assert row["paid_days_a_year_up_to"] == YEARLY_LIMIT_DAYS
        assert row["best_value"] == tier["best_value"]
        assert row["offered_here"] == tier["offered"]
        add_on = row["severe_haze_payout_add_on"]
        assert add_on["pays_once_sgd"] == tier["haze_bonus"]["lump_sum_sgd"]
        assert add_on["yearly_sgd"] == tier["haze_bonus"]["yearly_sgd"]
        assert row["proof"][-1].startswith("We estimate a year like 2015 would pay about")


def test_a_hawker_is_shown_the_tiers_its_centre_is_quoted(client):
    ctx = context()
    result = assistant.tool_describe_business(ctx, f"I sell chicken rice at {MAXWELL}")
    assert result["place"] == MAXWELL
    assert_rows_are_the_quote(result["tiers"], quote(client, centre=MAXWELL))
    rules = " ".join(result["cover_rules"])
    assert f"up to {YEARLY_LIMIT_DAYS} full days a year" in rules
    assert "40-day lockdown or closure order is paid in full" in rules
    assert ctx.actions[-1].fields == {
        "business_class": "hawker", "product": PRODUCT, "centre": MAXWELL,
    }


def test_maxwell_cooked_food_costs_the_final_monthly_prices(client):
    rows = assistant.tool_describe_business(context(), f"I sell chicken rice at {MAXWELL}")["tiers"]
    assert [round(row["monthly_premium_sgd"]) for row in rows] == [49, 252, 750, 1498]
    assert [row["pays_for_a_day_with_no_sales_sgd"] for row in rows] == [35, 195, 630, 1355]


def test_a_shop_is_shown_the_tiers_its_postcode_is_quoted(client):
    ctx = context()
    result = assistant.tool_describe_business(
        ctx, f"I sell chicken rice at my shop, {SHOP_POSTCODE}"
    )
    product = ctx.actions[-1].fields["product"]
    assert ctx.actions[-1].fields["postcode"] == SHOP_POSTCODE
    assert_rows_are_the_quote(result["tiers"], quote(client, product, postcode=SHOP_POSTCODE))
    assert "A shop here" in " ".join(result["tiers"][0]["proof"])


@pytest.mark.parametrize("place", [{"centre": MAXWELL}, {"postcode": SHOP_POSTCODE}])
def test_explain_price_breaks_down_the_quoted_premium(client, place):
    result = assistant.tool_explain_price(context(), product=PRODUCT, tier="tier_2", **place)
    tier = tier_of(quote(client, **place))
    build_up = result["build_up_sgd_a_year"]
    assert build_up["yearly_premium"] == tier["yearly_premium_sgd"]
    assert round(sum(v for k, v in build_up.items() if k != "yearly_premium"), 2) == \
        tier["yearly_premium_sgd"]
    assert result["monthly_premium_sgd"] == round(tier["yearly_premium_sgd"] / 12, 2)
    assert result["expected_paid_days_a_year"] == tier["expected_paid_days"]
    assert result["expected_payouts_share_of_premium_before_gst"] == "60%"
    closure = next(h for h in result["by_hazard"] if h["hazard"] == "closure")
    assert closure["priced_from"] == "an assumed 2 days a year"


def test_a_map_point_is_priced_at_its_nearest_region(client):
    ctx = context()
    where = assistant.point_place(ctx, "a point in the east", 1.3240, 103.9300)
    priced = assistant.place_quote(ctx, where, PRODUCT)
    assert priced.model_dump(mode="json") == quote(client, latitude=where.lat, longitude=where.lng)


def test_a_region_is_priced_as_the_region(client):
    ctx = context()
    priced = assistant.place_quote(ctx, assistant.region_place(ctx, "north"), PRODUCT)
    assert priced.model_dump(mode="json") == quote(client, region="north")


@pytest.mark.parametrize("place", [{"centre": MAXWELL}, {"postcode": SHOP_POSTCODE}])
def test_ten_year_record_replays_the_place_at_its_quoted_price(client, place):
    result = assistant.tool_ten_year_record(context(), tier="tier_2", **place)
    assert "error" not in result
    assert result["totals"]["from_year"] == 2017
    assert result["totals"]["premium_sgd"] == round(
        tier_of(quote(client, **place))["yearly_premium_sgd"] * len(result["years"]), 2
    )


def test_weather_now_reads_the_live_feed_by_the_payout_rule(client, hazy_today):
    result = assistant.tool_weather_now(context(), centre=MAXWELL)
    assert result["readings"]["haze"] == 150
    assert result["share_of_day_lost_pc_so_far"] > 0


def test_a_dispute_is_checked_against_the_recorded_readings(client):
    result = assistant.tool_check_dispute(context(), PAST_DAY, "It poured all day", centre=MAXWELL)
    assert result["readings_source"] == "NEA's recorded readings"
    assert set(result["readings"]) == {"haze", "rain", "heat"}
    assert "a human verifier decides" in result["draft_for_verifier"]


def buy_with_paynow(client) -> accounts.Account:
    payment = test_premium_payments.paid(client)
    body = test_premium_payments.buy_body(payment_token=payment["token"])
    response = client.post("/api/buy", json=body)
    assert response.status_code == 200, response.text
    return account(body["email"])


def test_a_customer_with_cover_hears_their_own_policy(client, hazy_today):
    ctx = context(buy_with_paynow(client), page="dashboard")
    tier = tier_of(quote(client, centre=MAXWELL))
    cover = assistant.tool_my_cover(ctx)
    assert cover["covered"] and cover["place"] == MAXWELL
    assert cover["weekly_premium_sgd"] == tier["weekly_premium_sgd"]
    assert cover["most_paid_days_a_year"] == YEARLY_LIMIT_DAYS
    assert cover["cover_pays_from"] == (assistant.today() + timedelta(days=30)).isoformat()
    price = assistant.tool_explain_price(ctx)
    assert price["build_up_sgd_a_year"]["yearly_premium"] == tier["yearly_premium_sgd"]
    paid = assistant.tool_why_paid(ctx, "yesterday")
    assert paid["in_waiting_period"] and paid["place"] == MAXWELL
    assert "error" not in assistant.tool_ten_year_record(ctx)
    assert "error" not in assistant.tool_weather_now(ctx)


def test_a_shop_customer_is_priced_and_paid_at_its_postcode(client):
    body = test_api.shop_body(postcode=SHOP_POSTCODE, email="shop@example.test")
    assert client.post("/api/buy", json=body).status_code == 200
    ctx = context(account(body["email"]), page="dashboard")
    cover = assistant.tool_my_cover(ctx)
    assert cover["place"].startswith(f"postcode {SHOP_POSTCODE}")
    tier = tier_of(quote(client, body["product"], postcode=SHOP_POSTCODE))
    assert cover["weekly_premium_sgd"] == tier["weekly_premium_sgd"]
    assert assistant.tool_explain_price(ctx)["monthly_premium_sgd"] == \
        round(tier["yearly_premium_sgd"] / 12, 2)


def test_insurer_tools_price_regions_on_the_replayed_years(client):
    buy_with_paynow(client)
    ctx = context(INSURER, page="dashboard")
    change = assistant.tool_tariff_change(ctx, "weight", 0.4, hazard="haze")
    rows = {row["region"]: row for row in change["tier_2_cooked_food"]}
    assert set(rows) == set(app.state.regions)
    for region, row in rows.items():
        assert row["yearly_now_sgd"] == tier_of(quote(client, region=region))["yearly_premium_sgd"]
        assert row["yearly_after_sgd"] < row["yearly_now_sgd"]
    shorter = assistant.tool_tariff_change(ctx, "yearly_limit_days", 10)
    assert all(r["yearly_after_sgd"] <= r["yearly_now_sgd"] for r in shorter["tier_2_cooked_food"])
    assert "error" in assistant.run_tool(ctx, "tariff_change",
                                         {"setting": "weight", "value": 2, "hazard": "haze"})
    day = assistant.tool_what_if_day(ctx, psi=320)
    assert day["book_total_payout_sgd"] > 0
    assert assistant.tool_portfolio(ctx)["policies"] == 1
    assert assistant.tool_underwriting_queue(ctx)["waiting_count"] == 0


def test_the_prompt_states_the_product_from_the_tariff(client):
    prompt = assistant.system_prompt(context())
    for fact in ("Tier 1 S$35, Tier 2 S$195, Tier 3 S$630 and Tier 4 S$1,355",
                 "A partly bad day pays the share of the day lost",
                 f"up to {YEARLY_LIMIT_DAYS} full days a year",
                 "one 40-day lockdown every 20 years", "the yearly premium over 12",
                 "55% on Tier 1, 60% on Tier 2, 65% on Tier 3 and 70% on Tier 4",
                 "40 or more days at PSI 101", "25 times the daily amount",
                 "divided by 10", "May to October", "30-day wait", "S142 and S128",
                 "no model predicts bad days", "suit businesses with higher takings"):
        assert fact in prompt


def chat(client, text: str, language: str = "en") -> dict:
    response = client.post("/api/assistant/chat", json={
        "messages": [{"role": "user", "content": text}], "language": language,
    })
    assert response.status_code == 200, response.text
    return response.json()


def test_chat_answers_without_a_model(client):
    reply = chat(client, f"I sell chicken rice at {MAXWELL}. What is the most cover?")
    assert reply["source"] == "rules"
    monthly = round(tier_of(quote(client, centre=MAXWELL), "tier_4")["yearly_premium_sgd"] / 12, 2)
    assert f"S${monthly:,.2f}/month" in reply["reply"]
    assert f"up to {YEARLY_LIMIT_DAYS} full days a year" in reply["reply"]
    assert "severe haze payout" in reply["reply"]
    assert reply["actions"][0]["type"] == "start_signup"


@pytest.mark.parametrize("question, words", [
    ("What if there is a lockdown?", "paid in full"),
    ("Tell me about the severe haze payout", "25 times the daily amount"),
    ("How long must I wait before it pays?", "30 days"),
    (f"Why does it cost so much at {MAXWELL}?", "a month"),
    (f"What would it have paid my shop at {SHOP_POSTCODE} in the past years?", "would have paid"),
])
def test_keyword_answers_come_from_the_tariff_and_the_quotes(client, question, words):
    assert words in chat(client, question)["reply"]


def hide_tier_1_at_maxwell(client) -> dict:
    """Set the share between Tier 1's and Tier 2's at Maxwell, so only Tier 1 is hidden there."""
    priced = quote(client, centre=MAXWELL)
    share = [t["yearly_premium_sgd"] / t["max_payout_per_year_sgd"] for t in priced["tiers"][:2]]
    saved = client.get("/api/admin/tariff", auth=("admin", "secret")).json()
    saved["tariff"]["pricing"]["refer_above_limit_share"] = round(sum(share) / 2, 4)
    change = {"based_on_version": saved["version"], "tariff": saved["tariff"]}
    assert client.put("/api/admin/tariff", json=change, auth=("admin", "secret")).status_code == 200
    priced = quote(client, centre=MAXWELL)
    assert [t["offered"] for t in priced["tiers"]] == [False, True, True, True]
    return priced


def test_a_tier_not_offered_is_never_suggested_and_the_reason_is_the_weather(client):
    hidden = tier_of(hide_tier_1_at_maxwell(client), "tier_1")
    result = assistant.tool_describe_business(
        context(), f"I sell chicken rice at {MAXWELL}, about $150 a day"
    )
    row = next(r for r in result["tiers"] if r["tier"] == "tier_1")
    assert row["offered_here"] is False
    assert row["not_offered_because"] == hidden["not_offered_reason"]
    assert result["suggested_tier"] is None
    reply = chat(client, f"I sell chicken rice at {MAXWELL}")["reply"]
    monthly = round(hidden["yearly_premium_sgd"] / 12, 2)
    assert f"S${monthly:,.2f}/month" not in reply
    assert "Tier 1 is not offered here." in reply and "weather history" in reply
    price = assistant.tool_explain_price(context(), centre=MAXWELL, tier="tier_1")
    assert price["not_offered_because"] == hidden["not_offered_reason"]


@pytest.mark.parametrize("sales, suggested, offered", [
    (150, "tier_1", ["tier_1"]),
    (500, "tier_2", ["tier_1", "tier_2"]),
    (1500, "tier_4", ["tier_1", "tier_2", "tier_3", "tier_4"]),
])
def test_the_suggestion_follows_the_business_daily_sales(client, sales, suggested, offered):
    result = assistant.tool_describe_business(
        context(), f"I sell chicken rice at {MAXWELL}", daily_sales_sgd=sales
    )
    assert result["suggested_tier"] == suggested
    assert [r["tier"] for r in result["tiers"] if r["offered_here"]] == offered
    assert result["a_day_with_no_sales_costs_this_business_sgd"] == sales


def test_without_daily_sales_the_assistant_asks_for_them_and_suggests_nothing(client):
    result = assistant.tool_describe_business(context(), f"I sell chicken rice at {MAXWELL}")
    assert result["suggested_tier"] is None
    reply = chat(client, f"I sell chicken rice at {MAXWELL}")["reply"]
    assert "Tell me your normal sales on a weekday" in reply
    assert "suggest" not in reply.lower()


def test_the_assistant_never_suggests_a_tier_above_the_loss(client):
    reply = chat(client, f"I sell chicken rice at {MAXWELL}, about $500 a day")["reply"]
    assert "A day with no sales costs this business about S$500." in reply
    assert "Suggested for your sales: Tier 2" in reply
    assert "Tier 3 pays S$630 for a day with no sales, more than this business loses" in reply
    monthly_tier_3 = round(tier_of(quote(client, centre=MAXWELL), "tier_3")["yearly_premium_sgd"]
                           / 12, 2)
    assert f"S${monthly_tier_3:,.2f}/month" not in reply


def test_chat_in_another_language_still_answers(client):
    assert chat(client, f"我在 {MAXWELL} 卖鸡饭", language="zh")["reply"]


class StandInModel:
    """A model that asks for describe_business once, then answers; it records the tool result."""

    def __init__(self) -> None:
        self.tool_results: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, messages: list[dict], **_) -> SimpleNamespace:
        self.tool_results += [json.loads(m["content"]) for m in messages if m["role"] == "tool"]
        if self.tool_results:
            message = ChatCompletionMessage(role="assistant", content="Here are your tiers.")
        else:
            call = ChatCompletionMessageToolCall(
                id="call-1", type="function", function=Function(
                    name="describe_business",
                    arguments=json.dumps({"description": f"I sell chicken rice at {MAXWELL}"}),
                ),
            )
            message = ChatCompletionMessage(role="assistant", content=None, tool_calls=[call])
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_the_model_path_runs_tools_priced_as_the_quote(client, monkeypatch):
    model = StandInModel()
    monkeypatch.setattr(assistant, "model_client", lambda: (model, "stand-in", False))
    reply = chat(client, "I sell chicken rice at Maxwell")
    assert (reply["reply"], reply["source"]) == ("Here are your tiers.", "llm")
    assert_rows_are_the_quote(model.tool_results[0]["tiers"], quote(client, centre=MAXWELL))


def test_no_key_and_no_local_model_means_no_model():
    assert assistant.model_client() is None
