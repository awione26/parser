<?php

namespace App\Http\Controllers\Admin;

use App\Http\Requests\Admin\YandexCatalog\DataRequest;
use App\Http\Requests\Admin\YandexCatalog\IndexRequest;
use App\Http\Requests\Admin\YandexCatalog\UpdateParsingRequest;
use App\Models\Category;
use App\Models\ParserCategory;
use App\Models\ParserCategoryTarget;
use App\Support\YandexCatalog;
use Carbon\CarbonImmutable;
use Illuminate\Contracts\View\View;
use Illuminate\Database\Eloquent\Collection;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Query\Builder;
use Illuminate\Database\Query\JoinClause;
use Illuminate\Http\RedirectResponse;
use Illuminate\Support\Facades\DB;
use Illuminate\Validation\ValidationException;
use Symfony\Component\HttpFoundation\JsonResponse;
use Yajra\DataTables\Facades\DataTables;

/**
 * Показывает таксономию Яндекс Услуг и управляет только выбором целей обхода.
 */
final class YandexCatalogController extends Controller
{
    /** @var array<string, string> */
    private const array STATUS_LABELS = [
        'confirmed' => 'Подтверждено',
        'discovered' => 'Найдено на сайте',
        'legacy' => 'Ранее проверено',
        'unverified' => 'Не проверено',
    ];

    /** @var array<string, string> */
    private const array STATUS_BADGES = [
        'confirmed' => 'success',
        'discovered' => 'info',
        'legacy' => 'warning',
        'unverified' => 'secondary',
    ];

    public function __construct()
    {
        parent::__construct();
        $this->middleware('permission:admin');
    }

    /**
     * Показать страницу каталога и передать справочники для клиентских фильтров.
     */
    public function index(IndexRequest $request): View
    {
        return view('admin.catalog.index', [
            'title' => 'Яндекс.Каталог',
            'groups' => $this->catalogGroups(),
            'filters' => $request->validated(),
            'statusOptions' => YandexCatalog::STATUS_LABELS,
        ]);
    }

    /**
     * Вернуть отфильтрованные строки каталога для серверной таблицы DataTables.
     */
    public function data(DataRequest $request): JsonResponse
    {
        $query = $this->catalogQuery();
        $this->applyFilters($query, $request->validated());
        $order = $request->validated('order', []);

        return DataTables::query($query)
            ->skipAutoFilter()
            ->order(fn (Builder $orderedQuery) => $this->applyDataTableOrdering(
                $orderedQuery,
                is_array($order) ? $order : [],
            ))
            ->addColumn('group', fn (object $row): string => $this->groupColumn($row))
            ->addColumn('occupation', fn (object $row): string => $this->nodeColumn(
                $row,
                'occupation',
                'occupationId',
            ))
            ->addColumn('specialization', fn (object $row): string => $this->nodeColumn(
                $row,
                'specialization',
                'specId',
            ))
            ->addColumn('service', fn (object $row): string => $this->nodeColumn(
                $row,
                'service',
                'serviceId',
            ))
            ->addColumn('slug_url', fn (object $row): string => $this->slugUrlColumn($row))
            ->addColumn('status', fn (object $row): string => $this->statusColumn($row))
            ->addColumn('parsing', fn (object $row): string => $this->parsingColumn($row))
            ->addColumn('actions', fn (object $row): string => $this->actionsColumn($row))
            ->rawColumns([
                'group',
                'occupation',
                'specialization',
                'service',
                'slug_url',
                'status',
                'parsing',
                'actions',
            ])
            ->only([
                'group',
                'occupation',
                'specialization',
                'service',
                'slug_url',
                'status',
                'parsing',
                'actions',
            ])
            ->toJson();
    }

    /**
     * Атомарно включить или выключить связанную строку каталога в плане обхода.
     */
    public function updateParsing(
        UpdateParsingRequest $request,
        Category $category,
        string $taxonomyLevel,
        int $catalogNode,
    ): RedirectResponse {
        $node = $this->linkedCatalogNode($category, $taxonomyLevel, $catalogNode);
        $urlPath = YandexCatalog::crawlPath(
            YandexCatalog::safeSourceUrl($node->getAttribute('source_url')),
            $node->getAttribute('external_number_id'),
        );
        $relativePath = YandexCatalog::catalogPath(
            $node->getAttribute('slug'),
            $node->getAttribute('external_number_id'),
        );

        if (
            $urlPath === null
            || $relativePath === null
            || ! hash_equals($relativePath, $urlPath)
            || ! in_array(
                $node->getAttribute('verification_status'),
                YandexCatalog::USABLE_STATUSES,
                true,
            )
        ) {
            throw ValidationException::withMessages([
                'catalog' => 'Эту строку нельзя использовать для парсинга: нужны проверенный статус, канонический URL, slug и числовой ID Яндекс.Каталога.',
            ]);
        }

        $isActive = $request->boolean('is_active');
        $rubricId = (int) $node->getAttribute('external_number_id');
        $now = CarbonImmutable::now('UTC');

        DB::connection($this->connectionName())->transaction(function () use (
            $category,
            $taxonomyLevel,
            $relativePath,
            $rubricId,
            $isActive,
            $now,
        ): void {
            // Блокировка всех конфигураций сериализует проверку глобальной
            // уникальности rubric ID даже при одновременных запросах.
            ParserCategory::query()
                ->orderBy('category_id')
                ->lockForUpdate()
                ->get(['category_id']);

            $configuration = ParserCategory::query()
                ->lockForUpdate()
                ->find($category->id);

            if ($configuration === null && ! $isActive) {
                return;
            }

            if ($configuration === null) {
                $configuration = new ParserCategory;
                $configuration->forceFill([
                    'category_id' => $category->id,
                    'seed_paths' => [],
                    'is_active' => false,
                    'sort_order' => min(
                        2147483647,
                        ((int) ParserCategory::query()->max('sort_order')) + 10,
                    ),
                    'created_at' => $now,
                    'updated_at' => $now,
                ])->save();
            }

            // Старый раздел мог выключить конфигурацию, оставив дочерние цели
            // активными. При повторном включении начинаем с выбранной строки,
            // чтобы одно действие в каталоге не включило скрыто весь набор.
            if ($isActive && ! $configuration->is_active) {
                ParserCategoryTarget::query()
                    ->where('category_id', $category->id)
                    ->where('is_active', true)
                    ->update([
                        'is_active' => false,
                        'updated_at' => $now,
                    ]);
            }

            if ($isActive) {
                $duplicate = ParserCategoryTarget::query()
                    ->where('source_rubric_number_id', $rubricId)
                    ->where('category_id', '<>', $category->id)
                    ->where('is_active', true)
                    ->lockForUpdate()
                    ->first();

                if ($duplicate !== null) {
                    throw ValidationException::withMessages([
                        'catalog' => "ID рубрики {$rubricId} уже включён в другую группу мастеров.",
                    ]);
                }
            }

            $target = ParserCategoryTarget::query()
                ->where('category_id', $category->id)
                ->where('source_rubric_number_id', $rubricId)
                ->lockForUpdate()
                ->first();

            if ($target === null && ! $isActive) {
                return;
            }

            if (
                $target !== null
                && $target->is_active
                && $target->taxonomy_level !== $taxonomyLevel
                && $isActive
            ) {
                throw ValidationException::withMessages([
                    'catalog' => "ID рубрики {$rubricId} уже включён на другом уровне Яндекс.Каталога.",
                ]);
            }

            if ($target === null) {
                $target = new ParserCategoryTarget;
                $target->forceFill([
                    'category_id' => $category->id,
                    'source_rubric_number_id' => $rubricId,
                    'sort_order' => min(
                        2147483647,
                        ((int) ParserCategoryTarget::query()
                            ->where('category_id', $category->id)
                            ->max('sort_order')) + 10,
                    ),
                    'created_at' => $now,
                ]);
            }

            $target->forceFill([
                'taxonomy_level' => $taxonomyLevel,
                'relative_path' => $relativePath,
                'is_active' => $isActive,
                'updated_at' => $now,
            ])->save();

            $activePaths = ParserCategoryTarget::query()
                ->where('category_id', $category->id)
                ->where('is_active', true)
                ->orderBy('sort_order')
                ->orderBy('id')
                ->pluck('relative_path')
                ->all();

            $configuration->forceFill([
                'seed_paths' => $activePaths,
                'is_active' => $activePaths !== [],
                'updated_at' => $now,
            ])->save();
        });

        return redirect()
            ->back()
            ->with('success', $isActive
                ? 'Категория Яндекс.Каталога включена в парсинг.'
                : 'Категория Яндекс.Каталога исключена из парсинга.');
    }

    /**
     * Объединить три уровня справочника в один плоский источник для таблицы.
     */
    private function catalogQuery(): Builder
    {
        $connection = DB::connection($this->connectionName());
        $union = $this->occupationRows()
            ->unionAll($this->specializationRows())
            ->unionAll($this->serviceRows());

        return $connection->query()->fromSub($union, 'catalog');
    }

    /**
     * Построить строки непосредственно связанных направлений.
     */
    private function occupationRows(): Builder
    {
        return DB::connection($this->connectionName())
            ->table('category_yandex_occupations as mapping')
            ->join('categories as category', 'category.id', '=', 'mapping.category_id')
            ->join('yandex_occupations as occupation', 'occupation.id', '=', 'mapping.occupation_id')
            ->leftJoin('parser_categories as parser_category', 'parser_category.category_id', '=', 'category.id')
            ->leftJoin('parser_category_targets as parser_target', function (JoinClause $join): void {
                $join->on('parser_target.category_id', '=', 'category.id')
                    ->on('parser_target.source_rubric_number_id', '=', 'occupation.external_number_id')
                    ->where('parser_target.taxonomy_level', '=', 'occupation')
                    ->where('parser_target.is_active', '=', 1);
            })
            ->selectRaw($this->rowSelectSql(
                taxonomyLevel: 'occupation',
                taxonomyLevelSort: 1,
                occupationAlias: 'occupation',
            ));
    }

    /**
     * Построить строки непосредственно связанных специализаций.
     */
    private function specializationRows(): Builder
    {
        return DB::connection($this->connectionName())
            ->table('category_yandex_specializations as mapping')
            ->join('categories as category', 'category.id', '=', 'mapping.category_id')
            ->join('yandex_specializations as specialization', 'specialization.id', '=', 'mapping.specialization_id')
            ->leftJoin('yandex_occupations as occupation', 'occupation.id', '=', 'specialization.occupation_id')
            ->leftJoin('parser_categories as parser_category', 'parser_category.category_id', '=', 'category.id')
            ->leftJoin('parser_category_targets as parser_target', function (JoinClause $join): void {
                $join->on('parser_target.category_id', '=', 'category.id')
                    ->on('parser_target.source_rubric_number_id', '=', 'specialization.external_number_id')
                    ->where('parser_target.taxonomy_level', '=', 'specialization')
                    ->where('parser_target.is_active', '=', 1);
            })
            ->selectRaw($this->rowSelectSql(
                taxonomyLevel: 'specialization',
                taxonomyLevelSort: 2,
                occupationAlias: 'occupation',
                specializationAlias: 'specialization',
            ));
    }

    /**
     * Построить строки непосредственно связанных услуг вместе с их родителями.
     */
    private function serviceRows(): Builder
    {
        return DB::connection($this->connectionName())
            ->table('category_yandex_services as mapping')
            ->join('categories as category', 'category.id', '=', 'mapping.category_id')
            ->join('yandex_services as service', 'service.id', '=', 'mapping.service_id')
            ->leftJoin('yandex_specializations as specialization', 'specialization.id', '=', 'service.specialization_id')
            ->leftJoin('yandex_occupations as occupation', 'occupation.id', '=', 'specialization.occupation_id')
            ->leftJoin('parser_categories as parser_category', 'parser_category.category_id', '=', 'category.id')
            ->leftJoin('parser_category_targets as parser_target', function (JoinClause $join): void {
                $join->on('parser_target.category_id', '=', 'category.id')
                    ->on('parser_target.source_rubric_number_id', '=', 'service.external_number_id')
                    ->where('parser_target.taxonomy_level', '=', 'service')
                    ->where('parser_target.is_active', '=', 1);
            })
            ->selectRaw($this->rowSelectSql(
                taxonomyLevel: 'service',
                taxonomyLevelSort: 3,
                occupationAlias: 'occupation',
                specializationAlias: 'specialization',
                serviceAlias: 'service',
            ));
    }

    /**
     * Сформировать одинаковый SELECT для каждого уровня UNION ALL.
     */
    private function rowSelectSql(
        string $taxonomyLevel,
        int $taxonomyLevelSort,
        ?string $occupationAlias = null,
        ?string $specializationAlias = null,
        ?string $serviceAlias = null,
    ): string {
        $occupation = $this->nodeSelectSql($occupationAlias, 'occupation');
        $specialization = $this->nodeSelectSql($specializationAlias, 'specialization');
        $service = $this->nodeSelectSql($serviceAlias, 'service');
        $target = match ($taxonomyLevel) {
            'occupation' => 'occupation',
            'specialization' => 'specialization',
            'service' => 'service',
        };

        return <<<SQL
            category.id AS category_id,
            category.key AS category_key,
            category.name AS category_name,
            COALESCE(parser_category.sort_order, 2147483647) AS category_sort_order,
            mapping.sort_order AS link_sort_order,
            '{$taxonomyLevel}' AS taxonomy_level,
            {$taxonomyLevelSort} AS taxonomy_level_sort,
            {$occupation},
            {$specialization},
            {$service},
            {$target}.id AS target_catalog_id,
            {$target}.external_id_raw AS target_external_id_raw,
            {$target}.external_number_id AS target_external_number_id,
            {$target}.slug AS target_slug,
            {$target}.source_url AS target_source_url,
            {$target}.verification_status AS target_verification_status,
            CASE
                WHEN parser_category.is_active = 1 AND parser_target.id IS NOT NULL THEN 1
                ELSE 0
            END AS used_for_parsing
            SQL;
    }

    /**
     * Вернуть поля узла или совместимые NULL-колонки для отсутствующего уровня.
     */
    private function nodeSelectSql(?string $tableAlias, string $columnPrefix): string
    {
        if ($tableAlias === null) {
            return implode(', ', [
                "NULL AS {$columnPrefix}_name",
                "NULL AS {$columnPrefix}_external_id_raw",
                "NULL AS {$columnPrefix}_external_number_id",
                "NULL AS {$columnPrefix}_slug",
            ]);
        }

        return implode(', ', [
            "{$tableAlias}.name AS {$columnPrefix}_name",
            "{$tableAlias}.external_id_raw AS {$columnPrefix}_external_id_raw",
            "{$tableAlias}.external_number_id AS {$columnPrefix}_external_number_id",
            "{$tableAlias}.slug AS {$columnPrefix}_slug",
        ]);
    }

    /**
     * Применить только прошедшие валидацию фильтры к серверному запросу.
     *
     * @param  array<string, mixed>  $filters
     */
    private function applyFilters(Builder $query, array $filters): void
    {
        $term = trim((string) ($filters['q'] ?? ''));
        if ($term !== '') {
            $pattern = "%{$term}%";
            $query->where(function (Builder $nested) use ($pattern, $term): void {
                foreach ([
                    'category_name',
                    'category_key',
                    'occupation_name',
                    'occupation_external_id_raw',
                    'occupation_slug',
                    'specialization_name',
                    'specialization_external_id_raw',
                    'specialization_slug',
                    'service_name',
                    'service_external_id_raw',
                    'service_slug',
                ] as $column) {
                    $nested->orWhere($column, 'like', $pattern);
                }

                if (ctype_digit($term)) {
                    $nested->orWhere('target_external_number_id', '=', (int) $term);
                }
            });
        }

        if (isset($filters['group'])) {
            $query->where('category_id', '=', (int) $filters['group']);
        }

        if (isset($filters['status'])) {
            $query->where('target_verification_status', '=', $filters['status']);
        }

        if (isset($filters['has_id'])) {
            $hasId = (string) $filters['has_id'] === '1';
            $query->{$hasId ? 'where' : 'whereNot'}(function (Builder $nested): void {
                $nested->whereNotNull('target_external_number_id')
                    ->orWhere(function (Builder $rawId): void {
                        $rawId->whereNotNull('target_external_id_raw')
                            ->where('target_external_id_raw', '<>', '');
                    });
            });
        }

        if (isset($filters['used_for_parsing'])) {
            $query->where('used_for_parsing', '=', (string) $filters['used_for_parsing'] === '1' ? 1 : 0);
        }
    }

    /**
     * Применить только разрешённые колонки сортировки и добавить стабильные поля.
     *
     * @param  array<int, array{column?: mixed, dir?: mixed}>  $order
     */
    private function applyDataTableOrdering(Builder $query, array $order): void
    {
        $columns = [
            0 => 'category_name',
            1 => 'occupation_name',
            2 => 'specialization_name',
            3 => 'service_name',
            4 => 'target_slug',
            5 => 'target_verification_status',
            6 => 'used_for_parsing',
        ];
        $orderedColumns = [];

        foreach ($order as $item) {
            $index = (int) ($item['column'] ?? -1);
            $column = $columns[$index] ?? null;
            if ($column === null || isset($orderedColumns[$column])) {
                continue;
            }

            $direction = ($item['dir'] ?? null) === 'desc' ? 'desc' : 'asc';
            $query->orderBy($column, $direction);
            $orderedColumns[$column] = true;
        }

        foreach ([
            'category_sort_order',
            'category_name',
            'taxonomy_level_sort',
            'link_sort_order',
            'occupation_name',
            'specialization_name',
            'service_name',
            'target_catalog_id',
            'category_id',
        ] as $column) {
            if (! isset($orderedColumns[$column])) {
                $query->orderBy($column);
            }
        }
    }

    /**
     * Сформировать безопасное представление внутренней группы мастеров.
     */
    private function groupColumn(object $row): string
    {
        return sprintf(
            '<strong>%s</strong><div><code>%s</code></div>',
            e((string) $row->category_name),
            e((string) $row->category_key),
        );
    }

    /**
     * Сформировать безопасное представление одного уровня каталога.
     */
    private function nodeColumn(object $row, string $prefix, string $externalIdLabel): string
    {
        $name = $row->{$prefix.'_name'};
        if (! is_string($name) || $name === '') {
            return '<span class="text-muted">—</span>';
        }

        $html = '<div>'.e($name).'</div>';
        $externalId = $row->{$prefix.'_external_id_raw'};
        if (is_string($externalId) && $externalId !== '') {
            $html .= sprintf(
                '<small class="d-block text-muted">%s: <code>%s</code></small>',
                e($externalIdLabel),
                e($externalId),
            );
        }

        $numberId = $row->{$prefix.'_external_number_id'};
        if (is_int($numberId) || (is_string($numberId) && ctype_digit($numberId))) {
            $html .= '<small class="text-muted">№ '.e((string) $numberId).'</small>';
        }

        return $html;
    }

    /**
     * Показать slug и только предварительно проверенную ссылку на Яндекс Услуги.
     */
    private function slugUrlColumn(object $row): string
    {
        $slug = trim((string) $row->target_slug);
        $html = $slug === ''
            ? '<span class="text-muted">slug не указан</span>'
            : '<code class="catalog-slug">'.e($slug).'</code>';
        $safeUrl = YandexCatalog::safeSourceUrl($row->target_source_url);

        if ($safeUrl !== null) {
            $html .= sprintf(
                '<div class="mt-1"><a href="%s" target="_blank" rel="noopener noreferrer nofollow">Открыть на uslugi.yandex.ru <i class="fas fa-external-link-alt ml-1" aria-hidden="true"></i></a></div>',
                e($safeUrl),
            );
        }

        return $html;
    }

    /**
     * Преобразовать технические значения статуса и уровня в фиксированные подписи.
     */
    private function statusColumn(object $row): string
    {
        $status = (string) $row->target_verification_status;
        $statusLabel = self::STATUS_LABELS[$status] ?? 'Неизвестный статус';
        $statusBadge = self::STATUS_BADGES[$status] ?? 'secondary';
        $levelLabel = YandexCatalog::LEVEL_LABELS[(string) $row->taxonomy_level] ?? 'Неизвестный уровень';

        return sprintf(
            '<span class="badge badge-%s">%s</span><small class="d-block text-muted mt-1">%s</small>',
            $statusBadge,
            e($statusLabel),
            e($levelLabel),
        );
    }

    /**
     * Сформировать индикатор и форму включения строки в план парсинга.
     */
    private function parsingColumn(object $row): string
    {
        $isActive = (bool) $row->used_for_parsing;
        $html = $isActive
            ? '<span class="badge badge-success mb-2"><i class="fas fa-check mr-1" aria-hidden="true"></i>В парсинге</span>'
            : '<span class="badge badge-light border mb-2">Не участвует</span>';

        if (! $this->canToggleParsing($row)) {
            return $html.'<small class="d-block text-muted">Недоступно: статус, slug, URL или ID не подтверждены</small>';
        }

        $action = route('admin.catalog.parsing', [
            'category' => (int) $row->category_id,
            'taxonomyLevel' => (string) $row->taxonomy_level,
            'catalogNode' => (int) $row->target_catalog_id,
        ]);
        $buttonClass = $isActive ? 'btn-outline-danger' : 'btn-outline-success';
        $buttonLabel = $isActive ? 'Исключить' : 'Включить';

        return $html.sprintf(
            '<form method="post" action="%s"><input type="hidden" name="_token" value="%s"><input type="hidden" name="_method" value="PATCH"><input type="hidden" name="is_active" value="%s"><button type="submit" class="btn btn-sm %s">%s</button></form>',
            e($action),
            e(csrf_token()),
            $isActive ? '0' : '1',
            $buttonClass,
            $buttonLabel,
        );
    }

    /**
     * Проверить, что строка содержит согласованные данные для управления парсингом.
     */
    private function canToggleParsing(object $row): bool
    {
        $numberId = $row->target_external_number_id;
        if (is_string($numberId) && ctype_digit($numberId)) {
            $numberId = (int) $numberId;
        }

        $urlPath = YandexCatalog::crawlPath(
            YandexCatalog::safeSourceUrl($row->target_source_url),
            $numberId,
        );
        $catalogPath = YandexCatalog::catalogPath($row->target_slug, $numberId);

        return $urlPath !== null
            && $catalogPath !== null
            && hash_equals($catalogPath, $urlPath)
            && in_array(
                $row->target_verification_status,
                YandexCatalog::USABLE_STATUSES,
                true,
            );
    }

    /**
     * Сформировать безопасные ссылки и форму удаления для CRUD каталога.
     */
    private function actionsColumn(object $row): string
    {
        $parameters = [
            'category' => (int) $row->category_id,
            'taxonomyLevel' => (string) $row->taxonomy_level,
            'catalogNode' => (int) $row->target_catalog_id,
        ];
        $editUrl = route('admin.catalog.edit', $parameters);
        $deleteUrl = route('admin.catalog.destroy', $parameters);
        $catalogNode = (int) $row->target_catalog_id;

        return sprintf(
            '<a href="%s" class="btn btn-sm btn-primary" aria-label="Редактировать %d"><i class="fas fa-edit" aria-hidden="true"></i><span class="sr-only">Редактировать</span></a> <form method="post" class="d-inline" action="%s" onsubmit="return confirm(\'Удалить категорию из выбранной группы? Цель парсинга будет отключена, а справочный узел сохранится для истории.\');"><input type="hidden" name="_token" value="%s"><input type="hidden" name="_method" value="DELETE"><input type="hidden" name="confirmed" value="1"><button type="submit" class="btn btn-sm btn-danger" aria-label="Удалить %d"><i class="fas fa-trash" aria-hidden="true"></i><span class="sr-only">Удалить</span></button></form>',
            e($editUrl),
            $catalogNode,
            e($deleteUrl),
            e(csrf_token()),
            $catalogNode,
        );
    }

    /**
     * Вернуть только группы, имеющие хотя бы одну связь со справочником Яндекса.
     *
     * @return Collection<int, Category>
     */
    private function catalogGroups(): Collection
    {
        return Category::query()
            ->where(function ($query): void {
                $query->whereHas('yandexOccupations')
                    ->orWhereHas('yandexSpecializations')
                    ->orWhereHas('yandexServices');
            })
            ->orderBy('name')
            ->get(['id', 'key', 'name']);
    }

    /**
     * Получить узел требуемого уровня и проверить его связь с группой мастеров.
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
        $isLinked = DB::connection($this->connectionName())
            ->table($definition['mapping'])
            ->where('category_id', $category->id)
            ->where($definition['foreign_key'], $catalogNode)
            ->exists();
        abort_unless($isLinked, 404);

        return $node;
    }

    /**
     * Вернуть имя подключения к общей базе Python-парсера.
     */
    private function connectionName(): string
    {
        return (string) config('parser.connection', 'parser');
    }
}
