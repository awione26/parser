<?php

namespace App\Http\Requests\Admin\YandexCatalog;

use App\Models\Category;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

/**
 * Проверяет GET-фильтры справочника Яндекс Услуг.
 */
class IndexRequest extends FormRequest
{
    /**
     * Разрешить просмотр только пользователю с ролью администратора.
     */
    public function authorize(): bool
    {
        return $this->user()?->isAdmin() === true;
    }

    /**
     * Ограничить значения фильтров фиксированными безопасными вариантами.
     *
     * @return array<string, mixed>
     */
    public function rules(): array
    {
        return [
            'q' => ['nullable', 'string', 'max:200', 'not_regex:/[\x00-\x1F\x7F]/u'],
            'group' => ['nullable', 'integer', Rule::exists(Category::class, 'id')],
            'status' => [
                'nullable',
                Rule::in(['confirmed', 'discovered', 'legacy', 'unverified']),
            ],
            'has_id' => ['nullable', Rule::in(['0', '1'])],
            'used_for_parsing' => ['nullable', Rule::in(['0', '1'])],
        ];
    }

    /**
     * Удалить пробелы и превратить пустые значения формы в NULL.
     */
    protected function prepareForValidation(): void
    {
        $normalized = [];

        foreach (['q', 'group', 'status', 'has_id', 'used_for_parsing'] as $key) {
            if (! $this->exists($key)) {
                continue;
            }

            $value = $this->input($key);
            if (is_string($value)) {
                $value = trim($value);
            }

            $normalized[$key] = $value === '' ? null : $value;
        }

        $this->merge($normalized);
    }
}
