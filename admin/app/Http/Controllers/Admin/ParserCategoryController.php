<?php

namespace App\Http\Controllers\Admin;

use App\Http\Requests\Admin\ParserCategory\ActivationRequest;
use App\Http\Requests\Admin\ParserCategory\StoreRequest;
use App\Http\Requests\Admin\ParserCategory\UpdateRequest;
use App\Models\Category;
use App\Models\ParserCategory;
use App\Models\ParserCategoryTarget;
use App\Models\YandexOccupation;
use App\Models\YandexService;
use App\Models\YandexSpecialization;
use Carbon\CarbonImmutable;
use Illuminate\Contracts\View\View;
use Illuminate\Http\RedirectResponse;
use Illuminate\Support\Facades\DB;
use Illuminate\Validation\ValidationException;

final class ParserCategoryController extends Controller
{
    public function __construct()
    {
        parent::__construct();
        $this->middleware('permission:admin');
    }

    /**
     * Показать небольшой упорядоченный список категорий без DataTables.
     */
    public function index(): View
    {
        $rows = ParserCategory::query()
            ->with(['category' => function ($query): void {
                $query->withCount([
                    'yandexOccupations',
                    'yandexSpecializations',
                    'yandexServices',
                ]);
            }])
            ->join('categories', 'categories.id', '=', 'parser_categories.category_id')
            ->select('parser_categories.*')
            ->orderBy('parser_categories.sort_order')
            ->orderBy('categories.name')
            ->orderBy('parser_categories.category_id')
            ->get();

        return view('admin.categories.index', compact('rows'))
            ->with('title', 'Категории парсинга');
    }

    /**
     * Открыть форму новой категории и предложить следующий порядок сортировки.
     */
    public function create(): View
    {
        $nextSortOrder = min(
            2147483647,
            ((int) ParserCategory::query()->max('sort_order')) + 10,
        );

        return view('admin.categories.create_edit', compact('nextSortOrder'))
            ->with('title', 'Добавить категорию');
    }

    /**
     * Атомарно создать конфигурацию и общую категорию или переиспользовать
     * историческую категорию, оставшуюся после прежнего удаления конфигурации.
     */
    public function store(StoreRequest $request): RedirectResponse
    {
        $data = $request->validated();
        $now = CarbonImmutable::now('UTC');

        DB::connection($this->connectionName())->transaction(function () use ($data, $now): void {
            $category = Category::query()
                ->where('key', $data['key'])
                ->lockForUpdate()
                ->first();

            if ($category !== null && ParserCategory::query()->whereKey($category->id)->exists()) {
                throw ValidationException::withMessages([
                    'key' => 'Категория с таким ключом уже настроена для парсинга.',
                ]);
            }

            if ($category === null) {
                $category = new Category;
                $category->forceFill([
                    'key' => $data['key'],
                    'created_at' => $now,
                ]);
            }

            $category->forceFill([
                'name' => $data['name'],
                'note' => $this->nullableNote($data['note'] ?? null),
                'updated_at' => $now,
            ])->save();

            $configuration = new ParserCategory;
            $configuration->forceFill([
                'category_id' => $category->id,
                'seed_paths' => $data['seed_paths'],
                'is_active' => (bool) $data['is_active'],
                'sort_order' => (int) $data['sort_order'],
                'created_at' => $now,
                'updated_at' => $now,
            ])->save();

            $this->replaceTargets($configuration, $data['seed_paths'], $now);
        });

        return redirect()
            ->route('admin.categories.index')
            ->with('success', 'Категория добавлена в план парсинга.');
    }

    /**
     * Открыть форму категории; технический ключ показывается без возможности изменения.
     */
    public function edit(ParserCategory $parserCategory): View
    {
        $parserCategory->load('category');
        abort_if($parserCategory->category === null, 404);

        return view('admin.categories.create_edit', ['row' => $parserCategory])
            ->with('title', 'Редактировать категорию');
    }

    /**
     * Атомарно обновить общие данные категории и параметры её обхода.
     */
    public function update(UpdateRequest $request, ParserCategory $parserCategory): RedirectResponse
    {
        $data = $request->validated();
        $now = CarbonImmutable::now('UTC');

        DB::connection($this->connectionName())->transaction(
            function () use ($parserCategory, $data, $now): void {
                $configuration = ParserCategory::query()
                    ->lockForUpdate()
                    ->findOrFail($parserCategory->category_id);
                $category = Category::query()
                    ->lockForUpdate()
                    ->findOrFail($configuration->category_id);

                $category->forceFill([
                    'name' => $data['name'],
                    'note' => $this->nullableNote($data['note'] ?? null),
                    'updated_at' => $now,
                ])->save();

                $configuration->forceFill([
                    'seed_paths' => $data['seed_paths'],
                    'is_active' => (bool) $data['is_active'],
                    'sort_order' => (int) $data['sort_order'],
                    'updated_at' => $now,
                ])->save();

                $this->replaceTargets($configuration, $data['seed_paths'], $now);
            },
        );

        return redirect()
            ->route('admin.categories.index')
            ->with('success', 'Категория обновлена.');
    }

    /**
     * Установить переданное состояние активности, не инвертируя его на сервере.
     */
    public function activation(
        ActivationRequest $request,
        ParserCategory $parserCategory,
    ): RedirectResponse {
        $parserCategory->forceFill([
            'is_active' => $request->boolean('is_active'),
            'updated_at' => CarbonImmutable::now('UTC'),
        ])->save();

        return redirect()
            ->route('admin.categories.index')
            ->with('success', $parserCategory->is_active ? 'Категория включена.' : 'Категория отключена.');
    }

    /**
     * Удалить только настройки обхода, сохранив категорию и исторические связи мастеров.
     */
    public function destroy(ParserCategory $parserCategory): RedirectResponse
    {
        $parserCategory->delete();

        return redirect()
            ->route('admin.categories.index')
            ->with('success', 'Категория удалена из плана парсинга. Исторические данные сохранены.');
    }

    /**
     * Вернуть имя отдельного подключения к базе данных Python-парсера.
     */
    private function connectionName(): string
    {
        return (string) (new ParserCategory)->getConnectionName();
    }

    /**
     * Хранить пустое примечание как NULL, а не как строку нулевой длины.
     */
    private function nullableNote(mixed $note): ?string
    {
        $value = trim((string) $note);

        return $value === '' ? null : $value;
    }

    /**
     * Заменить нормализованные цели обхода в той же транзакции, что и legacy JSON.
     *
     * @param  list<string>  $seedPaths
     */
    private function replaceTargets(
        ParserCategory $configuration,
        array $seedPaths,
        CarbonImmutable $now,
    ): void {
        $rubricIds = array_map(
            fn (string $path): int => $this->rubricIdFromPath($path),
            $seedPaths,
        );
        $levels = $this->taxonomyLevels($rubricIds);

        ParserCategoryTarget::query()
            ->where('category_id', $configuration->category_id)
            ->delete();

        $rows = [];
        foreach (array_values($seedPaths) as $index => $path) {
            $rubricId = $rubricIds[$index];
            $rows[] = [
                'category_id' => $configuration->category_id,
                'taxonomy_level' => $levels[$rubricId] ?? ParserCategoryTarget::LEVEL_UNKNOWN,
                'source_rubric_number_id' => $rubricId,
                'relative_path' => $path,
                'is_active' => true,
                'sort_order' => ($index + 1) * 10,
                'created_at' => $now,
                'updated_at' => $now,
            ];
        }

        ParserCategoryTarget::query()->insert($rows);
    }

    /**
     * Извлечь обязательный числовой ID рубрики из проверенного относительного пути.
     */
    private function rubricIdFromPath(string $path): int
    {
        if (preg_match('/--([1-9][0-9]*)$/D', $path, $matches) !== 1) {
            throw new \LogicException('Validated seed path has no rubric number ID.');
        }

        return (int) $matches[1];
    }

    /**
     * Однозначно определить уровень каждого ID по нормализованной таксономии.
     *
     * ID, отсутствующий в справочнике или найденный на нескольких уровнях,
     * получает уровень unknown и всё равно остаётся доступен парсеру.
     *
     * @param  list<int>  $rubricIds
     * @return array<int, string>
     */
    private function taxonomyLevels(array $rubricIds): array
    {
        $matches = [];
        $models = [
            ParserCategoryTarget::LEVEL_OCCUPATION => YandexOccupation::class,
            ParserCategoryTarget::LEVEL_SPECIALIZATION => YandexSpecialization::class,
            ParserCategoryTarget::LEVEL_SERVICE => YandexService::class,
        ];

        foreach ($models as $level => $model) {
            foreach ($model::query()
                ->whereIn('external_number_id', $rubricIds)
                ->pluck('external_number_id') as $rubricId) {
                $matches[(int) $rubricId][] = $level;
            }
        }

        $levels = [];
        foreach ($matches as $rubricId => $matchedLevels) {
            if (count($matchedLevels) === 1) {
                $levels[$rubricId] = $matchedLevels[0];
            }
        }

        return $levels;
    }
}
