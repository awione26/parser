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
     * Найти направление каталога по внешнему числовому ID рубрики.
     *
     * @return BelongsTo<YandexOccupation, $this>
     */
    public function yandexOccupation(): BelongsTo
    {
        return $this->belongsTo(
            YandexOccupation::class,
            'source_rubric_number_id',
            'external_number_id',
        );
    }

    /**
     * Найти специализацию каталога по внешнему числовому ID рубрики.
     *
     * @return BelongsTo<YandexSpecialization, $this>
     */
    public function yandexSpecialization(): BelongsTo
    {
        return $this->belongsTo(
            YandexSpecialization::class,
            'source_rubric_number_id',
            'external_number_id',
        );
    }

    /**
     * Найти услугу каталога по внешнему числовому ID рубрики.
     *
     * @return BelongsTo<YandexService, $this>
     */
    public function yandexService(): BelongsTo
    {
        return $this->belongsTo(
            YandexService::class,
            'source_rubric_number_id',
            'external_number_id',
        );
    }

    /**
     * Вернуть канонический узел Яндекс.Каталога для сохранённого доказательства.
     *
     * Старые строки без уровня принимаются только при однозначном совпадении ID
     * ровно на одном уровне, чтобы одинаковые числа не дали неверную категорию.
     */
    public function catalogNode(): ?Model
    {
        $knownNode = match ($this->source_rubric_level) {
            ParserCategoryTarget::LEVEL_OCCUPATION => $this->yandexOccupation,
            ParserCategoryTarget::LEVEL_SPECIALIZATION => $this->yandexSpecialization,
            ParserCategoryTarget::LEVEL_SERVICE => $this->yandexService,
            default => null,
        };

        if (in_array($this->source_rubric_level, [
            ParserCategoryTarget::LEVEL_OCCUPATION,
            ParserCategoryTarget::LEVEL_SPECIALIZATION,
            ParserCategoryTarget::LEVEL_SERVICE,
        ], true)) {
            return $knownNode;
        }

        $matches = array_values(array_filter([
            $this->yandexOccupation,
            $this->yandexSpecialization,
            $this->yandexService,
        ]));

        return count($matches) === 1 ? $matches[0] : null;
    }

    /**
     * Вернуть только каноническое название из Яндекс.Каталога.
     */
    public function catalogName(): ?string
    {
        $name = trim((string) $this->catalogNode()?->getAttribute('name'));

        return $name === '' ? null : $name;
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
