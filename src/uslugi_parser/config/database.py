"""Формирование безопасного SQLAlchemy URL для подключения к MySQL."""

from __future__ import annotations

import os
import re
from urllib.parse import quote

_HOST_RE = re.compile(r"\A(?:[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?|\[[0-9A-Fa-f:]+\])\Z")


def database_url_from_env() -> str:
    """Возвращает явный DATABASE_URL либо безопасно собирает и экранирует MySQL DSN."""

    explicit = os.getenv("DATABASE_URL")
    if explicit:
        return explicit

    try:
        port = int(os.getenv("MYSQL_PORT", "3306"))
    except ValueError as exc:
        raise ValueError("MYSQL_PORT must be an integer") from exc
    if not 1 <= port <= 65535:
        raise ValueError("MYSQL_PORT must be between 1 and 65535")

    host = os.getenv("MYSQL_HOST", "127.0.0.1").strip()
    if not _HOST_RE.fullmatch(host):
        raise ValueError("MYSQL_HOST must be a hostname, IPv4 address, or bracketed IPv6 address")

    username = quote(os.getenv("MYSQL_USER", "uslugi"), safe="")
    password = quote(os.getenv("MYSQL_PASSWORD", "change_me"), safe="")
    database = quote(os.getenv("MYSQL_DATABASE", "uslugi"), safe="")
    return f"mysql+pymysql://{username}:{password}@{host}:{port}/{database}?charset=utf8mb4"
