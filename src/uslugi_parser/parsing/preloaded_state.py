"""Безопасное извлечение JSON-состояния и карточек мастеров из HTML."""

from __future__ import annotations

import json
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlsplit

from uslugi_parser.exceptions import CaptchaDetected, ParseError
from uslugi_parser.parsing.urls import canonicalize_profile_url


class _ScriptExtractor(HTMLParser):
    """Собирает содержимое script по id без зависимости от полноценного DOM."""

    def __init__(self, target_id: str) -> None:
        """Настраивает извлечение содержимого единственного script с заданным id."""

        super().__init__(convert_charrefs=False)
        self.target_id = target_id
        self._capturing = False
        self._parts: list[str] = []
        self.value: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Начинает захват данных при открытии целевого тега script."""

        if tag.lower() != "script" or self.value is not None:
            return
        attributes = dict(attrs)
        if attributes.get("id") == self.target_id:
            self._capturing = True

    def handle_data(self, data: str) -> None:
        """Добавляет текстовый фрагмент, пока открыт целевой script."""

        if self._capturing:
            self._parts.append(data)

    def handle_entityref(self, name: str) -> None:
        """Сохраняет именованную HTML-сущность в исходном виде внутри script."""

        if self._capturing:
            self._parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        """Сохраняет числовую HTML-сущность в исходном виде внутри script."""

        if self._capturing:
            self._parts.append(f"&#{name};")

    def handle_endtag(self, tag: str) -> None:
        """Завершает захват и фиксирует содержимое целевого script."""

        if tag.lower() == "script" and self._capturing:
            self._capturing = False
            self.value = "".join(self._parts)


def detect_captcha(html: str) -> None:
    """Останавливает разбор при CAPTCHA, чтобы обработка завершалась безопасно."""

    head = html[:200_000].lower()
    markers = (
        "checkboxcaptcha",
        "advancedcaptcha",
        "/showcaptcha",
        "<title>ой!</title>",
    )
    if any(marker in head for marker in markers):
        raise CaptchaDetected("Yandex returned a CAPTCHA; collection was stopped")


def extract_preloaded_state(html: str) -> dict[str, Any]:
    """Извлекает и валидирует объект JSON из script ``__PRELOADED_STATE__``."""

    detect_captcha(html)
    extractor = _ScriptExtractor("__PRELOADED_STATE__")
    extractor.feed(html)
    if not extractor.value:
        raise ParseError("__PRELOADED_STATE__ was not found")
    try:
        state = json.loads(extractor.value)
    except json.JSONDecodeError as exc:
        raise ParseError("__PRELOADED_STATE__ is not valid JSON") from exc
    if not isinstance(state, dict):
        raise ParseError("__PRELOADED_STATE__ must be a JSON object")
    return state


def worker_items(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Проверяет workers.items и оставляет только объекты карточек мастеров."""

    workers = state.get("workers")
    if not isinstance(workers, dict):
        raise ParseError("workers object is missing")
    items = workers.get("items")
    if not isinstance(items, dict):
        raise ParseError("workers.items object is missing")
    return {key: value for key, value in items.items() if isinstance(value, dict)}


def source_profile_id(worker: dict[str, Any]) -> str:
    """Выбирает самый стабильный id мастера, необходимый для дедупликации."""

    # UUID мастера — основной ключ дедупликации, а seoid остаётся частью URL.
    for key in ("ydoWorkerId", "id", "seoid", "seoname"):
        value = worker.get(key)
        if value is not None and str(value).strip():
            if key == "seoname":
                import re

                suffix = re.search(r"-(\d+)$", str(value))
                if suffix:
                    return suffix.group(1)
            return str(value)
    raise ParseError("worker has no stable source id")


def find_profile_worker(state: dict[str, Any], profile_url: str) -> dict[str, Any]:
    """Находит карточку профиля по явному id, slug или безопасному fallback."""

    items = worker_items(state)
    workers = state.get("workers", {})
    selected_id = workers.get("singleSearchResultId")
    if selected_id in items:
        return items[selected_id]

    slug = urlsplit(canonicalize_profile_url(profile_url)).path.rsplit("/", 1)[-1]
    for worker in items.values():
        if worker.get("seoname") == slug or worker.get("seonameOld") == slug:
            return worker
    if len(items) == 1:
        return next(iter(items.values()))
    raise ParseError("profile worker was not found in workers.items")
