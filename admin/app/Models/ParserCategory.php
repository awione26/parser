<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

/**
 * Настройки категории, которую Python-парсер должен обходить.
 *
 * Название, ключ и примечание находятся в общей таблице categories, а эта
 * модель хранит только параметры запуска и ссылается на неё по category_id.
 */
class ParserCategory extends Model
{
    protected $table = 'parser_categories';

    protected $primaryKey = 'category_id';

    protected $guarded = ['*'];

    public $incrementing = false;

    public $timestamps = false;

    public function getConnectionName(): ?string
    {
        return (string) config('parser.connection', 'parser');
    }

    /**
     * Вернуть общие данные категории: ключ, название и примечание.
     *
     * @return BelongsTo<Category, $this>
     */
    public function category(): BelongsTo
    {
        return $this->belongsTo(Category::class, 'category_id');
    }

    /**
     * Вернуть нормализованные цели обхода этой категории.
     *
     * @return HasMany<ParserCategoryTarget, $this>
     */
    public function targets(): HasMany
    {
        return $this->hasMany(ParserCategoryTarget::class, 'category_id', 'category_id');
    }

    /**
     * Привести JSON-пути, флаг активности и служебные поля к удобным PHP-типам.
     *
     * @return array<string, string>
     */
    protected function casts(): array
    {
        return [
            'category_id' => 'integer',
            'seed_paths' => 'array',
            'is_active' => 'boolean',
            'sort_order' => 'integer',
            'created_at' => 'datetime',
            'updated_at' => 'datetime',
        ];
    }
}
