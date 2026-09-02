<?php

namespace App\Http\Requests\Admin\YandexCatalog;

use Illuminate\Foundation\Http\FormRequest;

/**
 * Проверяет подтверждение удаления строки Яндекс.Каталога.
 */
final class DeleteNodeRequest extends FormRequest
{
    /**
     * Разрешить удаление только администратору.
     */
    public function authorize(): bool
    {
        return $this->user()?->isAdmin() === true;
    }

    /**
     * Требовать явный маркер от формы с подтверждением пользователя.
     *
     * @return array<string, mixed>
     */
    public function rules(): array
    {
        return [
            'confirmed' => ['required', 'accepted'],
        ];
    }
}
