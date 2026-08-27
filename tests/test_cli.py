from __future__ import annotations

import argparse
import json
from collections.abc import Callable

import pytest
from conftest import html_with_state, make_state, make_worker

import uslugi_parser.cli.main as cli_main
from uslugi_parser.application import save_profile
from uslugi_parser.cli.commands import _run_parse_html
from uslugi_parser.config import Settings
from uslugi_parser.exceptions import ConfigurationError
from uslugi_parser.parsing import parse_profile_html


def cli_settings() -> Settings:
    """Создать валидные настройки для изолированных CLI-тестов."""

    return Settings(
        database_url="sqlite+pysqlite:///:memory:",
        user_agent="TestParser/1.0",
        geo="213-moscow",
        operator_permission=True,
        phone_permission=False,
        respect_robots=True,
        min_delay_seconds=0,
        max_delay_seconds=0,
        timeout_seconds=1,
        max_retries=0,
        collect_phone=False,
        phone_headless=True,
        phone_timeout_seconds=1,
        include_organizations=False,
    )


class RecordingRunService:
    """Проверять, что CLI передаёт сценарий сервису жизненного цикла."""

    def __init__(self) -> None:
        """Начать со счётчика без выполненных операций."""

        self.calls = 0

    def execute(self, operation: Callable[[], int]) -> int:
        """Посчитать вызов и выполнить переданный сценарий."""

        self.calls += 1
        return operation()


def test_local_html_masks_phone_without_permission(tmp_path, capsys) -> None:
    page = tmp_path / "profile.html"
    page.write_text(html_with_state(make_state(make_worker())), encoding="utf-8")
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        user_agent="TestParser/1.0",
        geo="213-moscow",
        operator_permission=False,
        phone_permission=False,
        respect_robots=True,
        min_delay_seconds=0,
        max_delay_seconds=0,
        timeout_seconds=1,
        max_retries=0,
        collect_phone=False,
        phone_headless=True,
        phone_timeout_seconds=1,
        include_organizations=False,
    )
    args = argparse.Namespace(
        file=page,
        source_url="https://uslugi.yandex.ru/profile/TestMaster-123456",
        save=False,
        category=None,
    )
    assert _run_parse_html(args, settings) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["phone"] is None
    assert output["phone_status"] == "permission_required"


class RecordingRepository:
    def __init__(self) -> None:
        self.evidence_ids: list[int | None] = []

    def upsert(self, _profile, _category, evidence=None) -> str:
        self.evidence_ids.append(evidence.number_id if evidence else None)
        return "created"


def test_named_category_save_requires_exact_profile_rubric() -> None:
    profile = parse_profile_html(
        html_with_state(make_state(make_worker())),
        "https://uslugi.yandex.ru/profile/TestMaster-123456",
    )
    repository = RecordingRepository()
    assert save_profile(repository, profile, "plumbers") == "created"
    assert repository.evidence_ids == [1844]
    with pytest.raises(ConfigurationError, match="no exact rubric match"):
        save_profile(repository, profile, "appliance_repair")


@pytest.mark.parametrize(
    "argv",
    [
        ["parse-html", "saved-profile.html"],
        ["parse-profile", "https://uslugi.yandex.ru/profile/TestMaster-123456"],
        ["crawl", "--category", "plumbers", "--max-profiles", "1"],
    ],
)
def test_parser_commands_use_run_log_lifecycle(
    argv: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = cli_settings()
    service = RecordingRunService()

    async def successful_async_command(*_args: object, **_kwargs: object) -> int:
        """Имитировать успешную асинхронную CLI-команду."""

        return 0

    monkeypatch.setattr(
        cli_main.Settings,
        "from_env",
        classmethod(lambda _cls: settings),
    )
    monkeypatch.setattr(cli_main, "_parser_run_service", lambda _settings: service)
    monkeypatch.setattr(cli_main, "_run_parse_html", lambda _args, _settings: 0)
    monkeypatch.setattr(cli_main, "_run_parse_profile", successful_async_command)
    monkeypatch.setattr(cli_main, "_run_crawl", successful_async_command)

    assert cli_main.main(argv) == 0
    assert service.calls == 1


def test_categories_command_does_not_create_parser_run_log(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = cli_settings()
    monkeypatch.setattr(
        cli_main.Settings,
        "from_env",
        classmethod(lambda _cls: settings),
    )

    def unexpected_service(_settings: Settings) -> RecordingRunService:
        """Сообщить об ошибке, если справочная команда откроет журнал."""

        raise AssertionError("categories must not create a parser run log")

    monkeypatch.setattr(cli_main, "_parser_run_service", unexpected_service)

    assert cli_main.main(["categories"]) == 0
    assert json.loads(capsys.readouterr().out)
