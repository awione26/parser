<?php

namespace App\Http\Requests\Admin\YandexCatalog;

use App\Models\Category;
use App\Models\YandexOccupation;
use App\Models\YandexService;
use App\Models\YandexSpecialization;
use App\Support\YandexCatalog;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Support\Facades\DB;
use Illuminate\Validation\Rule;
use Illuminate\Validation\Validator;

/**
 * Проверяет данные создаваемого узла Яндекс.Каталога и его группы мастеров.
 */
class StoreNodeRequest extends FormRequest
{
    /**
     * Разрешить изменение каталога только администратору.
     */
    public function authorize(): bool
    {
        return $this->user()?->isAdmin() === true;
    }

    /**
     * Нормализовать текстовые поля и зафиксировать уровень из маршрута при правке.
     */
    protected function prepareForValidation(): void
    {
        $normalized = [];
        foreach ([
            'taxonomy_level',
            'name',
            'external_id_raw',
            'slug',
            'source_url',
            'verification_status',
        ] as $key) {
            if (! $this->exists($key)) {
                continue;
            }

            $value = trim((string) $this->input($key));
            $normalized[$key] = $value === '' ? null : $value;
        }

        if (is_string($this->route('taxonomyLevel'))) {
            $normalized['taxonomy_level'] = $this->route('taxonomyLevel');
        }

        $level = $normalized['taxonomy_level'] ?? $this->input('taxonomy_level');
        if ($level === 'specialization') {
            $normalized['parent_id'] = $this->input('parent_occupation_id');
        } elseif ($level === 'service') {
            $normalized['parent_id'] = $this->input('parent_specialization_id');
        } else {
            $normalized['parent_id'] = null;
        }

        $this->merge($normalized);
    }

    /**
     * Требовать только полностью определённый и найденный на сайте узел.
     *
     * @return array<string, mixed>
     */
    public function rules(): array
    {
        return [
            'category_id' => ['required', 'integer', Rule::exists(Category::class, 'id')],
            'taxonomy_level' => ['required', Rule::in(array_keys(YandexCatalog::LEVEL_LABELS))],
            'parent_id' => [
                Rule::requiredIf(fn (): bool => in_array(
                    $this->input('taxonomy_level'),
                    ['specialization', 'service'],
                    true,
                )),
                'nullable',
                'integer',
                'min:1',
                Rule::prohibitedIf(fn (): bool => $this->input('taxonomy_level') === 'occupation'),
            ],
            'name' => ['required', 'string', 'max:255', 'not_regex:/[\x00-\x1F\x7F]/u'],
            'external_id_raw' => ['nullable', 'string', 'max:255', 'not_regex:/[\x00-\x1F\x7F]/u'],
            'external_number_id' => ['required', 'integer', 'min:1', 'max:2147483647'],
            'slug' => ['required', 'string', 'max:512', 'not_regex:/[\x00-\x1F\x7F]/u'],
            'source_url' => ['required', 'string', 'max:1024', 'url:http,https'],
            'verification_status' => ['required', Rule::in(YandexCatalog::USABLE_STATUSES)],
            'sort_order' => ['required', 'integer', 'min:0', 'max:2147483647'],
        ];
    }

    /**
     * Проверить родителя, глобальную уникальность ID и согласованность URL со slug.
     */
    public function after(): array
    {
        return [function (Validator $validator): void {
            if ($validator->errors()->hasAny([
                'taxonomy_level',
                'parent_id',
                'external_number_id',
                'slug',
                'source_url',
            ])) {
                return;
            }

            $level = (string) $this->input('taxonomy_level');
            $rubricId = $this->integer('external_number_id');
            $currentNodeId = $this->currentNodeId();

            $this->validateParent($validator, $level);
            $this->validateGlobalValue(
                $validator,
                $level,
                $currentNodeId,
                'external_number_id',
                $rubricId,
                'external_number_id',
                'Этот числовой ID уже используется в Яндекс.Каталоге.',
            );
            $this->validateGlobalValue(
                $validator,
                $level,
                $currentNodeId,
                'slug',
                (string) $this->input('slug'),
                'slug',
                'Этот slug уже используется в Яндекс.Каталоге.',
            );
            $this->validateGlobalValue(
                $validator,
                $level,
                $currentNodeId,
                'source_url',
                (string) $this->input('source_url'),
                'source_url',
                'Эта ссылка уже используется в Яндекс.Каталоге.',
            );

            $safeUrl = YandexCatalog::safeSourceUrl($this->input('source_url'));
            $urlPath = YandexCatalog::crawlPath($safeUrl, $rubricId);
            $slugPath = YandexCatalog::catalogPath($this->input('slug'), $rubricId);

            if ($safeUrl === null) {
                $validator->errors()->add(
                    'source_url',
                    'Укажите HTTPS-ссылку на uslugi.yandex.ru без параметров и фрагмента.',
                );
            } elseif ($urlPath === null) {
                $validator->errors()->add(
                    'source_url',
                    'Ссылка должна вести на канонический путь /category/...--ID Яндекс.Каталога.',
                );
            }

            if ($slugPath === null) {
                $validator->errors()->add(
                    'slug',
                    'Slug должен начинаться с /, состоять из латинских сегментов и не содержать суффикс --ID.',
                );
            } elseif ($urlPath !== null && ! hash_equals($slugPath, $urlPath)) {
                $validator->errors()->add(
                    'source_url',
                    'Путь ссылки не совпадает с указанными slug и числовым ID.',
                );
            }
        }];
    }

    /**
     * Вернуть ID редактируемого либо точно совпавшего скрытого узла.
     */
    protected function currentNodeId(): ?int
    {
        $value = $this->route('catalogNode');

        if (is_numeric($value)) {
            return (int) $value;
        }

        $level = (string) $this->input('taxonomy_level');
        $definition = YandexCatalog::definition($level);
        if ($definition === null) {
            return null;
        }

        $modelClass = $definition['model'];
        $node = $modelClass::query()
            ->where('external_number_id', $this->integer('external_number_id'))
            ->first();
        if (
            $node === null
            || (string) $node->getAttribute('name') !== (string) $this->input('name')
            || (string) ($node->getAttribute('external_id_raw') ?? '') !== (string) ($this->input('external_id_raw') ?? '')
            || (string) $node->getAttribute('slug') !== (string) $this->input('slug')
            || (string) $node->getAttribute('source_url') !== (string) $this->input('source_url')
            || (string) $node->getAttribute('verification_status') !== (string) $this->input('verification_status')
            || ($definition['parent_key'] !== null
                && (int) $node->getAttribute($definition['parent_key']) !== $this->integer('parent_id'))
        ) {
            return null;
        }

        $isMappedToSelectedGroup = DB::connection((string) config('parser.connection', 'parser'))
            ->table($definition['mapping'])
            ->where('category_id', $this->integer('category_id'))
            ->where($definition['foreign_key'], $node->getKey())
            ->exists();

        return $isMappedToSelectedGroup ? null : (int) $node->getKey();
    }

    /**
     * Убедиться, что выбранный родитель существует на правильном уровне.
     */
    private function validateParent(Validator $validator, string $level): void
    {
        $parentId = $this->integer('parent_id');
        $parentModel = match ($level) {
            'specialization' => YandexOccupation::class,
            'service' => YandexSpecialization::class,
            default => null,
        };

        if (
            $parentModel !== null
            && ! $parentModel::query()
                ->whereKey($parentId)
                ->whereIn('verification_status', YandexCatalog::USABLE_STATUSES)
                ->exists()
        ) {
            $validator->errors()->add('parent_id', 'Выбранный родитель Яндекс.Каталога не найден.');
        }
    }

    /**
     * Не допустить одинаковые ID, slug и URL на любом из трёх уровней каталога.
     */
    private function validateGlobalValue(
        Validator $validator,
        string $level,
        ?int $currentNodeId,
        string $column,
        int|string $value,
        string $errorKey,
        string $message,
    ): void {
        foreach ([
            'occupation' => YandexOccupation::class,
            'specialization' => YandexSpecialization::class,
            'service' => YandexService::class,
        ] as $candidateLevel => $modelClass) {
            $query = $modelClass::query()->where($column, $value);
            if ($candidateLevel === $level && $currentNodeId !== null) {
                $query->whereKeyNot($currentNodeId);
            }

            if ($query->exists()) {
                $validator->errors()->add($errorKey, $message);

                return;
            }
        }
    }
}
