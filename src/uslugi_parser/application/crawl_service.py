"""Сценарий массового обхода категорий и сохранения карточек мастеров."""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field

from uslugi_parser.application.dto import (
    CrawlOptions,
    CrawlProgressEvent,
    CrawlProgressReporter,
    CrawlProgressStage,
    FetcherFactory,
    ProfessionalWriter,
)
from uslugi_parser.catalog.categories import CategoryDefinition
from uslugi_parser.config import Settings
from uslugi_parser.domain import CrawlStats, ParsedProfessional
from uslugi_parser.exceptions import (
    BlockedRedirect,
    BlockingFetchError,
    CaptchaDetected,
    CrawlAborted,
    FetchError,
    ParseError,
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


@dataclass(slots=True)
class _TargetCursor:
    """Хранить состояние одной рубрики между кругами постраничного обхода."""

    category_index: int
    category: CategoryDefinition
    expected_level: str | None
    seed_url: str
    rubric_number_id: int
    page_number: int = 0
    pages_total: int | None = None
    seen_profiles: set[str] = field(default_factory=set)
    consecutive_pages_without_new_profiles: int = 0
    started: bool = False


def _target_queue(
    categories: list[CategoryDefinition],
    geo: str,
) -> deque[_TargetCursor]:
    """Развернуть категории в очередь рубрик для чередования страниц."""

    targets: deque[_TargetCursor] = deque()
    for category_index, category in enumerate(categories, start=1):
        for (_seed_path, expected_level), seed_url in zip(
            category.targets(),
            category.urls(geo),
            strict=True,
        ):
            targets.append(
                _TargetCursor(
                    category_index=category_index,
                    category=category,
                    expected_level=expected_level,
                    seed_url=seed_url,
                    rubric_number_id=seed_number_id(seed_url),
                )
            )
    return targets


async def crawl(
    *,
    settings: Settings,
    categories: list[CategoryDefinition],
    max_pages: int,
    max_profiles: int,
    repository: ProfessionalWriter | None,
    fetcher_factory: FetcherFactory,
    progress: CrawlProgressReporter | None = None,
) -> CrawlStats:
    """Обойти выбранные категории и вернуть статистику запуска.

    Сценарий координирует загрузку и разбор страниц, дедупликацию профилей,
    проверку рубрик и сохранение через порт репозитория. Телефоны в массовом
    обходе не извлекаются и не раскрываются. Блокирующие ответы и CAPTCHA прекращают обход
    целиком, а запрет отдельного URL в robots.txt безопасно пропускает только его.
    """

    options = CrawlOptions(
        max_pages=max_pages,
        max_profiles=max_profiles,
    )

    stats = CrawlStats()
    categories_total = len(categories)
    targets_total = sum(len(category.targets()) for category in categories)
    category_index = 0
    category_key: str | None = None
    category_name: str | None = None
    target_index = 0
    target_rubric_number_id: int | None = None
    current_page_number = 0
    current_pages_total: int | None = None
    current_profile_index = 0
    current_profiles_total = 0

    def report(stage: CrawlProgressStage, *, outcome: str | None = None) -> None:
        """Передать CLI безопасный снимок прогресса, если наблюдатель подключён."""

        if progress is None:
            return
        progress(
            CrawlProgressEvent.from_stats(
                stage=stage,
                stats=stats,
                categories_total=categories_total,
                category_index=category_index,
                category_key=category_key,
                category_name=category_name,
                targets_total=targets_total,
                target_index=target_index,
                target_rubric_number_id=target_rubric_number_id,
                page_number=current_page_number,
                pages_total=current_pages_total,
                profile_index=current_profile_index,
                profiles_total=current_profiles_total,
                dry_run=repository is None,
                outcome=outcome,
            )
        )

    report("started")
    profile_cache: dict[str, ParsedProfessional | None] = {}
    unique_fetched = 0
    limit_reached = False
    targets = _target_queue(categories, settings.geo)
    targets_completed = 0
    async with fetcher_factory(settings) as fetcher:
        while targets and not limit_reached:
            target = targets.popleft()
            category = target.category
            expected_level = target.expected_level
            category_index = target.category_index
            category_key = category.key
            category_name = category.name
            target_index = targets_completed + 1
            target_rubric_number_id = target.rubric_number_id
            current_page_number = target.page_number + 1
            current_pages_total = target.pages_total
            current_profile_index = 0
            current_profiles_total = 0
            if not target.started:
                target.started = True
                report("target_started")
            report("page_fetching")
            page_url = add_page_query(target.seed_url, target.page_number)
            target_finished = False
            try:
                category_result = await fetcher.get(page_url)
            except (
                BlockedRedirect,
                RobotsUnavailable,
                ServerAskedToStop,
                UnexpectedOrigin,
            ) as exc:
                raise CrawlAborted(f"Category request blocked by safety policy: {exc}") from exc
            except RobotsDenied:
                stats.robots_denied += 1
                logger.warning(
                    "category_page_denied_by_robots category=%s page=%s",
                    category.key,
                    target.page_number,
                )
                target_finished = True
            except BlockingFetchError as exc:
                stats.failed += 1
                logger.error(
                    "category_fetch_failed category=%s page=%s status=%s",
                    category.key,
                    target.page_number,
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
                    target.page_number,
                    exc.status_code,
                )
                target_finished = True

            if target_finished:
                targets_completed += 1
                target_index = targets_completed
                report("target_completed")
                continue

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
                    target.page_number,
                    type(exc).__name__,
                )
                targets_completed += 1
                target_index = targets_completed
                report("target_completed")
                continue

            stats.category_pages += 1
            stats.discovered += len(category_page.profiles)
            requested_page_limit = (
                category_page.total_pages if options.max_pages == 0 else options.max_pages
            )
            target.pages_total = min(category_page.total_pages, requested_page_limit)
            current_pages_total = target.pages_total
            current_profiles_total = len(category_page.profiles)
            report("page_parsed")
            new_in_page = sum(
                item.profile_url not in target.seen_profiles for item in category_page.profiles
            )
            target.seen_profiles.update(item.profile_url for item in category_page.profiles)
            if new_in_page:
                target.consecutive_pages_without_new_profiles = 0
            else:
                target.consecutive_pages_without_new_profiles += 1

            for next_profile_index, discovered in enumerate(category_page.profiles, start=1):
                cached = discovered.profile_url in profile_cache
                if not cached and options.max_profiles and unique_fetched >= options.max_profiles:
                    limit_reached = True
                    break

                current_profile_index = next_profile_index
                report("profile_started")

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
                            include_phone=False,
                        )
                        # Защита в глубину: даже если парсер профиля будет
                        # изменён, bulk-crawl не передаст номер в хранилище.
                        profile.phone = None
                        profile.phone_status = "not_requested"
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

                    profile_cache[discovered.profile_url] = profile

                if profile is None:
                    report("profile_completed", outcome="skipped")
                    continue
                evidence = match_rubric(
                    profile,
                    target_rubric_number_id,
                    expected_level,
                )
                if evidence is None:
                    stats.skipped_category_mismatch += 1
                    report("profile_completed", outcome="category_mismatch")
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
                    report("profile_completed", outcome="dry_run")
                else:
                    outcome = repository.upsert(profile, category, evidence)
                    if outcome == "created":
                        stats.created += 1
                    else:
                        stats.updated += 1
                    report("profile_completed", outcome=outcome)

            report("page_completed")
            if limit_reached:
                target_finished = True
            elif target.consecutive_pages_without_new_profiles >= 2:
                logger.warning(
                    "category_pagination_stopped_without_new_profiles category=%s",
                    category.key,
                )
                target_finished = True
            elif target.page_number + 1 >= min(
                category_page.total_pages,
                requested_page_limit,
            ):
                target_finished = True

            if target_finished:
                targets_completed += 1
                target_index = targets_completed
                report("target_completed")
            else:
                target.page_number += 1
                targets.append(target)
    report("completed", outcome="limit_reached" if limit_reached else None)
    return stats
