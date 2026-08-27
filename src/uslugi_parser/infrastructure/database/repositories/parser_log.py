"""Репозиторий двухфазной записи запусков парсера в таблицу logs."""

from __future__ import annotations

from sqlalchemy import update
from sqlalchemy.orm import Session, sessionmaker

from uslugi_parser.domain import ParserRunCompletion, ParserRunStart
from uslugi_parser.infrastructure.database.models import ParserLog


class ParserLogRepository:
    """Создавать незавершённый запуск и атомарно фиксировать его итог."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        """Принять фабрику коротких независимых транзакций журнала."""

        self.session_factory = session_factory

    def start(self, run: ParserRunStart) -> int:
        """Создать pending-запись до начала работы и вернуть её id."""

        with self.session_factory.begin() as session:
            entry = ParserLog(
                started_at=run.started_at,
                resource=run.resource,
            )
            session.add(entry)
            session.flush()
            return entry.id

    def finish(self, run_id: int, completion: ParserRunCompletion) -> None:
        """Однократно завершить pending-запись успехом или ошибкой."""

        with self.session_factory.begin() as session:
            result = session.execute(
                update(ParserLog)
                .where(ParserLog.id == run_id, ParserLog.result.is_(None))
                .values(
                    finished_at=completion.finished_at,
                    result=completion.result,
                    error_reason=completion.error_reason,
                )
            )
            if result.rowcount != 1:
                raise RuntimeError(f"pending parser log {run_id} was not found")
