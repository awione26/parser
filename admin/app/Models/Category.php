<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsToMany;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Database\Eloquent\Relations\HasOne;

/**
 * Общая категория мастеров, используемая парсером и его конфигурацией.
 */
class Category extends Model
{
    protected $table = 'categories';

    protected $guarded = ['*'];

    public $timestamps = false;

    public function getConnectionName(): ?string
    {
        return (string) config('parser.connection', 'parser');
    }

    /**
     * @return BelongsToMany<Professional, $this, ProfessionalCategory>
     */
    public function professionals(): BelongsToMany
    {
        return $this->belongsToMany(
            Professional::class,
            'professional_categories',
            'category_id',
            'professional_id'
        )
            ->using(ProfessionalCategory::class)
            ->withPivot(['first_seen_at', 'last_seen_at']);
    }

    /**
     * @return HasMany<ProfessionalCategory, $this>
     */
    public function professionalLinks(): HasMany
    {
        return $this->hasMany(ProfessionalCategory::class, 'category_id');
    }

    /**
     * @return HasMany<ProfessionalCategoryRubric, $this>
     */
    public function rubrics(): HasMany
    {
        return $this->hasMany(ProfessionalCategoryRubric::class, 'category_id');
    }

    /**
     * Вернуть настройки обхода этой категории, если она добавлена в план парсинга.
     *
     * @return HasOne<ParserCategory, $this>
     */
    public function parserConfiguration(): HasOne
    {
        return $this->hasOne(ParserCategory::class, 'category_id');
    }

    /**
     * Вернуть направления Яндекса, включённые во внутреннюю группу.
     *
     * @return BelongsToMany<YandexOccupation, $this>
     */
    public function yandexOccupations(): BelongsToMany
    {
        return $this->belongsToMany(
            YandexOccupation::class,
            'category_yandex_occupations',
            'category_id',
            'occupation_id',
        )->withPivot('sort_order');
    }

    /**
     * Вернуть специализации Яндекса, включённые во внутреннюю группу.
     *
     * @return BelongsToMany<YandexSpecialization, $this>
     */
    public function yandexSpecializations(): BelongsToMany
    {
        return $this->belongsToMany(
            YandexSpecialization::class,
            'category_yandex_specializations',
            'category_id',
            'specialization_id',
        )->withPivot('sort_order');
    }

    /**
     * Вернуть услуги Яндекса, включённые во внутреннюю группу.
     *
     * @return BelongsToMany<YandexService, $this>
     */
    public function yandexServices(): BelongsToMany
    {
        return $this->belongsToMany(
            YandexService::class,
            'category_yandex_services',
            'category_id',
            'service_id',
        )->withPivot('sort_order');
    }

    /**
     * @return array<string, string>
     */
    protected function casts(): array
    {
        return [
            'id' => 'integer',
            'created_at' => 'datetime',
            'updated_at' => 'datetime',
        ];
    }
}
