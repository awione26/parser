<?php

namespace App\Http\Requests\Admin\ParserCategory;

use Illuminate\Foundation\Http\FormRequest;

class ActivationRequest extends FormRequest
{
    public function authorize(): bool
    {
        return $this->user()?->isAdmin() === true;
    }

    /**
     * Принимать явное целевое состояние, чтобы повторный запрос был безопасным.
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
