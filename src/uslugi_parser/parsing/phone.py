"""Извлечение и единообразная нормализация публичных телефонных номеров."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, urlsplit


def normalize_phone(value: object, country: str | None = None) -> str | None:
    """Нормализует телефон к виду с плюсом для единообразного поиска и хранения."""

    if not isinstance(value, (str, int)):
        return None
    raw = str(value).strip()
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if not 8 <= len(digits) <= 15:
        return None
    country_is_russia = bool(country and country.casefold() in {"россия", "russia"})
    explicit_international_prefix = raw.lstrip().startswith("+")
    if (
        country_is_russia
        and not explicit_international_prefix
        and len(digits) == 11
        and digits.startswith("8")
    ):
        digits = "7" + digits[1:]
    elif len(digits) == 10 and country_is_russia:
        digits = "7" + digits
    return "+" + digits


def normalize_whatsapp_phone(value: object, country: str | None = None) -> str | None:
    """Извлекает номер из WhatsApp-ссылки, не считая трекинг частью телефона."""

    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    candidate = raw
    url_value = raw
    if raw.casefold().startswith(("wa.me/", "api.whatsapp.com/", "www.whatsapp.com/")):
        url_value = "https://" + raw
    parsed = urlsplit(url_value)
    if parsed.scheme == "whatsapp":
        phone_values = parse_qs(parsed.query, keep_blank_values=True).get("phone", [])
        if len(phone_values) != 1:
            return None
        candidate = phone_values[0]
    elif parsed.scheme and parsed.netloc:
        host = (parsed.hostname or "").casefold()
        if host.startswith("www."):
            host = host[4:]
        if host == "wa.me":
            segments = [segment for segment in parsed.path.split("/") if segment]
            if len(segments) != 1:
                return None
            candidate = segments[0]
        elif host in {"api.whatsapp.com", "whatsapp.com"}:
            phone_values = parse_qs(parsed.query, keep_blank_values=True).get("phone", [])
            if len(phone_values) != 1:
                return None
            candidate = phone_values[0]
        else:
            return None
    elif any(character in raw for character in ("/", "?", "&")):
        return None
    return normalize_phone(candidate, country)


def phone_from_worker(worker: dict[str, Any], country: str | None) -> tuple[str | None, str]:
    """Ищет только публичный телефон мастера и возвращает статус доступности."""

    personal = worker.get("personalInfo")
    personal = personal if isinstance(personal, dict) else {}
    # phoneId — внутренний идентификатор, его нельзя принимать за номер телефона.
    for container in (personal, worker):
        for key in ("phone", "publicPhone", "phoneNumber"):
            phone = normalize_phone(container.get(key), country)
            if phone:
                return phone, "public_profile"

    social_links = personal.get("socialLinks")
    if isinstance(social_links, dict):
        messengers = social_links.get("messengers")
        if isinstance(messengers, dict):
            phone = normalize_whatsapp_phone(messengers.get("whatsapp"), country)
            if phone:
                return phone, "public_messenger"
    display_options = worker.get("displayOptions")
    if isinstance(display_options, dict) and display_options.get("hasPhone") is False:
        return None, "not_public"
    return None, "not_requested"
