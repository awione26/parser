"""Нормализация возраста и опыта мастера из исходных значений профиля."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


def calculate_age(dob: date, on_date: date) -> int:
    """Вычисляет число полных лет на заданную дату для воспроизводимого возраста."""

    return on_date.year - dob.year - ((on_date.month, on_date.day) < (dob.month, dob.day))


def parse_dob(value: object) -> date | None:
    """Разбирает поддерживаемые даты рождения, не падая на плохих данных."""

    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return parsed.date()


def experience_values(worker: dict[str, Any]) -> list[int]:
    """Собирает корректные коды опыта из профессий и специализаций мастера."""

    result: list[int] = []
    occupations = worker.get("occupations")
    if not isinstance(occupations, list):
        return result
    for occupation in occupations:
        if not isinstance(occupation, dict):
            continue
        occupation_attrs = occupation.get("attrs")
        occupation_experience = (
            occupation_attrs.get("experience") if isinstance(occupation_attrs, dict) else None
        )
        if isinstance(occupation_experience, int) and occupation_experience >= 0:
            result.append(occupation_experience)
        specializations = occupation.get("specializations")
        if not isinstance(specializations, list):
            continue
        for specialization in specializations:
            if not isinstance(specialization, dict):
                continue
            attrs = specialization.get("attrs")
            value = attrs.get("experience") if isinstance(attrs, dict) else None
            if isinstance(value, int) and value >= 0:
                result.append(value)
    return result


def experience_label(code: int | None) -> str | None:
    """Преобразует код опыта в понятную русскую подпись для хранения и UI."""

    if code is None:
        return None
    if code >= 11:
        return "Более 10 лет"
    if code == 0:
        return "Без опыта"
    remainder_10 = code % 10
    remainder_100 = code % 100
    if remainder_10 == 1 and remainder_100 != 11:
        noun = "год"
    elif remainder_10 in {2, 3, 4} and remainder_100 not in {12, 13, 14}:
        noun = "года"
    else:
        noun = "лет"
    return f"{code} {noun}"
