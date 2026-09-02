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
        return view('admin.professionals.index', [
            'title' => 'Спарсенные данные',
            'catalogTargets' => $this->catalogTargets(),
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
     * Вернуть известные цели парсинга как безопасные значения фильтра level:id.
     *
     * @return Collection<int, object{token: string, name: string, level: string, external_number_id: int}>
     */
    private function catalogTargets(): Collection
    {
        $connection = DB::connection((string) config('parser.connection', 'parser'));
        $targets = collect();
        $levels = [
            ParserCategoryTarget::LEVEL_OCCUPATION => 'yandex_occupations',
            ParserCategoryTarget::LEVEL_SPECIALIZATION => 'yandex_specializations',
            ParserCategoryTarget::LEVEL_SERVICE => 'yandex_services',
        ];

        foreach ($levels as $level => $table) {
            $rows = $connection
                ->table('parser_category_targets as target')
                ->join("{$table} as catalog", 'catalog.external_number_id', '=', 'target.source_rubric_number_id')
                ->where('target.taxonomy_level', $level)
                ->get([
                    'catalog.name',
                    'catalog.external_number_id',
                ]);

            foreach ($rows as $row) {
                $row->level = $level;
                $row->external_number_id = (int) $row->external_number_id;
                $row->token = "{$level}:{$row->external_number_id}";
                $targets->push($row);
            }
        }

        return $targets
            ->unique('token')
            ->sortBy([
                ['name', 'asc'],
                ['token', 'asc'],
            ], SORT_NATURAL | SORT_FLAG_CASE)
            ->values();
    }
}
