from __future__ import annotations

import ast
import importlib
from pathlib import Path
from types import ModuleType

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "uslugi_parser"


def test_layered_package_layout() -> None:
    expected = {
        "cli/__init__.py",
        "cli/commands.py",
        "cli/main.py",
        "application/__init__.py",
        "application/crawl_service.py",
        "application/profile_service.py",
        "application/parser_log_service.py",
        "application/dto.py",
        "domain/__init__.py",
        "domain/professional.py",
        "domain/category.py",
        "domain/rubric.py",
        "domain/crawl.py",
        "domain/parser_log.py",
        "parsing/__init__.py",
        "parsing/profile_parser.py",
        "parsing/category_parser.py",
        "parsing/preloaded_state.py",
        "parsing/location.py",
        "parsing/experience.py",
        "parsing/phone.py",
        "parsing/urls.py",
        "infrastructure/http/fetcher.py",
        "infrastructure/http/rate_limiter.py",
        "infrastructure/http/robots.py",
        "infrastructure/browser/phone_collector.py",
        "infrastructure/database/connection.py",
        "infrastructure/database/models.py",
        "infrastructure/database/repositories/professional.py",
        "infrastructure/database/repositories/parser_log.py",
        "infrastructure/database/repositories/parser_category.py",
        "infrastructure/database/repositories/settings.py",
        "config/settings.py",
        "config/database.py",
        "catalog/categories.py",
        "exceptions.py",
        "__main__.py",
    }
    actual = {
        str(path.relative_to(PACKAGE))
        for path in PACKAGE.rglob("*.py")
        if "__pycache__" not in path.parts
    }
    assert expected <= actual

    old_flat_modules = {
        "categories.py",
        "cli.py",
        "config.py",
        "database.py",
        "db_url.py",
        "domain.py",
        "fetcher.py",
        "parsing.py",
        "phone.py",
        "pipeline.py",
    }
    assert old_flat_modules.isdisjoint(actual)


def test_domain_does_not_depend_on_outer_layers() -> None:
    forbidden = (
        "uslugi_parser.application",
        "uslugi_parser.catalog",
        "uslugi_parser.cli",
        "uslugi_parser.config",
        "uslugi_parser.infrastructure",
        "uslugi_parser.parsing",
    )
    for path in (PACKAGE / "domain").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports = [
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        ]
        assert not any(name.startswith(forbidden) for name in imports), path


def test_parsing_has_no_network_or_database_dependency() -> None:
    forbidden = (
        "sqlalchemy",
        "httpx",
        "playwright",
        "uslugi_parser.infrastructure",
    )
    for path in (PACKAGE / "parsing").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports = [
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        ]
        imports.extend(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        assert not any(name.startswith(forbidden) for name in imports), path


def test_application_uses_ports_instead_of_infrastructure_imports() -> None:
    for path in (PACKAGE / "application").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports = [
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        ]
        assert not any(name.startswith("uslugi_parser.infrastructure") for name in imports), path


def test_cli_main_name_resolves_to_submodule() -> None:
    module = importlib.import_module("uslugi_parser.cli.main")
    assert isinstance(module, ModuleType)


def test_runtime_roles_have_minimal_parser_log_grants() -> None:
    grant_script = (PACKAGE.parents[1] / "docker/mysql/grant-runtime-users.sh").read_text(
        encoding="utf-8"
    )

    assert (
        "GRANT SELECT, INSERT, UPDATE ON ${database}.logs TO 'uslugi_parser'@'%';" in grant_script
    )
    assert (
        "GRANT SELECT, INSERT ON ${database}.professional_identities "
        "TO 'uslugi_parser'@'%';" in grant_script
    )
    assert "GRANT SELECT ON ${database}.logs TO 'uslugi_admin'@'%';" in grant_script
    assert "DELETE ON ${database}.logs" not in grant_script


def test_runtime_roles_have_minimal_parser_setting_grants() -> None:
    """Проверить чтение настроек парсером и редактирование только через админку."""

    grant_script = (PACKAGE.parents[1] / "docker/mysql/grant-runtime-users.sh").read_text(
        encoding="utf-8"
    )

    assert "GRANT SELECT ON ${database}.settings TO 'uslugi_parser'@'%';" in grant_script
    assert (
        "GRANT SELECT, INSERT, UPDATE ON ${database}.settings TO 'uslugi_admin'@'%';"
        in grant_script
    )
    assert "INSERT, UPDATE ON ${database}.settings TO 'uslugi_parser'" not in grant_script
    assert "DELETE ON ${database}.settings" not in grant_script


def test_runtime_roles_separate_parser_category_read_and_admin_write() -> None:
    """Разрешить runtime-парсеру только чтение управляемых категорий."""

    grant_script = (PACKAGE.parents[1] / "docker/mysql/grant-runtime-users.sh").read_text(
        encoding="utf-8"
    )

    assert "GRANT SELECT ON ${database}.parser_categories TO 'uslugi_parser'@'%';" in grant_script
    assert (
        "GRANT SELECT, INSERT, UPDATE ON ${database}.parser_categories "
        "TO 'uslugi_admin'@'%';" in grant_script
    )
    assert (
        "GRANT SELECT, INSERT, UPDATE ON ${database}.parser_category_targets "
        "TO 'uslugi_admin'@'%';" in grant_script
    )
    assert "DELETE ON ${database}.parser_categories" not in grant_script
    assert "DELETE ON ${database}.parser_category_targets" not in grant_script
    assert "INSERT, UPDATE ON ${database}.parser_categories TO 'uslugi_parser'" not in grant_script
