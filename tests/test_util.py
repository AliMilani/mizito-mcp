from datetime import date, datetime, timedelta, timezone

import pytest

from mizito_mcp.util import (fa_datetime, g2j, j2g, norm, parse_user_datetime,
                             scrub, to_mizito_iso)
from tests.conftest import FAKE_JWT


def test_norm_unifies_arabic_and_persian_letters():
    assert norm("دستيار ميزيتو") == norm("دستیار میزیتو")
    assert norm("كتاب") == norm("کتاب")
    assert norm("می‌خواهم") == norm("می خواهم")
    assert norm("۱۴۰۵") == "1405"
    assert norm("  Hello   World ") == "hello world"


@pytest.mark.parametrize("g,j", [
    ((2026, 3, 21), (1405, 1, 1)),
    ((2026, 11, 12), (1405, 8, 21)),
    ((2025, 3, 20), (1403, 12, 30)),  # 1403 is a leap year
    ((2024, 2, 29), (1402, 12, 10)),
])
def test_jalali_known_dates(g, j):
    assert g2j(*g) == j
    assert j2g(*j) == g


def test_jalali_roundtrip_every_day_for_ten_years():
    d = date(2020, 1, 1)
    while d < date(2030, 1, 1):
        assert j2g(*g2j(d.year, d.month, d.day)) == (d.year, d.month, d.day)
        d += timedelta(days=1)


def test_fa_datetime_uses_tehran_time():
    # 20:45 UTC = 00:15 next day in Tehran (+03:30)
    assert fa_datetime("2026-11-11T20:45:00.000Z") == "1405/08/21 00:15"
    assert fa_datetime(None) is None
    assert fa_datetime("garbage") is None


def test_parse_user_datetime_variants():
    utc = timezone.utc
    assert parse_user_datetime("2026-11-20 14:30") == datetime(2026, 11, 20, 11, 0, tzinfo=utc)
    assert parse_user_datetime("1405/08/30 14:30") == datetime(2026, 11, 21, 11, 0, tzinfo=utc)
    assert parse_user_datetime("۱۴۰۵/۰۸/۳۰") == datetime(2026, 11, 21, 20, 29, tzinfo=utc)
    assert parse_user_datetime("2026-11-20T10:00:00Z") == datetime(2026, 11, 20, 10, 0, tzinfo=utc)
    with pytest.raises(ValueError):
        parse_user_datetime("next tuesday")


def test_to_mizito_iso_matches_js_tojson():
    dt = datetime(2026, 11, 20, 11, 0, 0, 123456, tzinfo=timezone.utc)
    assert to_mizito_iso(dt) == "2026-11-20T11:00:00.123Z"


def test_scrub_removes_tokens_everywhere():
    raw = {"_id": "x", "access_token": FAKE_JWT,
           "nested": [{"token": "abc", "url": f"https://cdn/{FAKE_JWT}"}],
           "title": "ok"}
    out = scrub(raw)
    assert "access_token" not in out
    assert "token" not in out["nested"][0]
    assert FAKE_JWT not in str(out)
    assert out["title"] == "ok"
