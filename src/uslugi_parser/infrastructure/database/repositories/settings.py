"""Чтение настроек парсера из общей базы данных."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from uslugi_parser.config.settings import SCRAPER_SETTING_DEFAULTS
from uslugi_parser.infrastructure.database.models import ParserSetting


class ParserSettingRepository:
    """Предоставлять парсеру доступ к настройкам только для чтения."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        """Принять фабрику коротких сессий, использующих runtime-роль парсера."""

        self.session_factory = session_factory

    def read_all(self) -> dict[str, str]:
        """Вернуть известные пары ключ-значение без изменения состояния базы данных."""

        with self.session_factory() as session:
            rows = session.execute(
                select(ParserSetting.key, ParserSetting.value).where(
                    ParserSetting.key.in_(SCRAPER_SETTING_DEFAULTS)
                )
            ).all()
        return {str(key): str(value) for key, value in rows}
