"""SQLAlchemy-модели таблиц мастеров, категорий и исходных рубрик."""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from uslugi_parser import __version__


def utcnow() -> datetime:
    """Вернуть текущее время UTC без timezone для совместимости с MySQL DATETIME."""

    # MySQL DATETIME не хранит часовой пояс, поэтому сохраняем UTC без timezone-метки.
    return datetime.now(UTC).replace(tzinfo=None)


PRIMARY_KEY_TYPE = BigInteger().with_variant(Integer, "sqlite")


class Base(DeclarativeBase):
    """Предоставлять общий декларативный базовый класс ORM-моделей парсера."""

    pass


class ParserLog(Base):
    """Хранить состояние и итог одного запуска сценария парсинга."""

    __tablename__ = "logs"
    __table_args__ = (
        CheckConstraint(
            "result IS NULL OR result IN ('success', 'failure')",
            name="ck_logs_result",
        ),
        CheckConstraint(
            "(result IS NULL AND finished_at IS NULL AND error_reason IS NULL) OR "
            "(result = 'success' AND finished_at IS NOT NULL AND error_reason IS NULL) OR "
            "(result = 'failure' AND finished_at IS NOT NULL AND error_reason IS NOT NULL)",
            name="ck_logs_lifecycle",
        ),
        Index("ix_logs_started_at", "started_at"),
        Index("ix_logs_result_started_at", "result", "started_at"),
        Index("ix_logs_resource_started_at", "resource", "started_at"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    id: Mapped[int] = mapped_column(PRIMARY_KEY_TYPE, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    result: Mapped[str | None] = mapped_column(String(16))
    error_reason: Mapped[str | None] = mapped_column(Text)
    resource: Mapped[str] = mapped_column(String(255), nullable=False)


class Professional(Base):
    """Представлять актуальные данные мастера, полученные из исходного профиля."""

    __tablename__ = "professionals"
    __table_args__ = (
        UniqueConstraint("source", "source_profile_id", name="uq_professional_source_id"),
        Index("ix_professionals_last_scraped_at", "last_scraped_at"),
        Index("ix_professionals_location", "country", "region", "city"),
        Index("ix_professionals_gender_age", "gender", "age"),
        Index("ix_professionals_experience_code", "experience_code"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    id: Mapped[int] = mapped_column(PRIMARY_KEY_TYPE, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_profile_id: Mapped[str] = mapped_column(String(128), nullable=False)
    profile_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(32), index=True)
    phone_status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_requested")
    city: Mapped[str | None] = mapped_column(String(255))
    region: Mapped[str | None] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(128))
    age: Mapped[int | None] = mapped_column(SmallInteger)
    age_as_of: Mapped[date] = mapped_column(Date, nullable=False)
    gender: Mapped[str | None] = mapped_column(String(16))
    experience_code: Mapped[int | None] = mapped_column(SmallInteger)
    experience_text: Mapped[str | None] = mapped_column(String(64))
    photo_url: Mapped[str | None] = mapped_column(Text)
    account_type: Mapped[str | None] = mapped_column(String(32))
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(32), nullable=False, default=__version__)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    last_scraped_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    category_links: Mapped[list[ProfessionalCategory]] = relationship(
        back_populates="professional", cascade="all, delete-orphan"
    )


class Category(Base):
    """Представлять настроенную категорию специалистов в локальном каталоге."""

    __tablename__ = "categories"
    __table_args__ = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}

    id: Mapped[int] = mapped_column(PRIMARY_KEY_TYPE, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    professional_links: Mapped[list[ProfessionalCategory]] = relationship(
        back_populates="category", cascade="all, delete-orphan"
    )


class ProfessionalCategory(Base):
    """Связывать мастера с категорией и хранить сроки наблюдения этой связи."""

    __tablename__ = "professional_categories"
    __table_args__ = (
        Index(
            "ix_professional_categories_category_professional",
            "category_id",
            "professional_id",
        ),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    professional_id: Mapped[int] = mapped_column(
        ForeignKey("professionals.id", ondelete="CASCADE"), primary_key=True
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True
    )
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    professional: Mapped[Professional] = relationship(back_populates="category_links")
    category: Mapped[Category] = relationship(back_populates="professional_links")
    rubrics: Mapped[list[ProfessionalCategoryRubric]] = relationship(
        back_populates="category_link", cascade="all, delete-orphan"
    )


class ProfessionalCategoryRubric(Base):
    """Хранить исходную рубрику, подтвердившую категорию конкретного мастера."""

    __tablename__ = "professional_category_rubrics"
    __table_args__ = (
        ForeignKeyConstraint(
            ["professional_id", "category_id"],
            [
                "professional_categories.professional_id",
                "professional_categories.category_id",
            ],
            ondelete="CASCADE",
        ),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )

    professional_id: Mapped[int] = mapped_column(PRIMARY_KEY_TYPE, primary_key=True)
    category_id: Mapped[int] = mapped_column(PRIMARY_KEY_TYPE, primary_key=True)
    source_rubric_number_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_rubric_id: Mapped[str | None] = mapped_column(String(255))
    source_rubric_seo_id: Mapped[str | None] = mapped_column(String(255))
    source_rubric_name: Mapped[str | None] = mapped_column(String(255))
    experience_code: Mapped[int | None] = mapped_column(SmallInteger)
    experience_text: Mapped[str | None] = mapped_column(String(64))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    category_link: Mapped[ProfessionalCategory] = relationship(back_populates="rubrics")
