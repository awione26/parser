"""Прикладной сервис журналирования полного жизненного цикла запуска."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol, TypeAlias

from uslugi_parser.domain import (
    PARSER_RESOURCE,
    ParserRunCompletion,
    ParserRunStart,
)

ERROR_REASON_MAX_LENGTH = 2000
_DATABASE_MODULES = ("pymysql", "sqlalchemy")
_SECRET_PATTERN = re.compile(
    r"(?i)\b(password|passwd|token|secret|api[_-]?key)\s*[:=]\s*([^\s,;]+)"
)
_URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)
_PHONE_PATTERN = re.compile(r"(?<!\w)\+?\d(?:[\s().-]*\d){7,15}(?!\w)")

Clock: TypeAlias = Callable[[], datetime]


class ParserLogWriter(Protocol):
    """Задавать порт создания и завершения записи о запуске парсера."""

    def start(self, run: ParserRunStart) -> int:
        """Создать незавершённую запись и вернуть её идентификатор."""

        ...

    def finish(self, run_id: int, completion: ParserRunCompletion) -> None:
        """Атомарно зафиксировать окончательный результат указанного запуска."""

        ...


def utcnow() -> datetime:
    """Вернуть текущее UTC-время без timezone для MySQL DATETIME."""

    return datetime.now(UTC).replace(tzinfo=None)


def safe_failure_reason(error: BaseException) -> str:
    """Сформировать ограниченную причину ошибки без URL, телефонов и секретов."""

    error_type = type(error).__name__
    module = type(error).__module__.casefold()
    if module.startswith(_DATABASE_MODULES):
        message = "Ошибка базы данных."
    else:
        message = " ".join(str(error).split()) or "Ошибка без текстового описания."
        message = _SECRET_PATTERN.sub(lambda match: f"{match.group(1)}=[СКРЫТО]", message)
        message = _URL_PATTERN.sub("[URL СКРЫТ]", message)
        message = _PHONE_PATTERN.sub("[ТЕЛЕФОН СКРЫТ]", message)

    reason = f"{error_type}: {message}"
    if len(reason) <= ERROR_REASON_MAX_LENGTH:
        return reason
    return reason[: ERROR_REASON_MAX_LENGTH - 1].rstrip() + "…"


class ParserRunService:
    """Выполнять операцию и независимо фиксировать начало и её итог в БД."""

    def __init__(
        self,
        writer: ParserLogWriter,
        *,
        resource: str = PARSER_RESOURCE,
        clock: Clock = utcnow,
    ) -> None:
        """Принять порт хранения, имя ресурса и заменяемые часы."""

        self.writer = writer
        self.resource = resource
        self.clock = clock

    def execute(self, operation: Callable[[], int]) -> int:
        """Выполнить CLI-операцию и записать итог по её исключению или exit code."""

        run_id = self.writer.start(ParserRunStart(started_at=self.clock(), resource=self.resource))
        try:
            outcome = operation()
        except BaseException as error:
            completion = ParserRunCompletion(
                finished_at=self.clock(),
                result="failure",
                error_reason=safe_failure_reason(error),
            )
            try:
                self.writer.finish(run_id, completion)
            except Exception as logging_error:
                error.add_note(
                    f"Не удалось завершить запись журнала: {safe_failure_reason(logging_error)}"
                )
            raise

        if outcome == 0:
            completion = ParserRunCompletion(finished_at=self.clock(), result="success")
        else:
            completion = ParserRunCompletion(
                finished_at=self.clock(),
                result="failure",
                error_reason=f"Команда завершилась с кодом {outcome}.",
            )
        self.writer.finish(run_id, completion)
        return outcome
