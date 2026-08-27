<?php

namespace App\Repositories;

use App\DTO\DataTransferObject;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Support\Collection;

abstract class BaseRepository implements RepositoryInterface
{
    /**
     * Сохраняет Eloquent-модель, с которой работает конкретный репозиторий.
     */
    public function __construct(protected Model $model) {}

    /**
     * Создает новую запись из массива атрибутов; базовая операция для всех наследников.
     */
    public function create(array $data): Builder|Model
    {
        return $this->model->create($data);
    }

    /**
     * Создает новую запись из DTO; нужен, чтобы сервисы не передавали сырые массивы напрямую.
     */
    public function createFromDto(DataTransferObject $dto): Builder|Model
    {
        return $this->create($dto->toArray());
    }

    /**
     * Обновляет запись по id переданными атрибутами; возвращает false, если запись не найдена.
     *
     * @param  array<string, mixed>  $data
     */
    public function update(int|string $id, array $data): bool
    {
        $model = $this->model->find($id);

        if ($model) {
            return $model->fill($data)->save();
        }

        return false;
    }

    /**
     * Обновляет запись по id данными из DTO; нужен для единого typed update-подхода.
     */
    public function updateFromDto(int|string $id, DataTransferObject $dto): bool
    {
        return $this->update($id, $dto->toArray());
    }

    /**
     * Возвращает все записи таблицы модели; используется только для простых выборок без фильтров.
     */
    public function all(): Collection
    {
        return $this->model->all();
    }

    /**
     * Ищет запись по первичному ключу и возвращает null, если запись отсутствует.
     */
    public function find(int|string $id): ?Model
    {
        return $this->model->find($id);
    }

    /**
     * Удаляет запись по первичному ключу; нужен для общей операции удаления в наследниках.
     */
    public function delete(int|string $id): bool
    {
        $model = $this->model->find($id);
        if ($model) {
            $model->delete();

            return true;
        }

        return false;
    }

    /**
     * Удаляет все записи через query builder без пересоздания таблицы.
     */
    public function deleteAll(): void
    {
        $this->model->query()->delete();
    }

    /**
     * Полностью очищает таблицу модели; полезно для служебной очистки и тестов.
     */
    public function truncate(): void
    {
        $this->model->truncate();
    }
}
