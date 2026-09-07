#!/bin/sh
set -eu

# Постоянный worker запускает отдельный crawl для каждого полного прохода, чтобы
# журнал событий сохранял независимый результат каждой итерации.
project_dir="${PARSER_PROJECT_DIR:-/opt/uslugi-parser}"
repeat_interval="${PARSER_REPEAT_INTERVAL_SECONDS:-600}"
child_pid=""
stop_requested=0

case "$repeat_interval" in
    ""|*[!0-9]*)
        echo "PARSER_REPEAT_INTERVAL_SECONDS must be an integer" >&2
        exit 2
        ;;
esac

if [ "$repeat_interval" -lt 60 ]; then
    echo "PARSER_REPEAT_INTERVAL_SECONDS must be at least 60" >&2
    exit 2
fi

stop_worker() {
    # Передать остановку текущему Compose-процессу и не начинать новый проход.
    stop_requested=1
    if [ -n "$child_pid" ]; then
        kill -TERM "$child_pid" 2>/dev/null || true
    fi
}

run_child() {
    # Запустить дочерний процесс так, чтобы trap мог корректно его остановить.
    "$@" &
    child_pid=$!
    set +e
    wait "$child_pid"
    child_status=$?
    set -e
    child_pid=""
    return "$child_status"
}

trap stop_worker INT TERM HUP

cd "$project_dir"

while [ "$stop_requested" -eq 0 ]; do
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) continuous crawl started"
    if run_child docker compose \
        -f compose.yaml \
        -f compose.production.yaml \
        run --rm --no-deps -T parser \
        crawl \
        --category all \
        --max-pages 0 \
        --max-profiles 0 \
        --no-respect-robots \
        --progress; then
        echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) continuous crawl completed"
    else
        crawl_status=$?
        echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) continuous crawl failed: ${crawl_status}" >&2
    fi

    if [ "$stop_requested" -ne 0 ]; then
        break
    fi

    echo "Next crawl starts in ${repeat_interval} seconds"
    run_child sleep "$repeat_interval" || true
done

echo "Continuous crawl stopped"
