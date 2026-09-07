from __future__ import annotations

from io import StringIO

import pytest

from uslugi_parser.application import CrawlProgressEvent
from uslugi_parser.cli.progress import ConsoleCrawlProgress
from uslugi_parser.domain import CrawlStats


def event(stage: str, **changes: object) -> CrawlProgressEvent:
    """Собрать небольшой снимок прогресса для проверки консольного адаптера."""

    values = {
        "stage": stage,
        "stats": CrawlStats(discovered=8, fetched=4, parsed=3, created=1, updated=2),
        "categories_total": 2,
        "category_index": 1,
        "category_key": "plumbers",
        "category_name": "Сантехник",
        "targets_total": 3,
        "target_index": 1,
        "target_rubric_number_id": 1844,
        "page_number": 1,
        "pages_total": 2,
        "profile_index": 3,
        "profiles_total": 8,
    }
    values.update(changes)
    return CrawlProgressEvent.from_stats(**values)


def test_console_progress_renders_detailed_terminal_state() -> None:
    """Показывать три шкалы, текущую рубрику и накопленные счётчики."""

    output = StringIO()
    reporter = ConsoleCrawlProgress(force=True, stream=output)

    with reporter:
        reporter(event("target_started", page_number=0, pages_total=None, profile_index=0))
        reporter(event("profile_completed", outcome="created"))
        reporter(
            event(
                "completed",
                target_index=3,
                page_number=2,
                profile_index=8,
            )
        )

    rendered = output.getvalue()
    assert "Парсер мастеров Яндекс.Услуг" in rendered
    assert "Сантехник (1/2)" in rendered
    assert "№ 1844" in rendered
    assert "Цели" in rendered
    assert "Страницы" in rendered
    assert "Профили" in rendered
    assert "Найдено" in rendered
    assert "Загружено" in rendered
    assert "Создано" in rendered
    assert "запись в MySQL" in rendered
    assert "Обход завершён" in rendered


def test_console_progress_can_be_disabled_explicitly() -> None:
    """Не печатать служебные строки в полностью машинном режиме."""

    output = StringIO()
    reporter = ConsoleCrawlProgress(force=False, stream=output)

    with reporter:
        reporter(event("completed", target_index=3))

    assert output.getvalue() == ""


def test_console_progress_keeps_failure_visible() -> None:
    """Завершать Live-панель красным аварийным состоянием при исключении сценария."""

    output = StringIO()
    reporter = ConsoleCrawlProgress(force=True, stream=output)

    with pytest.raises(RuntimeError, match="network stopped"):
        with reporter:
            reporter(event("page_fetching", pages_total=None, profile_index=0))
            raise RuntimeError("network stopped")

    assert "Остановлено с ошибкой" in output.getvalue()
