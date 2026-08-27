<?php

namespace App\Http\Requests\Admin\ParserSetting;

use Closure;
use Illuminate\Foundation\Http\FormRequest;

final class UpdateRequest extends FormRequest
{
    /**
     * Разрешить изменение конфигурации только администратору.
     */
    public function authorize(): bool
    {
        return $this->user()?->isAdmin() === true;
    }

    /**
     * Удалить внешние пробелы у строковых и числовых полей до проверки.
     */
    protected function prepareForValidation(): void
    {
        $trimmed = [];
        foreach ([
            'SCRAPER_USER_AGENT',
            'SCRAPER_GEO',
            'SCRAPER_MIN_DELAY_SECONDS',
            'SCRAPER_MAX_DELAY_SECONDS',
            'SCRAPER_TIMEOUT_SECONDS',
            'SCRAPER_MAX_RETRIES',
            'SCRAPER_PHONE_TIMEOUT_SECONDS',
        ] as $key) {
            if (is_string($this->input($key))) {
                $trimmed[$key] = trim((string) $this->input($key));
            }
        }

        $this->merge($trimmed);
    }

    /**
     * Проверить тот же контракт значений, который применяет Python-парсер.
     *
     * @return array<string, mixed>
     */
    public function rules(): array
    {
        $finite = static function (string $attribute, mixed $value, Closure $fail): void {
            if (! is_numeric($value) || ! is_finite((float) $value)) {
                $fail("Поле {$attribute} должно содержать конечное число.");
            }
        };

        return [
            'SCRAPER_USER_AGENT' => [
                'bail',
                'required',
                'string',
                'min:3',
                'max:512',
                'regex:/\A[\x20-\x7E]+\z/D',
            ],
            'SCRAPER_GEO' => [
                'bail',
                'required',
                'string',
                'max:128',
                'regex:/\A[0-9]+-[a-z0-9]+(?:-[a-z0-9]+)*\z/D',
            ],
            'SCRAPER_RESPECT_ROBOTS' => ['required', 'boolean'],
            'SCRAPER_MIN_DELAY_SECONDS' => ['bail', 'required', 'numeric', $finite, 'min:0'],
            'SCRAPER_MAX_DELAY_SECONDS' => [
                'bail',
                'required',
                'numeric',
                $finite,
                'gte:SCRAPER_MIN_DELAY_SECONDS',
            ],
            'SCRAPER_TIMEOUT_SECONDS' => ['bail', 'required', 'numeric', $finite, 'gt:0'],
            'SCRAPER_MAX_RETRIES' => ['bail', 'required', 'integer', 'min:0'],
            'SCRAPER_COLLECT_PHONE' => ['required', 'boolean'],
            'SCRAPER_PHONE_HEADLESS' => ['required', 'boolean'],
            'SCRAPER_PHONE_TIMEOUT_SECONDS' => [
                'bail',
                'required',
                'numeric',
                $finite,
                'gt:0',
            ],
            'SCRAPER_INCLUDE_ORGANIZATIONS' => ['required', 'boolean'],
        ];
    }

    /**
     * Вернуть понятные сообщения для ключевых ограничений формы.
     *
     * @return array<string, string>
     */
    public function messages(): array
    {
        return [
            'SCRAPER_USER_AGENT.regex' => 'User-Agent должен содержать только печатные ASCII-символы без переносов строк.',
            'SCRAPER_GEO.regex' => "География должна иметь вид '213-moscow': цифры, строчные латинские буквы и дефисы.",
            'SCRAPER_MAX_DELAY_SECONDS.gte' => 'Максимальная задержка не может быть меньше минимальной.',
            'SCRAPER_TIMEOUT_SECONDS.gt' => 'Тайм-аут HTTP должен быть больше нуля.',
            'SCRAPER_PHONE_TIMEOUT_SECONDS.gt' => 'Тайм-аут телефона должен быть больше нуля.',
        ];
    }
}
