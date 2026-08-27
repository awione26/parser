"""Сценарий массового обхода категорий и сохранения карточек мастеров."""

from __future__ import annotations

import logging
from contextlib import AsyncExitStack

from uslugi_parser.application.dto import (
    CrawlOptions,
    FetcherFactory,
    PhoneCollectorFactory,
    PhoneCollectorPort,
    ProfessionalWriter,
)
from uslugi_parser.catalog.categories import CategoryDefinition
from uslugi_parser.config import Settings
from uslugi_parser.domain import CrawlStats, ParsedProfessional
from uslugi_parser.exceptions import (
    BlockedRedirect,
    BlockingFetchError,
    CaptchaDetected,
    ConfigurationError,
    CrawlAborted,
    FetchError,
    ParseError,
    PhoneNavigationBlocked,
    RobotsDenied,
    RobotsUnavailable,
    ServerAskedToStop,
    UnexpectedOrigin,
)
from uslugi_parser.parsing import (
    add_page_query,
    experience_label,
    match_rubric,
    parse_category_html,
    parse_profile_html,
    seed_number_id,
)

logger = logging.getLogger(__name__)


async def crawl(
    *,
    settings: Settings,
    categories: list[CategoryDefinition],
    max_pages: int,
    max_profiles: int,
    collect_phone: bool,
    repository: ProfessionalWriter | None,
    fetcher_factory: FetcherFactory,
    phone_collector_factory: PhoneCollectorFactory | None = None,
) -> CrawlStats:
    """Обойти выбранные категории и вернуть статистику запуска.

    Сценарий координирует загрузку и разбор страниц, дедупликацию профилей,
    проверку рубрик, опциональное получение телефона и сохранение через порт
    репозитория. Блокирующие ответы, CAPTCHA и опасная навигация прекращают обход
    целиком, а запрет отдельного URL в robots.txt безопасно пропускает только его.
    """

    options = CrawlOptions(
        max_pages=max_pages,
        max_profiles=max_profiles,
        collect_phone=collect_phone,
    )
    settings.require_live_permission()
    if options.collect_phone:
        settings.require_phone_reveal_permission()
        if phone_collector_factory is None:
            raise ConfigurationError("phone collector is not configured")

    stats = CrawlStats()
    profile_cache: dict[str, ParsedProfessional | None] = {}
    unique_fetched = 0
    limit_reached = False
    phone_collection_enabled = options.collect_phone

    async with AsyncExitStack() as stack:
        fetcher = await stack.enter_async_context(fetcher_factory(settings))
        phone_collector: PhoneCollectorPort | None = None
        if options.collect_phone:
            assert phone_collector_factory is not None
            phone_collector = await stack.enter_async_context(phone_collector_factory(settings))

        for category in categories:
            if limit_reached:
                break
            for seed_url in category.urls(settings.geo):
                target_rubric_number_id = seed_number_id(seed_url)
                page_number = 0
                seen_in_seed: set[str] = set()
                consecutive_pages_without_new_profiles = 0
                while True:
                    page_url = add_page_query(seed_url, page_number)
                    try:
                        category_result = await fetcher.get(page_url)
                    except (
                        BlockedRedirect,
                        RobotsUnavailable,
                        ServerAskedToStop,
                        UnexpectedOrigin,
                    ) as exc:
                        raise CrawlAborted(
                            f"Category request blocked by safety policy: {exc}"
                        ) from exc
                    except RobotsDenied:
                        stats.robots_denied += 1
                        logger.warning(
                            "category_page_denied_by_robots category=%s page=%s",
                            category.key,
                            page_number,
                        )
                        break
                    except BlockingFetchError as exc:
                        stats.failed += 1
                        logger.error(
                            "category_fetch_failed category=%s page=%s status=%s",
                            category.key,
                            page_number,
                            exc.status_code,
                        )
                        raise CrawlAborted(
                            f"Yandex returned HTTP {exc.status_code}; crawl stopped"
                        ) from exc
                    except FetchError as exc:
                        stats.failed += 1
                        logger.error(
                            "category_fetch_failed category=%s page=%s status=%s",
                            category.key,
                            page_number,
                            exc.status_code,
                        )
                        break

                    try:
                        category_page = parse_category_html(category_result.text)
                    except CaptchaDetected as exc:
                        raise CrawlAborted(
                            "Yandex returned a CAPTCHA on a category page; crawl stopped"
                        ) from exc
                    except (ParseError, ValueError) as exc:
                        stats.failed += 1
                        logger.error(
                            "category_parse_failed category=%s page=%s error=%s",
                            category.key,
                            page_number,
                            type(exc).__name__,
                        )
                        break

                    stats.category_pages += 1
                    stats.discovered += len(category_page.profiles)
                    new_in_page = sum(
                        item.profile_url not in seen_in_seed for item in category_page.profiles
                    )
                    seen_in_seed.update(item.profile_url for item in category_page.profiles)
                    if new_in_page:
                        consecutive_pages_without_new_profiles = 0
                    else:
                        consecutive_pages_without_new_profiles += 1
                    for discovered in category_page.profiles:
                        cached = discovered.profile_url in profile_cache
                        if (
                            not cached
                            and options.max_profiles
                            and unique_fetched >= options.max_profiles
                        ):
                            limit_reached = True
                            break

                        if cached:
                            profile = profile_cache[discovered.profile_url]
                        else:
                            unique_fetched += 1
                            try:
                                profile_result = await fetcher.get(discovered.profile_url)
                                stats.fetched += 1
                                profile = parse_profile_html(
                                    profile_result.text,
                                    profile_result.url,
                                )
                                stats.parsed += 1
                            except (
                                BlockedRedirect,
                                RobotsUnavailable,
                                ServerAskedToStop,
                                UnexpectedOrigin,
                            ) as exc:
                                raise CrawlAborted(
                                    f"Profile request blocked by safety policy: {exc}"
                                ) from exc
                            except CaptchaDetected as exc:
                                raise CrawlAborted(
                                    "Yandex returned a CAPTCHA on a profile page; crawl stopped"
                                ) from exc
                            except RobotsDenied:
                                stats.robots_denied += 1
                                profile = None
                            except BlockingFetchError as exc:
                                stats.failed += 1
                                logger.error(
                                    "profile_fetch_failed source_id=%s status=%s",
                                    discovered.source_profile_id,
                                    exc.status_code,
                                )
                                raise CrawlAborted(
                                    f"Yandex returned HTTP {exc.status_code}; crawl stopped"
                                ) from exc
                            except FetchError as exc:
                                stats.failed += 1
                                logger.error(
                                    "profile_fetch_failed source_id=%s status=%s",
                                    discovered.source_profile_id,
                                    exc.status_code,
                                )
                                profile = None
                            except ParseError as exc:
                                stats.failed += 1
                                logger.error(
                                    "profile_parse_failed source_id=%s error=%s",
                                    discovered.source_profile_id,
                                    type(exc).__name__,
                                )
                                profile = None

                            if (
                                profile
                                and not settings.include_organizations
                                and profile.account_type != "person"
                            ):
                                stats.skipped_organizations += 1
                                profile = None

                            if profile and profile.phone and not settings.phone_permission:
                                profile.phone = None
                                profile.phone_status = "permission_required"

                            if profile and profile.phone:
                                stats.phone_collected += 1
                            elif profile and phone_collection_enabled and phone_collector:
                                try:
                                    phone = await phone_collector.collect(
                                        profile.profile_url,
                                        profile.country,
                                    )
                                    profile.phone = phone
                                    profile.phone_status = (
                                        "revealed_ui" if phone else "reveal_failed"
                                    )
                                    if phone:
                                        stats.phone_collected += 1
                                    else:
                                        stats.phone_unavailable += 1
                                except CaptchaDetected as exc:
                                    profile.phone_status = "blocked_captcha"
                                    stats.phone_unavailable += 1
                                    raise CrawlAborted(
                                        "Yandex returned a CAPTCHA during phone reveal; "
                                        "crawl stopped"
                                    ) from exc
                                except PhoneNavigationBlocked as exc:
                                    profile.phone_status = "blocked_navigation"
                                    raise CrawlAborted(
                                        "Phone navigation left the allowed profile scope; "
                                        "crawl stopped"
                                    ) from exc

                            profile_cache[discovered.profile_url] = profile

                        if profile is None:
                            continue
                        evidence = match_rubric(profile, target_rubric_number_id)
                        if evidence is None:
                            stats.skipped_category_mismatch += 1
                            continue
                        if repository is None:
                            item = profile.public_dict()
                            item["category"] = {
                                "key": category.key,
                                "name": category.name,
                                "source_rubric_number_id": evidence.number_id,
                                "source_rubric_id": evidence.rubric_id,
                                "source_rubric_seo_id": evidence.seo_id,
                                "source_rubric_name": evidence.name,
                                "experience": {
                                    "code": evidence.experience_code,
                                    "text": experience_label(evidence.experience_code),
                                },
                            }
                            stats.profiles.append(item)
                        else:
                            outcome = repository.upsert(profile, category, evidence)
                            if outcome == "created":
                                stats.created += 1
                            else:
                                stats.updated += 1

                    if limit_reached:
                        break
                    if consecutive_pages_without_new_profiles >= 2:
                        logger.warning(
                            "category_pagination_stopped_without_new_profiles category=%s",
                            category.key,
                        )
                        break
                    requested_page_limit = (
                        category_page.total_pages if options.max_pages == 0 else options.max_pages
                    )
                    if page_number + 1 >= min(category_page.total_pages, requested_page_limit):
                        break
                    page_number += 1
    return stats
