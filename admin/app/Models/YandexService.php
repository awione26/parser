<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\BelongsToMany;

/**
 * Конкретная услуга из публичного каталога Яндекс Услуг, доступная в CRUD админки.
 */
class YandexService extends Model
{
    protected $table = 'yandex_services';

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
     * Вернуть родительскую специализацию, если она установлена в справочнике.
     *
     * @return BelongsTo<YandexSpecialization, $this>
     */
    public function specialization(): BelongsTo
    {
        return $this->belongsTo(YandexSpecialization::class, 'specialization_id');
    }

    /**
     * Вернуть внутренние группы мастеров, связанные с услугой.
     *
     * @return BelongsToMany<Category, $this>
     */
    public function categories(): BelongsToMany
    {
        return $this->belongsToMany(
            Category::class,
            'category_yandex_services',
            'service_id',
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
            'specialization_id' => 'integer',
            'external_number_id' => 'integer',
            'created_at' => 'datetime',
            'updated_at' => 'datetime',
        ];
    }
}
