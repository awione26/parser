<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Database\Eloquent\Relations\Pivot;

/**
 * Read-only link between a professional and a parser category.
 */
class ProfessionalCategory extends Pivot
{
    protected $table = 'professional_categories';

    protected $guarded = ['*'];

    public $incrementing = false;

    public $timestamps = false;

    public function getConnectionName(): ?string
    {
        return (string) config('parser.connection', 'parser');
    }

    /**
     * @return BelongsTo<Professional, $this>
     */
    public function professional(): BelongsTo
    {
        return $this->belongsTo(Professional::class, 'professional_id');
    }

    /**
     * @return BelongsTo<Category, $this>
     */
    public function category(): BelongsTo
    {
        return $this->belongsTo(Category::class, 'category_id');
    }

    /**
     * Rubrics for this exact category link.
     *
     * This relation is intended for lazy loading on a hydrated pivot. For bulk
     * eager loading, use Professional::rubrics() or Category::rubrics().
     *
     * @return HasMany<ProfessionalCategoryRubric, $this>
     */
    public function rubrics(): HasMany
    {
        return $this->hasMany(
            ProfessionalCategoryRubric::class,
            'professional_id',
            'professional_id'
        )->where('category_id', $this->getAttribute('category_id'));
    }

    /**
     * @return array<string, string>
     */
    protected function casts(): array
    {
        return [
            'professional_id' => 'integer',
            'category_id' => 'integer',
            'first_seen_at' => 'datetime',
            'last_seen_at' => 'datetime',
        ];
    }
}
