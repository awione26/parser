<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsToMany;
use Illuminate\Database\Eloquent\Relations\HasMany;

/**
 * Направление верхнего уровня из публичного каталога Яндекс Услуг.
 *
 * Таблицей управляет Python/Alembic. Админ-панель использует модель только для
 * чтения нормализованного справочника и его связей с внутренними категориями.
 */
class YandexOccupation extends Model
{
    protected $table = 'yandex_occupations';

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
     * Вернуть специализации, входящие в это направление.
     *
     * @return HasMany<YandexSpecialization, $this>
     */
    public function specializations(): HasMany
    {
        return $this->hasMany(YandexSpecialization::class, 'occupation_id');
    }

    /**
     * Вернуть внутренние группы мастеров, связанные с направлением.
     *
     * @return BelongsToMany<Category, $this>
     */
    public function categories(): BelongsToMany
    {
        return $this->belongsToMany(
            Category::class,
            'category_yandex_occupations',
            'occupation_id',
            'category_id',
        )->withPivot('sort_order');
    }

    /**
     * Привести внешние идентификаторы и даты к удобным PHP-типам.
     *
     * @return array<string, string>
     */
    protected function casts(): array
    {
        return [
            'id' => 'integer',
            'external_number_id' => 'integer',
            'created_at' => 'datetime',
            'updated_at' => 'datetime',
        ];
    }
}
