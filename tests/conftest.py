from __future__ import annotations

import pytest

from api import onboarding, sms_gateway


@pytest.fixture(autouse=True)
def texts_stay_simulated(monkeypatch):
    """A textbee key in .env must never make a test text a real phone."""
    monkeypatch.setattr(sms_gateway, "textbee_key", lambda: None)


@pytest.fixture
def riders_open(monkeypatch):
    """Open the platform worker path, which the pilot keeps closed, to test it for the next phase."""
    monkeypatch.setattr(onboarding, "OPEN_CLASSES", onboarding.BUSINESS_CLASSES)
