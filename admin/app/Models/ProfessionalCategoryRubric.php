<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

/**
 * Read-only rubric evidence attached to a professional/category pair.
 */
class ProfessionalCategoryRubric extends Model
{
    protected $table = 'professional_category_rubrics';

    protected $guarded = ['*'];

    protected $primaryKey = null;

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
     * @return array<string, string>
     */
    protected function casts(): array
    {
        return [
            'professional_id' => 'integer',
            'category_id' => 'integer',
            'source_rubric_number_id' => 'integer',
            'experience_code' => 'integer',
            'first_seen_at' => 'datetime',
            'last_seen_at' => 'datetime',
        ];
    }
}
