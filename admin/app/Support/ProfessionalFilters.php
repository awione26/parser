<?php

namespace App\Support;

use App\Models\ParserCategoryTarget;
use App\Models\YandexOccupation;
use App\Models\YandexService;
use App\Models\YandexSpecialization;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Http\Request;

final class ProfessionalFilters
{
    /**
     * Применяет к запросу мастеров фильтры реестра и Excel-экспорта.
     */
    public static function apply(Builder $query, Request $request): void
    {
        $search = trim((string) data_get($request->input('search'), 'value', ''));
        if ($search !== '') {
            $query->where(function (Builder $nested) use ($search): void {
                $like = '%'.str_replace(['\\', '%', '_'], ['\\\\', '\\%', '\\_'], $search).'%';
                $nested
                    ->where('full_name', 'like', $like)
                    ->orWhere('city', 'like', $like)
                    ->orWhere('region', 'like', $like)
                    ->orWhere('country', 'like', $like)
                    ->orWhere('source_profile_id', 'like', $like);
            });
        }

        foreach (['city', 'region', 'country', 'source'] as $field) {
            $value = trim((string) $request->input($field, ''));
            if ($value !== '') {
                $query->where($field, $value);
            }
        }

        $gender = $request->string('gender')->toString();
        if (in_array($gender, ['male', 'female', 'other'], true)) {
            $query->where('gender', $gender);
        } elseif ($gender === 'unknown') {
            $query->whereNull('gender');
        }

        $phoneStatus = trim((string) $request->input('phone_status', ''));
        if ($phoneStatus !== '') {
            $query->where('phone_status', $phoneStatus);
        }

        $hasPhone = $request->input('has_phone');
        if ($hasPhone === 'yes') {
            $query->whereNotNull('phone')->where('phone', '<>', '');
        } elseif ($hasPhone === 'no') {
            $query->where(function (Builder $nested): void {
                $nested->whereNull('phone')->orWhere('phone', '');
            });
        }

        if ($request->filled('age_from')) {
            $query->where('age', '>=', max(0, (int) $request->input('age_from')));
        }
        if ($request->filled('age_to')) {
            $query->where('age', '<=', min(120, (int) $request->input('age_to')));
        }
        if ($request->filled('experience_from')) {
            $query->where(
                'experience_code',
                '>=',
                max(0, (int) $request->input('experience_from')),
            );
        }

        if ($request->filled('catalog_target')) {
            $target = trim((string) $request->input('catalog_target'));
            if (preg_match(
                '/\A(occupation|specialization|service):([1-9][0-9]*)\z/D',
                $target,
                $matches,
            ) !== 1) {
                $query->whereRaw('1 = 0');
            } else {
                $level = $matches[1];
                $rubricId = (int) $matches[2];
                $modelClass = match ($level) {
                    ParserCategoryTarget::LEVEL_OCCUPATION => YandexOccupation::class,
                    ParserCategoryTarget::LEVEL_SPECIALIZATION => YandexSpecialization::class,
                    ParserCategoryTarget::LEVEL_SERVICE => YandexService::class,
                };
                $isCatalogTarget = ParserCategoryTarget::query()
                    ->where('taxonomy_level', $level)
                    ->where('source_rubric_number_id', $rubricId)
                    ->exists()
                    && $modelClass::query()
                        ->where('external_number_id', $rubricId)
                        ->exists();

                if (! $isCatalogTarget) {
                    $query->whereRaw('1 = 0');

                    return;
                }

                $query->whereHas('rubrics', function (Builder $rubricQuery) use ($level, $rubricId): void {
                    $rubricQuery
                        ->where('source_rubric_number_id', $rubricId)
                        ->where('source_rubric_level', $level);
                });
            }
        }

        if ($request->filled('scraped_from')) {
            $query->whereDate('last_scraped_at', '>=', (string) $request->input('scraped_from'));
        }
        if ($request->filled('scraped_to')) {
            $query->whereDate('last_scraped_at', '<=', (string) $request->input('scraped_to'));
        }

        if ($request->user()?->isAdmin() && $request->filled('phone')) {
            $phone = PhoneNumber::normalizeSearch((string) $request->input('phone'));
            $phone === null
                ? $query->whereRaw('1 = 0')
                : $query->where('phone', $phone);
        }
    }
}
