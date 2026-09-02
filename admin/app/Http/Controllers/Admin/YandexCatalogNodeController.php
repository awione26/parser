<?php

namespace App\Http\Controllers\Admin;

use App\Http\Requests\Admin\YandexCatalog\DeleteNodeRequest;
use App\Http\Requests\Admin\YandexCatalog\StoreNodeRequest;
use App\Http\Requests\Admin\YandexCatalog\UpdateNodeRequest;
use App\Models\Category;
use App\Models\ParserCategory;
use App\Models\ParserCategoryTarget;
use App\Models\YandexOccupation;
use App\Models\YandexSpecialization;
use App\Support\YandexCatalog;
use Carbon\CarbonImmutable;
use Illuminate\Contracts\View\View;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Collection;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Http\RedirectResponse;
use Illuminate\Support\Facades\DB;
use Illuminate\Validation\ValidationException;

/**
 * Управляет ручным добавлением, редактированием и удалением узлов Яндекс.Каталога.
 */
final class YandexCatalogNodeController extends Controller
{
    public function __construct()
    {
        parent::__construct();
        $this->middleware('permission:admin');
    }

    /**
     * Показать форму добавления найденной категории Яндекс.Каталога.
     */
    public function create(): View
    {
        return view('admin.catalog.create_edit', $this->formData())
            ->with('title', 'Добавить категорию Яндекс.Каталога');
    }

    /**
     * Создать узел и связать его с выбранной группой мастеров одной транзакцией.
     */
    public function store(StoreNodeRequest $request): RedirectResponse
    {
        $data = $request->validated();
        $level = (string) $data['taxonomy_level'];
        $definition = YandexCatalog::definition($level);
        abort_if($definition === null, 404);
        $reattached = false;

        DB::connection($this->connectionName())->transaction(function () use (
            $data,
            $definition,
            $level,
            &$reattached,
        ): void {
            $this->lockCatalogWrites();
            $this->assertParentAvailable($level, $data['parent_id'] ?? null);
            $node = $this->reattachableNode($level, $data, true);
            $this->assertCatalogIdentityAvailable(
                (int) $data['external_number_id'],
                (string) $data['slug'],
                (string) $data['source_url'],
                $node === null ? null : $level,
                $node?->getKey(),
            );

            $now = CarbonImmutable::now('UTC');
            if ($node === null) {
                $modelClass = $definition['model'];
                $node = new $modelClass;
                $node->forceFill(array_merge(
                    $this->nodeAttributes($data, $definition['parent_key']),
                    ['created_at' => $now, 'updated_at' => $now],
                ))->save();
            } else {
                $reattached = true;
            }

            DB::connection($this->connectionName())
                ->table($definition['mapping'])
                ->insert([
                    'category_id' => (int) $data['category_id'],
                    $definition['foreign_key'] => (int) $node->getKey(),
                    'sort_order' => (int) $data['sort_order'],
                ]);
        });

        return redirect()
            ->route('admin.catalog.index', ['group' => $data['category_id']])
            ->with('success', $reattached
                ? 'Категория Яндекс.Каталога восстановлена в выбранной группе. Включите её в парсинг отдельной кнопкой.'
                : 'Категория Яндекс.Каталога добавлена. Включите её в парсинг отдельной кнопкой.');
    }

    /**
     * Показать форму правки узла и его привязки к группе.
     */
    public function edit(
        Category $category,
        string $taxonomyLevel,
        int $catalogNode,
    ): View {
        $node = $this->linkedCatalogNode($category, $taxonomyLevel, $catalogNode);
        $definition = YandexCatalog::definition($taxonomyLevel);
        abort_if($definition === null, 404);

        $mappingQuery = DB::connection($this->connectionName())
            ->table($definition['mapping'])
            ->where($definition['foreign_key'], $catalogNode);
        $sortOrder = (int) (clone $mappingQuery)
            ->where('category_id', $category->id)
            ->value('sort_order');
        $isShared = (clone $mappingQuery)->count() > 1;

        return view('admin.catalog.create_edit', $this->formData(
            node: $node,
            category: $category,
            level: $taxonomyLevel,
            sortOrder: $sortOrder,
            isShared: $isShared,
        ))->with('title', 'Редактировать категорию Яндекс.Каталога');
    }

    /**
     * Обновить узел и его единственную выбранную привязку без скрытых побочных эффектов.
     */
    public function update(
        UpdateNodeRequest $request,
        Category $category,
        string $taxonomyLevel,
        int $catalogNode,
    ): RedirectResponse {
        $data = $request->validated();
        $definition = YandexCatalog::definition($taxonomyLevel);
        abort_if($definition === null, 404);

        DB::connection($this->connectionName())->transaction(function () use (
            $data,
            $category,
            $taxonomyLevel,
            $catalogNode,
            $definition,
        ): void {
            $this->lockCatalogWrites();
            $modelClass = $definition['model'];
            $node = $modelClass::query()->lockForUpdate()->findOrFail($catalogNode);
            $this->assertLinked($category, $definition, $catalogNode);
            $this->assertParentAvailable($taxonomyLevel, $data['parent_id'] ?? null);
            $this->assertCatalogIdentityAvailable(
                (int) $data['external_number_id'],
                (string) $data['slug'],
                (string) $data['source_url'],
                $taxonomyLevel,
                $catalogNode,
            );

            $newAttributes = $this->nodeAttributes($data, $definition['parent_key']);
            $globalChanges = collect($newAttributes)->contains(
                fn (mixed $value, string $key): bool => (string) $node->getAttribute($key) !== (string) $value,
            );
            $mappingCount = DB::connection($this->connectionName())
                ->table($definition['mapping'])
                ->where($definition['foreign_key'], $catalogNode)
                ->count();

            if ($mappingCount > 1 && $globalChanges) {
                throw ValidationException::withMessages([
                    'catalog' => 'Узел связан с несколькими группами. Глобальные поля нельзя менять из одной строки; можно изменить только группу или порядок.',
                ]);
            }

            $oldRubricId = (int) $node->getAttribute('external_number_id');
            $newCategoryId = (int) $data['category_id'];
            if ($oldRubricId !== (int) $data['external_number_id']) {
                throw ValidationException::withMessages([
                    'external_number_id' => 'Числовой ID существующей категории изменять нельзя. Создайте новую категорию с другим ID.',
                ]);
            }
            $identityChanged = $newCategoryId !== (int) $category->id
                || (string) $node->getAttribute('slug') !== (string) $data['slug']
                || (string) $node->getAttribute('source_url') !== (string) $data['source_url'];
            $activeTarget = ParserCategoryTarget::query()
                ->where('category_id', $category->id)
                ->where('taxonomy_level', $taxonomyLevel)
                ->where('source_rubric_number_id', $oldRubricId)
                ->where('is_active', true)
                ->exists();

            $hasHistory = $this->hasProfessionalHistory($taxonomyLevel, $oldRubricId);

            if ($activeTarget && $identityChanged) {
                throw ValidationException::withMessages([
                    'catalog' => 'Сначала исключите категорию из парсинга, затем меняйте группу, slug, URL или числовой ID.',
                ]);
            }
            if ($hasHistory && $identityChanged) {
                throw ValidationException::withMessages([
                    'catalog' => 'Нельзя менять группу, slug или URL: категория уже встречалась в карточках мастеров.',
                ]);
            }

            if ($newCategoryId !== (int) $category->id) {
                $duplicateLink = DB::connection($this->connectionName())
                    ->table($definition['mapping'])
                    ->where('category_id', $newCategoryId)
                    ->where($definition['foreign_key'], $catalogNode)
                    ->exists();
                if ($duplicateLink) {
                    throw ValidationException::withMessages([
                        'category_id' => 'Эта категория уже связана с выбранной группой мастеров.',
                    ]);
                }
            }

            if ($identityChanged) {
                ParserCategoryTarget::query()
                    ->where('category_id', $category->id)
                    ->where('taxonomy_level', $taxonomyLevel)
                    ->where('source_rubric_number_id', $oldRubricId)
                    ->delete();
                $this->syncParserConfiguration((int) $category->id);
            }

            if ($globalChanges) {
                $node->forceFill(array_merge($newAttributes, [
                    'updated_at' => CarbonImmutable::now('UTC'),
                ]))->save();
            }

            $mapping = DB::connection($this->connectionName())
                ->table($definition['mapping'])
                ->where('category_id', $category->id)
                ->where($definition['foreign_key'], $catalogNode);
            if ($newCategoryId === (int) $category->id) {
                $mapping->update(['sort_order' => (int) $data['sort_order']]);
            } else {
                $mapping->delete();
                DB::connection($this->connectionName())
                    ->table($definition['mapping'])
                    ->insert([
                        'category_id' => $newCategoryId,
                        $definition['foreign_key'] => $catalogNode,
                        'sort_order' => (int) $data['sort_order'],
                    ]);
            }
        });

        return redirect()
            ->route('admin.catalog.index', ['group' => $data['category_id']])
            ->with('success', 'Категория Яндекс.Каталога обновлена.');
    }

    /**
     * Скрыть строку из каталога, сохранив физический узел для поздних результатов обхода.
     */
    public function destroy(
        DeleteNodeRequest $request,
        Category $category,
        string $taxonomyLevel,
        int $catalogNode,
    ): RedirectResponse {
        $definition = YandexCatalog::definition($taxonomyLevel);
        abort_if($definition === null, 404);

        DB::connection($this->connectionName())->transaction(function () use (
            $category,
            $taxonomyLevel,
            $catalogNode,
            $definition,
        ): void {
            $this->lockCatalogWrites();
            $modelClass = $definition['model'];
            $node = $modelClass::query()->lockForUpdate()->findOrFail($catalogNode);
            $this->assertLinked($category, $definition, $catalogNode);
            $rubricId = $node->getAttribute('external_number_id');
            $target = null;

            if (is_int($rubricId)) {
                $target = ParserCategoryTarget::query()
                    ->where('category_id', $category->id)
                    ->where('taxonomy_level', $taxonomyLevel)
                    ->where('source_rubric_number_id', $rubricId)
                    ->lockForUpdate()
                    ->first();
            }

            if (is_int($rubricId)) {
                $target?->delete();
                $this->syncParserConfiguration((int) $category->id);
            }

            DB::connection($this->connectionName())
                ->table($definition['mapping'])
                ->where('category_id', $category->id)
                ->where($definition['foreign_key'], $catalogNode)
                ->delete();
        });

        return redirect()
            ->route('admin.catalog.index')
            ->with('success', 'Категория удалена из выбранной группы. Справочный узел сохранён для истории и уже запущенных обходов.');
    }

    /**
     * Собрать справочники, необходимые общей форме создания и редактирования.
     *
     * @return array<string, mixed>
     */
    private function formData(
        ?Model $node = null,
        ?Category $category = null,
        ?string $level = null,
        int $sortOrder = 0,
        bool $isShared = false,
    ): array {
        return [
            'row' => $node,
            'selectedCategory' => $category,
            'selectedLevel' => $level,
            'sortOrder' => $sortOrder,
            'isShared' => $isShared,
            'groups' => Category::query()->orderBy('name')->get(['id', 'name']),
            'occupations' => $this->parentOptions(YandexOccupation::class),
            'specializations' => $this->parentOptions(YandexSpecialization::class),
            'levelOptions' => YandexCatalog::LEVEL_LABELS,
            'statusOptions' => YandexCatalog::STATUS_LABELS,
        ];
    }

    /**
     * Вернуть найденные узлы, которые допустимо выбирать родителями.
     *
     * @param  class-string<Model>  $modelClass
     * @return Collection<int, Model>
     */
    private function parentOptions(string $modelClass): Collection
    {
        return $modelClass::query()
            ->whereIn('verification_status', YandexCatalog::USABLE_STATUSES)
            ->where(function (Builder $query) use ($modelClass): void {
                if ($modelClass === YandexOccupation::class) {
                    $query->whereHas('categories')
                        ->orWhereHas('specializations.categories')
                        ->orWhereHas('specializations.services.categories');

                    return;
                }

                $query->whereHas('categories')
                    ->orWhereHas('services.categories');
            })
            ->orderBy('name')
            ->get(['id', 'name', 'external_number_id']);
    }

    /**
     * Найти физически сохранённый узел, который можно безошибочно вернуть в каталог.
     *
     * @param  array<string, mixed>  $data
     */
    private function reattachableNode(string $level, array $data, bool $lock): ?Model
    {
        $definition = YandexCatalog::definition($level);
        if ($definition === null) {
            return null;
        }

        $modelClass = $definition['model'];
        $query = $modelClass::query()
            ->where('external_number_id', (int) $data['external_number_id']);
        if ($lock) {
            $query->lockForUpdate();
        }
        $node = $query->first();
        if (
            $node === null
            || (string) $node->getAttribute('name') !== (string) $data['name']
            || (string) ($node->getAttribute('external_id_raw') ?? '') !== (string) ($data['external_id_raw'] ?? '')
            || (string) $node->getAttribute('slug') !== (string) $data['slug']
            || (string) $node->getAttribute('source_url') !== (string) $data['source_url']
            || (string) $node->getAttribute('verification_status') !== (string) $data['verification_status']
            || ($definition['parent_key'] !== null
                && (int) $node->getAttribute($definition['parent_key']) !== (int) ($data['parent_id'] ?? 0))
        ) {
            return null;
        }

        $isMappedToSelectedGroup = DB::connection($this->connectionName())
            ->table($definition['mapping'])
            ->where('category_id', (int) $data['category_id'])
            ->where($definition['foreign_key'], $node->getKey())
            ->exists();

        return $isMappedToSelectedGroup ? null : $node;
    }

    /**
     * Преобразовать проверенные поля формы в атрибуты таблицы нужного уровня.
     *
     * @param  array<string, mixed>  $data
     * @return array<string, mixed>
     */
    private function nodeAttributes(array $data, ?string $parentKey): array
    {
        $attributes = [
            'external_id_raw' => $data['external_id_raw'] ?? null,
            'external_number_id' => (int) $data['external_number_id'],
            'slug' => (string) $data['slug'],
            'name' => (string) $data['name'],
            'source_url' => (string) $data['source_url'],
            'verification_status' => (string) $data['verification_status'],
        ];

        if ($parentKey !== null) {
            $attributes[$parentKey] = (int) $data['parent_id'];
        }

        return $attributes;
    }

    /**
     * Найти узел и убедиться, что URL содержит действительную привязку к группе.
     */
    private function linkedCatalogNode(
        Category $category,
        string $taxonomyLevel,
        int $catalogNode,
    ): Model {
        $definition = YandexCatalog::definition($taxonomyLevel);
        abort_if($definition === null, 404);
        $modelClass = $definition['model'];
        $node = $modelClass::query()->findOrFail($catalogNode);
        $this->assertLinked($category, $definition, $catalogNode);

        return $node;
    }

    /**
     * Отклонить подменённый URL, если узел не связан с указанной группой.
     *
     * @param  array{mapping: string, foreign_key: string}  $definition
     */
    private function assertLinked(Category $category, array $definition, int $catalogNode): void
    {
        $isLinked = DB::connection($this->connectionName())
            ->table($definition['mapping'])
            ->where('category_id', $category->id)
            ->where($definition['foreign_key'], $catalogNode)
            ->exists();
        abort_unless($isLinked, 404);
    }

    /**
     * Повторно проверить глобальную уникальность ID, slug и URL внутри транзакции.
     */
    private function assertCatalogIdentityAvailable(
        int $rubricId,
        string $slug,
        string $sourceUrl,
        ?string $currentLevel = null,
        ?int $currentNode = null,
    ): void {
        foreach (YandexCatalog::LEVEL_LABELS as $level => $label) {
            $definition = YandexCatalog::definition($level);
            if ($definition === null) {
                continue;
            }
            $modelClass = $definition['model'];
            foreach ([
                'external_number_id' => [$rubricId, 'Этот числовой ID уже используется в Яндекс.Каталоге.'],
                'slug' => [$slug, 'Этот slug уже используется в Яндекс.Каталоге.'],
                'source_url' => [$sourceUrl, 'Эта ссылка уже используется в Яндекс.Каталоге.'],
            ] as $column => [$value, $message]) {
                $query = $modelClass::query()->where($column, $value);
                if ($level === $currentLevel && $currentNode !== null) {
                    $query->whereKeyNot($currentNode);
                }
                if ($query->exists()) {
                    throw ValidationException::withMessages([$column => $message]);
                }
            }
        }
    }

    /**
     * Повторно найти и заблокировать обязательного родителя внутри транзакции.
     */
    private function assertParentAvailable(string $taxonomyLevel, mixed $parentId): void
    {
        $parentModel = match ($taxonomyLevel) {
            'specialization' => YandexOccupation::class,
            'service' => YandexSpecialization::class,
            default => null,
        };
        if ($parentModel === null) {
            return;
        }

        $exists = $parentModel::query()
            ->whereKey((int) $parentId)
            ->whereIn('verification_status', YandexCatalog::USABLE_STATUSES)
            ->lockForUpdate()
            ->exists();
        if (! $exists) {
            throw ValidationException::withMessages([
                'parent_id' => 'Выбранный родитель Яндекс.Каталога больше не существует.',
            ]);
        }
    }

    /**
     * Заблокировать стабильный набор конфигураций и сериализовать ручные записи каталога.
     */
    private function lockCatalogWrites(): void
    {
        ParserCategory::query()
            ->orderBy('category_id')
            ->lockForUpdate()
            ->get(['category_id']);
    }

    /**
     * Проверить точные и старые записи мастеров для числового ID рубрики.
     */
    private function hasProfessionalHistory(string $taxonomyLevel, int $rubricId): bool
    {
        return DB::connection($this->connectionName())
            ->table('professional_category_rubrics')
            ->where('source_rubric_number_id', $rubricId)
            ->where(function ($query) use ($taxonomyLevel): void {
                $query->where('source_rubric_level', $taxonomyLevel)
                    ->orWhereNull('source_rubric_level');
            })
            ->exists();
    }

    /**
     * Пересобрать совместимый JSON-план и активность группы после удаления цели.
     */
    private function syncParserConfiguration(int $categoryId): void
    {
        $configuration = ParserCategory::query()->lockForUpdate()->find($categoryId);
        if ($configuration === null) {
            return;
        }

        $activePaths = ParserCategoryTarget::query()
            ->where('category_id', $categoryId)
            ->where('is_active', true)
            ->orderBy('sort_order')
            ->orderBy('id')
            ->pluck('relative_path')
            ->all();

        $configuration->forceFill([
            'seed_paths' => $activePaths,
            'is_active' => $activePaths !== [],
            'updated_at' => CarbonImmutable::now('UTC'),
        ])->save();
    }

    /**
     * Вернуть имя подключения к общей базе Python-парсера.
     */
    private function connectionName(): string
    {
        return (string) config('parser.connection', 'parser');
    }
}
