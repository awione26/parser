<?php

namespace App\Support;

final class PhoneNumber
{
    public static function isValid(mixed $phone): bool
    {
        return is_string($phone)
            && preg_match('/\A\+[0-9]{8,15}\z/D', $phone) === 1;
    }

    public static function normalizeSearch(?string $phone): ?string
    {
        $phone = trim((string) $phone);
        if ($phone === '') {
            return null;
        }

        if (self::isValid($phone)) {
            return $phone;
        }

        if (preg_match('/\A[+0-9\s().-]+\z/uD', $phone) !== 1) {
            return null;
        }

        if (substr_count($phone, '+') > 1 || (str_contains($phone, '+') && ! str_starts_with($phone, '+'))) {
            return null;
        }

        $digits = preg_replace('/\D+/', '', $phone);
        if (! is_string($digits)) {
            return null;
        }

        if (! str_starts_with($phone, '+') && strlen($digits) === 11 && str_starts_with($digits, '8')) {
            $digits = '7'.substr($digits, 1);
        } elseif (! str_starts_with($phone, '+') && strlen($digits) === 10) {
            $digits = '7'.$digits;
        }

        $normalized = '+'.$digits;

        return self::isValid($normalized) ? $normalized : null;
    }
}
