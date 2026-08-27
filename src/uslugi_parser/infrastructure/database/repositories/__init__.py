"""Репозитории для сохранения доменных сущностей в базе данных."""

from uslugi_parser.infrastructure.database.repositories.parser_log import (
    ParserLogRepository,
)
from uslugi_parser.infrastructure.database.repositories.professional import (
    ProfessionalRepository,
)

__all__ = ["ParserLogRepository", "ProfessionalRepository"]
