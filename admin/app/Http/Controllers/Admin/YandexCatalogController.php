<?php

namespace App\Http\Controllers\Admin;

use App\Http\Requests\Admin\YandexCatalog\IndexRequest;
use App\Models\Category;
use Illuminate\Contracts\View\View;
use Illuminate\Database\Eloquent\Collection;
use Illuminate\Database\Query\Builder;
use Illuminate\Database\Query\JoinClause;
use Illuminate\Support\Facades\DB;

/**
 * Показывает нормализованную таксономию Яндекс Услуг без возможности изменения.
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
     * Вывести серверную таблицу направлений, специализаций и услуг с фильтрами.
     */
    public function index(IndexRequest $request): View
    {
        $filters = $request->validated();
        $query = $this->catalogQuery();

        $this->applyFilters($query, $filters);

        $rows = $query
            ->orderBy('category_sort_order')
            ->orderBy('category_name')
            ->orderBy('taxonomy_level_sort')
            ->orderBy('link_sort_order')
            ->orderBy('occupation_name')
            ->orderBy('specialization_name')
            ->orderBy('service_name')
            ->paginate(50)
            ->appends($request->safe()->only([
                'q',
                'group',
                'status',
                'has_id',
                'used_for_parsing',
            ]));

        $rows->through(function (object $row): object {
            $status = (string) $row->target_verification_status;
            $row->status_label = self::STATUS_LABELS[$status] ?? 'Неизвестный статус';
            $row->status_badge = self::STATUS_BADGES[$status] ?? 'secondary';
            $row->safe_source_url = $this->safeSourceUrl($row->target_source_url);
            $row->used_for_parsing = (bool) $row->used_for_parsing;

            return $row;
        });

        return view('admin.catalog.index', [
            'title' => 'Каталог Яндекса',
            'rows' => $rows,
            'groups' => $this->catalogGroups(),
            'filters' => $filters,
            'statusOptions' => self::STATUS_LABELS,
        ]);
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
     * Разрешить внешнюю ссылку только на канонический HTTPS-хост Яндекс Услуг.
     */
    private function safeSourceUrl(mixed $url): ?string
    {
        $value = trim((string) $url);
        if ($value === '' || filter_var($value, FILTER_VALIDATE_URL) === false) {
            return null;
        }

        $parts = parse_url($value);
        if (
            ! is_array($parts)
            || strtolower((string) ($parts['scheme'] ?? '')) !== 'https'
            || strtolower((string) ($parts['host'] ?? '')) !== 'uslugi.yandex.ru'
            || isset($parts['user'])
            || isset($parts['pass'])
            || isset($parts['port'])
            || isset($parts['query'])
            || isset($parts['fragment'])
            || ! str_starts_with((string) ($parts['path'] ?? ''), '/')
        ) {
            return null;
        }

        return $value;
    }

    /**
     * Вернуть имя подключения к общей базе Python-парсера.
     */
    private function connectionName(): string
    {
        return (string) config('parser.connection', 'parser');
    }
}
