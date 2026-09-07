"""Отображение подробного прогресса массового обхода в терминале."""

from __future__ import annotations

import os
import sys
from types import TracebackType
from typing import TextIO

from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text

from uslugi_parser.application import CrawlProgressEvent

_STAGE_LABELS = {
    "started": "Подготовка обхода",
    "target_started": "Переход к рубрике",
    "page_fetching": "Загрузка страницы каталога",
    "page_parsed": "Страница каталога разобрана",
    "profile_started": "Загрузка карточки мастера",
    "profile_completed": "Карточка обработана",
    "page_completed": "Страница обработана",
    "target_completed": "Рубрика обработана",
    "completed": "Обход завершён",
}

_OUTCOME_LABELS = {
    "created": "создан",
    "updated": "обновлён",
    "dry_run": "проверен без записи",
    "skipped": "пропущен",
    "category_mismatch": "не соответствует рубрике",
    "limit_reached": "достигнут лимит профилей",
}


class ConsoleCrawlProgress:
    """Рисовать три прогресс-бара и актуальные счётчики обхода в ``stderr``."""

    def __init__(
        self,
        *,
        force: bool | None = None,
        stream: TextIO | None = None,
    ) -> None:
        """Выбрать поток и включить автоотображение только для интерактивного TTY."""

        self.stream = stream or sys.stderr
        interactive = bool(getattr(self.stream, "isatty", lambda: False)())
        self.interactive = interactive
        self.enabled = (
            force
            if force is not None
            else interactive and os.environ.get("TERM", "").casefold() != "dumb"
        )
        self.console = Console(file=self.stream, force_terminal=interactive)
        self._live: Live | None = None
        self._event: CrawlProgressEvent | None = None
        self._failed = False

        columns = (
            TextColumn("{task.description}", justify="right"),
            BarColumn(bar_width=None),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
        )
        self._targets = Progress(*columns, console=self.console, auto_refresh=False, expand=True)
        self._pages = Progress(*columns, console=self.console, auto_refresh=False, expand=True)
        self._profiles = Progress(*columns, console=self.console, auto_refresh=False, expand=True)
        self._target_task = self._targets.add_task("Цели", total=None)
        self._page_task = self._pages.add_task("Страницы", total=None)
        self._profile_task = self._profiles.add_task("Профили", total=None)

    def __enter__(self) -> ConsoleCrawlProgress:
        """Запустить динамическую область терминала перед сетевым обходом."""

        if self.enabled and self.interactive:
            self._live = Live(
                self._render(),
                console=self.console,
                refresh_per_second=8,
                transient=False,
                redirect_stdout=False,
                redirect_stderr=False,
            )
            self._live.start(refresh=True)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        """Зафиксировать финальный успешный или аварийный вид и освободить терминал."""

        if not self.enabled:
            return
        self._failed = exc_type is not None
        self._refresh()
        if self._live is not None:
            self._live.stop()
            self._live = None
        elif self.enabled:
            self.console.print(self._render())

    def __call__(self, event: CrawlProgressEvent) -> None:
        """Принять снимок сценария, обновить шкалы и немедленно перерисовать экран."""

        if not self.enabled:
            return
        self._event = event
        if event.stage == "target_started":
            self._pages.reset(self._page_task, total=None, completed=0, start=True)
            self._profiles.reset(self._profile_task, total=None, completed=0, start=True)
        if event.stage == "page_fetching":
            self._profiles.reset(self._profile_task, total=None, completed=0, start=True)

        targets_completed = event.target_index
        if event.stage not in {"target_completed", "completed"}:
            targets_completed = max(0, event.target_index - 1)
        self._targets.update(
            self._target_task,
            total=event.targets_total or None,
            completed=targets_completed,
        )

        pages_completed = event.page_number
        if event.stage == "page_fetching":
            pages_completed = max(0, event.page_number - 1)
        self._pages.update(
            self._page_task,
            total=event.pages_total,
            completed=pages_completed,
        )

        profiles_completed = event.profile_index
        if event.stage == "profile_started":
            profiles_completed = max(0, event.profile_index - 1)
        self._profiles.update(
            self._profile_task,
            total=event.profiles_total or None,
            completed=profiles_completed,
        )
        self._refresh()

    def _refresh(self) -> None:
        """Передать Live новый безопасно сформированный набор строк и таблиц."""

        if self._live is not None:
            self._live.update(self._render(), refresh=True)

    def _render(self) -> RenderableType:
        """Собрать панель без интерпретации пользовательских названий как Rich markup."""

        event = self._event
        status = "Ожидание запуска"
        category = "—"
        target = "—"
        if event is not None:
            status = _STAGE_LABELS[event.stage]
            if event.outcome:
                status = f"{status}: {_OUTCOME_LABELS.get(event.outcome, event.outcome)}"
            if event.category_name:
                category = event.category_name
                if event.categories_total:
                    category += f" ({event.category_index}/{event.categories_total})"
            if event.target_rubric_number_id is not None:
                target = f"№ {event.target_rubric_number_id}"
        if self._failed:
            status = "Остановлено с ошибкой"

        details = Table.grid(expand=True, padding=(0, 1))
        details.add_column(style="bold cyan", no_wrap=True)
        details.add_column(ratio=1)
        details.add_column(style="bold cyan", no_wrap=True)
        details.add_column(ratio=1)
        details.add_row("Категория", Text(category), "Рубрика", Text(target))
        mode = "без записи (dry-run)" if event and event.dry_run else "запись в MySQL"
        details.add_row("Этап", Text(status), "Режим", mode)

        counters = Table.grid(expand=True, padding=(0, 1))
        for _ in range(7):
            counters.add_column(justify="center", ratio=1)
        if event is None:
            values = (0, 0, 0, 0, 0, 0, 0)
        else:
            skipped = (
                event.skipped_organizations + event.skipped_category_mismatch + event.robots_denied
            )
            values = (
                event.discovered,
                event.fetched,
                event.parsed,
                event.created,
                event.updated,
                skipped,
                event.failed,
            )
        labels = (
            "Найдено",
            "Загружено",
            "Разобрано",
            "Создано",
            "Обновлено",
            "Пропущено",
            "Ошибки",
        )
        counters.add_row(*(Text(label, style="dim") for label in labels))
        counters.add_row(*(Text(str(value), style="bold") for value in values))

        border_style = "blue"
        if self._failed:
            border_style = "red"
        elif event and event.stage == "completed":
            border_style = "green"
        return Panel(
            Group(details, self._targets, self._pages, self._profiles, counters),
            title="[bold]Парсер мастеров Яндекс.Услуг[/bold]",
            border_style=border_style,
            padding=(0, 1),
        )
