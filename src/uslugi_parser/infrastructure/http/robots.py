"""Хранение и проверка правил robots.txt для разрешённого источника."""

from __future__ import annotations

from urllib.parse import urlsplit

from protego import Protego

from uslugi_parser.exceptions import FetchError


class RobotsPolicy:
    """Хранить разобранные robots.txt и проверять допустимость URL для агента."""

    def __init__(self, user_agent: str) -> None:
        """Создать реестр политик для указанного User-Agent парсера."""

        self.user_agent = user_agent
        self._parsers: dict[str, Protego] = {}

    def add(self, origin: str, text: str) -> None:
        """Разобрать robots.txt и связать полученную политику с origin."""

        self._parsers[origin] = Protego.parse(text)

    def allowed(self, url: str) -> bool:
        """Проверить, разрешает ли загруженная политика обращение к URL."""

        parsed = urlsplit(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        parser = self._parsers.get(origin)
        if parser is None:
            raise FetchError(f"robots.txt for {origin} has not been loaded")
        return parser.can_fetch(url, self.user_agent)
