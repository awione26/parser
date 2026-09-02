<?php

namespace App\Support;

use App\Models\YandexOccupation;
use App\Models\YandexService;
use App\Models\YandexSpecialization;
use Illuminate\Database\Eloquent\Model;

/**
 * Хранит единый контракт уровней и канонических адресов Яндекс.Каталога.
 */
final class YandexCatalog
{
    /** @var list<string> */
    public const array USABLE_STATUSES = [
        'confirmed',
        'discovered',
        'legacy',
    ];

    /** @var array<string, string> */
    public const array STATUS_LABELS = [
        'confirmed' => 'Подтверждено',
        'discovered' => 'Найдено на сайте',
        'legacy' => 'Ранее проверено',
    ];

    /** @var array<string, string> */
    public const array LEVEL_LABELS = [
        'occupation' => 'Направление',
        'specialization' => 'Специализация',
        'service' => 'Услуга',
    ];

    /**
     * Вернуть модель, таблицу связей и имя внешнего ключа для уровня каталога.
     *
     * @return array{model: class-string<Model>, table: string, mapping: string, foreign_key: string, parent_key: string|null}|null
     */
    public static function definition(string $level): ?array
    {
        return match ($level) {
            'occupation' => [
                'model' => YandexOccupation::class,
                'table' => 'yandex_occupations',
                'mapping' => 'category_yandex_occupations',
                'foreign_key' => 'occupation_id',
                'parent_key' => null,
            ],
            'specialization' => [
                'model' => YandexSpecialization::class,
                'table' => 'yandex_specializations',
                'mapping' => 'category_yandex_specializations',
                'foreign_key' => 'specialization_id',
                'parent_key' => 'occupation_id',
            ],
            'service' => [
                'model' => YandexService::class,
                'table' => 'yandex_services',
                'mapping' => 'category_yandex_services',
                'foreign_key' => 'service_id',
                'parent_key' => 'specialization_id',
            ],
            default => null,
        };
    }

    /**
     * Разрешить внешнюю ссылку только на HTTPS-хост Яндекс Услуг без параметров.
     */
    public static function safeSourceUrl(mixed $url): ?string
    {
        $value = trim((string) $url);
        if ($value === '' || filter_var($value, FILTER_VALIDATE_URL) === false) {
            return null;
        }

        $parts = parse_url($value);
        if (
            ! is_array($parts)
            || strtolower((string) ($parts['scheme'] ?? '')) !== 'https'
            || strtolower((string) ($parts['host'] ?? '')) !== 'uslugi.yandex.ru'
            || isset($parts['user'])
            || isset($parts['pass'])
            || isset($parts['port'])
            || isset($parts['query'])
            || isset($parts['fragment'])
            || ! str_starts_with((string) ($parts['path'] ?? ''), '/')
        ) {
            return null;
        }

        return $value;
    }

    /**
     * Извлечь относительный путь обхода из канонической ссылки Яндекс.Каталога.
     */
    public static function crawlPath(?string $url, mixed $rubricId): ?string
    {
        if ($url === null || ! is_int($rubricId) || $rubricId <= 0) {
            return null;
        }

        $absolutePath = (string) parse_url($url, PHP_URL_PATH);
        $seedPattern = '(?:[a-z0-9]+(?:-[a-z0-9]+)*\/)*'
            .'[a-z0-9]+(?:-[a-z0-9]+)*--'.preg_quote((string) $rubricId, '/');
        if (preg_match(
            '/\A\/(?:[0-9]+-[a-z0-9]+(?:-[a-z0-9]+)*\/)?category\/(?<seed>'.$seedPattern.')\z/D',
            $absolutePath,
            $matches,
        ) !== 1) {
            return null;
        }

        return $matches['seed'];
    }

    /**
     * Собрать путь обхода из slug и числового ID, одновременно проверив slug.
     */
    public static function catalogPath(mixed $slug, mixed $rubricId): ?string
    {
        if (
            ! is_string($slug)
            || $slug === ''
            || $slug !== trim($slug)
            || ! str_starts_with($slug, '/')
            || str_ends_with($slug, '/')
            || ! is_int($rubricId)
            || $rubricId <= 0
        ) {
            return null;
        }

        $path = substr($slug, 1);
        $suffix = "--{$rubricId}";
        if (str_ends_with($path, $suffix)) {
            return null;
        }
        $path .= $suffix;

        if (preg_match(
            '/\A(?:[a-z0-9]+(?:-[a-z0-9]+)*\/)*[a-z0-9]+(?:-[a-z0-9]+)*'.preg_quote($suffix, '/').'\z/D',
            $path,
        ) !== 1) {
            return null;
        }

        return $path;
    }
}
