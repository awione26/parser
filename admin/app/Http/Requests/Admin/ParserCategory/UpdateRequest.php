<?php

namespace App\Http\Requests\Admin\ParserCategory;

use App\Models\ParserCategory;
use Illuminate\Validation\Validator;

class UpdateRequest extends WriteRequest
{
    /**
     * Проверить изменяемые данные, не разрешая менять стабильный ключ категории.
     *
     * @return array<string, mixed>
     */
    public function rules(): array
    {
        return [
            'key' => ['prohibited'],
            ...$this->commonRules(),
        ];
    }

    /**
     * Проверить ID рубрик относительно всех категорий, кроме редактируемой.
     *
     * @return array<int, callable>
     */
    public function after(): array
    {
        return [function (Validator $validator): void {
            $row = $this->route('parserCategory');
            $categoryId = $row instanceof ParserCategory ? $row->category_id : null;
            $this->validateRubricIds($validator, $categoryId);
        }];
    }
}
