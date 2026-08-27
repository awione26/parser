# syntax=docker/dockerfile:1.7
ARG PYTHON_VERSION=3.13.7

FROM python:${PYTHON_VERSION}-slim-bookworm AS wheels

ENV PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src

RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip wheel --wheel-dir=/wheels .

FROM wheels AS phone-wheels

RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip wheel --find-links=/wheels --wheel-dir=/wheels '.[phone]'

FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Europe/Moscow \
    HOME=/home/parser

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ca-certificates tini tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 parser \
    && useradd --system --uid 10001 --gid parser \
       --create-home --home-dir /home/parser parser

WORKDIR /app
COPY alembic.ini ./
COPY migrations ./migrations
COPY docker/parser/entrypoint.sh /usr/local/bin/parser-entrypoint
RUN chmod 0555 /usr/local/bin/parser-entrypoint

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/parser-entrypoint"]
CMD ["categories"]

FROM runtime-base AS runtime

COPY --from=wheels /wheels /wheels
RUN python -m pip install --no-index --find-links=/wheels uslugi-yandex-parser \
    && rm -rf /wheels

USER parser

FROM runtime-base AS runtime-phone

ENV PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       chromium chromium-sandbox \
    && rm -rf /var/lib/apt/lists/*

COPY --from=phone-wheels /wheels /wheels
RUN python -m pip install --no-index --find-links=/wheels 'uslugi-yandex-parser[phone]' \
    && rm -rf /wheels

USER parser
