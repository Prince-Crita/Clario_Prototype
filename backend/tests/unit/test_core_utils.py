from __future__ import annotations

import logging
from datetime import UTC, date, datetime

import pytest
from cryptography.fernet import Fernet

from clario.core.crypto import DecryptionError, Encryptor, key_fingerprint
from clario.core.dates import (
    INDIA,
    DateRange,
    fiscal_year_label,
    fiscal_year_range,
    iter_month_starts,
    last_n_days,
    month_range,
    today_in,
    week_start,
)
from clario.core.errors import ValidationFailedError
from clario.core.ids import uuid7
from clario.core.logs import REDACTED, RedactingFilter, redact, redact_text
from clario.core.pagination import clamp_limit, decode_cursor, encode_cursor
from clario.core.text import normalise_typography


# ---------------------------------------------------------------- ids
def test_uuid7_version_variant_and_order() -> None:
    ids = [uuid7() for _ in range(2000)]
    assert all(i.version == 7 for i in ids)
    assert all(i.variant == "specified in RFC 4122" for i in ids)
    assert ids == sorted(ids), "UUIDv7 must be monotonic within a process"
    assert len(set(ids)) == len(ids)


# ---------------------------------------------------------------- dates
def test_today_in_uses_workspace_timezone() -> None:
    # 20:00 UTC on 25 Sep is already 26 Sep in India — the demo's date.today() bug.
    assert today_in(INDIA, datetime(2026, 9, 25, 20, 0, tzinfo=UTC)) == date(2026, 9, 26)
    with pytest.raises(ValueError, match="timezone-aware"):
        today_in(INDIA, datetime(2026, 9, 25, 20, 0))  # noqa: DTZ001


def test_fiscal_year_india() -> None:
    fy = fiscal_year_range(date(2026, 9, 26))
    assert fy == DateRange(date(2026, 4, 1), date(2027, 3, 31))
    assert fiscal_year_range(date(2026, 3, 20)).start == date(2025, 4, 1)
    assert fiscal_year_label(date(2026, 9, 26)) == "FY 2026-27"
    assert fiscal_year_label(date(2026, 9, 26), start_month=1) == "FY 2026"


def test_month_week_and_windows() -> None:
    assert month_range(date(2026, 2, 10)) == DateRange(date(2026, 2, 1), date(2026, 2, 28))
    assert list(iter_month_starts(date(2026, 3, 20), date(2026, 5, 2))) == [
        date(2026, 3, 1),
        date(2026, 4, 1),
        date(2026, 5, 1),
    ]
    assert week_start(date(2026, 9, 26)) == date(2026, 9, 21)  # Saturday → Monday
    window = last_n_days(date(2026, 9, 26), 30)
    assert window.start == date(2026, 8, 28)
    assert window.days == 30
    assert date(2026, 9, 1) in window
    with pytest.raises(ValueError, match="end must be"):
        DateRange(date(2026, 2, 1), date(2026, 1, 1))


# ---------------------------------------------------------------- crypto
def test_encrypt_decrypt_and_rotation() -> None:
    old, new = Fernet.generate_key().decode(), Fernet.generate_key().decode()
    stored = Encryptor([old]).encrypt(b"refresh-token")
    assert stored.key_id == key_fingerprint(old)

    rotated_encryptor = Encryptor([new, old])  # new key first = active; old still decrypts
    assert rotated_encryptor.decrypt(stored.ciphertext) == b"refresh-token"
    assert rotated_encryptor.needs_rotation(stored.key_id)
    rotated = rotated_encryptor.rotate(stored.ciphertext)
    assert rotated.key_id == key_fingerprint(new)
    assert Encryptor([new]).decrypt(rotated.ciphertext) == b"refresh-token"

    with pytest.raises(DecryptionError):
        Encryptor([Fernet.generate_key().decode()]).decrypt(stored.ciphertext)


# ---------------------------------------------------------------- logs
# Fake credentials are assembled at runtime so secret scanners never see key-shaped literals.
FAKE_ZOHO = "1000." + "abcdef123456"
FAKE_JWT = "eyJhbGciOiJIUzI1NiJ9"
FAKE_GROQ = "gsk" + "_" + "X" * 20
FAKE_CODE = "1000." + "secretcode"
FAKE_FERNET = "gAAAAA" + "B" * 24


@pytest.mark.parametrize(
    "text",
    [
        f"Authorization: Zoho-oauthtoken {FAKE_ZOHO}",
        f"header Bearer {FAKE_JWT}.payload.sig",
        f"key {FAKE_GROQ}",
        f"GET /callback?code={FAKE_CODE}&state=xyz",
        f"token={FAKE_FERNET}",
    ],
)
def test_redact_text_removes_credentials(text: str) -> None:
    redacted = redact_text(text)
    assert REDACTED in redacted
    for secret in (FAKE_ZOHO, FAKE_JWT, FAKE_GROQ, FAKE_CODE, FAKE_FERNET):
        assert secret not in redacted


def test_redact_structures_by_key() -> None:
    data = {
        "refresh_token": "r",
        "nested": {"client_secret": "c", "ok": "fine"},
        "items": ["Bearer abc"],
    }
    assert redact(data) == {
        "refresh_token": REDACTED,
        "nested": {"client_secret": REDACTED, "ok": "fine"},
        "items": [f"Bearer {REDACTED}"],
    }


def test_redacting_filter_scrubs_message_args_and_extras() -> None:
    record = logging.LogRecord(
        "t", logging.INFO, __file__, 1, "token is %s", ("Bearer abc123",), None
    )
    record.access_token = "leak"
    assert RedactingFilter().filter(record)
    assert "abc123" not in record.getMessage()
    assert record.access_token == REDACTED


# ---------------------------------------------------------------- pagination & text
def test_cursor_roundtrip_and_tamper() -> None:
    cursor = encode_cursor({"date": "2026-09-26", "id": "abc"})
    assert decode_cursor(cursor) == {"date": "2026-09-26", "id": "abc"}
    with pytest.raises(ValidationFailedError):
        decode_cursor("not*valid")
    with pytest.raises(ValidationFailedError):
        decode_cursor(encode_cursor({"x": 1})[:-3] + "!!!")


def test_clamp_limit() -> None:
    assert clamp_limit(None) == 50
    assert clamp_limit(1000) == 200
    with pytest.raises(ValidationFailedError):
        clamp_limit(0)


def test_normalise_typography() -> None:
    assert normalise_typography("INV‑1042 is 67 %") == "INV-1042 is 67%"
    assert normalise_typography("−₹6,48,028") == "−₹6,48,028"  # true minus is kept
