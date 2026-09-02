<?php

namespace App\Http\Controllers\Admin;

use App\Models\ParserCategoryTarget;
use App\Models\Professional;
use App\Support\PhoneNumber;
use App\Support\ProfessionalPresenter;
use Illuminate\Contracts\View\View;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\DB;

class ProfessionalController extends Controller
{
    public function index(): View
    {
        $catalogTargetGroups = $this->catalogTargetGroups();

        return view('admin.professionals.index', [
            'title' => 'Спарсенные данные',
            'catalogTargetGroups' => $catalogTargetGroups,
            'sources' => Professional::query()
                ->whereNotNull('source')
                ->distinct()
                ->orderBy('source')
                ->pluck('source'),
        ]);
    }

    public function show(Professional $professional): View
    {
        $professional->load([
            'rubrics' => fn ($query) => $query
                ->with([
                    'yandexOccupation:id,external_number_id,name',
                    'yandexSpecialization:id,external_number_id,name',
                    'yandexService:id,external_number_id,name',
                ])
                ->orderBy('category_id')
                ->orderBy('source_rubric_number_id'),
        ]);

        $catalogCategories = $professional->rubrics
            ->map(fn ($rubric): ?string => $rubric->catalogName())
            ->filter()
            ->unique()
            ->sort(SORT_NATURAL | SORT_FLAG_CASE)
            ->values();

        return view('admin.professionals.show', [
            'title' => $professional->full_name ?: 'Карточка мастера',
            'professional' => $professional,
            'hasPhone' => PhoneNumber::isValid($professional->phone),
            'photoUrl' => ProfessionalPresenter::safePhotoUrl($professional->photo_url),
            'profileUrl' => ProfessionalPresenter::safeProfileUrl($professional->profile_url),
            'catalogCategories' => $catalogCategories,
        ]);
    }

    /**
     * Вернуть цели парсинга, сгруппированные по категориям мастеров.
     *
     * Группы сортируются по порядку конфигурации парсера, а цели внутри
     * группы — по их sort_order, названию и стабильным ID. Токен level:id
     * остаётся прежним, чтобы группировка не меняла семантику фильтра.
     *
     * @return Collection<int, object{id: int, name: string, targets: Collection<int, object{token: string, name: string, level: string, external_number_id: int}>}>
     */
    private function catalogTargetGroups(): Collection
    {
        $connection = DB::connection((string) config('parser.connection', 'parser'));
        $targets = collect();
        $levels = [
            ParserCategoryTarget::LEVEL_OCCUPATION => [
                'table' => 'yandex_occupations',
                'mapping' => 'category_yandex_occupations',
                'foreign_key' => 'occupation_id',
                'sort_order' => 1,
            ],
            ParserCategoryTarget::LEVEL_SPECIALIZATION => [
                'table' => 'yandex_specializations',
                'mapping' => 'category_yandex_specializations',
                'foreign_key' => 'specialization_id',
                'sort_order' => 2,
            ],
            ParserCategoryTarget::LEVEL_SERVICE => [
                'table' => 'yandex_services',
                'mapping' => 'category_yandex_services',
                'foreign_key' => 'service_id',
                'sort_order' => 3,
            ],
        ];

        foreach ($levels as $level => $definition) {
            $table = $definition['table'];
            $mapping = $definition['mapping'];
            $foreignKey = $definition['foreign_key'];
            $rows = $connection
                ->table('parser_category_targets as target')
                ->join('parser_categories as parser_category', 'parser_category.category_id', '=', 'target.category_id')
                ->join('categories as category', 'category.id', '=', 'target.category_id')
                ->join("{$table} as catalog", 'catalog.external_number_id', '=', 'target.source_rubric_number_id')
                ->join("{$mapping} as mapping", function ($join) use ($foreignKey): void {
                    $join->on('mapping.category_id', '=', 'target.category_id')
                        ->on("mapping.{$foreignKey}", '=', 'catalog.id');
                })
                ->where('target.taxonomy_level', $level)
                ->get([
                    'target.id as target_id',
                    'target.category_id',
                    'target.sort_order as target_sort_order',
                    'parser_category.sort_order as group_sort_order',
                    'category.name as group_name',
                    'catalog.name',
                    'catalog.external_number_id',
                ]);

            foreach ($rows as $row) {
                $row->level = $level;
                $row->taxonomy_level_sort = $definition['sort_order'];
                $row->target_id = (int) $row->target_id;
                $row->category_id = (int) $row->category_id;
                $row->target_sort_order = (int) $row->target_sort_order;
                $row->group_sort_order = (int) $row->group_sort_order;
                $row->external_number_id = (int) $row->external_number_id;
                $row->token = "{$level}:{$row->external_number_id}";
                $targets->push($row);
            }
        }

        return $targets
            ->sortBy([
                ['group_sort_order', 'asc'],
                ['group_name', 'asc'],
                ['category_id', 'asc'],
                ['target_sort_order', 'asc'],
                ['name', 'asc'],
                ['taxonomy_level_sort', 'asc'],
                ['external_number_id', 'asc'],
                ['target_id', 'asc'],
            ], SORT_NATURAL | SORT_FLAG_CASE)
            ->groupBy('category_id')
            ->map(function (Collection $groupTargets): object {
                $first = $groupTargets->first();

                return (object) [
                    'id' => $first->category_id,
                    'name' => $first->group_name,
                    'targets' => $groupTargets
                        ->map(fn (object $target): object => (object) [
                            'token' => $target->token,
                            'name' => $target->name,
                            'level' => $target->level,
                            'external_number_id' => $target->external_number_id,
                        ])
                        ->values(),
                ];
            })
            ->values();
    }
}
