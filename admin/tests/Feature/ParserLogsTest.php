<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\Concerns\CreatesParserSchema;
use Tests\TestCase;

class ParserLogsTest extends TestCase
{
    use CreatesParserSchema;
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();

        config()->set('parser.connection', 'sqlite');
        config()->set('app.timezone', 'Europe/Moscow');
        $this->createParserSchema();
    }

    public function test_log_pages_are_available_only_to_administrators(): void
    {
        $this->get(route('admin.logs.index'))
            ->assertRedirect(route('login'));
        $this->getJson(route('admin.datatable.logs'))
            ->assertUnauthorized();

        $viewer = User::factory()->create(['role' => User::ROLE_VIEWER]);

        $this->actingAs($viewer)
            ->get(route('admin.logs.index'))
            ->assertForbidden();
        $this->actingAs($viewer)
            ->getJson(route('admin.datatable.logs'))
            ->assertForbidden();
    }

    public function test_log_menu_and_page_are_visible_to_admin_but_not_viewer(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);
        $viewer = User::factory()->create(['role' => User::ROLE_VIEWER]);

        $this->actingAs($admin)
            ->get(route('admin.logs.index'))
            ->assertOk()
            ->assertSee('Журнал событий')
            ->assertSee('parser-logs');

        $this->actingAs($viewer)
            ->get(route('admin.professionals.index'))
            ->assertOk()
            ->assertDontSee(route('admin.logs.index'), false);
    }

    public function test_admin_receives_newest_logs_with_local_time_and_statuses(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);
        $this->seedLog([
            'started_at' => '2026-08-27 08:10:00',
            'finished_at' => '2026-08-27 08:11:00',
            'result' => 'success',
            'resource' => 'uslugi.yandex.ru',
        ]);
        $this->seedLog([
            'started_at' => '2026-08-27 09:15:30',
            'finished_at' => '2026-08-27 09:16:00',
            'result' => 'failure',
            'error_reason' => 'Источник вернул CAPTCHA',
            'resource' => 'uslugi.yandex.ru',
        ]);
        $this->seedLog([
            'started_at' => '2026-08-27 10:20:00',
            'result' => null,
            'resource' => 'uslugi.yandex.ru',
        ]);

        $response = $this->actingAs($admin)
            ->getJson(route('admin.datatable.logs', $this->dataTableParameters()))
            ->assertOk()
            ->assertJsonPath('recordsTotal', 3)
            ->assertJsonPath('recordsFiltered', 3)
            ->assertJsonPath('data.0.started_at', '27.08.2026 13:20:00')
            ->assertJsonPath('data.2.started_at', '27.08.2026 11:10:00');

        $this->assertStringContainsString('Выполняется', (string) $response->json('data.0.result'));
        $this->assertStringContainsString('Неуспех', (string) $response->json('data.1.result'));
        $this->assertSame('Источник вернул CAPTCHA', $response->json('data.1.error_reason'));
        $this->assertStringContainsString('Успех', (string) $response->json('data.2.result'));
        $this->assertSame('—', $response->json('data.2.error_reason'));
    }

    public function test_log_filters_use_local_calendar_dates_and_exact_resource(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);
        $matchingId = $this->seedLog([
            // 21:30 UTC уже относится к следующему календарному дню в Москве.
            'started_at' => '2026-08-27 21:30:00',
            'result' => 'failure',
            'error_reason' => 'Сетевая ошибка',
            'resource' => 'uslugi.yandex.ru',
        ]);
        $this->seedLog([
            'started_at' => '2026-08-27 20:30:00',
            'result' => 'failure',
            'resource' => 'uslugi.yandex.ru',
        ]);
        $this->seedLog([
            'started_at' => '2026-08-28 08:00:00',
            'result' => 'failure',
            'resource' => 'example.test',
        ]);
        $this->seedLog([
            'started_at' => '2026-08-28 08:00:00',
            'result' => 'success',
            'resource' => 'uslugi.yandex.ru',
        ]);

        $parameters = array_merge($this->dataTableParameters(), [
            'result' => 'failure',
            'resource' => 'uslugi.yandex.ru',
            'started_from' => '2026-08-28',
            'started_to' => '2026-08-28',
        ]);

        $this->actingAs($admin)
            ->getJson(route('admin.datatable.logs', $parameters))
            ->assertOk()
            ->assertJsonPath('recordsTotal', 1)
            ->assertJsonPath('recordsFiltered', 1)
            ->assertJsonPath('data.0.id', $matchingId);
    }

    public function test_log_error_and_resource_are_escaped_while_status_badge_is_fixed(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);
        $this->seedLog([
            'result' => 'failure',
            'error_reason' => '<script>alert(1)</script>',
            'resource' => '<img src=x onerror=alert(2)>',
        ]);

        $response = $this->actingAs($admin)
            ->getJson(route('admin.datatable.logs', $this->dataTableParameters()))
            ->assertOk();

        $this->assertStringNotContainsString('<script>', (string) $response->getContent());
        $this->assertStringNotContainsString('<img src=x', (string) $response->getContent());
        $this->assertStringContainsString('&lt;script&gt;', (string) $response->json('data.0.error_reason'));
        $this->assertStringContainsString('&lt;img', (string) $response->json('data.0.resource'));
        $this->assertStringContainsString('<span class="badge badge-danger">', (string) $response->json('data.0.result'));
    }

    public function test_invalid_log_filters_are_rejected(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);

        $this->actingAs($admin)
            ->getJson(route('admin.datatable.logs', [
                ...$this->dataTableParameters(),
                'result' => 'unknown',
                'started_from' => '2026-08-29',
                'started_to' => '2026-08-28',
            ]))
            ->assertUnprocessable()
            ->assertJsonValidationErrors(['result', 'started_to']);
    }

    /**
     * @param  array<string, mixed>  $overrides
     */
    private function seedLog(array $overrides = []): int
    {
        return (int) DB::connection($this->parserConnection())->table('logs')->insertGetId(array_merge([
            'started_at' => '2026-08-27 09:00:00',
            'finished_at' => null,
            'result' => null,
            'error_reason' => null,
            'resource' => 'uslugi.yandex.ru',
        ], $overrides));
    }

    /**
     * @return array<string, mixed>
     */
    private function dataTableParameters(): array
    {
        return [
            'draw' => 1,
            'start' => 0,
            'length' => 25,
            'order' => [['column' => 0, 'dir' => 'desc']],
            'columns' => [
                ['data' => 'started_at', 'name' => 'started_at', 'searchable' => 'false', 'orderable' => 'true'],
                ['data' => 'result', 'name' => 'result', 'searchable' => 'false', 'orderable' => 'true'],
                ['data' => 'error_reason', 'name' => 'error_reason', 'searchable' => 'false', 'orderable' => 'false'],
                ['data' => 'resource', 'name' => 'resource', 'searchable' => 'false', 'orderable' => 'true'],
            ],
        ];
    }

    private function parserConnection(): string
    {
        return (string) config('parser.connection');
    }
}
