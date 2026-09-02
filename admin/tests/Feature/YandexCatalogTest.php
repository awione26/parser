<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Database\Connection;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\Concerns\CreatesParserSchema;
use Tests\TestCase;

class YandexCatalogTest extends TestCase
{
    use CreatesParserSchema;
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();

        config()->set('parser.connection', 'sqlite');
        $this->createParserSchema();
    }

    public function test_catalog_is_available_only_to_administrators_and_hidden_from_viewers(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);
        $viewer = User::factory()->create(['role' => User::ROLE_VIEWER]);

        $this->get(route('admin.catalog.index'))
            ->assertRedirect(route('login'));
        $this->getJson(route('admin.datatable.catalog', $this->dataTableParameters()))
            ->assertUnauthorized();

        $this->actingAs($viewer)
            ->get(route('admin.catalog.index'))
            ->assertForbidden();
        $this->actingAs($viewer)
            ->getJson(route('admin.datatable.catalog', $this->dataTableParameters()))
            ->assertForbidden();

        $this->actingAs($viewer)
            ->get(route('admin.professionals.index'))
            ->assertOk()
            ->assertDontSee(route('admin.catalog.index'), false);

        $this->actingAs($admin)
            ->get(route('admin.catalog.index'))
            ->assertOk()
            ->assertSee('Яндекс.Каталог')
            ->assertSee('yandex-catalog');
    }

    public function test_catalog_renders_hierarchy_escapes_data_and_allows_only_canonical_urls(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);
        $ids = $this->seedHierarchy();

        $page = $this->actingAs($admin)
            ->get(route('admin.catalog.index'))
            ->assertOk();
        $response = $this->actingAs($admin)
            ->getJson(route('admin.datatable.catalog', $this->dataTableParameters()))
            ->assertOk()
            ->assertJsonPath('recordsTotal', 3)
            ->assertJsonPath('recordsFiltered', 3)
            ->assertJsonCount(3, 'data');

        $content = collect($response->json('data'))
            ->flatMap(static fn (array $row): array => array_values($row))
            ->implode('');
        $this->assertStringContainsString('Сантехники', $content);
        $this->assertStringContainsString('Сантехнические работы', $content);
        $this->assertStringContainsString('&lt;script&gt;Монтаж смесителя&lt;/script&gt;', $content);
        $this->assertStringNotContainsString('<script>Монтаж смесителя</script>', $content);
        $this->assertStringContainsString('https://uslugi.yandex.ru/category/remont/santehnika--101', $content);
        $this->assertStringContainsString('https://uslugi.yandex.ru/213-moscow/category/remont/smesitel--303', $content);
        $this->assertStringContainsString('rel="noopener noreferrer nofollow"', $content);
        $this->assertStringNotContainsString('javascript:alert(1)', $content);
        $this->assertStringContainsString('В парсинге', $content);
        $this->assertSame($ids['category'], $page->viewData('groups')->first()->id);
    }

    public function test_server_side_filters_and_fixed_pagination_are_applied(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);
        $ids = $this->seedHierarchy();

        $filtered = $this->actingAs($admin)
            ->getJson(route('admin.datatable.catalog', [
                ...$this->dataTableParameters(),
                'group' => (string) $ids['category'],
                'status' => 'confirmed',
                'has_id' => '1',
                'used_for_parsing' => '1',
            ]))
            ->assertOk()
            ->assertJsonPath('recordsTotal', 1)
            ->assertJsonCount(1, 'data');
        $this->assertStringContainsString(
            '&lt;script&gt;Монтаж смесителя&lt;/script&gt;',
            (string) $filtered->json('data.0.service'),
        );

        $byRubricId = $this->actingAs($admin)
            ->getJson(route('admin.datatable.catalog', [
                ...$this->dataTableParameters(),
                'q' => '101',
                'used_for_parsing' => '0',
            ]))
            ->assertOk()
            ->assertJsonPath('recordsTotal', 1);
        $this->assertStringContainsString('Сантехники', (string) $byRubricId->json('data.0.group'));
        $this->assertStringNotContainsString(
            '&lt;script&gt;Монтаж смесителя&lt;/script&gt;',
            (string) $byRubricId->json('data.0.service'),
        );

        $categoryId = $this->insertCategory('pagination', 'Пагинация');
        for ($number = 1; $number <= 51; $number++) {
            $serviceId = $this->insertTaxonomy('yandex_services', [
                'external_number_id' => 1000 + $number,
                'name' => "Услуга {$number}",
                'slug' => "service-{$number}",
                'verification_status' => 'legacy',
            ]);
            $this->parserDb()->table('category_yandex_services')->insert([
                'category_id' => $categoryId,
                'service_id' => $serviceId,
                'sort_order' => $number * 10,
            ]);
        }

        $page = $this->actingAs($admin)
            ->getJson(route('admin.datatable.catalog', [
                ...$this->dataTableParameters(),
                'group' => $categoryId,
            ]))
            ->assertOk()
            ->assertJsonPath('recordsTotal', 51)
            ->assertJsonPath('recordsFiltered', 51)
            ->assertJsonCount(25, 'data');

        $this->actingAs($admin)
            ->getJson(route('admin.datatable.catalog', [
                ...$this->dataTableParameters(),
                'start' => 50,
                'group' => $categoryId,
            ]))
            ->assertOk()
            ->assertJsonPath('recordsTotal', 51)
            ->assertJsonCount(1, 'data');
    }

    public function test_invalid_catalog_filters_are_rejected(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);

        $this->actingAs($admin)
            ->getJson(route('admin.datatable.catalog', [
                ...$this->dataTableParameters(),
                'q' => "bad\x00query",
                'group' => '999999',
                'status' => 'verified',
                'has_id' => 'yes',
                'used_for_parsing' => 'all',
            ]))
            ->assertUnprocessable()
            ->assertJsonValidationErrors([
                'q',
                'group',
                'status',
                'has_id',
                'used_for_parsing',
            ]);
    }

    public function test_invalid_datatable_pagination_and_column_contract_are_rejected(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);
        $parameters = $this->dataTableParameters();
        $parameters['start'] = -1;
        $parameters['length'] = -1;
        $parameters['columns'][0]['name'] = 'target_source_url';
        $parameters['columns'][1]['searchable'] = 'true';
        $parameters['columns'][1]['search']['value'] = 'forged search';
        $parameters['order'][0]['column'] = 7;

        $this->actingAs($admin)
            ->getJson(route('admin.datatable.catalog', $parameters))
            ->assertUnprocessable()
            ->assertJsonValidationErrors([
                'start',
                'length',
                'columns.0.name',
                'columns.1.searchable',
                'order.0.column',
            ]);
    }

    public function test_legacy_categories_section_is_removed(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);

        $this->actingAs($admin)
            ->get('/cp/categories')
            ->assertNotFound();

        $this->actingAs($admin)
            ->get(route('admin.catalog.index'))
            ->assertOk()
            ->assertDontSee('/cp/categories', false);
    }

    public function test_admin_can_atomically_disable_and_enable_a_canonical_catalog_target(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);
        $ids = $this->seedHierarchy();
        $route = route('admin.catalog.parsing', [
            'category' => $ids['category'],
            'taxonomyLevel' => 'service',
            'catalogNode' => $ids['service'],
        ]);

        $this->actingAs($admin)
            ->patch($route, ['is_active' => '0'])
            ->assertRedirect()
            ->assertSessionHas('success');

        $this->assertDatabaseHas('parser_category_targets', [
            'category_id' => $ids['category'],
            'source_rubric_number_id' => 303,
            'is_active' => false,
        ], 'sqlite');
        $configuration = $this->parserDb()->table('parser_categories')
            ->where('category_id', $ids['category'])
            ->first();
        $this->assertNotNull($configuration);
        $this->assertSame(0, (int) $configuration->is_active);
        $this->assertSame([], json_decode((string) $configuration->seed_paths, true));

        $this->actingAs($admin)
            ->patch($route, ['is_active' => '1'])
            ->assertRedirect()
            ->assertSessionHas('success');

        $this->assertDatabaseHas('parser_category_targets', [
            'category_id' => $ids['category'],
            'taxonomy_level' => 'service',
            'source_rubric_number_id' => 303,
            'relative_path' => 'remont/smesitel--303',
            'is_active' => true,
        ], 'sqlite');
        $configuration = $this->parserDb()->table('parser_categories')
            ->where('category_id', $ids['category'])
            ->first();
        $this->assertNotNull($configuration);
        $this->assertSame(1, (int) $configuration->is_active);
        $this->assertSame(
            ['remont/smesitel--303'],
            json_decode((string) $configuration->seed_paths, true),
        );
    }

    public function test_enabling_one_target_does_not_restore_stale_targets_from_disabled_config(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);
        $ids = $this->seedHierarchy();
        $now = '2026-09-02 10:00:00';

        $this->parserDb()->table('parser_category_targets')->insert([
            'category_id' => $ids['category'],
            'taxonomy_level' => 'occupation',
            'source_rubric_number_id' => 101,
            'relative_path' => 'remont/santehnika--101',
            'is_active' => true,
            'sort_order' => 20,
            'created_at' => $now,
            'updated_at' => $now,
        ]);
        $this->parserDb()->table('parser_categories')
            ->where('category_id', $ids['category'])
            ->update([
                'seed_paths' => json_encode([
                    'remont/smesitel--303',
                    'remont/santehnika--101',
                ]),
                'is_active' => false,
            ]);

        $this->actingAs($admin)
            ->patch(route('admin.catalog.parsing', [
                'category' => $ids['category'],
                'taxonomyLevel' => 'service',
                'catalogNode' => $ids['service'],
            ]), ['is_active' => '1'])
            ->assertRedirect()
            ->assertSessionHas('success');

        $this->assertDatabaseHas('parser_category_targets', [
            'category_id' => $ids['category'],
            'source_rubric_number_id' => 303,
            'is_active' => true,
        ], 'sqlite');
        $this->assertDatabaseHas('parser_category_targets', [
            'category_id' => $ids['category'],
            'source_rubric_number_id' => 101,
            'is_active' => false,
        ], 'sqlite');
        $configuration = $this->parserDb()->table('parser_categories')
            ->where('category_id', $ids['category'])
            ->first();
        $this->assertNotNull($configuration);
        $this->assertSame(
            ['remont/smesitel--303'],
            json_decode((string) $configuration->seed_paths, true),
        );
    }

    public function test_catalog_target_update_requires_admin_link_canonical_url_and_unique_rubric(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);
        $viewer = User::factory()->create(['role' => User::ROLE_VIEWER]);
        $ids = $this->seedHierarchy();
        $serviceRoute = route('admin.catalog.parsing', [
            'category' => $ids['category'],
            'taxonomyLevel' => 'service',
            'catalogNode' => $ids['service'],
        ]);

        $this->patch($serviceRoute, ['is_active' => '0'])
            ->assertRedirect(route('login'));
        $this->actingAs($viewer)
            ->patch($serviceRoute, ['is_active' => '0'])
            ->assertForbidden();

        $unsafeRoute = route('admin.catalog.parsing', [
            'category' => $ids['category'],
            'taxonomyLevel' => 'specialization',
            'catalogNode' => $ids['specialization'],
        ]);
        $this->actingAs($admin)
            ->patchJson($unsafeRoute, ['is_active' => true])
            ->assertUnprocessable()
            ->assertJsonValidationErrors('catalog');

        $this->parserDb()->table('yandex_specializations')
            ->where('id', $ids['specialization'])
            ->update([
                'source_url' => 'https://uslugi.yandex.ru/category/santehnicheskie-raboty--202',
            ]);
        $this->actingAs($admin)
            ->patchJson($unsafeRoute, ['is_active' => true])
            ->assertUnprocessable()
            ->assertJsonValidationErrors('catalog');

        $otherCategory = $this->insertCategory('electricians', 'Электрики');
        $this->actingAs($admin)
            ->patchJson(route('admin.catalog.parsing', [
                'category' => $otherCategory,
                'taxonomyLevel' => 'service',
                'catalogNode' => $ids['service'],
            ]), ['is_active' => true])
            ->assertNotFound();

        $this->parserDb()->table('parser_categories')->insert([
            'category_id' => $otherCategory,
            'seed_paths' => json_encode(['remont/santehnika--101']),
            'is_active' => true,
            'sort_order' => 20,
            'created_at' => '2026-09-01 10:00:00',
            'updated_at' => '2026-09-01 10:00:00',
        ]);
        $this->parserDb()->table('category_yandex_occupations')->insert([
            'category_id' => $otherCategory,
            'occupation_id' => $ids['occupation'],
            'sort_order' => 10,
        ]);
        $this->parserDb()->table('parser_category_targets')->insert([
            'category_id' => $otherCategory,
            'taxonomy_level' => 'occupation',
            'source_rubric_number_id' => 101,
            'relative_path' => 'remont/santehnika--101',
            'is_active' => true,
            'sort_order' => 10,
            'created_at' => '2026-09-01 10:00:00',
            'updated_at' => '2026-09-01 10:00:00',
        ]);

        $this->actingAs($admin)
            ->patchJson(route('admin.catalog.parsing', [
                'category' => $ids['category'],
                'taxonomyLevel' => 'occupation',
                'catalogNode' => $ids['occupation'],
            ]), ['is_active' => true])
            ->assertUnprocessable()
            ->assertJsonValidationErrors('catalog');
    }

    /**
     * Заполнить минимальную трёхуровневую таксономию для feature-тестов.
     *
     * @return array{category: int, occupation: int, specialization: int, service: int}
     */
    private function seedHierarchy(): array
    {
        $categoryId = $this->insertCategory('plumbers', 'Сантехники');
        $occupationId = $this->insertTaxonomy('yandex_occupations', [
            'external_id_raw' => '/remont-i-stroitel_stvo',
            'external_number_id' => 101,
            'slug' => '/remont/santehnika',
            'name' => 'Ремонт и строительство',
            'source_url' => 'https://uslugi.yandex.ru/category/remont/santehnika--101',
            'verification_status' => 'confirmed',
        ]);
        $specializationId = $this->insertTaxonomy('yandex_specializations', [
            'occupation_id' => $occupationId,
            'external_id_raw' => '/santehnika',
            'external_number_id' => 202,
            'slug' => 'santehnicheskie-raboty',
            'name' => 'Сантехнические работы',
            'source_url' => 'javascript:alert(1)',
            'verification_status' => 'discovered',
        ]);
        $serviceId = $this->insertTaxonomy('yandex_services', [
            'specialization_id' => $specializationId,
            'external_id_raw' => '/montazh-smesitelya',
            'external_number_id' => 303,
            'slug' => '/remont/smesitel',
            'name' => '<script>Монтаж смесителя</script>',
            'source_url' => 'https://uslugi.yandex.ru/213-moscow/category/remont/smesitel--303',
            'verification_status' => 'confirmed',
        ]);

        $this->parserDb()->table('parser_categories')->insert([
            'category_id' => $categoryId,
            'seed_paths' => json_encode(['remont/smesitel--303']),
            'is_active' => true,
            'sort_order' => 10,
            'created_at' => '2026-09-01 10:00:00',
            'updated_at' => '2026-09-01 10:00:00',
        ]);
        $this->parserDb()->table('parser_category_targets')->insert([
            'category_id' => $categoryId,
            'taxonomy_level' => 'service',
            'source_rubric_number_id' => 303,
            'relative_path' => 'remont/smesitel--303',
            'is_active' => true,
            'sort_order' => 10,
            'created_at' => '2026-09-01 10:00:00',
            'updated_at' => '2026-09-01 10:00:00',
        ]);
        $this->parserDb()->table('category_yandex_occupations')->insert([
            'category_id' => $categoryId,
            'occupation_id' => $occupationId,
            'sort_order' => 10,
        ]);
        $this->parserDb()->table('category_yandex_specializations')->insert([
            'category_id' => $categoryId,
            'specialization_id' => $specializationId,
            'sort_order' => 10,
        ]);
        $this->parserDb()->table('category_yandex_services')->insert([
            'category_id' => $categoryId,
            'service_id' => $serviceId,
            'sort_order' => 10,
        ]);

        return [
            'category' => $categoryId,
            'occupation' => $occupationId,
            'specialization' => $specializationId,
            'service' => $serviceId,
        ];
    }

    /**
     * Создать внутреннюю группу мастеров.
     */
    private function insertCategory(string $key, string $name): int
    {
        return (int) $this->parserDb()->table('categories')->insertGetId([
            'key' => $key,
            'name' => $name,
            'note' => null,
            'created_at' => '2026-09-01 10:00:00',
            'updated_at' => '2026-09-01 10:00:00',
        ]);
    }

    /**
     * Создать узел одного из трёх уровней внешней таксономии.
     *
     * @param  array<string, mixed>  $values
     */
    private function insertTaxonomy(string $table, array $values): int
    {
        return (int) $this->parserDb()->table($table)->insertGetId(array_merge([
            'external_id_raw' => null,
            'external_number_id' => null,
            'slug' => null,
            'name' => 'Без названия',
            'source_url' => null,
            'verification_status' => 'unverified',
            'created_at' => '2026-09-01 10:00:00',
            'updated_at' => '2026-09-01 10:00:00',
        ], $values));
    }

    /**
     * Сформировать параметры запроса, которые отправляет таблица каталога.
     *
     * @return array<string, mixed>
     */
    private function dataTableParameters(): array
    {
        $columns = [
            ['data' => 'group', 'name' => 'category_name'],
            ['data' => 'occupation', 'name' => 'occupation_name'],
            ['data' => 'specialization', 'name' => 'specialization_name'],
            ['data' => 'service', 'name' => 'service_name'],
            ['data' => 'slug_url', 'name' => 'target_slug'],
            ['data' => 'status', 'name' => 'target_verification_status'],
            ['data' => 'parsing', 'name' => 'used_for_parsing'],
            ['data' => 'actions', 'name' => ''],
        ];

        return [
            'draw' => 1,
            'start' => 0,
            'length' => 25,
            'order' => [['column' => 0, 'dir' => 'asc']],
            'columns' => array_map(
                static fn (array $column, int $index): array => [
                    ...$column,
                    'searchable' => 'false',
                    'orderable' => $index === 7 ? 'false' : 'true',
                    'search' => ['value' => '', 'regex' => 'false'],
                ],
                $columns,
                array_keys($columns),
            ),
            'search' => ['value' => '', 'regex' => 'false'],
        ];
    }

    /**
     * Вернуть query builder отдельной тестовой базы парсера.
     */
    private function parserDb(): Connection
    {
        return DB::connection((string) config('parser.connection'));
    }
}
