from __future__ import annotations

import base64
from types import SimpleNamespace

import anthropic
import httpx2
import pytest
from fastapi.testclient import TestClient

from api import kyc
from api.main import app
from api.models import KYC_PHOTO_MAX_BASE64_CHARS

PHOTO = {"media_type": "image/png", "data": base64.b64encode(b"not really a png").decode()}
STORM = {"lat": 1.2848, "lng": 103.8322, "radius_km": 0.5, "readings": {"rain": 50, "flood": 1}}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'tariff.db'}")
    monkeypatch.setattr(kyc, "api_key", lambda: None)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def model(monkeypatch):
    """Stand in for the Anthropic client: records each call and answers with `model.answer`."""
    fake = SimpleNamespace(calls=[], answer=None, error=None, stop_reason="end_turn")

    def parse(**request):
        fake.calls.append(request)
        if fake.error:
            raise fake.error
        return SimpleNamespace(stop_reason=fake.stop_reason, parsed_output=fake.answer)

    def client(api_key):
        fake.api_key = api_key
        return SimpleNamespace(messages=SimpleNamespace(parse=parse))

    monkeypatch.setattr(kyc, "api_key", lambda: "test-key")
    monkeypatch.setattr(kyc.anthropic, "Anthropic", client)
    return fake


def read(client, text, **extra):
    response = client.post("/api/map/kyc", json={"text": text, **extra})
    assert response.status_code == 200
    return response.json()


def test_keywords_read_a_fruit_shop_at_a_hawker_centre(client):
    shop = read(client, "I have a fruit shop at Tiong Bahru market, I sell fresh fruit")
    assert shop["product"] == "fresh_produce"
    assert shop["place"] == {
        "name": "Tiong Bahru Market",
        "lat": 1.28479,
        "lng": 103.83218,
        "region": "south",
        "match": "hawker_centre",
        "area": None,
    }
    assert shop["summary"] == "Fresh produce, meat and seafood at Tiong Bahru Market"
    assert (shop["source"], shop["confidence"]) == ("keywords", None)


@pytest.mark.parametrize(
    ("text", "product", "place", "match"),
    [
        (
            "seafood stall, Chinatown Complex",
            "fresh_produce",
            "Smith Street Blk 335 (Chinatown Complex Market)",
            "hawker_centre",
        ),
        (
            "flowers near Tekka",
            "flowers",
            "Buffalo Road Blk 665 (Tekka Centre/Zhu Jiao Market)",
            "hawker_centre",
        ),
        ("drinks at Newton food centre", "packaged_food", "Newton Food Centre", "hawker_centre"),
        ("chicken rice at Tiong Baru Markt", "cooked_food", "Tiong Bahru Market", "hawker_centre"),
    ],
)
def test_keywords_and_place_names(client, text, product, place, match):
    shop = read(client, text)
    assert shop["product"] == product
    assert (shop["place"]["name"], shop["place"]["match"]) == (place, match)


def test_a_planning_area_lands_on_a_hawker_centre_inside_it(client):
    shop = read(client, "I sell clothes at Bedok, open-air")
    assert shop["product"] == "general_goods"
    place = shop["place"]
    assert (place["name"], place["area"]) == ("New Upper Changi Road Blk 208B", "Bedok")
    assert (place["match"], place["region"]) == ("planning_area", "east")
    centres = client.get("/api/map/static").json()["hawker_centres"]
    centre = next(c for c in centres if c["name"] == place["name"])
    assert (place["lat"], place["lng"]) == (centre["lat"], centre["lng"])
    assert shop["summary"] == (
        "Clothing and general goods at New Upper Changi Road Blk 208B "
        "(the hawker centre nearest the middle of Bedok)"
    )


def test_a_planning_area_without_a_hawker_centre_keeps_its_middle_and_says_so(client):
    shop = read(client, "phone shop in Tengah")
    assert (shop["place"]["name"], shop["place"]["area"]) == ("Tengah", "Tengah")
    assert shop["summary"].endswith(
        "(no hawker centre found in Tengah; priced at the area centre)"
    )


def test_area_place_picks_the_centre_inside_the_area_nearest_its_middle():
    square = [[103.0, 1.0], [103.2, 1.0], [103.2, 1.2], [103.0, 1.2], [103.0, 1.0]]
    area = {
        "name": "Square",
        "psi_region": "east",
        "geometry": {"type": "Polygon", "coordinates": [square]},
    }

    def centre(name: str, lat: float, lng: float) -> kyc.KycPlace:
        return kyc.KycPlace(name=name, lat=lat, lng=lng, region="east", match="hawker_centre")

    corner, middle = centre("Corner", 1.01, 103.01), centre("Near the middle", 1.11, 103.09)
    outside = centre("Outside but closest", 1.1, 103.21)

    snapped = kyc.area_place(area, [corner, outside, middle])
    assert (snapped.name, snapped.lat, snapped.lng) == ("Near the middle", 1.11, 103.09)
    assert (snapped.match, snapped.area) == ("planning_area", "Square")

    empty = kyc.area_place(area, [outside])
    assert (empty.name, empty.area) == ("Square", "Square")
    assert (empty.lat, empty.lng) == (1.1, 103.1)


def test_an_unknown_place_and_product_come_back_empty(client):
    shop = read(client, "my shop on the moon")
    assert shop["product"] is None
    assert shop["place"] is None


def test_a_generic_word_is_not_a_place(client):
    assert read(client, "a market stall near the food centre")["place"] is None


def test_the_answer_never_carries_a_price(client):
    shop = read(client, "fruit shop at Tiong Bahru market")
    assert set(shop) == {"product", "place", "confidence", "summary", "source"}
    assert set(shop["place"]) == {"name", "lat", "lng", "region", "match", "area"}


def test_empty_request_and_oversized_or_wrong_photo_are_refused(client):
    assert client.post("/api/map/kyc", json={"text": "  "}).status_code == 422
    too_big = {"media_type": "image/png", "data": "A" * (KYC_PHOTO_MAX_BASE64_CHARS + 1)}
    assert client.post("/api/map/kyc", json={"text": "", "photo": too_big}).status_code == 422
    gif = {"media_type": "image/gif", "data": PHOTO["data"]}
    assert client.post("/api/map/kyc", json={"text": "", "photo": gif}).status_code == 422


def test_model_reads_the_product_and_sees_the_tariff_the_places_and_the_photo(client, model):
    model.answer = kyc.ModelAnswer(
        product="fresh_produce",
        place_name="Bedok",
        confidence=0.9,
        summary="Fresh produce stall at Tiong Bahru Market",
    )
    shop = read(client, "I sell durian at Tiong Bahru market", photo=PHOTO)
    assert shop["product"] == "fresh_produce"
    assert shop["place"]["name"] == "Tiong Bahru Market"
    assert (shop["confidence"], shop["source"]) == (0.9, "llm")
    assert shop["summary"] == "Fresh produce stall at Tiong Bahru Market"

    assert model.api_key == "test-key"
    (call,) = model.calls
    assert "fresh_produce: Fresh produce, meat and seafood" in call["system"]
    assert "- Tiong Bahru Market" in call["system"]
    assert "- Bedok" in call["system"]
    image, words = call["messages"][0]["content"]
    assert image == {"type": "image", "source": {"type": "base64", **PHOTO}}
    assert words == {"type": "text", "text": "I sell durian at Tiong Bahru market"}
    assert call["output_format"] is kyc.ModelAnswer
    assert call["model"] == kyc.MODEL == "claude-haiku-5-5"


def test_model_chooses_the_place_when_the_words_name_none(client, model):
    model.answer = kyc.ModelAnswer(
        product="cooked_food",
        place_name="Maxwell Food Centre (Kim Hua Market)",
        confidence=0.7,
        summary="Cooked food near Chinatown",
    )
    shop = read(client, "noodles next to the big temple in Chinatown")
    assert shop["place"]["name"] == "Maxwell Food Centre (Kim Hua Market)"
    assert shop["place"]["match"] == "hawker_centre"


def test_model_answers_outside_the_lists_are_dropped(client, model):
    model.answer = kyc.ModelAnswer(
        product="durian", place_name="Johor Bahru", confidence=0.4, summary="Durian seller"
    )
    shop = read(client, "I sell durian across the causeway")
    assert shop["product"] is None
    assert shop["place"] is None


def test_with_no_route_to_the_model_the_keywords_answer(client, model):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    model.error = anthropic.APIConnectionError(request=request)
    shop = read(client, "fruit shop at Tiong Bahru market")
    assert len(model.calls) == 1
    assert shop["product"] == "fresh_produce"
    assert shop["place"]["name"] == "Tiong Bahru Market"
    assert (shop["source"], shop["confidence"]) == ("keywords", None)


def test_an_unparsed_or_refused_model_answer_gives_no_product_but_keeps_the_place(client, model):
    model.error = ValueError("not the JSON that was asked for")
    shop = read(client, "fruit shop at Tiong Bahru market")
    assert shop["product"] is None
    assert shop["place"]["name"] == "Tiong Bahru Market"
    assert shop["source"] == "llm"

    model.error, model.stop_reason = None, "refusal"
    assert read(client, "fruit shop at Tiong Bahru market")["product"] is None


def test_scenario_prices_the_product_it_is_sent(client):
    def payout(product: str) -> float:
        response = client.post("/api/map/scenario", json={**STORM, "product": product})
        assert response.status_code == 200
        return response.json()["assessment"]["payout_sgd"]

    assert payout("fresh_produce") != payout("cooked_food")
    assert payout("cooked_food") == client.post("/api/map/scenario", json=STORM).json()[
        "assessment"
    ]["payout_sgd"]


def test_scenario_takes_a_reading_for_every_hazard_in_the_tariff(client):
    hazards = [hazard["key"] for hazard in client.get("/api/options").json()["hazards"]]
    assert {"haze", "rain", "heat", "flood", "closure"} <= set(hazards)
    body = {**STORM, "product": "flowers", "readings": dict.fromkeys(hazards, 0) | {"rain": 50}}
    response = client.post("/api/map/scenario", json=body)
    assert response.status_code == 200
    priced = response.json()["assessment"]["hazards"]
    assert [loss["hazard"] for loss in priced] == hazards
