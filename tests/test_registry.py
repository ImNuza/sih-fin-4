"""UEN and licence lookups (api/registry.py) and how the buy flow uses them."""

from __future__ import annotations

import pytest

from api import registry
from tests.test_api import buy_body, client, shop_body  # noqa: F401  (client is a fixture)

# Rows shaped as data.gov.sg returns them: an ENTITIES row and a details row.
ENTITY = {
    "uen": "201502270M", "issuance_agency_desc": "ACRA", "uen_status_desc": "Registered",
    "entity_name": "CREME WORKS PRIVATE LIMITED", "entity_type_desc": "Local Company",
    "uen_issue_date": "2015-01-22", "reg_street_name": "WOODLANDS HEIGHT",
    "reg_postal_code": "737859",
}
DETAILS = {
    "uen": "201502270M", "entity_name": "CREME WORKS PRIVATE LIMITED",
    "entity_type_description": "Local Company", "entity_status_description": "Live Company",
    "block": "1", "street_name": "WOODLANDS HEIGHT", "level_no": "04", "unit_no": "06",
    "building_name": "na", "postal_code": "737859", "primary_ssic_code": "47102",
    "primary_ssic_description": "MINI-MARTS, CONVENIENCE STORES AND PROVISION SHOPS",
}


def acra_answers(monkeypatch, entity: dict | None, details: dict | None = None) -> list[str]:
    """Make data.gov.sg answer with these rows. Returns the dataset ids called, in order."""
    calls: list[str] = []

    def fetch(resource_id: str, filters: dict) -> list[dict]:
        calls.append(resource_id)
        if resource_id == registry.ENTITIES:
            return [entity] if entity else []
        return [details] if details else []

    monkeypatch.setattr(registry, "fetch_records", fetch)
    return calls


def test_a_demo_company_is_found_without_calling_data_gov_sg(client):
    uen = client.get("/api/buy/options").json()["demo_uens"][0]
    business = client.get(f"/api/lookup/uen/{uen.lower()}").json()
    assert business["uen"] == uen and business["live"] is True
    assert business["name"] and business["ssic_code"] and business["postcode"]
    assert business["source"].startswith("ACRA via data.gov.sg, saved ")


def test_the_buy_options_hold_20_live_demo_companies_and_the_demo_licences(client):
    options = client.get("/api/buy/options").json()
    assert len(options["demo_uens"]) == 20
    assert all(registry.lookup_uen(uen).live for uen in options["demo_uens"])
    assert options["demo_licences"] and all(
        licence["licence_no"].startswith("DEMO") for licence in options["demo_licences"]
    )


def test_a_live_lookup_reads_both_acra_datasets_and_keeps_the_answer(client, monkeypatch):
    calls = acra_answers(monkeypatch, ENTITY, DETAILS)
    business = client.get("/api/lookup/uen/201502270M").json()
    assert business["name"] == "CREME WORKS PRIVATE LIMITED"
    assert (business["entity_type"], business["status"], business["live"]) == (
        "Local Company", "Live Company", True
    )
    assert business["address"] == "1 WOODLANDS HEIGHT #04-06 Singapore 737859"
    assert (business["ssic_code"], business["ssic_title"]) == (
        "47102", "Mini-marts, convenience stores and provision shops"
    )
    assert calls == [registry.ENTITIES, registry.DETAILS_BY_LETTER["C"]]
    client.get("/api/lookup/uen/201502270M")
    assert len(calls) == 2


def test_a_lookup_without_the_details_still_gives_the_name(client, monkeypatch):
    acra_answers(monkeypatch, ENTITY, None)
    business = client.get("/api/lookup/uen/201502270M").json()
    assert (business["name"], business["postcode"], business["ssic_code"]) == (
        "CREME WORKS PRIVATE LIMITED", "737859", None
    )


@pytest.mark.parametrize(
    ("uen", "code"), [("NOT-A-UEN", 422), ("201999999Z", 503)],
)
def test_a_bad_uen_is_refused_and_an_offline_registry_says_so(client, uen, code):
    assert client.get(f"/api/lookup/uen/{uen}").status_code == code


def test_an_unknown_uen_is_not_found(client, monkeypatch):
    acra_answers(monkeypatch, None)
    assert client.get("/api/lookup/uen/201999999Z").status_code == 404


def test_buy_refuses_a_uen_acra_does_not_list(client, monkeypatch):
    acra_answers(monkeypatch, None)
    response = client.post("/api/buy", json=shop_body(uen="201999999Z"))
    assert response.status_code == 422
    assert "ACRA has no business" in response.json()["detail"]


def test_buy_refuses_a_deregistered_business(client, monkeypatch):
    gone = {**ENTITY, "uen": "53474759X", "uen_status_desc": "Deregistered"}
    acra_answers(monkeypatch, gone, {**DETAILS, "entity_status_description": "Ceased Registration"})
    response = client.post("/api/buy", json=shop_body(uen="53474759X"))
    assert response.status_code == 422
    assert "Ceased Registration" in response.json()["detail"]


def test_a_shop_with_a_live_uen_is_marked_checked_with_its_acra_name(client):
    application = client.post("/api/buy", json=shop_body()).json()["application"]
    assert (application["uen_check"], application["applicant_type"]) == ("acra", "company")
    assert application["registered_name"] == "AL-TRICIA MARKETING PTE. LTD."
    assert application["entity_type"] == "Local Company"


def test_a_uen_is_marked_not_checked_when_data_gov_sg_is_down(client):
    application = client.post("/api/buy", json=buy_body(uen="201912345K")).json()["application"]
    assert application["uen_check"] == "not_checked"


def test_a_sole_proprietor_applies_as_an_individual(client, monkeypatch):
    sole = {**ENTITY, "uen": "53123456A", "entity_type_desc": "Sole Proprietorship/ Partnership"}
    acra_answers(monkeypatch, sole, None)
    application = client.post("/api/buy", json=shop_body(uen="53123456A")).json()["application"]
    assert (application["applicant_type"], application["uen_check"]) == ("individual", "acra")


def test_the_client_cannot_choose_the_applicant_type(client):
    body = buy_body(applicant_type="company", uen=None)
    application = client.post("/api/buy", json=body).json()["application"]
    assert (application["applicant_type"], application["uen"]) == ("individual", None)


def test_a_demo_licence_fills_in_the_stall(client):
    licence = client.get("/api/lookup/licence", params={"licence_no": "demo10231k"}).json()
    assert licence["centre"] == "Maxwell Food Centre (Kim Hua Market)"
    assert (licence["licensee_name"], licence["stall_unit"]) == ("Tan Wei Ming", "01-15")
    assert "made up" in licence["source"]
    assert client.get("/api/lookup/licence", params={"licence_no": "FS12345X"}).status_code == 404


@pytest.mark.parametrize(
    ("licence_no", "check"), [("DEMO10231K", "demo_register"), ("DEMO/12345", "not_checked")],
)
def test_a_hawker_licence_is_marked_by_whether_the_register_lists_it(client, licence_no, check):
    application = client.post("/api/buy", json=buy_body(licence_no=licence_no)).json()["application"]
    assert application["licence_check"] == check


def test_the_underwriter_queue_shows_the_checks(client):
    body = buy_body(declined_before=True, declined_details="Declined in 2024", payment_method=None)
    assert client.post("/api/buy", json=body).status_code == 200
    client.post("/api/auth/logout")
    client.post("/api/auth/register", json={
        "role": "insurer", "name": "Desk", "email": "desk@example.test",
        "password": "insurer-pass-1", "insurer": "Income Insurance",
    })
    [waiting] = client.get("/api/insurer/applications").json()["waiting"]
    assert waiting["licence_check"] == "not_checked" and waiting["uen_check"] is None
