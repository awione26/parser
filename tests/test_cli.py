from __future__ import annotations

import argparse
import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import replace

import pytest
from conftest import html_with_state, make_state, make_worker
from sqlalchemy.exc import OperationalError

import uslugi_parser.cli.commands as cli_commands
import uslugi_parser.cli.main as cli_main
from uslugi_parser.application import save_profile
from uslugi_parser.catalog import DEFAULT_CATEGORIES
from uslugi_parser.cli.commands import _build_parser, _run_parse_html, _run_parse_profile
from uslugi_parser.config import Settings
from uslugi_parser.config.settings import SCRAPER_SETTING_DEFAULTS
from uslugi_parser.exceptions import ConfigurationError
from uslugi_parser.parsing import parse_profile_html


def cli_settings() -> Settings:
    """Создать валидные настройки для изолированных CLI-тестов."""

    return Settings(
        database_url="sqlite+pysqlite:///:memory:",
        user_agent="TestParser/1.0",
        geo="213-moscow",
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


def test_local_html_keeps_public_phone_without_permission_flags(tmp_path, capsys) -> None:
    """Возвращать публичный телефон без устаревших YANDEX_PERMISSION-флагов."""

    page = tmp_path / "profile.html"
    page.write_text(html_with_state(make_state(make_worker())), encoding="utf-8")
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        user_agent="TestParser/1.0",
        geo="213-moscow",
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
    assert output["phone"] == "+79991234567"
    assert output["phone_status"] == "public_messenger"


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
    assert save_profile(repository, profile, DEFAULT_CATEGORIES["plumbers"]) == "created"
    assert repository.evidence_ids == [1844]
    with pytest.raises(ConfigurationError, match="no exact rubric match"):
        save_profile(repository, profile, DEFAULT_CATEGORIES["appliance_repair"])


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

    monkeypatch.setattr(cli_main, "_load_effective_settings", lambda **_kwargs: settings)
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
    monkeypatch.setattr(cli_main, "_load_effective_settings", lambda **_kwargs: settings)

    def unexpected_service(_settings: Settings) -> RecordingRunService:
        """Сообщить об ошибке, если справочная команда откроет журнал."""

        raise AssertionError("categories must not create a parser run log")

    monkeypatch.setattr(cli_main, "_parser_run_service", unexpected_service)
    monkeypatch.setattr(
        cli_commands,
        "_category_repository",
        lambda _settings: StaticCategoryRepository(),
    )

    assert cli_main.main(["categories"]) == 0
    assert json.loads(capsys.readouterr().out)


class StaticCategoryRepository:
    """Возвращать один проверенный снимок категории без настоящей БД."""

    def list_active(self):
        """Вернуть активную тестовую категорию."""

        return [DEFAULT_CATEGORIES["plumbers"]]

    def resolve(self, _keys):
        """Разрешить выбор в ту же тестовую категорию."""

        return self.list_active()


class RejectingCategoryRepository:
    """Имитировать fail-closed разрешение категории до сетевых операций."""

    def resolve(self, _keys):
        """Сообщить, что выбранная категория выключена."""

        raise ConfigurationError("Inactive parser categories: disabled")


def test_parse_profile_resolves_category_before_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Не загружать карточку при неизвестной или выключенной категории save."""

    network_called = False

    async def forbidden_network(*_args, **_kwargs):
        """Зафиксировать ошибочный сетевой вызов."""

        nonlocal network_called
        network_called = True
        raise AssertionError("network must not be called")

    monkeypatch.setattr(
        cli_commands,
        "_category_repository",
        lambda _settings: RejectingCategoryRepository(),
    )
    monkeypatch.setattr(cli_commands, "parse_live_profile", forbidden_network)
    args = argparse.Namespace(
        url="https://uslugi.yandex.ru/profile/Test-1",
        save=True,
        category="disabled",
        no_respect_robots=False,
        collect_phone=None,
    )

    with pytest.raises(ConfigurationError, match="Inactive parser categories"):
        asyncio.run(_run_parse_profile(args, cli_settings()))
    assert network_called is False


def test_crawl_resolves_categories_before_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Не создавать HTTP-сценарий crawl при недопустимом выборе категории."""

    network_called = False

    async def forbidden_crawl(*_args, **_kwargs):
        """Зафиксировать ошибочный запуск сетевого сценария."""

        nonlocal network_called
        network_called = True
        raise AssertionError("crawl must not be called")

    monkeypatch.setattr(
        cli_commands,
        "_category_repository",
        lambda _settings: RejectingCategoryRepository(),
    )
    monkeypatch.setattr(cli_commands, "crawl", forbidden_crawl)
    args = argparse.Namespace(
        category=["disabled"],
        geo=None,
        respect_robots=None,
        dry_run=True,
        max_pages=1,
        max_profiles=1,
    )

    with pytest.raises(ConfigurationError, match="Inactive parser categories"):
        asyncio.run(cli_commands._run_crawl(args, cli_settings()))
    assert network_called is False


def test_cli_accepts_database_category_key_without_static_choices() -> None:
    """Передать новый DB-ключ в resolver вместо раннего отказа argparse."""

    args = _build_parser().parse_args(["crawl", "--category", "future_category"])

    assert args.category == ["future_category"]


def test_crawl_command_has_no_phone_collection_switch() -> None:
    """Не позволять включить сбор телефонов для массового crawl."""

    with pytest.raises(SystemExit) as error:
        _build_parser().parse_args(["crawl", "--collect-phone"])

    assert error.value.code == 2


def test_cli_database_settings_override_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверить приоритет значения из таблицы settings над окружением CLI."""

    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("SCRAPER_GEO", "213-moscow")
    monkeypatch.setenv("SCRAPER_COLLECT_PHONE", "false")
    monkeypatch.setattr(
        cli_main.ParserSettingRepository,
        "read_all",
        lambda _repository: {
            "SCRAPER_GEO": "54-ekaterinburg",
            "SCRAPER_COLLECT_PHONE": "true",
        },
    )

    loaded = cli_main._load_effective_settings()

    assert loaded.geo == "54-ekaterinburg"
    assert loaded.collect_phone is True
    assert loaded.user_agent == SCRAPER_SETTING_DEFAULTS["SCRAPER_USER_AGENT"]


def test_cli_uses_environment_when_settings_table_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Продолжить bootstrap с env и записать безопасное предупреждение без SQL/DSN."""

    environment = cli_settings()
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setattr(
        cli_main.Settings,
        "from_env",
        classmethod(lambda _cls: environment),
    )

    def unavailable(_repository: object) -> dict[str, str]:
        """Имитировать отсутствующую таблицу без открытия настоящей базы."""

        raise OperationalError("SELECT secret", {}, RuntimeError("dsn-password-secret"))

    monkeypatch.setattr(cli_main.ParserSettingRepository, "read_all", unavailable)

    with caplog.at_level(logging.WARNING):
        loaded = cli_main._load_effective_settings(allow_environment_fallback=True)

    assert loaded is environment
    assert "используются значения окружения" in caplog.text
    assert "SELECT secret" not in caplog.text
    assert "dsn-password-secret" not in caplog.text


def test_network_command_fails_closed_when_database_settings_are_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Остановить сетевой запуск, если безопасную политику нельзя прочитать из БД."""

    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")

    def unavailable(_repository: object) -> dict[str, str]:
        """Имитировать недоступную таблицу конфигурации."""

        raise OperationalError("SELECT settings", {}, RuntimeError("database unavailable"))

    monkeypatch.setattr(cli_main.ParserSettingRepository, "read_all", unavailable)

    with pytest.raises(ConfigurationError, match="сетевой сбор остановлен"):
        cli_main._load_effective_settings()


def test_cli_does_not_hide_invalid_database_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    """Передать ошибку валидации БД вызывающему коду вместо тихого env fallback."""

    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")

    def unexpected_env_fallback(_cls: type[Settings]) -> Settings:
        """Сообщить, если доступная таблица ошибочно заменена окружением."""

        raise AssertionError("invalid database values must not trigger env fallback")

    monkeypatch.setattr(
        cli_main.Settings,
        "from_env",
        classmethod(unexpected_env_fallback),
    )
    monkeypatch.setattr(
        cli_main.ParserSettingRepository,
        "read_all",
        lambda _repository: {"SCRAPER_TIMEOUT_SECONDS": "never"},
    )

    with pytest.raises(ConfigurationError, match="must be a number"):
        cli_main._load_effective_settings()


def test_valid_database_settings_ignore_invalid_operational_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Не валидировать повреждённый SCRAPER env, когда authoritative БД доступна."""

    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("SCRAPER_TIMEOUT_SECONDS", "invalid-env-value")
    monkeypatch.setattr(
        cli_main.ParserSettingRepository,
        "read_all",
        lambda _repository: dict(SCRAPER_SETTING_DEFAULTS),
    )

    loaded = cli_main._load_effective_settings()

    assert loaded.timeout_seconds == 30.0


def test_parse_profile_phone_flag_is_tristate() -> None:
    """Оставить настройку БД основной и разрешить явное включение либо выключение CLI."""

    parser = _build_parser()
    base = ["parse-profile", "https://uslugi.yandex.ru/profile/Test-1"]

    assert parser.parse_args(base).collect_phone is None
    assert parser.parse_args([*base, "--collect-phone"]).collect_phone is True
    assert parser.parse_args([*base, "--no-collect-phone"]).collect_phone is False


class PublicProfileStub:
    """Предоставлять минимальный публичный результат для CLI-теста профиля."""

    def public_dict(self) -> dict[str, str]:
        """Вернуть сериализуемое представление фиктивного профиля."""

        return {"source": "test"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("argument_value", "expected"),
    [(None, True), (True, True), (False, False)],
)
async def test_parse_profile_uses_database_phone_default_and_cli_override(
    argument_value: bool | None,
    expected: bool,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Передать в профиль effective collect_phone с приоритетом явного CLI-флага."""

    observed: list[bool] = []

    async def fake_parse_live_profile(
        _url: str,
        _settings: Settings,
        *,
        collect_phone: bool,
        **_kwargs: object,
    ) -> PublicProfileStub:
        """Запомнить effective-флаг без выполнения сетевого запроса."""

        observed.append(collect_phone)
        return PublicProfileStub()

    monkeypatch.setattr(cli_commands, "parse_live_profile", fake_parse_live_profile)
    args = argparse.Namespace(
        url="https://uslugi.yandex.ru/profile/Test-1",
        collect_phone=argument_value,
        save=False,
        category=None,
        no_respect_robots=False,
    )

    assert await _run_parse_profile(args, replace(cli_settings(), collect_phone=True)) == 0
    assert observed == [expected]
    assert json.loads(capsys.readouterr().out) == {"source": "test"}
