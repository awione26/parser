#!/bin/sh
set -eu

if [ -z "${APP_KEY:-}" ]; then
    echo "ADMIN_APP_KEY is empty; generate and set it before starting the admin panel." >&2
    exit 1
fi

rm -f /tmp/admin-ready
touch /tmp/admin-ready
exec php-fpm
