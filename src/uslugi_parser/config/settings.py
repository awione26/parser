"""Загрузка, проверка и переопределение настроек парсера."""

from __future__ import annotations

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass, replace

from dotenv import load_dotenv

from uslugi_parser.catalog import validate_geo_slug
from uslugi_parser.config.database import database_url_from_env
from uslugi_parser.exceptions import ConfigurationError

SCRAPER_SETTING_DEFAULTS: dict[str, str] = {
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

_SCRAPER_SETTING_FIELDS = {
    "SCRAPER_USER_AGENT": "user_agent",
    "SCRAPER_GEO": "geo",
    "SCRAPER_RESPECT_ROBOTS": "respect_robots",
    "SCRAPER_MIN_DELAY_SECONDS": "min_delay_seconds",
    "SCRAPER_MAX_DELAY_SECONDS": "max_delay_seconds",
    "SCRAPER_TIMEOUT_SECONDS": "timeout_seconds",
    "SCRAPER_MAX_RETRIES": "max_retries",
    "SCRAPER_COLLECT_PHONE": "collect_phone",
    "SCRAPER_PHONE_HEADLESS": "phone_headless",
    "SCRAPER_PHONE_TIMEOUT_SECONDS": "phone_timeout_seconds",
    "SCRAPER_INCLUDE_ORGANIZATIONS": "include_organizations",
}
_BOOLEAN_SETTINGS = frozenset(
    {
        "SCRAPER_RESPECT_ROBOTS",
        "SCRAPER_COLLECT_PHONE",
        "SCRAPER_PHONE_HEADLESS",
        "SCRAPER_INCLUDE_ORGANIZATIONS",
    }
)
_FLOAT_SETTINGS = frozenset(
    {
        "SCRAPER_MIN_DELAY_SECONDS",
        "SCRAPER_MAX_DELAY_SECONDS",
        "SCRAPER_TIMEOUT_SECONDS",
        "SCRAPER_PHONE_TIMEOUT_SECONDS",
    }
)


def _parse_bool(name: str, value: str) -> bool:
    """Преобразовать строку окружения или БД в строгое булево значение."""

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{name} must be true or false, got {value!r}")


def _env_bool(name: str, default: bool) -> bool:
    """Читает булеву переменную, использует default при её отсутствии и отклоняет иное."""

    value = os.getenv(name)
    if value is None:
        return default
    return _parse_bool(name, value)


def _parse_float(name: str, value: str) -> float:
    """Преобразовать строковую настройку в число и дать понятную ошибку формата."""

    try:
        return float(value.strip())
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"{name} must be a number, got {value!r}") from exc


def _parse_int(name: str, value: str) -> int:
    """Преобразовать строковую настройку в целое число без неявного округления."""

    try:
        return int(value.strip())
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"{name} must be an integer, got {value!r}") from exc


def _parse_scraper_values(values: Mapping[str, str]) -> dict[str, object]:
    """Проверить имена и типы строковых SCRAPER-настроек и собрать поля dataclass."""

    unknown = sorted(set(values) - SCRAPER_SETTING_DEFAULTS.keys())
    if unknown:
        raise ConfigurationError(f"unknown scraper settings: {', '.join(unknown)}")

    changes: dict[str, object] = {}
    for name, value in values.items():
        if not isinstance(value, str):
            raise ConfigurationError(f"{name} must be stored as text")
        if name in _BOOLEAN_SETTINGS:
            parsed: object = _parse_bool(name, value)
        elif name in _FLOAT_SETTINGS:
            parsed = _parse_float(name, value)
        elif name == "SCRAPER_MAX_RETRIES":
            parsed = _parse_int(name, value)
        else:
            parsed = value.strip()
        changes[_SCRAPER_SETTING_FIELDS[name]] = parsed
    return changes


def bootstrap_database_url_from_env() -> str:
    """Загрузить .env и вернуть DSN без разбора операционных SCRAPER-параметров."""

    load_dotenv()
    return database_url_from_env()


@dataclass(frozen=True, slots=True)
class Settings:
    """Хранит настройки парсера и явные предохранители живого сбора.

    Фабрики :meth:`from_env`, :meth:`from_database_values` и :meth:`with_overrides`
    возвращают уже проверенные экземпляры; при прямом создании проверку нужно
    вызвать явно.
    """

    database_url: str
    user_agent: str
    geo: str
    operator_permission: bool
    phone_permission: bool
    respect_robots: bool
    min_delay_seconds: float
    max_delay_seconds: float
    timeout_seconds: float
    max_retries: int
    collect_phone: bool
    phone_headless: bool
    phone_timeout_seconds: float
    include_organizations: bool

    @classmethod
    def _from_scraper_values(
        cls,
        *,
        database_url: str,
        scraper_values: Mapping[str, str],
    ) -> Settings:
        """Собрать экземпляр из DSN, env-разрешений и выбранного источника SCRAPER-значений."""

        parsed = _parse_scraper_values(scraper_values)
        settings = cls(
            database_url=database_url,
            user_agent=str(parsed["user_agent"]),
            geo=str(parsed["geo"]),
            operator_permission=_env_bool("YANDEX_OPERATOR_PERMISSION", False),
            phone_permission=_env_bool("YANDEX_PHONE_PERMISSION", False),
            respect_robots=bool(parsed["respect_robots"]),
            min_delay_seconds=float(parsed["min_delay_seconds"]),
            max_delay_seconds=float(parsed["max_delay_seconds"]),
            timeout_seconds=float(parsed["timeout_seconds"]),
            max_retries=int(parsed["max_retries"]),
            collect_phone=bool(parsed["collect_phone"]),
            phone_headless=bool(parsed["phone_headless"]),
            phone_timeout_seconds=float(parsed["phone_timeout_seconds"]),
            include_organizations=bool(parsed["include_organizations"]),
        )
        settings.validate()
        return settings

    @classmethod
    def from_env(cls) -> Settings:
        """Загружает .env, читает переменные окружения и возвращает проверенные настройки."""

        load_dotenv()
        scraper_values = {
            name: os.getenv(name, default) for name, default in SCRAPER_SETTING_DEFAULTS.items()
        }
        return cls._from_scraper_values(
            database_url=database_url_from_env(),
            scraper_values=scraper_values,
        )

    @classmethod
    def from_database_values(
        cls,
        database_url: str,
        values: Mapping[str, str],
    ) -> Settings:
        """Собрать настройки из БД, дополнив отсутствующие строки каноническими defaults."""

        load_dotenv()
        database_values = dict(SCRAPER_SETTING_DEFAULTS)
        database_values.update(values)
        return cls._from_scraper_values(
            database_url=database_url,
            scraper_values=database_values,
        )

    def validate(self) -> None:
        """Проверить User-Agent, geo slug и безопасные числовые диапазоны."""

        if not 3 <= len(self.user_agent) <= 512 or not self.user_agent.strip():
            raise ConfigurationError("SCRAPER_USER_AGENT must contain 3 to 512 characters")
        if any(not 32 <= ord(character) <= 126 for character in self.user_agent):
            raise ConfigurationError("SCRAPER_USER_AGENT must contain printable ASCII only")
        try:
            validate_geo_slug(self.geo)
        except ValueError as exc:
            raise ConfigurationError(str(exc)) from exc
        numeric_values = {
            "SCRAPER_MIN_DELAY_SECONDS": self.min_delay_seconds,
            "SCRAPER_MAX_DELAY_SECONDS": self.max_delay_seconds,
            "SCRAPER_TIMEOUT_SECONDS": self.timeout_seconds,
            "SCRAPER_PHONE_TIMEOUT_SECONDS": self.phone_timeout_seconds,
        }
        if any(not math.isfinite(value) for value in numeric_values.values()):
            invalid = ", ".join(
                name for name, value in numeric_values.items() if not math.isfinite(value)
            )
            raise ConfigurationError(f"numeric settings must be finite: {invalid}")
        if not 0 <= self.min_delay_seconds <= 3600:
            raise ConfigurationError("SCRAPER_MIN_DELAY_SECONDS must be between 0 and 3600")
        if self.max_delay_seconds < self.min_delay_seconds:
            raise ConfigurationError(
                "SCRAPER_MAX_DELAY_SECONDS must be >= SCRAPER_MIN_DELAY_SECONDS"
            )
        if self.max_delay_seconds > 3600:
            raise ConfigurationError("SCRAPER_MAX_DELAY_SECONDS must not exceed 3600")
        if not 0 < self.timeout_seconds <= 300:
            raise ConfigurationError("SCRAPER_TIMEOUT_SECONDS must be > 0 and <= 300")
        if not 0 < self.phone_timeout_seconds <= 300:
            raise ConfigurationError("SCRAPER_PHONE_TIMEOUT_SECONDS must be > 0 and <= 300")
        if not 0 <= self.max_retries <= 10:
            raise ConfigurationError("SCRAPER_MAX_RETRIES must be between 0 and 10")

    def require_live_permission(self) -> None:
        """Запрещает живой сбор без явно подтверждённого разрешения оператора."""

        if not self.operator_permission:
            raise ConfigurationError(
                "Live collection is disabled. Obtain written permission from the Yandex "
                "Services operator, then set YANDEX_OPERATOR_PERMISSION=true."
            )

    def require_phone_reveal_permission(self) -> None:
        """Проверяет разрешения на живой сбор и контакты, а также допустимость robots policy."""

        self.require_live_permission()
        if not self.phone_permission:
            raise ConfigurationError(
                "Phone collection is disabled. Confirm that permission and your lawful basis "
                "cover contact data, then set YANDEX_PHONE_PERMISSION=true."
            )
        if self.respect_robots:
            raise ConfigurationError(
                "The current phone reveal uses a route disallowed by robots.txt. It remains "
                "disabled while SCRAPER_RESPECT_ROBOTS=true."
            )

    def with_overrides(self, **changes: object) -> Settings:
        """Создаёт проверенную копию настроек с переданными точечными изменениями."""

        updated = replace(self, **changes)
        updated.validate()
        return updated

    def with_database_values(self, values: Mapping[str, str]) -> Settings:
        """Наложить значения из БД поверх окружения и строго проверить итоговый набор."""

        return self.with_overrides(**_parse_scraper_values(values))
