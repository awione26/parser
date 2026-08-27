"""Экспорт чистых функций извлечения и нормализации данных Яндекс Услуг.

Пакет сохраняет прежний публичный API ``uslugi_parser.parsing``, чтобы разделение
реализации по ролям не требовало изменений от вызывающего кода.
"""

from uslugi_parser.exceptions import CaptchaDetected, ParseError
from uslugi_parser.parsing.category_parser import (
    match_rubric,
    parse_category_html,
    parse_category_state,
)
from uslugi_parser.parsing.experience import calculate_age, experience_label
from uslugi_parser.parsing.phone import normalize_phone, normalize_whatsapp_phone
from uslugi_parser.parsing.preloaded_state import (
    detect_captcha,
    extract_preloaded_state,
    find_profile_worker,
)
from uslugi_parser.parsing.profile_parser import parse_profile_html, parse_profile_state
from uslugi_parser.parsing.urls import (
    add_page_query,
    canonicalize_live_profile_url,
    canonicalize_profile_url,
    seed_number_id,
)

__all__ = (
    "CaptchaDetected",
    "ParseError",
    "add_page_query",
    "calculate_age",
    "canonicalize_live_profile_url",
    "canonicalize_profile_url",
    "detect_captcha",
    "experience_label",
    "extract_preloaded_state",
    "find_profile_worker",
    "match_rubric",
    "normalize_phone",
    "normalize_whatsapp_phone",
    "parse_category_html",
    "parse_category_state",
    "parse_profile_html",
    "parse_profile_state",
    "seed_number_id",
)
