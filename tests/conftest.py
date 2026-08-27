from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

import pytest


def make_worker(
    *,
    worker_id: str = "worker-1",
    seoid: str = "123456",
    seoname: str = "TestMaster-123456",
) -> dict[str, Any]:
    return {
        "id": worker_id,
        "ydoWorkerId": worker_id,
        "seoid": seoid,
        "seoname": seoname,
        "displayOptions": {"allowProfileParsing": True, "hasPhone": True},
        "personalInfo": {
            "displayName": "Иван Тестов",
            "firstName": "Иван",
            "lastName": "Тестов",
            "dob": "1990-08-21",
            "gender": "male",
            "avatar": "https://avatars.example.test/get/avatar/abc",
            "accountType": "person",
            "phoneId": "987654321",
            "socialLinks": {"messengers": {"whatsapp": "https://wa.me/79991234567"}},
            "addressesList": [{"address": "Тестоград, Тестовая улица, 1"}],
            "areasList": [
                {
                    "name": "Тестоград",
                    "name_components": [
                        {"kind": "country", "name": "Россия"},
                        {"kind": "province", "name": "Тестовый федеральный округ"},
                        {"kind": "province", "name": "Тестовая область"},
                    ],
                }
            ],
        },
        "address": {
            "name": "Тестоград",
            "nameComponents": {"country": "Россия", "province": "Тестовая область"},
        },
        "occupations": [
            {
                "name": "Ремонт и строительство",
                "rubricId": "/remont-i-stroitel_stvo",
                "numberId": 1344,
                "seoId": "/remont-i-stroitelstvo",
                "specializations": [
                    {
                        "name": "Тестовые работы",
                        "rubricId": ("/remont-i-stroitel_stvo/santehniceskie-raboty-i-otoplenie"),
                        "numberId": 1844,
                        "seoId": ("/remont-i-stroitelstvo/santehnicheskie-rabotyi-i-otoplenie"),
                        "attrs": {"experience": 11},
                        "services": [
                            {
                                "name": "Тестовая услуга",
                                "rubricId": "9999",
                                "numberId": 9999,
                                "seoId": "/test-service",
                            }
                        ],
                    }
                ],
            }
        ],
    }


def make_state(*workers: dict[str, Any]) -> dict[str, Any]:
    if not workers:
        workers = (make_worker(),)
    items = {worker["id"]: deepcopy(worker) for worker in workers}
    return {
        "workers": {
            "singleSearchResultId": workers[0]["id"] if len(workers) == 1 else None,
            "encryptedPhones": {},
            "items": items,
        },
        "search": {
            "workerIds": [worker["id"] for worker in workers],
            "params": {"pagination": {"p": 0, "perPage": 10, "totalItems": len(workers)}},
        },
    }


def html_with_state(state: dict[str, Any]) -> str:
    payload = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
    return (
        "<!doctype html><html><head></head><body>"
        f'<script id="__PRELOADED_STATE__" type="application/json">{payload}</script>'
        "</body></html>"
    )


@pytest.fixture
def worker() -> dict[str, Any]:
    return make_worker()


@pytest.fixture
def profile_html(worker: dict[str, Any]) -> str:
    return html_with_state(make_state(worker))
