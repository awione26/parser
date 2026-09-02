"""Сценарии разбора, проверки и сохранения одной карточки мастера."""

from __future__ import annotations

from contextlib import AsyncExitStack

from uslugi_parser.application.dto import (
    FetcherFactory,
    PhoneCollectorFactory,
    ProfessionalWriter,
    ProfileOptions,
)
from uslugi_parser.catalog.categories import CategoryDefinition
from uslugi_parser.config import Settings
from uslugi_parser.domain import ParsedProfessional
from uslugi_parser.exceptions import (
    CaptchaDetected,
    ConfigurationError,
    ParseError,
    PhoneNavigationBlocked,
)
from uslugi_parser.parsing import (
    canonicalize_live_profile_url,
    match_rubric,
    parse_profile_html,
    seed_number_id,
)

MANUAL_CATEGORY = CategoryDefinition("manual", "Ручной импорт", ())


def apply_profile_policy(profile: ParsedProfessional, settings: Settings) -> ParsedProfessional:
    """Применить единое правило допустимого типа аккаунта.

    Проверка используется для локальных и сетевых страниц, чтобы ни один путь
    импорта не обходил ограничение конфигурации для организаций.
    """

    if not settings.include_organizations and profile.account_type != "person":
        raise ParseError("profile is not explicitly marked as a person")
    return profile


def parse_saved_profile(
    html: str,
    source_url: str,
    settings: Settings,
) -> ParsedProfessional:
    """Разобрать сохранённую страницу и применить правило типа аккаунта.

    Политика robots.txt здесь не проверяется, поскольку сетевой запрос не выполняется.
    """

    return apply_profile_policy(parse_profile_html(html, source_url), settings)


def save_profile(
    repository: ProfessionalWriter,
    profile: ParsedProfessional,
    category: CategoryDefinition | None,
) -> str:
    """Сохранить профиль только при точном совпадении с выбранной рубрикой.

    Для ручного импорта без категории совпадение не требуется. Для именованной
    категории функция находит все подтверждающие рубрики исходного профиля.
    """

    if category is None:
        return repository.upsert(profile, MANUAL_CATEGORY)
    evidences = [
        evidence
        for path, expected_level in category.targets()
        if (evidence := match_rubric(profile, seed_number_id(path), expected_level)) is not None
    ]
    if not evidences:
        raise ConfigurationError(f"profile has no exact rubric match for category {category.key!r}")
    outcomes = [repository.upsert(profile, category, evidence) for evidence in evidences]
    return "created" if "created" in outcomes else "updated"


async def parse_live_profile(
    profile_url: str,
    settings: Settings,
    *,
    collect_phone: bool,
    fetcher_factory: FetcherFactory,
    phone_collector_factory: PhoneCollectorFactory | None = None,
) -> ParsedProfessional:
    """Загрузить, проверить и разобрать одну публичную карточку мастера.

    При включённой настройке сценарий также может получить номер через браузерный
    интерфейс сайта, сохраняя политики robots.txt, CAPTCHA и безопасной навигации.
    """

    options = ProfileOptions(collect_phone=collect_phone)
    profile_url = canonicalize_live_profile_url(profile_url)
    async with AsyncExitStack() as stack:
        fetcher = await stack.enter_async_context(fetcher_factory(settings))
        result = await fetcher.get(profile_url)
        profile = apply_profile_policy(parse_profile_html(result.text, result.url), settings)
        if options.collect_phone and not profile.phone:
            settings.require_phone_reveal_policy()
            if phone_collector_factory is None:
                raise ConfigurationError("phone collector is not configured")
            collector = await stack.enter_async_context(phone_collector_factory(settings))
            try:
                phone = await collector.collect(profile.profile_url, profile.country)
                profile.phone = phone
                profile.phone_status = "revealed_ui" if phone else "reveal_failed"
            except CaptchaDetected:
                profile.phone_status = "blocked_captcha"
            except PhoneNavigationBlocked:
                profile.phone_status = "blocked_navigation"
                raise
        return profile
