<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsToMany;
use Illuminate\Database\Eloquent\Relations\HasMany;

/**
 * Projection of a professional collected by the Python parser.
 *
 * The parser owns this table and its migrations. The admin panel may read records
 * and let an administrator delete complete profiles; it never edits their fields.
 */
class Professional extends Model
{
    protected $table = 'professionals';

    protected $guarded = ['*'];

    protected $hidden = [
        'phone',
        'content_hash',
    ];

    public $timestamps = false;

    public function getConnectionName(): ?string
    {
        return (string) config('parser.connection', 'parser');
    }

    /**
     * @return BelongsToMany<Category, $this, ProfessionalCategory>
     */
    public function categories(): BelongsToMany
    {
        return $this->belongsToMany(
            Category::class,
            'professional_categories',
            'professional_id',
            'category_id'
        )
            ->using(ProfessionalCategory::class)
            ->withPivot(['first_seen_at', 'last_seen_at']);
    }

    /**
     * @return HasMany<ProfessionalCategory, $this>
     */
    public function categoryLinks(): HasMany
    {
        return $this->hasMany(ProfessionalCategory::class, 'professional_id');
    }

    /**
     * @return HasMany<ProfessionalCategoryRubric, $this>
     */
    public function rubrics(): HasMany
    {
        return $this->hasMany(ProfessionalCategoryRubric::class, 'professional_id');
    }

    /**
     * @return array<string, string>
     */
    protected function casts(): array
    {
        return [
            'id' => 'integer',
            'age' => 'integer',
            'age_as_of' => 'date',
            'experience_code' => 'integer',
            'first_seen_at' => 'datetime',
            'last_seen_at' => 'datetime',
            'last_scraped_at' => 'datetime',
        ];
    }
}
