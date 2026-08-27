#!/bin/sh
set -eu

umask 077

if [ "$#" -eq 0 ]; then
    set -- categories
fi

case "$1" in
    -h|--help|--verbose|categories|parse-html|parse-profile|crawl)
        set -- uslugi-parser "$@"
        ;;
esac

exec "$@"
