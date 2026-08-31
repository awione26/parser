"""Создать управляемый каталог категорий парсинга и заполнить его.

Revision ID: 20260831_07
Revises: 20260827_06
Create Date: 2026-08-31
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

revision: str = "20260831_07"
down_revision: str | None = "20260827_06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PRIMARY_KEY_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")

# Миграция намеренно хранит собственный неизменяемый снимок данных и не импортирует
# runtime-каталог: будущая правка приложения не должна менять старую ревизию Alembic.
_CATEGORY_SEEDS: tuple[tuple[str, str, tuple[str, ...], str | None], ...] = (
    ("designers", "Дизайнеры", ("dizajneryi--217",), None),
    (
        "estimators",
        "Сметчики",
        (
            "remont-i-stroitelstvo/proektirovanie-i-smetyi/sostavlenie-smetyi--1809",
            "remont-i-stroitelstvo/proektirovanie-i-smetyi/"
            "sostavlenie-smetyi-na-stroitelnyie-rabotyi--1815",
            "remont-i-stroitelstvo/proektirovanie-i-smetyi/"
            "sostavlenie-smetyi-na-remontnyie-rabotyi--1814",
            "remont-i-stroitelstvo/proektirovanie-i-smetyi/"
            "sostavlenie-smetyi-na-proektnyie-rabotyi--1812",
            "remont-i-stroitelstvo/proektirovanie-i-smetyi/"
            "sostavlenie-smetyi-na-montazh-oborudovaniya--1811",
            "remont-i-stroitelstvo/proektirovanie-i-smetyi/"
            "sostavlenie-smetyi-na-izyiskatelskie-rabotyi--1810",
            "remont-i-stroitelstvo/proektirovanie-i-smetyi/"
            "sostavlenie-smetyi-na-puskonaladochnyie-rabotyi--1813",
        ),
        "Объединение семи официальных услуг по составлению смет.",
    ),
    (
        "plumbers",
        "Сантехник",
        ("remont-i-stroitelstvo/santehnicheskie-rabotyi-i-otoplenie--1844",),
        None,
    ),
    (
        "electricians",
        "Электрик",
        ("remont-i-stroitelstvo/elektromontazhnyie-rabotyi--2007",),
        None,
    ),
    (
        "carpenters",
        "Плотник",
        ("remont-i-stroitelstvo/stoljarnye-i-plotnitskie-raboty--5788",),
        None,
    ),
    (
        "furniture_assemblers",
        "Сборщик мебели",
        (
            "remont-i-stroitelstvo/mebel/sborka-mebeli--4638",
            "remont-i-stroitelstvo/sborka-i-remont-mebeli/sborka-komplekta-mebeli--5954",
            "remont-i-stroitelstvo/mebel/sborka-kuhni--4641",
            "remont-i-stroitelstvo/mebel/sobrat-kuhonnyij-garnitur--4643",
            "remont-i-stroitelstvo/mebel/sobrat-shkaf--4635",
            "remont-i-stroitelstvo/mebel/sborka-shkafa--4642",
            "remont-i-stroitelstvo/mebel/sobrat-divan--4630",
        ),
        "Точные услуги сборки; ремонт и разборка мебели исключены.",
    ),
    (
        "finishers",
        "Отделочник",
        (
            "remont-i-stroitelstvo/remont-kvartir-i-domov/chistovaya-otdelka--1827",
            "remont-i-stroitelstvo/remont-kvartir-i-domov/chernovaya-otdelka--1826",
            "remont-i-stroitelstvo/remont-kvartir-i-domov/kosmeticheskij-remont-kvartiryi--1820",
            "remont-i-stroitelstvo/oboi-i-malyarnyie-rabotyi/poklejka-oboev--1679",
            "remont-i-stroitelstvo/oboi-i-malyarnyie-rabotyi/pokraska-sten--1686",
            "remont-i-stroitelstvo/oboi-i-malyarnyie-rabotyi/shtukaturka-sten--1692",
            "remont-i-stroitelstvo/oboi-i-malyarnyie-rabotyi/shpatlevanie-poverhnosti--1690",
            "remont-i-stroitelstvo/plitochnyie-rabotyi/ukladka-plitki--1755",
            "remont-i-stroitelstvo/polyi-i-napolnyie-pokryitiya/ukladka-laminata--1777",
            "remont-i-stroitelstvo/polyi-i-napolnyie-pokryitiya/ukladka-linoleuma--1778",
            "remont-i-stroitelstvo/drugoe/montazh-peregorodok-iz-gipsokartona--5695",
            "remont-i-stroitelstvo/drugoe/obshivka-sten-gipsokartonom--5697",
            "remont-i-stroitelstvo/potolki/ustanovka-natyajnogo-potolka--1795",
        ),
        "Allowlist конкретных чистовых, черновых и отделочных услуг.",
    ),
    (
        "appliance_repair",
        "Мастер по ремонту бытовой техники",
        (
            "remont-i-ustanovka-tehniki/stiralnyie-mashinyi/remont-stiralnoj-mashinyi--4023",
            "remont-i-ustanovka-tehniki/posudomoechnyie-mashinyi/"
            "remont-posudomoechnyih-mashin--4064",
            "remont-i-ustanovka-tehniki/holodilniki/remont-holodilnika--2237",
            "remont-i-ustanovka-tehniki/kuhonnyie-plityi/remont-kuhonnoj-plityi--2079",
            "remont-i-ustanovka-tehniki/remont-melkoj-byitovoj-tehniki/"
            "remont-melkoj-byitovoj-tehniki--2101",
            "remont-i-ustanovka-tehniki/sushilnyie-mashinyi/remont-sushilnoj-mashinyi--4448",
            "remont-i-ustanovka-tehniki/dukhovie-shkafi/remont-dukhovogo-shkafa--6226",
            "remont-i-ustanovka-tehniki/varochnie-paneli/remont-varochnoi-paneli--6223",
            "remont-i-ustanovka-tehniki/morozilnie-kameri/remont-morozilnoi-kameri--6416",
            "remont-i-ustanovka-tehniki/remont-melkoj-byitovoj-tehniki/remont-vyityazhki--5362",
            "remont-i-ustanovka-tehniki/remont-melkoj-byitovoj-tehniki/remont-kofemashinyi--5360",
        ),
        "Только услуги ремонта бытовой техники; установка исключена.",
    ),
    (
        "window_repair",
        "Мастер по ремонту окон",
        (
            "remont-i-stroitelstvo/okna-i-balkonyi/remont-okon--1725",
            "remont-i-stroitelstvo/okna-i-balkonyi/zamena-stekol--1715",
            "remont-i-stroitelstvo/okna-i-balkonyi/uteplenie-okon--4299",
            "remont-i-stroitelstvo/okna-i-balkonyi/ustanovka-ili-zamena-okonnyih-ruchek--1727",
            "remont-i-stroitelstvo/okna-i-balkonyi/"
            "germetizatsiya-mest-primyikaniya-okonnoj-ramyi--1712",
            "remont-i-stroitelstvo/okna-i-balkonyi/germetizatsiya-okon--1713",
            "remont-i-stroitelstvo/okna-i-balkonyi/zvukoizolyatsiya-okon--4300",
            "remont-i-stroitelstvo/okna-i-balkonyi/diagnostika--6405",
        ),
        "Только ремонтные оконные услуги; балконные работы исключены.",
    ),
    (
        "locks_and_doors",
        "Мастер по замкам и дверям",
        (
            "remont-i-stroitelstvo/dveri-i-zamki/remont-zamka--5320",
            "remont-i-stroitelstvo/remont-i-ustanovka-zamkov/"
            "remont-zamka-mezhkomnatnoi-dveri--6442",
            "remont-i-stroitelstvo/dveri-i-zamki/ustanovka-zamka--5321",
            "remont-i-stroitelstvo/remont-i-ustanovka-zamkov/"
            "ustanovka-zamka-dlya-mezhkomnatnoi-dveri--6441",
            "remont-i-stroitelstvo/dveri-i-zamki/zamena-zamka--5323",
            "remont-i-stroitelstvo/remont-i-ustanovka-zamkov/"
            "zamena-zamka-mezhkomnatnoi-dveri--6443",
            "remont-i-stroitelstvo/dveri-i-zamki/zamena-tsilindra-zamka--5322",
            "remont-i-stroitelstvo/dveri-i-zamki/vskryitie-zamka--5273",
            "remont-i-stroitelstvo/vskrytie-zamkov/vskritie-zamka-ot-vkhodnoi-dveri--6436",
            "remont-i-stroitelstvo/vskrytie-zamkov/vskritie-zamka-ot-mezhkomnatnoi-dveri--6437",
            "remont-i-stroitelstvo/dveri-i-zamki/remont-dverej--5314",
            "remont-i-stroitelstvo/dveri-i-zamki/ustanovka-mezhkomnatnoj-dveri--5291",
            "remont-i-stroitelstvo/dveri-i-zamki/ustanovka-vhodnoj-dveri--5295",
        ),
        "Allowlist строительных дверей и замков; авто-, сейфовые и гаражные исключены.",
    ),
    (
        "low_voltage",
        "Мастер по слаботочным системам",
        ("remont-i-stroitelstvo/slabotochnye-sistemy--5784",),
        None,
    ),
)


def _upsert_master_categories(categories: sa.TableClause) -> None:
    """Добавить либо синхронизировать 11 master-категорий без изменения их ID."""

    bind = op.get_bind()
    dialect = bind.dialect.name
    for key, name, _paths, note in _CATEGORY_SEEDS:
        values = {
            "key": key,
            "name": name,
            "note": note,
            "created_at": sa.func.current_timestamp(),
            "updated_at": sa.func.current_timestamp(),
        }
        if dialect == "mysql":
            statement = mysql_insert(categories).values(**values)
            statement = statement.on_duplicate_key_update(
                name=statement.inserted.name,
                note=statement.inserted.note,
                updated_at=sa.func.current_timestamp(),
            )
            op.execute(statement)
        elif dialect == "sqlite":
            statement = sqlite_insert(categories).values(**values)
            statement = statement.on_conflict_do_update(
                index_elements=["key"],
                set_={
                    "name": name,
                    "note": note,
                    "updated_at": sa.func.current_timestamp(),
                },
            )
            op.execute(statement)
        else:
            connection = op.get_bind()
            existing_id = connection.scalar(
                sa.select(categories.c.id).where(categories.c.key == key)
            )
            if existing_id is None:
                connection.execute(categories.insert().values(**values))
            else:
                connection.execute(
                    categories.update()
                    .where(categories.c.id == existing_id)
                    .values(
                        name=name,
                        note=note,
                        updated_at=sa.func.current_timestamp(),
                    )
                )


def upgrade() -> None:
    """Создать конфигурации обхода и заполнить их 11 разрешёнными категориями."""

    categories = sa.table(
        "categories",
        sa.column("id", _PRIMARY_KEY_TYPE),
        sa.column("key", sa.String(length=64)),
        sa.column("name", sa.String(length=255)),
        sa.column("note", sa.Text()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )
    _upsert_master_categories(categories)

    op.create_table(
        "parser_categories",
        sa.Column("category_id", _PRIMARY_KEY_TYPE, nullable=False),
        sa.Column("seed_paths", sa.JSON(), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("sort_order >= 0", name="ck_parser_categories_sort_order"),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name="fk_parser_categories_category_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("category_id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index(
        "ix_parser_categories_active_order",
        "parser_categories",
        ["is_active", "sort_order", "category_id"],
        unique=False,
    )

    parser_categories = sa.table(
        "parser_categories",
        sa.column("category_id", _PRIMARY_KEY_TYPE),
        sa.column("seed_paths", sa.JSON()),
        sa.column("is_active", sa.Boolean()),
        sa.column("sort_order", sa.Integer()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )
    for position, (key, _name, seed_paths, _note) in enumerate(_CATEGORY_SEEDS, start=1):
        source = sa.select(
            categories.c.id,
            sa.literal(json.dumps(seed_paths, ensure_ascii=False), type_=sa.Text()),
            sa.true(),
            sa.literal(position * 10),
            sa.func.current_timestamp(),
            sa.func.current_timestamp(),
        ).where(categories.c.key == key)
        op.execute(
            parser_categories.insert().from_select(
                [
                    "category_id",
                    "seed_paths",
                    "is_active",
                    "sort_order",
                    "created_at",
                    "updated_at",
                ],
                source,
            )
        )


def downgrade() -> None:
    """Удалить только настройки обхода, сохранив категории и связи мастеров."""

    op.drop_index("ix_parser_categories_active_order", table_name="parser_categories")
    op.drop_table("parser_categories")
