<?php

namespace App\Repositories;

use App\DTO\DataTransferObject;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Support\Collection;

interface RepositoryInterface
{
    /**
     * Возвращает все записи модели; нужен для простых сценариев чтения без фильтров.
     */
    public function all(): Collection;

    /**
     * Ищет запись по первичному ключу; используется как базовый безопасный доступ к модели.
     */
    public function find(int|string $id): ?Model;

    /**
     * Создает запись из массива атрибутов; общий низкоуровневый метод для наследников.
     */
    public function create(array $data): Builder|Model;

    /**
     * Создает запись из DTO; нужен, чтобы запись данных шла через типизированный контракт.
     */
    public function createFromDto(DataTransferObject $dto): Builder|Model;

    /**
     * Обновляет запись по первичному ключу массивом атрибутов; возвращает результат сохранения.
     */
    public function update(int|string $id, array $data): bool;

    /**
     * Обновляет запись по первичному ключу данными из DTO; используется для typed update-операций.
     */
    public function updateFromDto(int|string $id, DataTransferObject $dto): bool;

    /**
     * Удаляет запись по первичному ключу; возвращает false, если запись не найдена.
     */
    public function delete(int|string $id): bool;

    /**
     * Удаляет все записи модели без сброса sequence; нужен для очистки таблицы через query builder.
     */
    public function deleteAll(): void;

    /**
     * Полностью очищает таблицу модели со сбросом счетчиков там, где это поддерживает драйвер.
     */
    public function truncate(): void;
}
