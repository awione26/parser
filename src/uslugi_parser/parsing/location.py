"""Извлечение согласованной локации мастера из адреса и зон обслуживания."""

from __future__ import annotations

from typing import Any


def _component_values(components: object, kind: str) -> list[str]:
    """Извлекает компоненты адреса нужного типа из двух форматов источника."""

    if isinstance(components, dict):
        value = components.get(kind)
        return [str(value).strip()] if value else []
    if isinstance(components, list):
        result: list[str] = []
        for component in components:
            if isinstance(component, dict) and component.get("kind") == kind:
                value = component.get("name")
                if value:
                    result.append(str(value).strip())
        return result
    return []


def location(worker: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    """Возвращает город, регион и страну, не смешивая зоны обслуживания."""

    address = worker.get("address")
    address = address if isinstance(address, dict) else {}
    city = str(address.get("name")).strip() if address.get("name") else None
    components = address.get("nameComponents")
    countries = _component_values(components, "country")
    provinces = _component_values(components, "province")

    def values_from_area(area: object) -> tuple[str | None, str | None, str | None]:
        """Нормализует одну зону обслуживания в согласованную тройку локации."""

        if not isinstance(area, dict):
            return None, None, None
        area_city = str(area.get("name")).strip() if area.get("name") else None
        area_components = area.get("name_components") or area.get("nameComponents")
        area_countries = _component_values(area_components, "country")
        area_provinces = _component_values(area_components, "province")
        specific = [
            value for value in area_provinces if "федеральный округ" not in value.casefold()
        ]
        return (
            area_city,
            (specific or area_provinces or [None])[-1],
            next((value for value in area_countries if value), None),
        )

    personal = worker.get("personalInfo")
    personal = personal if isinstance(personal, dict) else {}
    areas = personal.get("areasList")
    country = next((value for value in countries if value), None)
    specific_provinces = [
        value for value in provinces if "федеральный округ" not in value.casefold()
    ]
    region = (specific_provinces or provinces or [None])[-1]

    if isinstance(areas, list):
        if city:
            # Дополняем только из одной подходящей зоны обслуживания, чтобы не объединять
            # части адресов, которые в источнике никогда не относились к одной локации.
            matching = next(
                (
                    values_from_area(area)
                    for area in areas
                    if isinstance(area, dict)
                    and str(area.get("name") or "").strip().casefold() == city.casefold()
                ),
                None,
            )
            if matching:
                _, matching_region, matching_country = matching
                region = region or matching_region
                country = country or matching_country
        else:
            selected = next(
                (values_from_area(area) for area in areas if values_from_area(area)[0]),
                None,
            )
            if selected:
                city, region, country = selected
    return city, region, country
