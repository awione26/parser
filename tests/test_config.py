from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

import pytest

from uslugi_parser.config import ConfigurationError, Settings
from uslugi_parser.config.settings import SCRAPER_SETTING_DEFAULTS


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


def test_geo_cannot_exceed_database_form_limit() -> None:
    """Отклонить формально корректный slug длиннее лимита формы и БД."""

    with pytest.raises(ConfigurationError, match="128"):
        replace(settings(), geo=f"1-{'a' * 127}").validate()


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


def test_database_values_override_all_scraper_environment_fields() -> None:
    """Проверить преобразование всех одиннадцати значений БД в поля Settings."""

    updated = settings().with_database_values(
        {
            "SCRAPER_USER_AGENT": "DatabaseParser/2.0 (+mailto:owner@example.test)",
            "SCRAPER_GEO": "2-sankt-peterburg",
            "SCRAPER_RESPECT_ROBOTS": "false",
            "SCRAPER_MIN_DELAY_SECONDS": "1.25",
            "SCRAPER_MAX_DELAY_SECONDS": "4.5",
            "SCRAPER_TIMEOUT_SECONDS": "21",
            "SCRAPER_MAX_RETRIES": "7",
            "SCRAPER_COLLECT_PHONE": "true",
            "SCRAPER_PHONE_HEADLESS": "false",
            "SCRAPER_PHONE_TIMEOUT_SECONDS": "11.5",
            "SCRAPER_INCLUDE_ORGANIZATIONS": "true",
        }
    )

    assert updated.user_agent == "DatabaseParser/2.0 (+mailto:owner@example.test)"
    assert updated.geo == "2-sankt-peterburg"
    assert updated.respect_robots is False
    assert updated.min_delay_seconds == 1.25
    assert updated.max_delay_seconds == 4.5
    assert updated.timeout_seconds == 21
    assert updated.max_retries == 7
    assert updated.collect_phone is True
    assert updated.phone_headless is False
    assert updated.phone_timeout_seconds == 11.5
    assert updated.include_organizations is True
    assert updated.operator_permission is False
    assert updated.phone_permission is False


def test_missing_database_values_keep_environment_fallback() -> None:
    """Проверить, что отсутствующая строка БД не затирает значение окружения."""

    base = settings()
    updated = base.with_database_values({"SCRAPER_GEO": "54-ekaterinburg"})

    assert updated.geo == "54-ekaterinburg"
    assert updated.user_agent == base.user_agent
    assert updated.timeout_seconds == base.timeout_seconds


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("SCRAPER_RESPECT_ROBOTS", "sometimes", "must be true or false"),
        ("SCRAPER_MIN_DELAY_SECONDS", "fast", "must be a number"),
        ("SCRAPER_MAX_RETRIES", "1.5", "must be an integer"),
        ("SCRAPER_USER_AGENT", "line one\nline two", "printable ASCII"),
        ("SCRAPER_USER_AGENT", "Parser\t1.0", "printable ASCII"),
        ("SCRAPER_USER_AGENT", "Парсер/1.0", "printable ASCII"),
        ("SCRAPER_USER_AGENT", "ab", "3 to 512"),
        ("SCRAPER_USER_AGENT", "A" * 513, "3 to 512"),
        ("SCRAPER_USER_AGENT", "   ", "3 to 512"),
    ],
)
def test_database_values_are_strictly_validated(name: str, value: str, message: str) -> None:
    """Отклонить повреждённые значения БД до запуска сетевого сценария."""

    with pytest.raises(ConfigurationError, match=message):
        settings().with_database_values({name: value})


def test_database_values_reject_unknown_setting_key() -> None:
    """Не принимать произвольные ключи даже при ручном изменении таблицы."""

    with pytest.raises(ConfigurationError, match="unknown scraper settings"):
        settings().with_database_values({"SCRAPER_UNEXPECTED_SECRET": "value"})


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("min_delay_seconds", -0.1, "SCRAPER_MIN_DELAY_SECONDS"),
        ("min_delay_seconds", 3600.1, "SCRAPER_MIN_DELAY_SECONDS"),
        ("max_delay_seconds", 3600.1, "SCRAPER_MAX_DELAY_SECONDS"),
        ("timeout_seconds", 0, "SCRAPER_TIMEOUT_SECONDS"),
        ("timeout_seconds", 300.1, "SCRAPER_TIMEOUT_SECONDS"),
        ("phone_timeout_seconds", 0, "SCRAPER_PHONE_TIMEOUT_SECONDS"),
        ("phone_timeout_seconds", 300.1, "SCRAPER_PHONE_TIMEOUT_SECONDS"),
        ("max_retries", -1, "SCRAPER_MAX_RETRIES"),
        ("max_retries", 11, "SCRAPER_MAX_RETRIES"),
    ],
)
def test_scraper_numeric_limits_match_admin_contract(
    field: str,
    value: float | int,
    message: str,
) -> None:
    """Отклонить значения вне диапазонов, разрешённых формой админки."""

    with pytest.raises(ConfigurationError, match=message):
        replace(settings(), **{field: value}).validate()


def test_scraper_defaults_match_database_bootstrap_contract() -> None:
    """Зафиксировать полный набор и канонические форматы начальных значений."""

    assert SCRAPER_SETTING_DEFAULTS == {
        "SCRAPER_USER_AGENT": ("CompanyName-UslugiParser/0.1 (+mailto:parser-owner@example.com)"),
        "SCRAPER_GEO": "213-moscow",
        "SCRAPER_RESPECT_ROBOTS": "true",
        "SCRAPER_MIN_DELAY_SECONDS": "2.0",
        "SCRAPER_MAX_DELAY_SECONDS": "5.0",
        "SCRAPER_TIMEOUT_SECONDS": "30.0",
        "SCRAPER_MAX_RETRIES": "3",
        "SCRAPER_COLLECT_PHONE": "false",
        "SCRAPER_PHONE_HEADLESS": "true",
        "SCRAPER_PHONE_TIMEOUT_SECONDS": "15.0",
        "SCRAPER_INCLUDE_ORGANIZATIONS": "false",
    }


def test_laravel_and_python_share_the_same_setting_defaults() -> None:
    """Не позволить PHP-форме и Python-парсеру незаметно разойтись по defaults."""

    support_file = (
        Path(__file__).resolve().parents[1] / "admin/app/Support/ParserSettings.php"
    ).read_text(encoding="utf-8")
    php_defaults = dict(re.findall(r"'(SCRAPER_[A-Z_]+)'\s*=>\s*'([^']*)'", support_file))

    assert php_defaults == SCRAPER_SETTING_DEFAULTS
