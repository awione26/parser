<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

/**
 * Представляет одну настройку Python-парсера из общей таблицы key/value.
 *
 * Схемой и начальными строками управляет Alembic. Админ-панель может читать и
 * обновлять только заранее разрешённый набор ключей через ParserSettings.
 */
class ParserSetting extends Model
{
    protected $table = 'settings';

    protected $primaryKey = 'key';

    protected $keyType = 'string';

    protected $guarded = ['*'];

    public $incrementing = false;

    public $timestamps = false;

    public function getConnectionName(): ?string
    {
        return (string) config('parser.connection', 'parser');
    }

    /**
     * @return array<string, string>
     */
    protected function casts(): array
    {
        return [
            'created_at' => 'datetime',
            'updated_at' => 'datetime',
        ];
    }
}
