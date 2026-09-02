"""Read-only репозиторий настроенных в базе категорий обхода."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import and_, select
from sqlalchemy.orm import Session, sessionmaker

from uslugi_parser.catalog import (
    RESERVED_PARSER_CATEGORY_KEYS,
    CategoryDefinition,
    validate_category_definitions,
    validate_category_key,
    validate_geo_slug,
    validate_seed_path,
)
from uslugi_parser.exceptions import ConfigurationError
from uslugi_parser.infrastructure.database.models import (
    Category,
    CategoryYandexOccupation,
    CategoryYandexService,
    CategoryYandexSpecialization,
    ParserCategory,
    ParserCategoryTarget,
    YandexOccupation,
    YandexService,
    YandexSpecialization,
)

CrawlTarget = tuple[str, int, str]
CatalogNode = tuple[str | None, str | None, str]
_USABLE_VERIFICATION_STATUSES = frozenset({"confirmed", "discovered", "legacy"})


class ParserCategoryRepository:
    """Читать категории обхода из БД без права изменять конфигурацию."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        """Сохранить фабрику коротких read-only сессий."""

        self.session_factory = session_factory

    def list_active(self) -> list[CategoryDefinition]:
        """Вернуть все активные категории в административно заданном порядке."""

        rows = self._load_configurations(active_only=True)
        definitions = [self._definition_from_row(row[0], row[1], row[2], row[4]) for row in rows]
        self._validate_loaded(definitions)
        return definitions

    def resolve(self, keys: Sequence[str] | None) -> list[CategoryDefinition]:
        """Разрешить `all` либо явные ключи, отклоняя отсутствующие и выключенные."""

        if not keys:
            return self.list_active()

        requested = list(dict.fromkeys(keys))
        if "all" in requested:
            if requested != ["all"]:
                raise ConfigurationError("category 'all' cannot be combined with explicit keys")
            return self.list_active()

        for key in requested:
            try:
                validate_category_key(key)
            except (TypeError, ValueError) as exc:
                raise ConfigurationError(f"Invalid parser category key: {key!r}") from exc
            if key in RESERVED_PARSER_CATEGORY_KEYS:
                raise ConfigurationError(f"Reserved parser category key: {key!r}")

        rows = self._load_configurations(active_only=False)

        rows_by_key = {str(row[0]): row for row in rows}
        missing = [key for key in requested if key not in rows_by_key]
        if missing:
            raise ConfigurationError(f"Unknown parser categories: {', '.join(missing)}")
        inactive = [key for key in requested if not bool(rows_by_key[key][3])]
        if inactive:
            raise ConfigurationError(f"Inactive parser categories: {', '.join(inactive)}")

        active_definitions = [
            self._definition_from_row(row[0], row[1], row[2], row[4])
            for row in rows
            if bool(row[3])
        ]
        self._validate_loaded(active_definitions)
        definitions_by_key = {definition.key: definition for definition in active_definitions}
        return [definitions_by_key[key] for key in requested]

    def _load_configurations(
        self,
        *,
        active_only: bool,
    ) -> list[tuple[object, object, object, bool, list[CrawlTarget]]]:
        """Снять атомарный снимок категорий и их нормализованных целей обхода."""

        statement = (
            select(
                Category.key,
                Category.name,
                Category.note,
                ParserCategory.is_active,
                ParserCategoryTarget.relative_path,
                ParserCategoryTarget.source_rubric_number_id,
                ParserCategoryTarget.taxonomy_level,
                ParserCategory.category_id,
            )
            .join(ParserCategory, ParserCategory.category_id == Category.id)
            .outerjoin(
                ParserCategoryTarget,
                and_(
                    ParserCategoryTarget.category_id == ParserCategory.category_id,
                    ParserCategoryTarget.is_active.is_(True),
                ),
            )
            .order_by(
                ParserCategory.sort_order,
                ParserCategory.category_id,
                ParserCategoryTarget.sort_order,
                ParserCategoryTarget.id,
            )
        )
        if active_only:
            statement = statement.where(ParserCategory.is_active.is_(True))

        with self.session_factory() as session:
            rows = session.execute(statement).all()
            catalog_nodes = {
                "occupation": self._catalog_nodes(
                    session,
                    YandexOccupation,
                    CategoryYandexOccupation,
                    "occupation_id",
                ),
                "specialization": self._catalog_nodes(
                    session,
                    YandexSpecialization,
                    CategoryYandexSpecialization,
                    "specialization_id",
                ),
                "service": self._catalog_nodes(
                    session,
                    YandexService,
                    CategoryYandexService,
                    "service_id",
                ),
            }

        grouped: dict[str, tuple[object, object, object, bool, list[CrawlTarget]]] = {}
        for row in rows:
            key = str(row.key)
            if key not in grouped:
                grouped[key] = (row.key, row.name, row.note, bool(row.is_active), [])
            if isinstance(row.relative_path, str):
                rubric_id = int(row.source_rubric_number_id)
                level = str(row.taxonomy_level)
                try:
                    path_rubric_id = validate_seed_path(row.relative_path)
                except (TypeError, ValueError) as exc:
                    raise ConfigurationError(
                        f"Parser category {key!r} has an invalid crawl target: {exc}"
                    ) from exc
                if path_rubric_id != rubric_id:
                    raise ConfigurationError(
                        f"Parser category {key!r} crawl target ID {rubric_id} "
                        f"does not match path ID {path_rubric_id}"
                    )
                if level not in catalog_nodes:
                    raise ConfigurationError(
                        f"Parser category {key!r} has a target outside Yandex catalog"
                    )
                node = catalog_nodes[level].get((int(row.category_id), rubric_id))
                if node is None:
                    raise ConfigurationError(
                        f"Parser category {key!r} references an unmapped "
                        f"Yandex catalog {level} ID {rubric_id}"
                    )
                catalog_slug, source_url, verification_status = node
                if verification_status not in _USABLE_VERIFICATION_STATUSES:
                    raise ConfigurationError(
                        f"Parser category {key!r} references unverified {level} ID {rubric_id}"
                    )
                try:
                    catalog_path = self._catalog_path(catalog_slug, source_url, rubric_id)
                except (TypeError, ValueError) as exc:
                    raise ConfigurationError(
                        f"Parser category {key!r} has an invalid {level} catalog slug: {exc}"
                    ) from exc
                if row.relative_path != catalog_path:
                    raise ConfigurationError(
                        f"Parser category {key!r} crawl target path does not match "
                        f"Yandex catalog {level} ID {rubric_id}"
                    )
                grouped[key][4].append((catalog_path, rubric_id, level))
        return list(grouped.values())

    @staticmethod
    def _catalog_nodes(
        session: Session,
        model: type[Any],
        mapping_model: type[Any],
        mapping_foreign_key: str,
    ) -> dict[tuple[int, int], CatalogNode]:
        """Загрузить узлы уровня вместе с их точной внутренней группой."""

        mapping_column = getattr(mapping_model, mapping_foreign_key)
        rows = session.execute(
            select(
                mapping_model.category_id,
                model.external_number_id,
                model.slug,
                model.source_url,
                model.verification_status,
            )
            .join(model, model.id == mapping_column)
            .where(model.external_number_id.is_not(None))
        )
        return {
            (int(row.category_id), int(row.external_number_id)): (
                None if row.slug is None else str(row.slug),
                None if row.source_url is None else str(row.source_url),
                str(row.verification_status),
            )
            for row in rows
        }

    @staticmethod
    def _catalog_path(slug: str | None, source_url: str | None, rubric_id: int) -> str:
        """Построить seed path из канонического URL и проверить его по slug."""

        if (
            not isinstance(slug, str)
            or not slug
            or slug != slug.strip()
            or not slug.startswith("/")
            or slug.endswith("/")
        ):
            raise ValueError("catalog slug is missing")
        slug_path = f"{slug[1:]}--{rubric_id}"
        if validate_seed_path(slug_path) != rubric_id:
            raise ValueError("catalog slug contains a different rubric ID")

        if not isinstance(source_url, str) or not source_url or source_url != source_url.strip():
            raise ValueError("catalog source_url is missing")
        parsed = urlsplit(source_url)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "uslugi.yandex.ru"
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("catalog source_url is not canonical")
        path_parts = parsed.path.split("/")
        if len(path_parts) >= 3 and not path_parts[0] and path_parts[1] == "category":
            source_path = "/".join(path_parts[2:])
        elif len(path_parts) >= 4 and not path_parts[0] and path_parts[2] == "category":
            try:
                validate_geo_slug(path_parts[1])
            except (TypeError, ValueError) as exc:
                raise ValueError("catalog source_url is not canonical") from exc
            source_path = "/".join(path_parts[3:])
        else:
            raise ValueError("catalog source_url is not canonical")
        if validate_seed_path(source_path) != rubric_id:
            raise ValueError("catalog source_url contains a different rubric ID")
        if source_path != slug_path:
            raise ValueError("catalog source_url and slug do not match")
        return source_path

    @staticmethod
    def _definition_from_row(
        key: object,
        name: object,
        note: object,
        targets: object,
    ) -> CategoryDefinition:
        """Преобразовать одну строку JOIN в проверенное доменное определение."""

        if not isinstance(key, str) or not isinstance(name, str):
            raise ConfigurationError("Parser category key and name must be strings")
        if key in RESERVED_PARSER_CATEGORY_KEYS:
            raise ConfigurationError(f"Parser category {key!r} uses a reserved key")
        if note is not None and not isinstance(note, str):
            raise ConfigurationError(f"Parser category {key!r} has an invalid note")
        if not isinstance(targets, list) or not targets:
            raise ConfigurationError(
                f"Parser category {key!r} must contain at least one active crawl target"
            )
        if not all(
            isinstance(target, tuple)
            and len(target) == 3
            and isinstance(target[0], str)
            and isinstance(target[1], int)
            and isinstance(target[2], str)
            for target in targets
        ):
            raise ConfigurationError(f"Parser category {key!r} crawl targets are malformed")
        try:
            return CategoryDefinition(
                key=key,
                name=name,
                seed_paths=tuple(target[0] for target in targets),
                note=note or "",
                taxonomy_levels=tuple(target[2] for target in targets),
            )
        except (TypeError, ValueError) as exc:
            raise ConfigurationError(f"Invalid parser category {key!r}: {exc}") from exc

    @staticmethod
    def _validate_loaded(definitions: list[CategoryDefinition]) -> None:
        """Проверить непустой снимок и глобальную уникальность исходных рубрик."""

        if not definitions:
            raise ConfigurationError("No active parser categories are configured")
        try:
            validate_category_definitions(definitions)
        except (TypeError, ValueError) as exc:
            raise ConfigurationError(f"Invalid parser category configuration: {exc}") from exc
