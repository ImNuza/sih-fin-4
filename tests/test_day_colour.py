from __future__ import annotations

import pytest

from api import sms


@pytest.mark.parametrize(
    ("loss_percent", "colour"),
    [(0, "none"), (0.1, "yellow"), (29.9, "yellow"), (30, "red"), (69.9, "red"),
     (70, "red"), (100, "red")],
)
def test_day_colour_bands(loss_percent, colour):
    assert sms.day_colour(loss_percent) == colour


@pytest.mark.parametrize("language", sms.LANGUAGES)
def test_paid_text_names_the_day_colour_and_loss(language):
    body = sms.payout_text(
        "payout_paid", language, "rain", day_colour=sms.day_name(language, 85), loss="85",
        amount="85.00", proxy="+65 ****4567", centre="Tiong Bahru", day="14 Nov", ref="SD-1",
    )
    assert sms.DAY_NAMES[language]["red"] in body
    assert "85%" in body
