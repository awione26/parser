<?php

namespace Tests\Unit;

use App\Support\PhoneNumber;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;

class PhoneNumberTest extends TestCase
{
    #[DataProvider('validStoredPhoneProvider')]
    public function test_accepts_only_normalized_stored_phones(string $phone): void
    {
        $this->assertTrue(PhoneNumber::isValid($phone));
    }

    /**
     * @return iterable<string, array{string}>
     */
    public static function validStoredPhoneProvider(): iterable
    {
        yield 'minimum' => ['+12345678'];
        yield 'russian' => ['+79991234567'];
        yield 'maximum' => ['+123456789012345'];
    }

    #[DataProvider('invalidStoredPhoneProvider')]
    public function test_rejects_invalid_stored_phones(mixed $phone): void
    {
        $this->assertFalse(PhoneNumber::isValid($phone));
    }

    /**
     * @return iterable<string, array{mixed}>
     */
    public static function invalidStoredPhoneProvider(): iterable
    {
        yield 'null' => [null];
        yield 'empty' => [''];
        yield 'formatted' => ['8 (999) 123-45-67'];
        yield 'without plus' => ['79991234567'];
        yield 'too short' => ['+1234567'];
        yield 'too long' => ['+1234567890123456'];
        yield 'object' => [new \stdClass];
    }

    #[DataProvider('searchPhoneProvider')]
    public function test_normalizes_phone_filter(string $input, ?string $expected): void
    {
        $this->assertSame($expected, PhoneNumber::normalizeSearch($input));
    }

    /**
     * @return iterable<string, array{string, ?string}>
     */
    public static function searchPhoneProvider(): iterable
    {
        yield 'normalized' => ['+79991234567', '+79991234567'];
        yield 'russian trunk prefix' => ['8 (999) 123-45-67', '+79991234567'];
        yield 'russian local' => ['999 123-45-67', '+79991234567'];
        yield 'international formatting' => ['+800 1234 5678', '+80012345678'];
        yield 'invalid text' => ['internal-id-12345678', null];
        yield 'extension' => ['+79991234567 ext 12', null];
        yield 'misplaced plus' => ['7+9991234567', null];
    }
}
