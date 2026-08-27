"""Асинхронное ограничение частоты запросов к внешнему сайту."""

from __future__ import annotations

import asyncio
import random
import time


class PoliteRateLimiter:
    """Выдерживать случайный минимальный интервал между HTTP-запросами."""

    def __init__(self, min_delay: float, max_delay: float) -> None:
        """Сохранить диапазон задержки и создать блокировку общей очереди."""

        self.min_delay = min_delay
        self.max_delay = max_delay
        self._lock = asyncio.Lock()
        self._last_request = 0.0

    async def wait(self) -> None:
        """Асинхронно дождаться разрешённого момента следующего запроса."""

        async with self._lock:
            delay = random.uniform(self.min_delay, self.max_delay)
            remaining = self._last_request + delay - time.monotonic()
            if remaining > 0:
                await asyncio.sleep(remaining)
            self._last_request = time.monotonic()
