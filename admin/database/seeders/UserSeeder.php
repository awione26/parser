<?php

namespace Database\Seeders;

use App\Models\User;
use Illuminate\Database\Seeder;
use Illuminate\Support\Facades\Hash;
use RuntimeException;

class UserSeeder extends Seeder
{
    public function run(): void
    {
        $login = mb_strtolower(trim((string) env('ADMIN_INITIAL_LOGIN', '')));
        $password = (string) env('ADMIN_INITIAL_PASSWORD', '');
        $name = trim((string) env('ADMIN_INITIAL_NAME', 'Главный администратор'));
        $allowWeakInitialPassword = filter_var(
            env('ADMIN_ALLOW_WEAK_INITIAL_PASSWORD', false),
            FILTER_VALIDATE_BOOLEAN,
        );

        if ($login === '' && $password === '') {
            $this->command?->warn(
                'Начальный администратор не создан: задайте ADMIN_INITIAL_LOGIN и ADMIN_INITIAL_PASSWORD.',
            );

            return;
        }

        if ($login === '' || $password === '') {
            throw new RuntimeException(
                'ADMIN_INITIAL_LOGIN и ADMIN_INITIAL_PASSWORD должны быть заданы вместе.',
            );
        }

        if (mb_strlen($login) < 3 || mb_strlen($login) > 255) {
            throw new RuntimeException('ADMIN_INITIAL_LOGIN должен содержать от 3 до 255 символов.');
        }

        if (mb_strlen($password) < 7) {
            throw new RuntimeException('ADMIN_INITIAL_PASSWORD должен содержать минимум 7 символов.');
        }

        if (mb_strlen($password) < 12 && ! $allowWeakInitialPassword) {
            throw new RuntimeException('ADMIN_INITIAL_PASSWORD должен содержать минимум 12 символов.');
        }

        if ($name === '' || mb_strlen($name) > 255) {
            throw new RuntimeException('ADMIN_INITIAL_NAME должен содержать от 1 до 255 символов.');
        }

        User::firstOrCreate(['login' => $login], [
            'name' => $name,
            'role' => User::ROLE_ADMIN,
            'password' => Hash::make($password),
        ]);
    }
}
