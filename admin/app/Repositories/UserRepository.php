<?php

namespace App\Repositories;

use App\DTO\User\UserData;
use App\Models\User;
use DomainException;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Collection;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Pagination\LengthAwarePaginator;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Hash;
use InvalidArgumentException;

class UserRepository extends BaseRepository
{
    public const string SELF_DELETE_MESSAGE = 'Нельзя удалить текущего администратора.';

    public const string LAST_ADMIN_DELETE_MESSAGE = 'Нельзя удалить последнего администратора.';

    public const string LAST_ADMIN_DEMOTION_MESSAGE = 'Нельзя понизить роль последнего администратора.';

    public function __construct(User $model)
    {
        parent::__construct($model);
    }

    /**
     * @return array<string, string>
     */
    public function roleOptions(): array
    {
        return User::$role_name;
    }

    /**
     * @return LengthAwarePaginator<int, User>
     */
    public function paginateForAdmin(int $perPage = 25): LengthAwarePaginator
    {
        return User::query()
            ->orderBy('name')
            ->orderBy('id')
            ->paginate($perPage);
    }

    public function createFromData(UserData $data): Builder|Model
    {
        if ($data->password === null) {
            throw new InvalidArgumentException('Для нового администратора требуется пароль.');
        }

        $payload = $data->toArray();
        $payload['password'] = Hash::make($data->password);

        return $this->create($payload);
    }

    /**
     * @param  array<string, mixed>  $data
     */
    public function createFromArray(array $data): Builder|Model
    {
        return $this->createFromData(UserData::fromArray($data));
    }

    public function updateFromData(UserData $data): bool
    {
        return DB::transaction(function () use ($data): bool {
            $adminIds = $this->lockAdministrators();
            $user = User::query()->lockForUpdate()->find($data->id);

            if ($user === null) {
                return false;
            }

            if (
                $user->role === User::ROLE_ADMIN
                && $data->role !== User::ROLE_ADMIN
                && $adminIds->count() <= 1
            ) {
                throw new DomainException(self::LAST_ADMIN_DEMOTION_MESSAGE);
            }

            $payload = $data->toArray();

            if ($data->password !== null) {
                $payload['password'] = Hash::make($data->password);
            }

            return $user->fill($payload)->save();
        });
    }

    /**
     * @param  array<string, mixed>  $data
     */
    public function updateFromArray(array $data): bool
    {
        return $this->updateFromData(UserData::fromArray($data));
    }

    public function deleteSafely(int $id, int $actorId): bool
    {
        return DB::transaction(function () use ($id, $actorId): bool {
            $adminIds = $this->lockAdministrators();
            $user = User::query()->lockForUpdate()->find($id);

            if ($user === null) {
                return false;
            }

            if ($user->id === $actorId) {
                throw new DomainException(self::SELF_DELETE_MESSAGE);
            }

            if ($user->role === User::ROLE_ADMIN && $adminIds->count() <= 1) {
                throw new DomainException(self::LAST_ADMIN_DELETE_MESSAGE);
            }

            return (bool) $user->delete();
        });
    }

    /**
     * Locking all administrator rows serializes concurrent deletion and demotion.
     *
     * @return Collection<int, User>
     */
    private function lockAdministrators(): Collection
    {
        return User::query()
            ->where('role', User::ROLE_ADMIN)
            ->orderBy('id')
            ->lockForUpdate()
            ->get(['id']);
    }
}
