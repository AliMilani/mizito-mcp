"""Small pure helpers: Persian text matching, Jalali/Tehran dates, scrubbing.

Everything here is side-effect free and unit-tested (tests/test_util.py).
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

# Iran has had no DST since 2022, so a fixed offset is exact for current data
# and avoids depending on tzdata inside slim Docker images.
TEHRAN = timezone(timedelta(hours=3, minutes=30), "Asia/Tehran")

# ---------------------------------------------------------------- text

_CHAR_MAP = str.maketrans({
    "ي": "ی", "ى": "ی", "ئ": "ی", "ك": "ک", "ة": "ه", "ۀ": "ه",
    "أ": "ا", "إ": "ا", "ٱ": "ا",
    "‌": " ", "‍": "", "‎": "", "‏": "", "ـ": "",
    "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
    "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
    "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
})
_DIACRITICS = re.compile(r"[ً-ٰٟ]")
_SPACES = re.compile(r"\s+")


def norm(text: str | None) -> str:
    """Normalise for matching: Arabic->Persian letters, digits->ASCII,
    ZWNJ->space, no diacritics, collapsed spaces, casefolded."""
    if not text:
        return ""
    t = _DIACRITICS.sub("", str(text).translate(_CHAR_MAP))
    return _SPACES.sub(" ", t).strip().casefold()


_TAG_BREAK = re.compile(r"<\s*(br|/div|/p|/li)\s*/?>", re.I)
_TAG = re.compile(r"<[^>]+>")


def plain_text(text: str | None) -> str:
    """Server-stored rich text (the SPA's editor sends HTML such as
    `<div>a</div><div>b</div>`) -> comparable plain text. Used to verify that
    a write landed without depending on how Mizito re-encodes it."""
    import html
    if not text:
        return ""
    t = _TAG.sub("", _TAG_BREAK.sub("\n", str(text)))
    return norm(html.unescape(t))


def to_ascii_digits(text: str) -> str:
    return str(text).translate(_CHAR_MAP) if text else text


def truncate(text: str | None, n: int) -> str:
    text = text or ""
    return text if len(text) <= n else text[:n].rstrip() + "…"


OBJECT_ID = re.compile(r"^[0-9a-f]{24}$")


def is_object_id(value: str | None) -> bool:
    return bool(value) and bool(OBJECT_ID.match(value))


# ---------------------------------------------------------------- Jalali
# Standard arithmetic conversion (33-year cycle approximation used by most
# Iranian software; exact for 1178-1633 AP).

def g2j(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    g_d_m = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)
    gy2 = gy + 1 if gm > 2 else gy
    days = (355666 + 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100
            + (gy2 + 399) // 400 + gd + g_d_m[gm - 1])
    jy = -1595 + 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        return jy, 1 + days // 31, 1 + days % 31
    return jy, 7 + (days - 186) // 30, 1 + (days - 186) % 30


def j2g(jy: int, jm: int, jd: int) -> tuple[int, int, int]:
    jy += 1595
    days = (-355668 + 365 * jy + (jy // 33) * 8 + ((jy % 33) + 3) // 4 + jd
            + ((jm - 1) * 31 if jm < 7 else (jm - 7) * 30 + 186))
    gy = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * (days // 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365
    gd = days + 1
    leap = (gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0
    month_days = (31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    gm = 1
    for md in month_days:
        if gd <= md:
            break
        gd -= md
        gm += 1
    return gy, gm, gd


# ---------------------------------------------------------------- dates

def parse_iso(value: Any) -> datetime | None:
    """Mizito ISO string ("2026-11-10T08:30:55.426Z") or epoch ms -> aware UTC."""
    if value in (None, "", 0):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    try:
        s = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def fa_datetime(value: Any, with_time: bool = True) -> str | None:
    """UTC ISO -> Tehran local time in Jalali, e.g. '1405/08/21 14:30'."""
    dt = parse_iso(value)
    if dt is None:
        return None
    local = dt.astimezone(TEHRAN)
    jy, jm, jd = g2j(local.year, local.month, local.day)
    out = f"{jy:04d}/{jm:02d}/{jd:02d}"
    return f"{out} {local:%H:%M}" if with_time else out


_DATE_RE = re.compile(
    r"^\s*(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})"
    r"(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?\s*$")


def parse_user_datetime(value: str, *, default_hour: int = 23,
                        default_minute: int = 59) -> datetime:
    """Parse a date the agent passes in. Accepts:

    - full ISO with offset/Z ("2026-11-20T10:00:00Z") -> taken as is
    - "YYYY-MM-DD[ HH:MM]" Gregorian (year >= 1700), Tehran local time
    - "YYYY/MM/DD[ HH:MM]" Jalali (year < 1700), Tehran local time
    Persian/Arabic digits are fine. Without a time, defaults to 23:59 Tehran.
    Returns an aware UTC datetime.
    """
    if not value or not str(value).strip():
        raise ValueError("empty date")
    raw = to_ascii_digits(str(value).strip())
    if ("T" in raw and ("Z" in raw or "+" in raw[10:] or "-" in raw[10:])):
        dt = parse_iso(raw)
        if dt is None:
            raise ValueError(f"unparseable ISO datetime {value!r}")
        return dt.astimezone(timezone.utc)
    m = _DATE_RE.match(raw)
    if not m:
        raise ValueError(
            f"unrecognised date {value!r}; use 'YYYY-MM-DD HH:MM' (Gregorian), "
            "'1405/08/30 14:00' (Jalali) or full ISO with Z")
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    hh = int(m.group(4)) if m.group(4) else default_hour
    mm = int(m.group(5)) if m.group(5) else default_minute
    if y < 1700:
        if not (1 <= mo <= 12 and 1 <= d <= 31):
            raise ValueError(f"invalid Jalali date {value!r}")
        y, mo, d = j2g(y, mo, d)
    local = datetime(y, mo, d, hh, mm, tzinfo=TEHRAN)
    return local.astimezone(timezone.utc)


def to_mizito_iso(dt: datetime) -> str:
    """Aware datetime -> the JS `Date.toJSON()` format Mizito stores."""
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def today_tehran() -> date:
    return now_utc().astimezone(TEHRAN).date()


# ---------------------------------------------------------------- secrets

JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")
SECRET_KEYS = {"access_token", "token", "x-token", "x_token", "password", "pass"}


def scrub(obj: Any) -> Any:
    """Last line of defence before anything leaves the server.

    A task's `access_token` is a JWT whose payload embeds the user's session
    token, so it is as sensitive as the session itself. Drop secret-looking
    keys and blank out any JWT-shaped string.
    """
    if isinstance(obj, dict):
        return {k: scrub(v) for k, v in obj.items()
                if not (isinstance(k, str) and k.lower() in SECRET_KEYS)}
    if isinstance(obj, list):
        return [scrub(v) for v in obj]
    if isinstance(obj, tuple):
        return [scrub(v) for v in obj]
    if isinstance(obj, str) and "eyJ" in obj:
        return JWT_RE.sub("<redacted>", obj)
    return obj
