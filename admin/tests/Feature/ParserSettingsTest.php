<?php

namespace Tests\Feature;

use App\Models\User;
use App\Support\ParserSettings;
use Carbon\CarbonImmutable;
use Illuminate\Database\Query\Builder;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\Concerns\CreatesParserSchema;
use Tests\TestCase;

class ParserSettingsTest extends TestCase
{
    use CreatesParserSchema;
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();

        config()->set('parser.connection', 'sqlite');
        $this->createParserSchema();
    }

    protected function tearDown(): void
    {
        CarbonImmutable::setTestNow();

        parent::tearDown();
    }

    public function test_settings_are_available_only_to_administrators(): void
    {
        $payload = $this->validPayload();

        $this->get(route('admin.settings.index'))
            ->assertRedirect(route('login'));
        $this->put(route('admin.settings.update'), $payload)
            ->assertRedirect(route('login'));

        $viewer = User::factory()->create(['role' => User::ROLE_VIEWER]);

        $this->actingAs($viewer)
            ->get(route('admin.settings.index'))
            ->assertForbidden();
        $this->actingAs($viewer)
            ->put(route('admin.settings.update'), $payload)
            ->assertForbidden();

        $this->assertSame(0, $this->settingsTable()->count());
    }

    public function test_admin_sees_fixed_settings_form_and_viewer_does_not_see_menu_link(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);
        $viewer = User::factory()->create(['role' => User::ROLE_VIEWER]);
        $this->settingsTable()->insert([
            'key' => 'UNSUPPORTED_PRIVATE_KEY',
            'value' => 'must-not-be-rendered',
            'created_at' => '2026-08-27 09:00:00',
            'updated_at' => '2026-08-27 09:00:00',
        ]);

        $response = $this->actingAs($admin)
            ->get(route('admin.settings.index'))
            ->assertOk()
            ->assertSee('Настройки')
            ->assertSee('Сохранить настройки')
            ->assertSee('письменного разрешения Яндекса')
            ->assertDontSee('YANDEX_OPERATOR_PERMISSION')
            ->assertDontSee('YANDEX_PHONE_PERMISSION')
            ->assertDontSee('UNSUPPORTED_PRIVATE_KEY')
            ->assertDontSee('must-not-be-rendered');

        foreach (ParserSettings::keys() as $key) {
            $response->assertSee('name="'.$key.'"', false);
        }

        $this->actingAs($viewer)
            ->get(route('admin.professionals.index'))
            ->assertOk()
            ->assertDontSee(route('admin.settings.index'), false);
    }

    public function test_form_uses_database_values_and_defaults_for_missing_rows(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);
        $this->settingsTable()->insert([
            'key' => 'SCRAPER_GEO',
            'value' => '2-saint-petersburg',
            'created_at' => '2026-08-27 09:00:00',
            'updated_at' => '2026-08-27 09:00:00',
        ]);

        $this->actingAs($admin)
            ->get(route('admin.settings.index'))
            ->assertOk()
            ->assertSee('value="2-saint-petersburg"', false)
            ->assertSee('value="'.ParserSettings::DEFAULTS['SCRAPER_USER_AGENT'].'"', false);
    }

    public function test_admin_atomically_upserts_only_whitelisted_settings(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);
        $this->settingsTable()->insert([
            'key' => 'SCRAPER_GEO',
            'value' => '213-moscow',
            'created_at' => '2026-08-20 10:00:00',
            'updated_at' => '2026-08-20 10:00:00',
        ]);
        CarbonImmutable::setTestNow(CarbonImmutable::parse('2026-08-28 12:34:56', 'UTC'));

        $payload = [
            ...$this->validPayload(),
            'SCRAPER_GEO' => '2-saint-petersburg',
            'SCRAPER_RESPECT_ROBOTS' => '0',
            'SCRAPER_MIN_DELAY_SECONDS' => '1.25',
            'SCRAPER_MAX_DELAY_SECONDS' => '4.75',
            'SCRAPER_MAX_RETRIES' => '7',
            'SCRAPER_COLLECT_PHONE' => '1',
            'SCRAPER_PHONE_HEADLESS' => '0',
            'SCRAPER_INCLUDE_ORGANIZATIONS' => '1',
            'UNSUPPORTED_SETTING' => 'must-not-be-created',
        ];

        $this->actingAs($admin)
            ->put(route('admin.settings.update'), $payload)
            ->assertRedirect(route('admin.settings.index'))
            ->assertSessionHas('success');

        $this->assertSame(count(ParserSettings::DEFAULTS), $this->settingsTable()->count());
        $this->assertFalse($this->settingsTable()->where('key', 'UNSUPPORTED_SETTING')->exists());
        $this->assertSame('2-saint-petersburg', $this->storedValue('SCRAPER_GEO'));
        $this->assertSame('false', $this->storedValue('SCRAPER_RESPECT_ROBOTS'));
        $this->assertSame('1.25', $this->storedValue('SCRAPER_MIN_DELAY_SECONDS'));
        $this->assertSame('4.75', $this->storedValue('SCRAPER_MAX_DELAY_SECONDS'));
        $this->assertSame('7', $this->storedValue('SCRAPER_MAX_RETRIES'));
        $this->assertSame('true', $this->storedValue('SCRAPER_COLLECT_PHONE'));
        $this->assertSame('false', $this->storedValue('SCRAPER_PHONE_HEADLESS'));
        $this->assertSame('true', $this->storedValue('SCRAPER_INCLUDE_ORGANIZATIONS'));

        $geo = $this->settingsTable()->where('key', 'SCRAPER_GEO')->first();
        $this->assertSame('2026-08-20 10:00:00', $geo->created_at);
        $this->assertSame('2026-08-28 12:34:56', $geo->updated_at);
        $this->assertSame(
            '2026-08-28 12:34:56',
            $this->settingsTable()->where('key', 'SCRAPER_USER_AGENT')->value('created_at'),
        );
    }

    public function test_invalid_geo_user_agent_numbers_retries_and_booleans_are_rejected(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);
        $invalidCases = [
            ['SCRAPER_GEO', '/evil.example'],
            ['SCRAPER_GEO', '213-Moscow'],
            ['SCRAPER_USER_AGENT', 'ab'],
            ['SCRAPER_USER_AGENT', str_repeat('a', 513)],
            ['SCRAPER_USER_AGENT', "ValidAgent/1.0\r\nX-Injected: yes"],
            ['SCRAPER_USER_AGENT', "ValidAgent/1.0\x7F"],
            ['SCRAPER_USER_AGENT', 'Парсер/1.0'],
            ['SCRAPER_MIN_DELAY_SECONDS', '-0.1'],
            ['SCRAPER_MIN_DELAY_SECONDS', '1e309'],
            ['SCRAPER_MIN_DELAY_SECONDS', '3600.01'],
            ['SCRAPER_MAX_DELAY_SECONDS', '3600.01'],
            ['SCRAPER_TIMEOUT_SECONDS', '0'],
            ['SCRAPER_TIMEOUT_SECONDS', '300.01'],
            ['SCRAPER_PHONE_TIMEOUT_SECONDS', 'INF'],
            ['SCRAPER_PHONE_TIMEOUT_SECONDS', '300.01'],
            ['SCRAPER_MAX_RETRIES', '-1'],
            ['SCRAPER_MAX_RETRIES', '1.5'],
            ['SCRAPER_MAX_RETRIES', '11'],
            ['SCRAPER_RESPECT_ROBOTS', 'sometimes'],
        ];

        foreach ($invalidCases as [$field, $value]) {
            $this->actingAs($admin)
                ->from(route('admin.settings.index'))
                ->put(route('admin.settings.update'), [
                    ...$this->validPayload(),
                    $field => $value,
                ])
                ->assertRedirect(route('admin.settings.index'))
                ->assertSessionHasErrors($field);

            $this->assertSame(0, $this->settingsTable()->count());
        }
    }

    public function test_maximum_delay_must_not_be_less_than_minimum_delay(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);

        $this->actingAs($admin)
            ->from(route('admin.settings.index'))
            ->put(route('admin.settings.update'), [
                ...$this->validPayload(),
                'SCRAPER_MIN_DELAY_SECONDS' => '5.1',
                'SCRAPER_MAX_DELAY_SECONDS' => '5.0',
            ])
            ->assertRedirect(route('admin.settings.index'))
            ->assertSessionHasErrors('SCRAPER_MAX_DELAY_SECONDS');

        $this->assertSame(0, $this->settingsTable()->count());
    }

    /**
     * @return array<string, string>
     */
    private function validPayload(): array
    {
        return [
            'SCRAPER_USER_AGENT' => ParserSettings::DEFAULTS['SCRAPER_USER_AGENT'],
            'SCRAPER_GEO' => '213-moscow',
            'SCRAPER_RESPECT_ROBOTS' => '1',
            'SCRAPER_MIN_DELAY_SECONDS' => '2.0',
            'SCRAPER_MAX_DELAY_SECONDS' => '5.0',
            'SCRAPER_TIMEOUT_SECONDS' => '30.0',
            'SCRAPER_MAX_RETRIES' => '3',
            'SCRAPER_COLLECT_PHONE' => '0',
            'SCRAPER_PHONE_HEADLESS' => '1',
            'SCRAPER_PHONE_TIMEOUT_SECONDS' => '15.0',
            'SCRAPER_INCLUDE_ORGANIZATIONS' => '0',
        ];
    }

    private function settingsTable(): Builder
    {
        return DB::connection((string) config('parser.connection'))->table('settings');
    }

    private function storedValue(string $key): string
    {
        return (string) $this->settingsTable()->where('key', $key)->value('value');
    }
}
