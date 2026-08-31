<?php

namespace App\Http\Requests\Admin\ParserCategory;

use App\Models\ParserCategory;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Validator;

abstract class WriteRequest extends FormRequest
{
    private const string SEED_PATH_PATTERN = '/\A(?:[a-z0-9]+(?:-[a-z0-9]+)*\/)*[a-z0-9]+(?:-[a-z0-9]+)*--[1-9][0-9]*\z/D';

    public function authorize(): bool
    {
        return $this->user()?->isAdmin() === true;
    }

    /**
     * Нормализовать поля формы и преобразовать строки textarea в массив путей.
     */
    protected function prepareForValidation(): void
    {
        $paths = $this->input('seed_paths');
        if (is_string($paths)) {
            $paths = preg_split('/\R/u', $paths) ?: [];
        }
        if (is_array($paths)) {
            $paths = array_values(array_filter(
                array_map(
                    static fn (mixed $path): mixed => is_string($path) ? trim($path) : $path,
                    $paths,
                ),
                static fn (mixed $path): bool => $path !== '',
            ));
        }

        $normalized = [
            'name' => trim((string) $this->input('name')),
            'note' => trim((string) $this->input('note')),
            'seed_paths' => $paths,
        ];
        if ($this->exists('key')) {
            $normalized['key'] = mb_strtolower(trim((string) $this->input('key')));
        }

        $this->merge($normalized);
    }

    /**
     * Вернуть общие строгие правила для редактируемых полей категории.
     *
     * @return array<string, mixed>
     */
    protected function commonRules(): array
    {
        return [
            'name' => ['required', 'string', 'max:255', 'not_regex:/[\x00-\x1F\x7F]/'],
            'note' => ['nullable', 'string', 'max:5000'],
            'seed_paths' => ['required', 'array', 'min:1', 'max:100'],
            'seed_paths.*' => [
                'required',
                'string',
                'distinct',
                'max:1024',
                'regex:'.self::SEED_PATH_PATTERN,
            ],
            'sort_order' => ['required', 'integer', 'between:0,2147483647'],
            'is_active' => ['required', 'boolean'],
        ];
    }

    /**
     * Задать понятные русские названия полей в сообщениях валидатора.
     *
     * @return array<string, string>
     */
    public function attributes(): array
    {
        return [
            'key' => 'ключ категории',
            'name' => 'название',
            'note' => 'примечание',
            'seed_paths' => 'пути рубрик',
            'seed_paths.*' => 'путь рубрики',
            'sort_order' => 'порядок',
            'is_active' => 'активность',
        ];
    }

    /**
     * Пояснить допустимый формат технического ключа и относительных путей.
     *
     * @return array<string, string>
     */
    public function messages(): array
    {
        return [
            'key.regex' => 'Ключ должен начинаться с латинской буквы и содержать только строчные буквы, цифры и подчёркивания.',
            'key.not_in' => 'Ключи all и manual зарезервированы внутренней логикой парсера.',
            'name.not_regex' => 'Название не должно содержать управляющие символы.',
            'seed_paths.*.regex' => 'Каждый путь должен быть относительным путём рубрики Яндекса и заканчиваться числовым идентификатором вида --123.',
            'seed_paths.*.distinct' => 'Пути рубрик не должны повторяться.',
        ];
    }

    /**
     * Проверить, что числовые ID рубрик не повторяются внутри формы и среди
     * других категорий. Один ID должен однозначно указывать на одну категорию.
     */
    protected function validateRubricIds(
        Validator $validator,
        ?int $exceptCategoryId = null,
    ): void {
        if (
            $validator->errors()->has('seed_paths')
            || $validator->errors()->has('seed_paths.*')
        ) {
            return;
        }

        $usedIds = [];
        $rows = ParserCategory::query()
            ->with('category:categories.id,key,name')
            ->when(
                $exceptCategoryId !== null,
                fn ($query) => $query->where('category_id', '!=', $exceptCategoryId),
            )
            ->get(['category_id', 'seed_paths']);

        foreach ($rows as $row) {
            foreach (($row->seed_paths ?? []) as $path) {
                $rubricId = $this->rubricId((string) $path);
                if ($rubricId !== null) {
                    $usedIds[$rubricId] = $row->category?->name ?: $row->category?->key ?: (string) $row->category_id;
                }
            }
        }

        $incomingIds = [];
        foreach ((array) $this->input('seed_paths', []) as $index => $path) {
            $rubricId = $this->rubricId((string) $path);
            if ($rubricId === null) {
                continue;
            }

            if (isset($incomingIds[$rubricId])) {
                $validator->errors()->add(
                    "seed_paths.{$index}",
                    "ID рубрики {$rubricId} повторяется в этой категории.",
                );
            } elseif (isset($usedIds[$rubricId])) {
                $validator->errors()->add(
                    "seed_paths.{$index}",
                    "ID рубрики {$rubricId} уже используется категорией «{$usedIds[$rubricId]}».",
                );
            }

            $incomingIds[$rubricId] = true;
        }
    }

    /**
     * Извлечь ID из уже проверенного суффикса относительного пути.
     */
    private function rubricId(string $path): ?string
    {
        return preg_match('/--([1-9][0-9]*)\z/D', $path, $matches) === 1
            ? $matches[1]
            : null;
    }
}
