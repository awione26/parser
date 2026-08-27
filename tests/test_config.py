from __future__ import annotations

from dataclasses import replace

import pytest

from uslugi_parser.config import ConfigurationError, Settings


def settings() -> Settings:
    return Settings(
        database_url="sqlite+pysqlite:///:memory:",
        user_agent="TestParser/1.0",
        geo="213-moscow",
        operator_permission=False,
        phone_permission=False,
        respect_robots=True,
        min_delay_seconds=0,
        max_delay_seconds=0,
        timeout_seconds=1,
        max_retries=0,
        collect_phone=False,
        phone_headless=True,
        phone_timeout_seconds=1,
        include_organizations=False,
    )


def test_live_and_phone_permission_gates() -> None:
    base = settings()
    with pytest.raises(ConfigurationError, match="Live collection is disabled"):
        base.require_live_permission()

    live = replace(base, operator_permission=True)
    live.require_live_permission()
    with pytest.raises(ConfigurationError, match="Phone collection is disabled"):
        live.require_phone_reveal_permission()

    phone_allowed = replace(
        live,
        phone_permission=True,
    )
    with pytest.raises(ConfigurationError, match="robots.txt"):
        phone_allowed.require_phone_reveal_permission()

    replace(phone_allowed, respect_robots=False).require_phone_reveal_permission()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("min_delay_seconds", float("nan")),
        ("max_delay_seconds", float("inf")),
        ("timeout_seconds", float("nan")),
        ("phone_timeout_seconds", float("inf")),
    ],
)
def test_numeric_settings_must_be_finite(field: str, value: float) -> None:
    with pytest.raises(ConfigurationError, match="must be finite"):
        replace(settings(), **{field: value}).validate()


def test_geo_cannot_change_request_origin() -> None:
    with pytest.raises(ConfigurationError, match="213-moscow"):
        replace(settings(), geo="/evil.example").validate()


def test_local_database_url_percent_encodes_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("MYSQL_PASSWORD", "space and/slash")
    monkeypatch.setenv("MYSQL_HOST", "mysql")
    monkeypatch.setenv("MYSQL_DATABASE", "uslugi-container")
    loaded = Settings.from_env()
    assert "space%20and%2Fslash" in loaded.database_url
    assert "@mysql:3306/uslugi-container" in loaded.database_url


@pytest.mark.parametrize("port", ["not-a-port", "0", "65536"])
def test_mysql_port_must_be_valid(monkeypatch: pytest.MonkeyPatch, port: str) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("MYSQL_PORT", port)
    with pytest.raises(ValueError, match="MYSQL_PORT"):
        Settings.from_env()


def test_mysql_host_cannot_inject_a_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("MYSQL_HOST", "mysql/other-db")
    with pytest.raises(ValueError, match="MYSQL_HOST"):
        Settings.from_env()
