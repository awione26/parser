<?php

namespace App\Http\Requests\Admin\YandexCatalog;

use Illuminate\Validation\Rule;

/**
 * Проверяет фильтры, пагинацию и сортировку серверной таблицы каталога.
 */
final class DataRequest extends IndexRequest
{
    /** @var array<int, array{data: string, name: string}> */
    private const array COLUMNS = [
        ['data' => 'group', 'name' => 'category_name'],
        ['data' => 'occupation', 'name' => 'occupation_name'],
        ['data' => 'specialization', 'name' => 'specialization_name'],
        ['data' => 'service', 'name' => 'service_name'],
        ['data' => 'slug_url', 'name' => 'target_slug'],
        ['data' => 'status', 'name' => 'target_verification_status'],
        ['data' => 'parsing', 'name' => 'used_for_parsing'],
        ['data' => 'actions', 'name' => ''],
    ];

    /**
     * Разрешить только ожидаемый контракт DataTables и ограничить размер страницы.
     *
     * @return array<string, mixed>
     */
    public function rules(): array
    {
        $rules = [
            ...parent::rules(),
            'draw' => ['required', 'integer', 'min:0', 'max:2147483647'],
            'start' => ['required', 'integer', 'min:0', 'max:2147483647'],
            'length' => ['required', 'integer', Rule::in([10, 25, 50, 100])],
            'columns' => ['required', 'array', 'size:8'],
            'order' => ['nullable', 'array', 'max:7'],
            'order.*.column' => ['required', 'integer', 'between:0,6'],
            'order.*.dir' => ['required', Rule::in(['asc', 'desc'])],
            'search' => ['nullable', 'array'],
            'search.value' => ['nullable', 'string', 'max:200'],
            'search.regex' => ['nullable', Rule::in(['false', '0', false, 0])],
        ];

        foreach (self::COLUMNS as $index => $column) {
            $rules["columns.{$index}.data"] = [
                'required',
                'string',
                Rule::in([$column['data']]),
            ];
            $rules["columns.{$index}.name"] = $column['name'] === ''
                ? ['nullable', Rule::in([''])]
                : ['required', 'string', Rule::in([$column['name']])];
            $rules["columns.{$index}.searchable"] = [
                'required',
                Rule::in(['false', '0', false, 0]),
            ];
            $rules["columns.{$index}.orderable"] = $index === 7
                ? ['required', Rule::in(['false', '0', false, 0])]
                : ['required', Rule::in(['true', 'false', '1', '0', true, false, 1, 0])];
            $rules["columns.{$index}.search"] = ['nullable', 'array'];
            $rules["columns.{$index}.search.value"] = ['nullable', 'string', 'max:200'];
            $rules["columns.{$index}.search.regex"] = [
                'nullable',
                Rule::in(['false', '0', false, 0]),
            ];
        }

        return $rules;
    }
}
