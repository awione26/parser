#!/usr/bin/env bash
set -Eeuo pipefail

: "${MYSQL_ROOT_PASSWORD:?MYSQL_ROOT_PASSWORD is required}"
: "${MYSQL_PARSER_PASSWORD:?MYSQL_PARSER_PASSWORD is required}"
: "${MYSQL_ADMIN_PASSWORD:?MYSQL_ADMIN_PASSWORD is required}"

database="${MYSQL_DATABASE:-uslugi}"
if [[ ! "$database" =~ ^[A-Za-z0-9_]+$ ]]; then
    echo "MYSQL_DATABASE must contain only ASCII letters, digits, and underscores." >&2
    exit 1
fi

encode_password() {
    printf '%s' "$1" | base64 | tr -d '\n'
}

parser_password_b64="$(encode_password "$MYSQL_PARSER_PASSWORD")"
admin_password_b64="$(encode_password "$MYSQL_ADMIN_PASSWORD")"

export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"
mysql \
    --protocol=TCP \
    --host="${MYSQL_HOST:-mysql}" \
    --port="${MYSQL_PORT:-3306}" \
    --user=root \
    --batch \
    --skip-column-names <<SQL
SET @parser_password = CONVERT(FROM_BASE64('${parser_password_b64}') USING utf8mb4);
SET @create_parser = CONCAT(
    "CREATE USER IF NOT EXISTS 'uslugi_parser'@'%' IDENTIFIED BY ",
    QUOTE(@parser_password)
);
PREPARE create_parser FROM @create_parser;
EXECUTE create_parser;
DEALLOCATE PREPARE create_parser;
SET @alter_parser = CONCAT(
    "ALTER USER 'uslugi_parser'@'%' IDENTIFIED BY ",
    QUOTE(@parser_password)
);
PREPARE alter_parser FROM @alter_parser;
EXECUTE alter_parser;
DEALLOCATE PREPARE alter_parser;

SET @admin_password = CONVERT(FROM_BASE64('${admin_password_b64}') USING utf8mb4);
SET @create_admin = CONCAT(
    "CREATE USER IF NOT EXISTS 'uslugi_admin'@'%' IDENTIFIED BY ",
    QUOTE(@admin_password)
);
PREPARE create_admin FROM @create_admin;
EXECUTE create_admin;
DEALLOCATE PREPARE create_admin;
SET @alter_admin = CONCAT(
    "ALTER USER 'uslugi_admin'@'%' IDENTIFIED BY ",
    QUOTE(@admin_password)
);
PREPARE alter_admin FROM @alter_admin;
EXECUTE alter_admin;
DEALLOCATE PREPARE alter_admin;

REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'uslugi_parser'@'%';
REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'uslugi_admin'@'%';

GRANT SELECT, INSERT, UPDATE ON ${database}.professionals TO 'uslugi_parser'@'%';
GRANT SELECT, INSERT ON ${database}.professional_identities TO 'uslugi_parser'@'%';
GRANT SELECT, INSERT, UPDATE ON ${database}.categories TO 'uslugi_parser'@'%';
GRANT SELECT ON ${database}.parser_categories TO 'uslugi_parser'@'%';
GRANT SELECT, INSERT, UPDATE ON ${database}.professional_categories TO 'uslugi_parser'@'%';
GRANT SELECT, INSERT, UPDATE ON ${database}.professional_category_rubrics TO 'uslugi_parser'@'%';
GRANT SELECT, INSERT, UPDATE ON ${database}.logs TO 'uslugi_parser'@'%';
GRANT SELECT ON ${database}.settings TO 'uslugi_parser'@'%';
GRANT SELECT ON ${database}.alembic_version TO 'uslugi_parser'@'%';

GRANT SELECT, DELETE ON ${database}.professionals TO 'uslugi_admin'@'%';
GRANT SELECT ON ${database}.professional_identities TO 'uslugi_admin'@'%';
GRANT SELECT, INSERT, UPDATE ON ${database}.categories TO 'uslugi_admin'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON ${database}.parser_categories TO 'uslugi_admin'@'%';
GRANT SELECT ON ${database}.professional_categories TO 'uslugi_admin'@'%';
GRANT SELECT ON ${database}.professional_category_rubrics TO 'uslugi_admin'@'%';
GRANT SELECT ON ${database}.logs TO 'uslugi_admin'@'%';
GRANT SELECT, INSERT, UPDATE ON ${database}.settings TO 'uslugi_admin'@'%';
GRANT SELECT ON ${database}.alembic_version TO 'uslugi_admin'@'%';

GRANT SELECT, INSERT, UPDATE, DELETE ON ${database}.users TO 'uslugi_admin'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON ${database}.password_reset_tokens TO 'uslugi_admin'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON ${database}.sessions TO 'uslugi_admin'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON ${database}.phone_access_logs TO 'uslugi_admin'@'%';
GRANT SELECT ON ${database}.migrations TO 'uslugi_admin'@'%';

FLUSH PRIVILEGES;
SQL
unset MYSQL_PWD

echo "Runtime MySQL users and least-privilege grants are ready."
