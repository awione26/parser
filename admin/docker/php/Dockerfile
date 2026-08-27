FROM composer:2.8 AS vendor

WORKDIR /app
COPY . .
RUN composer install \
    --no-dev \
    --no-interaction \
    --no-progress \
    --prefer-dist \
    --optimize-autoloader

FROM php:8.3-fpm-alpine

RUN apk add --no-cache icu-libs libzip oniguruma \
    && apk add --no-cache --virtual .build-deps icu-dev libzip-dev oniguruma-dev \
    && docker-php-ext-install intl mbstring pdo_mysql zip \
    && apk del .build-deps

WORKDIR /var/www/html
COPY . .
COPY --from=vendor /app/vendor ./vendor
COPY --from=vendor /app/bootstrap/cache ./bootstrap/cache
COPY docker/php/start.sh /usr/local/bin/start-admin

RUN chmod 0755 /usr/local/bin/start-admin \
    && chown -R www-data:www-data storage bootstrap/cache

USER www-data
CMD ["/usr/local/bin/start-admin"]
