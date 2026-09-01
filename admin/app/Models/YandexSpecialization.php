<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\BelongsToMany;
use Illuminate\Database\Eloquent\Relations\HasMany;

/**
 * Специализация из публичного каталога Яндекс Услуг.
 */
class YandexSpecialization extends Model
{
    protected $table = 'yandex_specializations';

    protected $guarded = ['*'];

    public $timestamps = false;

    /**
     * Использовать отдельное подключение к базе данных парсера.
     */
    public function getConnectionName(): ?string
    {
        return (string) config('parser.connection', 'parser');
    }

    /**
     * Вернуть родительское направление, если оно установлено в справочнике.
     *
     * @return BelongsTo<YandexOccupation, $this>
     */
    public function occupation(): BelongsTo
    {
        return $this->belongsTo(YandexOccupation::class, 'occupation_id');
    }

    /**
     * Вернуть услуги, относящиеся к специализации.
     *
     * @return HasMany<YandexService, $this>
     */
    public function services(): HasMany
    {
        return $this->hasMany(YandexService::class, 'specialization_id');
    }

    /**
     * Вернуть внутренние группы мастеров, связанные со специализацией.
     *
     * @return BelongsToMany<Category, $this>
     */
    public function categories(): BelongsToMany
    {
        return $this->belongsToMany(
            Category::class,
            'category_yandex_specializations',
            'specialization_id',
            'category_id',
        )->withPivot('sort_order');
    }

    /**
     * Привести ключи и даты к удобным PHP-типам.
     *
     * @return array<string, string>
     */
    protected function casts(): array
    {
        return [
            'id' => 'integer',
            'occupation_id' => 'integer',
            'external_number_id' => 'integer',
            'created_at' => 'datetime',
            'updated_at' => 'datetime',
        ];
    }
}
