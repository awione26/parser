<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

/**
 * Нормализованная цель обхода одной категории парсера.
 *
 * Раздел «Яндекс.Каталог» синхронизирует эти строки с legacy-полем seed_paths,
 * чтобы Python-парсер и административная панель использовали один план обхода.
 */
class ParserCategoryTarget extends Model
{
    public const string LEVEL_OCCUPATION = 'occupation';

    public const string LEVEL_SPECIALIZATION = 'specialization';

    public const string LEVEL_SERVICE = 'service';

    public const string LEVEL_UNKNOWN = 'unknown';

    protected $table = 'parser_category_targets';

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
     * Вернуть конфигурацию категории, которой принадлежит цель.
     *
     * @return BelongsTo<ParserCategory, $this>
     */
    public function parserCategory(): BelongsTo
    {
        return $this->belongsTo(ParserCategory::class, 'category_id', 'category_id');
    }

    /**
     * Привести идентификаторы, флаг активности и даты к PHP-типам.
     *
     * @return array<string, string>
     */
    protected function casts(): array
    {
        return [
            'id' => 'integer',
            'category_id' => 'integer',
            'source_rubric_number_id' => 'integer',
            'is_active' => 'boolean',
            'sort_order' => 'integer',
            'created_at' => 'datetime',
            'updated_at' => 'datetime',
        ];
    }
}
