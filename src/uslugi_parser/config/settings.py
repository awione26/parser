"""Загрузка, проверка и переопределение настроек парсера."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, replace

from dotenv import load_dotenv

from uslugi_parser.catalog import validate_geo_slug
from uslugi_parser.config.database import database_url_from_env
from uslugi_parser.exceptions import ConfigurationError


def _env_bool(name: str, default: bool) -> bool:
    """Читает булеву переменную, использует default при её отсутствии и отклоняет иное."""

    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{name} must be true or false, got {value!r}")


@dataclass(frozen=True, slots=True)
class Settings:
    """Хранит настройки парсера и явные предохранители живого сбора.

    Фабрики :meth:`from_env` и :meth:`with_overrides` возвращают уже проверенные
    экземпляры; при прямом создании проверку нужно вызвать явно.
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
    def from_env(cls) -> Settings:
        """Загружает .env, читает переменные окружения и возвращает проверенные настройки."""

        load_dotenv()
        settings = cls(
            database_url=database_url_from_env(),
            user_agent=os.getenv("SCRAPER_USER_AGENT", "UslugiParser/0.1"),
            geo=os.getenv("SCRAPER_GEO", "213-moscow"),
            operator_permission=_env_bool("YANDEX_OPERATOR_PERMISSION", False),
            phone_permission=_env_bool("YANDEX_PHONE_PERMISSION", False),
            respect_robots=_env_bool("SCRAPER_RESPECT_ROBOTS", True),
            min_delay_seconds=float(os.getenv("SCRAPER_MIN_DELAY_SECONDS", "2.0")),
            max_delay_seconds=float(os.getenv("SCRAPER_MAX_DELAY_SECONDS", "5.0")),
            timeout_seconds=float(os.getenv("SCRAPER_TIMEOUT_SECONDS", "30.0")),
            max_retries=int(os.getenv("SCRAPER_MAX_RETRIES", "3")),
            collect_phone=_env_bool("SCRAPER_COLLECT_PHONE", False),
            phone_headless=_env_bool("SCRAPER_PHONE_HEADLESS", True),
            phone_timeout_seconds=float(os.getenv("SCRAPER_PHONE_TIMEOUT_SECONDS", "15.0")),
            include_organizations=_env_bool("SCRAPER_INCLUDE_ORGANIZATIONS", False),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        """Проверяет geo slug, конечность чисел, интервалы задержек и тайм-ауты."""

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
        if self.min_delay_seconds < 0:
            raise ConfigurationError("SCRAPER_MIN_DELAY_SECONDS cannot be negative")
        if self.max_delay_seconds < self.min_delay_seconds:
            raise ConfigurationError(
                "SCRAPER_MAX_DELAY_SECONDS must be >= SCRAPER_MIN_DELAY_SECONDS"
            )
        if self.timeout_seconds <= 0 or self.phone_timeout_seconds <= 0:
            raise ConfigurationError("timeouts must be positive")
        if self.max_retries < 0:
            raise ConfigurationError("SCRAPER_MAX_RETRIES cannot be negative")

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
