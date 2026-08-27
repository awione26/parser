<?php

namespace App\Http\Requests\Admin\Professional;

use Illuminate\Foundation\Http\FormRequest;

final class DeleteRequest extends FormRequest
{
    /**
     * Разрешает удаление мастера только пользователю с ролью администратора.
     */
    public function authorize(): bool
    {
        return $this->user()?->isAdmin() === true;
    }

    /**
     * Дополнительные поля не проверяются: существование мастера гарантирует route binding.
     *
     * @return array<string, mixed>
     */
    public function rules(): array
    {
        return [];
    }
}
