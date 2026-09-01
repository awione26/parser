"""Read-only репозиторий настроенных в базе категорий обхода."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import and_, select
from sqlalchemy.orm import Session, sessionmaker

from uslugi_parser.catalog import (
    RESERVED_PARSER_CATEGORY_KEYS,
    CategoryDefinition,
    validate_category_definitions,
    validate_category_key,
    validate_seed_path,
)
from uslugi_parser.exceptions import ConfigurationError
from uslugi_parser.infrastructure.database.models import (
    Category,
    ParserCategory,
    ParserCategoryTarget,
    YandexOccupation,
    YandexService,
    YandexSpecialization,
)

CrawlTarget = tuple[str, int, str]


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
            known_ids = {
                "occupation": set(
                    session.scalars(
                        select(YandexOccupation.external_number_id).where(
                            YandexOccupation.external_number_id.is_not(None)
                        )
                    )
                ),
                "specialization": set(
                    session.scalars(
                        select(YandexSpecialization.external_number_id).where(
                            YandexSpecialization.external_number_id.is_not(None)
                        )
                    )
                ),
                "service": set(
                    session.scalars(
                        select(YandexService.external_number_id).where(
                            YandexService.external_number_id.is_not(None)
                        )
                    )
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
                if level != "unknown" and rubric_id not in known_ids.get(level, set()):
                    raise ConfigurationError(
                        f"Parser category {key!r} references unknown {level} ID {rubric_id}"
                    )
                grouped[key][4].append((row.relative_path, rubric_id, level))
        return list(grouped.values())

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
