<?php

namespace App\Support;

use App\Models\Professional;
use Illuminate\Support\Str;

final class ProfessionalPresenter
{
    public static function location(Professional $professional): string
    {
        $parts = array_values(array_filter([
            $professional->city,
            $professional->region,
            $professional->country,
        ], static fn ($value): bool => is_string($value) && trim($value) !== ''));

        return $parts === [] ? '—' : implode(', ', array_unique($parts));
    }

    public static function gender(?string $gender): string
    {
        return match ($gender) {
            'male' => 'Мужской',
            'female' => 'Женский',
            'other' => 'Другой',
            default => 'Не указан',
        };
    }

    public static function phoneStatus(?string $status): string
    {
        return match ($status) {
            'available', 'published', 'revealed' => 'Телефон доступен',
            'hidden' => 'Телефон скрыт',
            'not_available', 'missing' => 'Телефон не указан',
            'permission_denied' => 'Нет разрешения на сбор',
            'blocked_captcha' => 'Получение заблокировано',
            default => $status ? Str::headline($status) : 'Телефон не указан',
        };
    }

    public static function initials(?string $name): string
    {
        $words = preg_split('/\s+/u', trim((string) $name), -1, PREG_SPLIT_NO_EMPTY) ?: [];
        $initials = collect(array_slice($words, 0, 2))
            ->map(static fn (string $word): string => mb_strtoupper(mb_substr($word, 0, 1)))
            ->implode('');

        return $initials !== '' ? $initials : '?';
    }

    public static function safeProfileUrl(?string $url): ?string
    {
        if (! self::isHttps($url)) {
            return null;
        }

        $host = mb_strtolower((string) parse_url((string) $url, PHP_URL_HOST));
        $path = (string) parse_url((string) $url, PHP_URL_PATH);

        return $host === 'uslugi.yandex.ru' && str_starts_with($path, '/profile/')
            ? $url
            : null;
    }

    public static function safePhotoUrl(?string $url): ?string
    {
        if (! self::isHttps($url)) {
            return null;
        }

        $host = mb_strtolower((string) parse_url((string) $url, PHP_URL_HOST));
        foreach (['yandex.ru', 'yandex.net', 'yandex.com'] as $allowed) {
            if ($host === $allowed || str_ends_with($host, '.'.$allowed)) {
                return $url;
            }
        }

        return null;
    }

    private static function isHttps(?string $url): bool
    {
        return is_string($url)
            && filter_var($url, FILTER_VALIDATE_URL) !== false
            && mb_strtolower((string) parse_url($url, PHP_URL_SCHEME)) === 'https';
    }
}
