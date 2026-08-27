from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError

from uslugi_parser.application import (
    ERROR_REASON_MAX_LENGTH,
    ParserRunService,
    safe_failure_reason,
)
from uslugi_parser.domain import ParserRunCompletion, ParserRunStart
from uslugi_parser.infrastructure.database import (
    Base,
    ParserLog,
    ParserLogRepository,
    make_session_factory,
)


class RecordingLogWriter:
    """Запоминать вызовы порта журнала без подключения к базе данных."""

    def __init__(self) -> None:
        """Подготовить коллекции созданных и завершённых записей."""

        self.started: list[ParserRunStart] = []
        self.finished: list[tuple[int, ParserRunCompletion]] = []

    def start(self, run: ParserRunStart) -> int:
        """Сохранить данные начала и вернуть стабильный тестовый id."""

        self.started.append(run)
        return 41

    def finish(self, run_id: int, completion: ParserRunCompletion) -> None:
        """Сохранить переданный итог запуска."""

        self.finished.append((run_id, completion))


def clock(*moments: datetime):
    """Вернуть часы, последовательно выдающие заданные моменты времени."""

    values: Iterator[datetime] = iter(moments)
    return lambda: next(values)


def test_service_records_successful_lifecycle() -> None:
    started_at = datetime(2026, 8, 27, 10, 0, 0)
    finished_at = datetime(2026, 8, 27, 10, 1, 0)
    writer = RecordingLogWriter()
    service = ParserRunService(writer, clock=clock(started_at, finished_at))

    assert service.execute(lambda: 0) == 0

    assert writer.started == [ParserRunStart(started_at=started_at, resource="uslugi.yandex.ru")]
    assert writer.finished == [
        (
            41,
            ParserRunCompletion(finished_at=finished_at, result="success"),
        )
    ]


def test_service_records_failure_and_reraises_original_exception() -> None:
    writer = RecordingLogWriter()
    service = ParserRunService(
        writer,
        clock=clock(
            datetime(2026, 8, 27, 10, 0, 0),
            datetime(2026, 8, 27, 10, 0, 1),
        ),
    )
    error = RuntimeError(
        "request https://uslugi.yandex.ru/profile/Test-1?token=secret failed for +7 (999) 123-45-67"
    )

    with pytest.raises(RuntimeError) as caught:
        service.execute(lambda: (_ for _ in ()).throw(error))

    assert caught.value is error
    completion = writer.finished[0][1]
    assert completion.result == "failure"
    assert completion.error_reason is not None
    assert "https://" not in completion.error_reason
    assert "secret" not in completion.error_reason
    assert "7999" not in completion.error_reason.replace(" ", "")


def test_service_records_nonzero_exit_code_as_failure() -> None:
    writer = RecordingLogWriter()
    service = ParserRunService(
        writer,
        clock=clock(
            datetime(2026, 8, 27, 10, 0, 0),
            datetime(2026, 8, 27, 10, 0, 2),
        ),
    )

    assert service.execute(lambda: 2) == 2
    assert writer.finished[0][1].result == "failure"
    assert writer.finished[0][1].error_reason == "Команда завершилась с кодом 2."


def test_safe_failure_reason_is_bounded_and_hides_database_details() -> None:
    long_reason = safe_failure_reason(RuntimeError("x" * (ERROR_REASON_MAX_LENGTH * 2)))
    database_reason = safe_failure_reason(SQLAlchemyError("SELECT private_data"))

    assert len(long_reason) == ERROR_REASON_MAX_LENGTH
    assert long_reason.endswith("…")
    assert database_reason == "SQLAlchemyError: Ошибка базы данных."
    assert "private_data" not in database_reason


def test_repository_persists_pending_and_completed_lifecycle() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    sessions = make_session_factory(engine)
    repository = ParserLogRepository(sessions)
    started_at = datetime(2026, 8, 27, 10, 0, 0)
    finished_at = datetime(2026, 8, 27, 10, 0, 3)

    run_id = repository.start(ParserRunStart(started_at=started_at))
    with sessions() as session:
        pending = session.get(ParserLog, run_id)
        assert pending is not None
        assert pending.started_at == started_at
        assert pending.finished_at is None
        assert pending.result is None
        assert pending.error_reason is None
        assert pending.resource == "uslugi.yandex.ru"

    repository.finish(
        run_id,
        ParserRunCompletion(
            finished_at=finished_at,
            result="failure",
            error_reason="FetchError: HTTP 503",
        ),
    )
    with sessions() as session:
        completed = session.scalar(select(ParserLog).where(ParserLog.id == run_id))
        assert completed is not None
        assert completed.finished_at == finished_at
        assert completed.result == "failure"
        assert completed.error_reason == "FetchError: HTTP 503"

    with pytest.raises(RuntimeError, match="was not found"):
        repository.finish(
            run_id,
            ParserRunCompletion(finished_at=finished_at, result="success"),
        )


def test_domain_rejects_timezone_aware_and_contradictory_states() -> None:
    from datetime import UTC

    with pytest.raises(ValueError, match="naive UTC"):
        ParserRunStart(started_at=datetime.now(UTC))
    with pytest.raises(ValueError, match="255"):
        ParserRunStart(
            started_at=datetime(2026, 8, 27, 10, 0, 0),
            resource="x" * 256,
        )
    with pytest.raises(ValueError, match="success or failure"):
        ParserRunCompletion(
            finished_at=datetime(2026, 8, 27, 10, 0, 0),
            result="invalid",  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="cannot have"):
        ParserRunCompletion(
            finished_at=datetime(2026, 8, 27, 10, 0, 0),
            result="success",
            error_reason="unexpected",
        )
    with pytest.raises(ValueError, match="must have"):
        ParserRunCompletion(
            finished_at=datetime(2026, 8, 27, 10, 0, 0),
            result="failure",
        )
