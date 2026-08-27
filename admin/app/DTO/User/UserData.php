<?php

namespace App\DTO\User;

use App\DTO\DataTransferObject;

final readonly class UserData implements DataTransferObject
{
    public function __construct(
        public int $id,
        public string $login,
        public string $name,
        public string $role,
        public ?string $password = null,
    ) {}

    public static function fromArray(array $data): self
    {
        return new self(
            id: (int) ($data['id'] ?? 0),
            login: mb_strtolower(trim((string) $data['login'])),
            name: trim((string) $data['name']),
            role: (string) $data['role'],
            password: ! empty($data['password']) ? (string) $data['password'] : null,
        );
    }

    public function toArray(): array
    {
        $data = [
            'login' => $this->login,
            'name' => $this->name,
            'role' => $this->role,
        ];

        return $data;
    }
}
