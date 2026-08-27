<?php

namespace App\Support;

/**
 * Описывает единственный разрешённый набор настроек парсера и их формат в БД.
 */
final class ParserSettings
{
    /**
     * Значения соответствуют начальному набору, который создаёт Alembic.
     *
     * @var array<string, string>
     */
    public const array DEFAULTS = [
        'SCRAPER_USER_AGENT' => 'CompanyName-UslugiParser/0.1 (+mailto:parser-owner@example.com)',
        'SCRAPER_GEO' => '213-moscow',
        'SCRAPER_RESPECT_ROBOTS' => 'true',
        'SCRAPER_MIN_DELAY_SECONDS' => '2.0',
        'SCRAPER_MAX_DELAY_SECONDS' => '5.0',
        'SCRAPER_TIMEOUT_SECONDS' => '30.0',
        'SCRAPER_MAX_RETRIES' => '3',
        'SCRAPER_COLLECT_PHONE' => 'false',
        'SCRAPER_PHONE_HEADLESS' => 'true',
        'SCRAPER_PHONE_TIMEOUT_SECONDS' => '15.0',
        'SCRAPER_INCLUDE_ORGANIZATIONS' => 'false',
    ];

    /** @var list<string> */
    public const array BOOLEAN_KEYS = [
        'SCRAPER_RESPECT_ROBOTS',
        'SCRAPER_COLLECT_PHONE',
        'SCRAPER_PHONE_HEADLESS',
        'SCRAPER_INCLUDE_ORGANIZATIONS',
    ];

    /**
     * Вернуть whitelist ключей в стабильном порядке формы.
     *
     * @return list<string>
     */
    public static function keys(): array
    {
        return array_keys(self::DEFAULTS);
    }

    /**
     * Дополнить отсутствующие строки безопасными начальными значениями.
     *
     * @param  array<string, mixed>  $stored
     * @return array<string, string>
     */
    public static function withDefaults(array $stored): array
    {
        $values = self::DEFAULTS;
        foreach (self::keys() as $key) {
            if (array_key_exists($key, $stored)) {
                $values[$key] = (string) $stored[$key];
            }
        }

        return $values;
    }

    /**
     * Привести проверенные значения к строковому формату Python-конфигурации.
     *
     * @param  array<string, mixed>  $validated
     * @return array<string, string>
     */
    public static function normalize(array $validated): array
    {
        $values = [];
        foreach (self::keys() as $key) {
            if (in_array($key, self::BOOLEAN_KEYS, true)) {
                $values[$key] = filter_var($validated[$key], FILTER_VALIDATE_BOOL)
                    ? 'true'
                    : 'false';
            } elseif ($key === 'SCRAPER_MAX_RETRIES') {
                $values[$key] = (string) (int) $validated[$key];
            } else {
                $values[$key] = trim((string) $validated[$key]);
            }
        }

        return $values;
    }

    /**
     * Определить отмеченное состояние checkbox по каноническому значению из БД.
     */
    public static function booleanValue(mixed $value): bool
    {
        return filter_var($value, FILTER_VALIDATE_BOOL);
    }
}
