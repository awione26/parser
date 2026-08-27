<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

/**
 * Представляет один запуск парсера, записанный Python-приложением.
 *
 * Схемой таблицы управляет Alembic. Админ-панель использует модель только для
 * чтения журнала через отдельное ограниченное подключение к базе парсера.
 */
class ParserLog extends Model
{
    public const string RESULT_SUCCESS = 'success';

    public const string RESULT_FAILURE = 'failure';

    protected $table = 'logs';

    protected $guarded = ['*'];

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
            'id' => 'integer',
            'started_at' => 'datetime',
            'finished_at' => 'datetime',
        ];
    }
}
