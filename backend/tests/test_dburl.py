"""Database URL normalisation for Neon / asyncpg (pure functions: no database needed)."""

import pytest

from clario.core.dburl import (
    describe,
    direct_database_url,
    engine_options,
    is_pooled,
    normalize_database_url,
)

POOLED = (
    "postgresql://owner:s3cret_pw@ep-quiet-sound-a1b2c3d4-pooler.c-4.ap-southeast-1.aws.neon.tech"
    "/appdb?sslmode=require&channel_binding=require"
)


def test_normalises_a_neon_url_for_asyncpg() -> None:
    url = normalize_database_url(POOLED)
    assert url.startswith("postgresql+asyncpg://owner:s3cret_pw@ep-quiet-sound-a1b2c3d4-pooler.")
    assert "ssl=require" in url
    assert "sslmode" not in url
    assert "channel_binding" not in url  # libpq-only; asyncpg would reject it


@pytest.mark.parametrize("scheme", ["postgres", "postgresql", "postgresql+asyncpg"])
def test_accepts_every_postgres_scheme_and_is_idempotent(scheme: str) -> None:
    once = normalize_database_url(f"{scheme}://u:p@localhost:5432/clario_dev")
    assert once == "postgresql+asyncpg://u:p@localhost:5432/clario_dev"
    assert normalize_database_url(once) == once


@pytest.mark.parametrize(
    "bad", ["", "not a url", "mysql://u:p@h/db", "postgresql://u:p@h/db?sslmode=bogus"]
)
def test_rejects_non_postgres_urls_without_echoing_them(bad: str) -> None:
    with pytest.raises(ValueError, match=r"database URL|PostgreSQL URL|sslmode") as caught:
        normalize_database_url(bad)
    assert bad == "" or bad not in str(caught.value)


def test_pooled_and_direct_endpoints() -> None:
    assert is_pooled(POOLED)
    direct = direct_database_url(POOLED)
    assert not is_pooled(direct)
    assert "@ep-quiet-sound-a1b2c3d4.c-4.ap-southeast-1.aws.neon.tech/" in direct
    assert "s3cret_pw" in direct  # credentials carried over
    assert "ssl=require" in direct  # and TLS stays required
    assert direct_database_url(direct) == direct  # already direct: unchanged


def test_local_urls_are_direct_and_need_no_engine_options() -> None:
    local = "postgresql+asyncpg://u:p@localhost:5432/clario_dev"
    assert not is_pooled(local)
    assert direct_database_url(local) == local
    assert engine_options(local) == {}


def test_pooled_endpoints_disable_prepared_statement_caches() -> None:
    args = engine_options(POOLED)["connect_args"]
    assert args["statement_cache_size"] == 0
    assert args["prepared_statement_cache_size"] == 0
    assert args["prepared_statement_name_func"]() != args["prepared_statement_name_func"]()


def test_describe_never_contains_the_credentials() -> None:
    text = describe(POOLED)
    assert "s3cret_pw" not in text
    assert "owner" not in text
    assert text.endswith("/appdb (pooled)")
