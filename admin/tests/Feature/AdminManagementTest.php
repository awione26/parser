<?php

namespace Tests\Feature;

use App\Models\User;
use App\Repositories\UserRepository;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Hash;
use Tests\TestCase;

class AdminManagementTest extends TestCase
{
    use RefreshDatabase;

    private const string PASSWORD = 'Correct Horse Battery 123!';

    private const string NEW_PASSWORD = 'Another Secure Password 456!';

    public function test_only_administrators_can_open_management_pages(): void
    {
        $viewer = $this->createUser('viewer', User::ROLE_VIEWER);
        $target = $this->createUser('target', User::ROLE_ADMIN);

        $this->actingAs($viewer)->get('/cp/administrators')->assertForbidden();
        $this->actingAs($viewer)->get('/cp/administrators/create')->assertForbidden();
        $this->actingAs($viewer)->get("/cp/administrators/{$target->id}/edit")->assertForbidden();
        $this->actingAs($viewer)->post('/cp/administrators', $this->validPayload('created'))
            ->assertForbidden();
        $this->actingAs($viewer)->put("/cp/administrators/{$target->id}", [
            ...$this->validPayload('target'),
        ])->assertForbidden();
        $this->actingAs($viewer)->delete("/cp/administrators/{$target->id}")
            ->assertForbidden();
    }

    public function test_administrator_list_is_server_rendered_and_paginated(): void
    {
        $admin = $this->createUser('administrator', User::ROLE_ADMIN);
        $viewer = $this->createUser('report-viewer', User::ROLE_VIEWER);

        $this->actingAs($admin)
            ->get('/cp/administrators')
            ->assertOk()
            ->assertSee($admin->login)
            ->assertSee($viewer->login)
            ->assertSee('Администраторы');
    }

    public function test_administrator_can_create_a_user_with_supported_role(): void
    {
        $admin = $this->createUser('administrator', User::ROLE_ADMIN);

        $this->actingAs($admin)
            ->post('/cp/administrators', $this->validPayload(' NEW-VIEWER '))
            ->assertRedirect(route('admin.admin.index'));

        $created = User::query()->where('login', 'new-viewer')->firstOrFail();

        $this->assertSame(User::ROLE_VIEWER, $created->role);
        $this->assertTrue(Hash::check(self::PASSWORD, $created->password));
    }

    public function test_create_requires_a_twelve_character_confirmed_password_and_known_role(): void
    {
        $admin = $this->createUser('administrator', User::ROLE_ADMIN);

        $this->actingAs($admin)->post('/cp/administrators', [
            'name' => 'Новый пользователь',
            'login' => 'new-user',
            'role' => 'moderator',
            'password' => 'short',
            'password_confirmation' => 'different',
        ])->assertSessionHasErrors(['role', 'password']);

        $this->assertDatabaseMissing('users', ['login' => 'new-user']);
    }

    public function test_administrator_can_update_role_and_password(): void
    {
        $admin = $this->createUser('administrator', User::ROLE_ADMIN);
        $target = $this->createUser('target', User::ROLE_VIEWER);

        $this->actingAs($admin)->put("/cp/administrators/{$target->id}", [
            'name' => 'Обновлённый пользователь',
            'login' => 'UPDATED-TARGET',
            'role' => User::ROLE_ADMIN,
            'password' => self::NEW_PASSWORD,
            'password_confirmation' => self::NEW_PASSWORD,
        ])->assertRedirect(route('admin.admin.index'));

        $target->refresh();
        $this->assertSame('updated-target', $target->login);
        $this->assertSame(User::ROLE_ADMIN, $target->role);
        $this->assertTrue(Hash::check(self::NEW_PASSWORD, $target->password));
    }

    public function test_last_administrator_cannot_be_demoted(): void
    {
        $admin = $this->createUser('administrator', User::ROLE_ADMIN);

        $this->actingAs($admin)
            ->from("/cp/administrators/{$admin->id}/edit")
            ->put("/cp/administrators/{$admin->id}", [
                'name' => $admin->name,
                'login' => $admin->login,
                'role' => User::ROLE_VIEWER,
                'password' => '',
                'password_confirmation' => '',
            ])
            ->assertRedirect("/cp/administrators/{$admin->id}/edit")
            ->assertSessionHasErrors('role');

        $this->assertDatabaseHas('users', [
            'id' => $admin->id,
            'role' => User::ROLE_ADMIN,
        ]);
    }

    public function test_administrator_can_be_demoted_when_another_admin_remains(): void
    {
        $actor = $this->createUser('actor', User::ROLE_ADMIN);
        $target = $this->createUser('target', User::ROLE_ADMIN);

        $this->actingAs($actor)->put("/cp/administrators/{$target->id}", [
            'name' => $target->name,
            'login' => $target->login,
            'role' => User::ROLE_VIEWER,
            'password' => '',
            'password_confirmation' => '',
        ])->assertRedirect(route('admin.admin.index'));

        $this->assertDatabaseHas('users', [
            'id' => $target->id,
            'role' => User::ROLE_VIEWER,
        ]);
    }

    public function test_administrator_cannot_delete_own_account(): void
    {
        $admin = $this->createUser('administrator', User::ROLE_ADMIN);

        $this->actingAs($admin)
            ->delete("/cp/administrators/{$admin->id}")
            ->assertRedirect(route('admin.admin.index'))
            ->assertSessionHas('error', UserRepository::SELF_DELETE_MESSAGE);

        $this->assertDatabaseHas('users', ['id' => $admin->id]);
    }

    public function test_last_administrator_guard_is_enforced_inside_repository_transaction(): void
    {
        $admin = $this->createUser('administrator', User::ROLE_ADMIN);
        $viewer = $this->createUser('viewer', User::ROLE_VIEWER);

        $this->expectException(DomainException::class);
        $this->expectExceptionMessage(UserRepository::LAST_ADMIN_DELETE_MESSAGE);

        $this->app->make(UserRepository::class)
            ->deleteSafely($admin->id, $viewer->id);
    }

    public function test_administrator_can_delete_another_account(): void
    {
        $admin = $this->createUser('administrator', User::ROLE_ADMIN);
        $viewer = $this->createUser('viewer', User::ROLE_VIEWER);

        $this->actingAs($admin)
            ->delete("/cp/administrators/{$viewer->id}")
            ->assertRedirect(route('admin.admin.index'));

        $this->assertDatabaseMissing('users', ['id' => $viewer->id]);
    }

    /**
     * @return array<string, string>
     */
    private function validPayload(string $login): array
    {
        return [
            'name' => 'Новый пользователь',
            'login' => $login,
            'role' => User::ROLE_VIEWER,
            'password' => self::PASSWORD,
            'password_confirmation' => self::PASSWORD,
        ];
    }

    private function createUser(string $login, string $role): User
    {
        return User::query()->create([
            'name' => ucfirst($login),
            'login' => $login,
            'role' => $role,
            'password' => Hash::make(self::PASSWORD),
        ]);
    }
}
