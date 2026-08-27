<?php

namespace App\Http\Requests\Admin\Admin;

use App\Models\User;
use Illuminate\Contracts\Validation\ValidationRule;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;
use Illuminate\Validation\Rules\Password;

class EditRequest extends FormRequest
{
    /**
     * Determine if the user is authorized to make this request.
     */
    public function authorize(): bool
    {
        return $this->user()?->isAdmin() === true;
    }

    protected function prepareForValidation(): void
    {
        $this->merge([
            'id' => $this->route('id'),
            'login' => mb_strtolower(trim((string) $this->input('login'))),
            'name' => trim((string) $this->input('name')),
        ]);
    }

    /**
     * Get the validation rules that apply to the request.
     *
     * @return array<string, ValidationRule|array<mixed>|string>
     */
    public function rules(): array
    {
        return [
            'id' => ['required', 'integer', 'exists:'.User::getTableName().',id'],
            'login' => [
                'required',
                'string',
                'min:3',
                'max:255',
                Rule::unique(User::getTableName(), 'login')->ignore((int) $this->input('id')),
            ],
            'name' => ['required', 'string', 'max:255'],
            'role' => ['required', Rule::in(array_keys(User::$role_name))],
            'password' => ['nullable', 'confirmed', Password::min(12)],
        ];
    }
}
