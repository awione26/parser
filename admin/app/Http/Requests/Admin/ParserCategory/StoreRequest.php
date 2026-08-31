<?php

namespace App\Http\Requests\Admin\ParserCategory;

use App\Models\ParserCategory;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Validation\Validator;

class StoreRequest extends WriteRequest
{
    /**
     * Проверить данные новой категории и её конфигурации парсинга.
     *
     * @return array<string, mixed>
     */
    public function rules(): array
    {
        return [
            'key' => [
                'required',
                'string',
                'max:64',
                'regex:/\A[a-z][a-z0-9_]{0,63}\z/D',
                'not_in:all,manual',
            ],
            ...$this->commonRules(),
        ];
    }

    /**
     * Запретить второй конфигурационный ряд для уже настроенной категории.
     *
     * Сама categories может содержать историческую строку после удаления
     * конфигурации; такую строку разрешено повторно подключить к парсеру.
     *
     * @return array<int, callable>
     */
    public function after(): array
    {
        return [function (Validator $validator): void {
            if (! $validator->errors()->has('key')) {
                $key = (string) $this->input('key');
                $exists = ParserCategory::query()
                    ->whereHas(
                        'category',
                        fn (Builder $query): Builder => $query->where('key', $key),
                    )
                    ->exists();

                if ($exists) {
                    $validator->errors()->add('key', 'Категория с таким ключом уже настроена для парсинга.');
                }
            }

            $this->validateRubricIds($validator);
        }];
    }
}
