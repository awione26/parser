"""Read-only репозиторий настроенных в базе категорий обхода."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from uslugi_parser.catalog import (
    RESERVED_PARSER_CATEGORY_KEYS,
    CategoryDefinition,
    validate_category_definitions,
    validate_category_key,
)
from uslugi_parser.exceptions import ConfigurationError
from uslugi_parser.infrastructure.database.models import Category, ParserCategory


class ParserCategoryRepository:
    """Читать категории обхода из БД без права изменять конфигурацию."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        """Сохранить фабрику коротких read-only сессий."""

        self.session_factory = session_factory

    def list_active(self) -> list[CategoryDefinition]:
        """Вернуть все активные категории в административно заданном порядке."""

        with self.session_factory() as session:
            rows = session.execute(
                select(
                    Category.key,
                    Category.name,
                    Category.note,
                    ParserCategory.seed_paths,
                )
                .join(ParserCategory, ParserCategory.category_id == Category.id)
                .where(ParserCategory.is_active.is_(True))
                .order_by(ParserCategory.sort_order, ParserCategory.category_id)
            ).all()
        definitions = [self._definition_from_row(*row) for row in rows]
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

        with self.session_factory() as session:
            rows = session.execute(
                select(
                    Category.key,
                    Category.name,
                    Category.note,
                    ParserCategory.seed_paths,
                    ParserCategory.is_active,
                )
                .join(ParserCategory, ParserCategory.category_id == Category.id)
                .order_by(ParserCategory.sort_order, ParserCategory.category_id)
            ).all()

        rows_by_key = {str(row.key): row for row in rows}
        missing = [key for key in requested if key not in rows_by_key]
        if missing:
            raise ConfigurationError(f"Unknown parser categories: {', '.join(missing)}")
        inactive = [key for key in requested if not bool(rows_by_key[key].is_active)]
        if inactive:
            raise ConfigurationError(f"Inactive parser categories: {', '.join(inactive)}")

        active_definitions = [
            self._definition_from_row(row.key, row.name, row.note, row.seed_paths)
            for row in rows
            if bool(row.is_active)
        ]
        self._validate_loaded(active_definitions)
        definitions_by_key = {definition.key: definition for definition in active_definitions}
        return [definitions_by_key[key] for key in requested]

    @staticmethod
    def _definition_from_row(
        key: object,
        name: object,
        note: object,
        seed_paths: object,
    ) -> CategoryDefinition:
        """Преобразовать одну строку JOIN в проверенное доменное определение."""

        if not isinstance(key, str) or not isinstance(name, str):
            raise ConfigurationError("Parser category key and name must be strings")
        if key in RESERVED_PARSER_CATEGORY_KEYS:
            raise ConfigurationError(f"Parser category {key!r} uses a reserved key")
        if note is not None and not isinstance(note, str):
            raise ConfigurationError(f"Parser category {key!r} has an invalid note")
        if not isinstance(seed_paths, list) or not seed_paths:
            raise ConfigurationError(
                f"Parser category {key!r} must contain a non-empty JSON array of seed paths"
            )
        if not all(isinstance(path, str) for path in seed_paths):
            raise ConfigurationError(f"Parser category {key!r} seed paths must all be strings")
        try:
            return CategoryDefinition(
                key=key,
                name=name,
                seed_paths=tuple(seed_paths),
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
