<?php

namespace App\Http\Requests\Admin\Professional;

use App\Models\Professional;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

final class BulkDeleteRequest extends FormRequest
{
    /**
     * Разрешает массовое удаление только пользователю с ролью администратора.
     */
    public function authorize(): bool
    {
        return $this->user()?->isAdmin() === true;
    }

    /**
     * Ограничивает пакет 500 уникальными существующими идентификаторами мастеров.
     *
     * @return array<string, mixed>
     */
    public function rules(): array
    {
        return [
            'ids' => ['required', 'array', 'min:1', 'max:500'],
            'ids.*' => [
                'required',
                'integer',
                'distinct',
                Rule::exists(Professional::class, 'id'),
            ],
        ];
    }
}
