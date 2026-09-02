<?php

namespace App\Http\Requests\Admin\YandexCatalog;

use Illuminate\Foundation\Http\FormRequest;

/**
 * Проверяет изменение участия узла Яндекс.Каталога в плане парсинга.
 */
class UpdateParsingRequest extends FormRequest
{
    /**
     * Разрешить изменение плана обхода только администратору.
     */
    public function authorize(): bool
    {
        return $this->user()?->isAdmin() === true;
    }

    /**
     * Принимать только явно переданное логическое состояние переключателя.
     *
     * @return array<string, mixed>
     */
    public function rules(): array
    {
        return [
            'is_active' => ['required', 'boolean'],
        ];
    }
}
