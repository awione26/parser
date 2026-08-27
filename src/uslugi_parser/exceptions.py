"""Исключения для конфигурации, сети, разбора и защитной остановки парсера."""

from __future__ import annotations


class ConfigurationError(RuntimeError):
    """Сообщает, что конфигурация не позволяет безопасно выполнить запуск."""


class ParseError(RuntimeError):
    """Сообщает об отсутствии ожидаемых публичных данных на странице Яндекса."""


class CaptchaDetected(ParseError):
    """Останавливает обработку при появлении CAPTCHA без попытки её обхода."""


class FetchError(RuntimeError):
    """Описывает ошибку, из-за которой страницу нельзя безопасно загрузить."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        """Сохранить понятное сообщение и необязательный HTTP-статус ответа."""

        super().__init__(message)
        self.status_code = status_code


class BlockingFetchError(FetchError):
    """Требует остановить весь обход после блокирующего HTTP-ответа."""


class RobotsDenied(FetchError):
    """Сообщает, что правила robots.txt запрещают загрузку конкретного URL."""

    def __init__(self, url: str) -> None:
        """Создать ошибку и сохранить запрещённый адрес для диагностики."""

        super().__init__("robots.txt does not allow this URL")
        self.url = url


class UnexpectedOrigin(FetchError):
    """Блокирует навигацию, покинувшую разрешённый домен Яндекса."""


class BlockedRedirect(FetchError):
    """Блокирует небезопасное или запрещённое политикой перенаправление."""


class RobotsUnavailable(FetchError):
    """Останавливает запрос, если robots.txt нельзя надёжно интерпретировать."""


class ServerAskedToStop(FetchError):
    """Останавливает сбор, когда Retry-After требует слишком долгого ожидания."""


class PhoneCollectorUnavailable(RuntimeError):
    """Сообщает, что браузерный сборщик телефона недоступен или не запустился."""


class PhoneNavigationBlocked(RuntimeError):
    """Блокирует браузер, покинувший область публичной карточки профиля."""


class CrawlAborted(RuntimeError):
    """Сообщает о штатной защитной остановке всего обхода."""
