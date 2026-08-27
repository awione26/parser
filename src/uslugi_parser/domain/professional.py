"""Доменное представление разобранной карточки мастера."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from uslugi_parser.domain.rubric import RubricEvidence

SOURCE = "uslugi.yandex.ru"


@dataclass(slots=True)
class ParsedProfessional:
    """Представляет нормализованные публичные данные карточки мастера и её рубрики."""

    source_profile_id: str
    profile_url: str
    full_name: str | None
    phone: str | None
    phone_status: str
    city: str | None
    region: str | None
    country: str | None
    age: int | None
    age_as_of: date
    gender: str | None
    experience_code: int | None
    experience_text: str | None
    photo_url: str | None
    account_type: str | None
    rubrics: tuple[RubricEvidence, ...] = ()
    source: str = SOURCE

    def public_dict(self) -> dict[str, Any]:
        """Формирует публичный словарь с вложенными локацией и опытом без служебных рубрик."""

        return {
            "source": self.source,
            "source_profile_id": self.source_profile_id,
            "profile_url": self.profile_url,
            "full_name": self.full_name,
            "phone": self.phone,
            "phone_status": self.phone_status,
            "location": {
                "city": self.city,
                "region": self.region,
                "country": self.country,
            },
            "age": self.age,
            "age_as_of": self.age_as_of.isoformat(),
            "gender": self.gender,
            "experience": {
                "code": self.experience_code,
                "text": self.experience_text,
            },
            "photo_url": self.photo_url,
            "account_type": self.account_type,
        }

    def content_payload(self) -> dict[str, Any]:
        """Возвращает полный payload для сравнения содержимого с датой в формате ISO 8601."""

        payload = asdict(self)
        payload["age_as_of"] = self.age_as_of.isoformat()
        return payload
