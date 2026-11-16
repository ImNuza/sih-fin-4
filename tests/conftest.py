from __future__ import annotations

import pytest

from api import onboarding, payout_api, registry, sms_gateway


@pytest.fixture(autouse=True)
def texts_stay_simulated(monkeypatch):
    """A textbee key in .env must never make a test text a real phone."""
    monkeypatch.setattr(sms_gateway, "textbee_key", lambda: None)


@pytest.fixture(autouse=True)
def no_demo_phone(monkeypatch):
    """A DEMO_PAYOUT_MOBILE in .env must not change a test. A test that needs it sets its own."""
    monkeypatch.setattr(payout_api, "api_key", lambda setting: None)


@pytest.fixture(autouse=True)
def registry_offline(monkeypatch):
    """No test calls data.gov.sg. A UEN outside the demo companies counts as not checked.
    A test that needs an ACRA answer replaces registry.fetch_records itself."""

    def offline(resource_id: str, filters: dict) -> list[dict]:
        raise registry.RegistryUnavailable("tests run offline")

    monkeypatch.setattr(registry, "fetch_records", offline)
    monkeypatch.setattr(registry, "LOOKED_UP", {})


@pytest.fixture
def riders_open(monkeypatch):
    """Open the platform worker path, which the pilot keeps closed, to test it for the next phase."""
    monkeypatch.setattr(onboarding, "OPEN_CLASSES", onboarding.BUSINESS_CLASSES)
