from __future__ import annotations

import pytest

from api import sms_gateway


@pytest.fixture(autouse=True)
def texts_stay_simulated(monkeypatch):
    """Twilio keys in .env must never make a test text a real phone."""
    monkeypatch.setattr(sms_gateway, "twilio", lambda: None)
