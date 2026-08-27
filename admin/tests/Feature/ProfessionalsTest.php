<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\Concerns\CreatesParserSchema;
use Tests\TestCase;

class ProfessionalsTest extends TestCase
{
    use CreatesParserSchema;
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        config()->set('parser.connection', 'sqlite');
        $this->createParserSchema();
    }

    public function test_guest_is_redirected_to_login(): void
    {
        $this->get('/cp/professionals')->assertRedirect(route('login'));
    }

    public function test_authenticated_user_can_view_registry_and_filtered_datatable(): void
    {
        $this->actingAs(User::factory()->create(['role' => User::ROLE_VIEWER]));
        [$professionalId, $categoryId] = $this->seedProfessional();

        $this->get('/cp/professionals')
            ->assertOk()
            ->assertSee('Спарсенные данные')
            ->assertSee('Сантехники');

        $response = $this->getJson(route('admin.datatable.professionals', [
            'category_id' => $categoryId,
            'city' => 'Москва',
            'search' => ['value' => 'Иван'],
            'draw' => 1,
            'start' => 0,
            'length' => 25,
        ]));

        $response->assertOk()
            ->assertJsonPath('recordsFiltered', 1)
            ->assertJsonPath('data.0.id', $professionalId);

        $this->assertStringNotContainsString('<script>', (string) $response->json('data.0.full_name'));
        $this->assertStringNotContainsString('+79991234567', (string) $response->getContent());
    }

    public function test_admin_can_filter_by_normalized_plaintext_phone(): void
    {
        $this->actingAs(User::factory()->create(['role' => User::ROLE_ADMIN]));
        [$professionalId] = $this->seedProfessional();

        $response = $this->getJson(route('admin.datatable.professionals', [
            'phone' => '8 (999) 123-45-67',
            'draw' => 1,
            'start' => 0,
            'length' => 25,
        ]));

        $response->assertOk()
            ->assertJsonPath('recordsFiltered', 1)
            ->assertJsonPath('data.0.id', $professionalId);

        $this->assertStringNotContainsString('+79991234567', (string) $response->getContent());
    }

    public function test_datatable_does_not_repeat_shared_search_with_column_rules(): void
    {
        $this->actingAs(User::factory()->create(['role' => User::ROLE_VIEWER]));
        [$professionalId] = $this->seedProfessional();

        $columns = [
            [
                'data' => 'full_name',
                'name' => 'full_name',
                'searchable' => 'true',
                'orderable' => 'true',
                'search' => ['value' => '', 'regex' => 'false'],
            ],
            [
                'data' => 'location',
                'name' => 'city',
                'searchable' => 'false',
                'orderable' => 'false',
                'search' => ['value' => '', 'regex' => 'false'],
            ],
        ];

        foreach (['Москва', 'worker-1'] as $search) {
            $this->getJson(route('admin.datatable.professionals', [
                'draw' => 1,
                'start' => 0,
                'length' => 25,
                'search' => ['value' => $search, 'regex' => 'false'],
                'columns' => $columns,
            ]))
                ->assertOk()
                ->assertJsonPath('recordsFiltered', 1)
                ->assertJsonPath('data.0.id', $professionalId);
        }
    }

    public function test_only_admin_can_reveal_phone_and_access_is_audited(): void
    {
        [$professionalId] = $this->seedProfessional();
        $viewer = User::factory()->create(['role' => User::ROLE_VIEWER]);
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);

        $this->actingAs($viewer)
            ->postJson(route('admin.professionals.phone', $professionalId))
            ->assertForbidden();

        $this->actingAs($admin)
            ->postJson(route('admin.professionals.phone', $professionalId))
            ->assertOk()
            ->assertExactJson(['phone' => '+79991234567']);

        $this->assertDatabaseHas('phone_access_logs', [
            'user_id' => $admin->id,
            'professional_id' => $professionalId,
            'action' => 'reveal',
        ]);
    }

    public function test_invalid_plaintext_phone_is_not_returned_or_audited(): void
    {
        [$professionalId] = $this->seedProfessional(['phone' => 'not-a-phone']);
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);

        $this->actingAs($admin)
            ->postJson(route('admin.professionals.phone', $professionalId))
            ->assertUnprocessable()
            ->assertExactJson(['message' => 'Телефон недоступен или имеет неверный формат.']);

        $this->assertDatabaseMissing('phone_access_logs', [
            'user_id' => $admin->id,
            'professional_id' => $professionalId,
        ]);
    }

    public function test_unsafe_external_urls_are_not_rendered(): void
    {
        $this->actingAs(User::factory()->create(['role' => User::ROLE_ADMIN]));
        [$professionalId] = $this->seedProfessional([
            'profile_url' => 'javascript:alert(1)',
            'photo_url' => 'https://evil.example/avatar.jpg',
        ]);

        $this->get(route('admin.professionals.show', $professionalId))
            ->assertOk()
            ->assertDontSee('javascript:alert', false)
            ->assertDontSee('evil.example', false);
    }

    /**
     * @param  array<string, mixed>  $overrides
     * @return array{int, int}
     */
    private function seedProfessional(array $overrides = []): array
    {
        $now = '2026-08-26 12:00:00';
        $categoryId = DB::connection('sqlite')->table('categories')->insertGetId([
            'key' => 'plumbers',
            'name' => 'Сантехники',
            'created_at' => $now,
            'updated_at' => $now,
        ]);

        $professionalId = DB::connection('sqlite')->table('professionals')->insertGetId(array_merge([
            'source' => 'uslugi.yandex.ru',
            'source_profile_id' => 'worker-1',
            'profile_url' => 'https://uslugi.yandex.ru/profile/Ivan-1',
            'full_name' => '<script>alert(1)</script> Иван Петров',
            'phone' => '+79991234567',
            'phone_status' => 'published',
            'city' => 'Москва',
            'region' => 'Москва',
            'country' => 'Россия',
            'age' => 38,
            'age_as_of' => '2026-08-26',
            'gender' => 'male',
            'experience_code' => 11,
            'experience_text' => 'Более 10 лет',
            'photo_url' => 'https://avatars.mds.yandex.net/get-ydo/1',
            'account_type' => 'person',
            'content_hash' => str_repeat('a', 64),
            'parser_version' => '1.0.0',
            'first_seen_at' => $now,
            'last_seen_at' => $now,
            'last_scraped_at' => $now,
        ], $overrides));

        DB::connection('sqlite')->table('professional_categories')->insert([
            'professional_id' => $professionalId,
            'category_id' => $categoryId,
            'first_seen_at' => $now,
            'last_seen_at' => $now,
        ]);

        return [$professionalId, $categoryId];
    }
}
