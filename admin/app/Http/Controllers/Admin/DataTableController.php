<?php

namespace App\Http\Controllers\Admin;

use App\Models\ParserLog;
use App\Models\Professional;
use App\Support\PhoneNumber;
use App\Support\ProfessionalFilters;
use App\Support\ProfessionalPresenter;
use Carbon\CarbonImmutable;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Symfony\Component\HttpFoundation\JsonResponse;
use Throwable;
use Yajra\DataTables\Facades\DataTables;

class DataTableController extends Controller
{
    /**
     * Вернуть журнал запусков парсера для серверной таблицы админки.
     */
    public function logs(Request $request): JsonResponse
    {
        $filters = $request->validate([
            'result' => ['nullable', 'string', 'in:success,failure,running'],
            'resource' => ['nullable', 'string', 'max:255'],
            'started_from' => ['nullable', 'date_format:Y-m-d'],
            'started_to' => ['nullable', 'date_format:Y-m-d', 'after_or_equal:started_from'],
        ]);

        $query = ParserLog::query()
            ->select([
                'id',
                'started_at',
                'finished_at',
                'result',
                'error_reason',
                'resource',
            ])
            ->orderByDesc('started_at')
            ->orderByDesc('id');

        if (($filters['result'] ?? null) === 'running') {
            $query->whereNull('result');
        } elseif (in_array($filters['result'] ?? null, [
            ParserLog::RESULT_SUCCESS,
            ParserLog::RESULT_FAILURE,
        ], true)) {
            $query->where('result', $filters['result']);
        }

        $resource = trim((string) ($filters['resource'] ?? ''));
        if ($resource !== '') {
            $query->where('resource', $resource);
        }

        if (! empty($filters['started_from'])) {
            $query->where(
                'started_at',
                '>=',
                $this->localDateBoundaryUtc($filters['started_from'])->format('Y-m-d H:i:s'),
            );
        }
        if (! empty($filters['started_to'])) {
            $query->where(
                'started_at',
                '<',
                $this->localDateBoundaryUtc($filters['started_to'])->addDay()->format('Y-m-d H:i:s'),
            );
        }

        return DataTables::eloquent($query)
            ->skipAutoFilter()
            ->editColumn('started_at', fn (ParserLog $row): string => $this->parserLogStartedAt($row))
            ->editColumn('result', fn (ParserLog $row): string => $this->parserLogResult($row))
            ->editColumn('error_reason', fn (ParserLog $row): string => $row->error_reason ?: '—')
            ->editColumn('resource', fn (ParserLog $row): string => $row->resource ?: '—')
            ->rawColumns(['result'])
            ->only(['id', 'started_at', 'result', 'error_reason', 'resource'])
            ->toJson();
    }

    public function professionals(Request $request): JsonResponse
    {
        $query = Professional::query()
            ->select([
                'id',
                'source',
                'source_profile_id',
                'profile_url',
                'full_name',
                'phone',
                'phone_status',
                'city',
                'region',
                'country',
                'age',
                'age_as_of',
                'gender',
                'experience_code',
                'experience_text',
                'photo_url',
                'last_scraped_at',
            ])
            ->with([
                'rubrics.yandexOccupation:id,external_number_id,name',
                'rubrics.yandexSpecialization:id,external_number_id,name',
                'rubrics.yandexService:id,external_number_id,name',
            ])
            ->orderByDesc('last_scraped_at');

        ProfessionalFilters::apply($query, $request);

        return DataTables::eloquent($query)
            ->skipAutoFilter()
            ->addColumn('photo', fn (Professional $row): string => $this->photoColumn($row))
            ->editColumn('full_name', fn (Professional $row): string => $row->full_name ?: '—')
            ->addColumn('phone', fn (Professional $row): string => $this->phoneColumn($row))
            ->addColumn('location', fn (Professional $row): string => ProfessionalPresenter::location($row))
            ->addColumn('age_display', fn (Professional $row): string => $row->age === null ? '—' : (string) $row->age)
            ->editColumn('gender', fn (Professional $row): string => ProfessionalPresenter::gender($row->gender))
            ->addColumn('experience', fn (Professional $row): string => $row->experience_text ?: '—')
            ->addColumn('categories_display', fn (Professional $row): string => $this->categoriesColumn($row))
            ->addColumn('resource', fn (Professional $row): string => $this->resourceColumn($row))
            ->addColumn('scraped_at', fn (Professional $row): string => $row->last_scraped_at?->format('d.m.Y H:i') ?? '—')
            ->addColumn('action', fn (Professional $row): string => $this->actionColumn($row))
            ->rawColumns(['photo', 'phone', 'categories_display', 'resource', 'action'])
            ->only([
                'id',
                'photo',
                'full_name',
                'phone',
                'location',
                'age_display',
                'gender',
                'experience',
                'categories_display',
                'resource',
                'scraped_at',
                'action',
            ])
            ->toJson();
    }

    /**
     * Преобразовать начало локального дня из часового пояса панели в UTC для БД.
     */
    private function localDateBoundaryUtc(string $date): CarbonImmutable
    {
        return CarbonImmutable::createFromFormat(
            '!Y-m-d',
            $date,
            (string) config('app.timezone', 'UTC'),
        )->utc();
    }

    /**
     * Показать UTC-время запуска в часовом поясе, настроенном для админки.
     */
    private function parserLogStartedAt(ParserLog $row): string
    {
        $startedAt = $row->getRawOriginal('started_at');
        if (! is_string($startedAt) || trim($startedAt) === '') {
            return '—';
        }

        try {
            return CarbonImmutable::createFromFormat('Y-m-d H:i:s', $startedAt, 'UTC')
                ->setTimezone((string) config('app.timezone', 'UTC'))
                ->format('d.m.Y H:i:s');
        } catch (Throwable) {
            return '—';
        }
    }

    /**
     * Преобразовать технический результат запуска в фиксированный безопасный badge.
     */
    private function parserLogResult(ParserLog $row): string
    {
        return match ($row->result) {
            ParserLog::RESULT_SUCCESS => '<span class="badge badge-success">Успех</span>',
            ParserLog::RESULT_FAILURE => '<span class="badge badge-danger">Неуспех</span>',
            null, '' => '<span class="badge badge-info">Выполняется</span>',
            default => '<span class="badge badge-secondary">Неизвестно</span>',
        };
    }

    private function photoColumn(Professional $row): string
    {
        $url = ProfessionalPresenter::safePhotoUrl($row->photo_url);
        if ($url === null) {
            return sprintf('<span class="profile-initials" aria-hidden="true">%s</span>', e(ProfessionalPresenter::initials($row->full_name)));
        }

        return sprintf(
            '<img class="profile-avatar" src="%s" alt="Фото: %s" loading="lazy" referrerpolicy="no-referrer">',
            e($url),
            e($row->full_name ?: 'мастер'),
        );
    }

    private function phoneColumn(Professional $row): string
    {
        $status = e(ProfessionalPresenter::phoneStatus($row->phone_status));
        if (! PhoneNumber::isValid($row->phone) || ! Auth::user()?->isAdmin()) {
            return '<span class="text-muted">'.$status.'</span>';
        }

        return sprintf(
            '<button type="button" class="btn btn-sm btn-outline-secondary js-reveal-phone" data-url="%s"><i class="fas fa-phone mr-1" aria-hidden="true"></i>Показать</button>',
            e(route('admin.professionals.phone', $row)),
        );
    }

    private function categoriesColumn(Professional $row): string
    {
        $names = $row->rubrics
            ->map(fn ($rubric): ?string => $rubric->catalogName())
            ->filter()
            ->unique()
            ->sort(SORT_NATURAL | SORT_FLAG_CASE)
            ->values();

        if ($names->isEmpty()) {
            return '<span class="text-muted">—</span>';
        }

        return $names
            ->map(fn (string $name): string => '<span class="badge badge-light border mr-1 mb-1">'.e($name).'</span>')
            ->implode('');
    }

    private function resourceColumn(Professional $row): string
    {
        $url = ProfessionalPresenter::safeProfileUrl($row->profile_url);
        if ($url === null) {
            return '<span class="text-muted">'.e($row->source ?: '—').'</span>';
        }

        return sprintf(
            '<a href="%s" target="_blank" rel="noopener noreferrer">%s <i class="fas fa-external-link-alt fa-xs" aria-hidden="true"></i></a>',
            e($url),
            e($row->source ?: 'uslugi.yandex.ru'),
        );
    }

    private function actionColumn(Professional $row): string
    {
        $name = $row->full_name ?: (string) $row->id;
        $view = sprintf(
            '<a class="btn btn-sm btn-outline-primary" href="%s" aria-label="Открыть карточку %s"><i class="fas fa-eye" aria-hidden="true"></i></a>',
            e(route('admin.professionals.show', $row)),
            e($name),
        );

        if (! Auth::user()?->isAdmin()) {
            return $view;
        }

        $delete = sprintf(
            '<button type="button" class="btn btn-sm btn-outline-danger js-delete-professional" data-id="%d" data-name="%s" data-url="%s" aria-label="Удалить мастера %s"><i class="fas fa-trash" aria-hidden="true"></i></button>',
            $row->id,
            e($name),
            e(route('admin.professionals.destroy', $row)),
            e($name),
        );

        return '<div class="btn-group" role="group">'.$view.$delete.'</div>';
    }
}
