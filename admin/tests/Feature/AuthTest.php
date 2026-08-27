<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Hash;
use Illuminate\Support\Facades\RateLimiter;
use Tests\TestCase;

class AuthTest extends TestCase
{
    use RefreshDatabase;

    private const string PASSWORD = 'Correct Horse Battery 123!';

    protected function tearDown(): void
    {
        RateLimiter::clear('administrator|127.0.0.1');

        parent::tearDown();
    }

    public function test_login_page_is_available_to_guests(): void
    {
        $this->get('/cp/login')
            ->assertOk()
            ->assertSee('Введите логин и пароль');
    }

    public function test_valid_credentials_authenticate_and_regenerate_session(): void
    {
        $user = $this->createUser('administrator');
        $this->withSession(['marker' => 'before-login']);
        $oldSessionId = session()->getId();

        $response = $this->post('/cp/login', [
            'login' => '  ADMINISTRATOR  ',
            'password' => self::PASSWORD,
            'remember' => '1',
        ]);

        $response->assertRedirect(route('admin.dashboard.index'));
        $this->assertAuthenticatedAs($user);
        $this->assertNotSame($oldSessionId, session()->getId());
    }

    public function test_invalid_credentials_are_rate_limited_by_normalized_login_and_ip(): void
    {
        $key = 'administrator|127.0.0.1';
        RateLimiter::clear($key);

        for ($attempt = 0; $attempt < 5; $attempt++) {
            $this->post('/cp/login', [
                'login' => $attempt % 2 === 0 ? 'Administrator' : 'ADMINISTRATOR',
                'password' => 'wrong-password',
            ])->assertSessionHasErrors('login');
        }

        $this->assertTrue(RateLimiter::tooManyAttempts($key, 5));

        $this->post('/cp/login', [
            'login' => 'administrator',
            'password' => 'wrong-password',
        ])
            ->assertSessionHasErrors('login');

        $this->assertGuest();
    }

    public function test_successful_login_clears_previous_failed_attempts(): void
    {
        $this->createUser('administrator');
        $key = 'administrator|127.0.0.1';
        RateLimiter::hit($key, 60);

        $this->post('/cp/login', [
            'login' => 'administrator',
            'password' => self::PASSWORD,
        ])->assertRedirect(route('admin.dashboard.index'));

        $this->assertSame(0, RateLimiter::attempts($key));
    }

    public function test_logout_invalidates_session_and_requires_post(): void
    {
        $user = $this->createUser('administrator');

        $response = $this
            ->actingAs($user)
            ->withSession(['private-value' => 'must-disappear'])
            ->post('/cp/logout');

        $response
            ->assertRedirect(route('login'))
            ->assertSessionMissing('private-value');
        $this->assertGuest();
        $this->get('/cp/logout')->assertMethodNotAllowed();
    }

    private function createUser(string $login): User
    {
        return User::query()->create([
            'name' => 'Администратор',
            'login' => $login,
            'role' => User::ROLE_ADMIN,
            'password' => Hash::make(self::PASSWORD),
        ]);
    }
}
