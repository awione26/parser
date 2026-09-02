<?php

namespace Tests\Feature;

use App\Models\ProfessionalCategoryRubric;
use App\Models\User;
use Illuminate\Database\Connection;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\Concerns\CreatesParserSchema;
use Tests\TestCase;

class YandexCatalogCrudTest extends TestCase
{
    use CreatesParserSchema;
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();

        config()->set('parser.connection', 'sqlite');
        $this->createParserSchema();
    }

    public function test_crud_is_available_only_to_admin_and_index_has_actions_without_unverified_filter(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);
        $viewer = User::factory()->create(['role' => User::ROLE_VIEWER]);
        $ids = $this->seedHierarchy();
        $editRoute = route('admin.catalog.edit', [
            'category' => $ids['category'],
            'taxonomyLevel' => 'service',
            'catalogNode' => $ids['service'],
        ]);

        $this->get(route('admin.catalog.create'))->assertRedirect(route('login'));
        $this->actingAs($viewer)->get(route('admin.catalog.create'))->assertForbidden();
        $this->actingAs($viewer)->get($editRoute)->assertForbidden();
        $this->actingAs($viewer)->post(route('admin.catalog.store'), [])->assertForbidden();
        $this->actingAs($viewer)->delete(route('admin.catalog.destroy', [
            'category' => $ids['category'],
            'taxonomyLevel' => 'service',
            'catalogNode' => $ids['service'],
        ]), ['confirmed' => '1'])->assertForbidden();

        $this->actingAs($admin)
            ->get(route('admin.catalog.index'))
            ->assertOk()
            ->assertSee('Добавить категорию')
            ->assertDontSee('<option value="unverified"', false);
        $catalogData = $this->actingAs($admin)
            ->getJson(route('admin.datatable.catalog', $this->dataTableParameters()))
            ->assertOk();
        $this->assertStringContainsString(
            $editRoute,
            collect($catalogData->json('data'))->pluck('actions')->implode(''),
        );
        $this->actingAs($admin)
            ->get(route('admin.catalog.create'))
            ->assertOk()
            ->assertSee('Добавить категорию Яндекс.Каталога')
            ->assertDontSee('Не проверено');
        $this->actingAs($admin)
            ->get($editRoute)
            ->assertOk()
            ->assertSee('Сохранить изменения')
            ->assertSee('ID существующей категории не изменяется')
            ->assertSee('Сам справочный')
            ->assertSee('Удалить категорию');
    }

    public function test_admin_can_create_a_fully_verified_service_and_it_starts_outside_parser_plan(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);
        $ids = $this->seedHierarchy();

        $response = $this->actingAs($admin)->post(route('admin.catalog.store'), $this->validPayload([
            'category_id' => $ids['category'],
            'taxonomy_level' => 'service',
            'parent_specialization_id' => $ids['specialization'],
        ]));

        $service = $this->parserDb()->table('yandex_services')
            ->where('external_number_id', 909)
            ->first();
        $this->assertNotNull($service);
        $response
            ->assertRedirect(route('admin.catalog.index', ['group' => $ids['category']]))
            ->assertSessionHas('success');
        $this->assertSame($ids['specialization'], (int) $service->specialization_id);
        $this->assertDatabaseHas('category_yandex_services', [
            'category_id' => $ids['category'],
            'service_id' => $service->id,
            'sort_order' => 70,
        ], 'sqlite');
        $this->assertDatabaseMissing('parser_category_targets', [
            'category_id' => $ids['category'],
            'source_rubric_number_id' => 909,
        ], 'sqlite');
    }

    public function test_create_rejects_unusable_or_inconsistent_data_and_global_duplicates(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);
        $ids = $this->seedHierarchy();

        $this->actingAs($admin)
            ->postJson(route('admin.catalog.store'), $this->validPayload([
                'category_id' => $ids['category'],
                'taxonomy_level' => 'service',
                'parent_specialization_id' => $ids['specialization'],
                'verification_status' => 'unverified',
                'source_url' => 'https://evil.example/category/remont/novaya-usluga--909',
            ]))
            ->assertUnprocessable()
            ->assertJsonValidationErrors(['verification_status', 'source_url']);

        $this->actingAs($admin)
            ->postJson(route('admin.catalog.store'), $this->validPayload([
                'category_id' => $ids['category'],
                'taxonomy_level' => 'service',
                'parent_specialization_id' => $ids['specialization'],
                'external_number_id' => 101,
                'source_url' => 'https://uslugi.yandex.ru/category/remont/novaya-usluga--101',
            ]))
            ->assertUnprocessable()
            ->assertJsonValidationErrors('external_number_id');

        $this->actingAs($admin)
            ->postJson(route('admin.catalog.store'), $this->validPayload([
                'category_id' => $ids['category'],
                'taxonomy_level' => 'service',
                'parent_specialization_id' => $ids['specialization'],
                'slug' => '/remont/santehnika',
                'source_url' => 'https://uslugi.yandex.ru/category/remont/santehnika--909',
            ]))
            ->assertUnprocessable()
            ->assertJsonValidationErrors('slug');

        $this->assertDatabaseMissing('yandex_services', [
            'external_number_id' => 909,
        ], 'sqlite');
    }

    public function test_admin_can_update_an_unshared_inactive_node_and_move_its_group(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);
        $ids = $this->seedHierarchy();
        $newGroup = $this->insertCategory('new-plumbers', 'Новая группа');

        $this->parserDb()->table('parser_category_targets')
            ->where('category_id', $ids['category'])
            ->where('source_rubric_number_id', 303)
            ->update(['is_active' => false]);

        $payload = $this->payloadForService($ids, [
            'category_id' => $newGroup,
            'name' => 'Монтаж нового смесителя',
            'slug' => '/remont/novyy-smesitel',
            'source_url' => 'https://uslugi.yandex.ru/category/remont/novyy-smesitel--303',
            'sort_order' => 80,
        ]);
        $this->actingAs($admin)
            ->put(route('admin.catalog.update', [
                'category' => $ids['category'],
                'taxonomyLevel' => 'service',
                'catalogNode' => $ids['service'],
            ]), $payload)
            ->assertRedirect(route('admin.catalog.index', ['group' => $newGroup]))
            ->assertSessionHas('success');

        $this->assertDatabaseHas('yandex_services', [
            'id' => $ids['service'],
            'external_number_id' => 303,
            'name' => 'Монтаж нового смесителя',
            'slug' => '/remont/novyy-smesitel',
        ], 'sqlite');
        $this->assertDatabaseMissing('category_yandex_services', [
            'category_id' => $ids['category'],
            'service_id' => $ids['service'],
        ], 'sqlite');
        $this->assertDatabaseHas('category_yandex_services', [
            'category_id' => $newGroup,
            'service_id' => $ids['service'],
            'sort_order' => 80,
        ], 'sqlite');
        $this->assertDatabaseMissing('parser_category_targets', [
            'category_id' => $ids['category'],
            'source_rubric_number_id' => 303,
        ], 'sqlite');
        $configuration = $this->parserDb()->table('parser_categories')
            ->where('category_id', $ids['category'])
            ->first();
        $this->assertNotNull($configuration);
        $this->assertSame(0, (int) $configuration->is_active);
        $this->assertSame([], json_decode((string) $configuration->seed_paths, true));
    }

    public function test_update_protects_immutable_id_active_target_history_and_shared_node(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);
        $ids = $this->seedHierarchy();
        $route = route('admin.catalog.update', [
            'category' => $ids['category'],
            'taxonomyLevel' => 'service',
            'catalogNode' => $ids['service'],
        ]);

        $this->actingAs($admin)
            ->putJson($route, $this->payloadForService($ids, [
                'external_number_id' => 404,
                'source_url' => 'https://uslugi.yandex.ru/category/remont/smesitel--404',
            ]))
            ->assertUnprocessable()
            ->assertJsonValidationErrors('external_number_id');

        $this->actingAs($admin)
            ->putJson($route, $this->payloadForService($ids, [
                'slug' => '/remont/drugoy-smesitel',
                'source_url' => 'https://uslugi.yandex.ru/category/remont/drugoy-smesitel--303',
            ]))
            ->assertUnprocessable()
            ->assertJsonValidationErrors('catalog');

        $this->parserDb()->table('parser_category_targets')
            ->where('category_id', $ids['category'])
            ->where('source_rubric_number_id', 303)
            ->update(['is_active' => false]);
        $this->insertProfessionalEvidence($ids['category'], 303, null);
        $this->actingAs($admin)
            ->putJson($route, $this->payloadForService($ids, [
                'slug' => '/remont/drugoy-smesitel',
                'source_url' => 'https://uslugi.yandex.ru/category/remont/drugoy-smesitel--303',
            ]))
            ->assertUnprocessable()
            ->assertJsonValidationErrors('catalog');

        $otherGroup = $this->insertCategory('shared', 'Общая группа');
        $this->parserDb()->table('category_yandex_services')->insert([
            'category_id' => $otherGroup,
            'service_id' => $ids['service'],
            'sort_order' => 10,
        ]);
        $this->actingAs($admin)
            ->putJson($route, $this->payloadForService($ids, ['name' => 'Скрытая общая правка']))
            ->assertUnprocessable()
            ->assertJsonValidationErrors('catalog');

        $this->assertDatabaseHas('yandex_services', [
            'id' => $ids['service'],
            'name' => 'Монтаж смесителя',
            'external_number_id' => 303,
        ], 'sqlite');
    }

    public function test_delete_unlinks_active_target_but_retains_node_for_late_crawl_evidence(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);
        $ids = $this->seedHierarchy();
        $destroyRoute = route('admin.catalog.destroy', [
            'category' => $ids['category'],
            'taxonomyLevel' => 'service',
            'catalogNode' => $ids['service'],
        ]);

        $this->actingAs($admin)
            ->delete($destroyRoute, ['confirmed' => 'yes'])
            ->assertRedirect(route('admin.catalog.index'))
            ->assertSessionHas('success');

        $this->assertDatabaseMissing('category_yandex_services', [
            'category_id' => $ids['category'],
            'service_id' => $ids['service'],
        ], 'sqlite');
        $this->assertDatabaseHas('yandex_services', [
            'id' => $ids['service'],
            'external_number_id' => 303,
            'name' => 'Монтаж смесителя',
        ], 'sqlite');
        $this->assertDatabaseMissing('parser_category_targets', [
            'category_id' => $ids['category'],
            'source_rubric_number_id' => 303,
        ], 'sqlite');
        $configuration = $this->parserDb()->table('parser_categories')
            ->where('category_id', $ids['category'])
            ->first();
        $this->assertNotNull($configuration);
        $this->assertSame(0, (int) $configuration->is_active);
        $this->assertSame([], json_decode((string) $configuration->seed_paths, true));
        $this->actingAs($admin)
            ->getJson(route('admin.datatable.catalog', [
                ...$this->dataTableParameters(),
                'group' => $ids['category'],
                'q' => '303',
            ]))
            ->assertOk()
            ->assertJsonPath('recordsTotal', 0)
            ->assertJsonCount(0, 'data');

        // Имитируем результат обхода, который снял старый план до удаления строки.
        $this->insertProfessionalEvidence($ids['category'], 303, 'service');
        $rubric = ProfessionalCategoryRubric::query()
            ->where('source_rubric_number_id', 303)
            ->firstOrFail();
        $this->assertSame('Монтаж смесителя', $rubric->catalogName());
    }

    public function test_delete_requires_confirmation_and_retains_nodes_with_history_or_children(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);
        $ids = $this->seedHierarchy();
        $serviceRoute = route('admin.catalog.destroy', [
            'category' => $ids['category'],
            'taxonomyLevel' => 'service',
            'catalogNode' => $ids['service'],
        ]);

        $this->actingAs($admin)
            ->deleteJson($serviceRoute)
            ->assertUnprocessable()
            ->assertJsonValidationErrors('confirmed');

        $this->insertProfessionalEvidence($ids['category'], 303, null);
        $this->actingAs($admin)
            ->delete($serviceRoute, ['confirmed' => '1'])
            ->assertRedirect(route('admin.catalog.index'))
            ->assertSessionHas('success');
        $this->assertDatabaseHas('yandex_services', ['id' => $ids['service']], 'sqlite');
        $this->assertDatabaseMissing('category_yandex_services', [
            'category_id' => $ids['category'],
            'service_id' => $ids['service'],
        ], 'sqlite');

        $occupationRoute = route('admin.catalog.destroy', [
            'category' => $ids['category'],
            'taxonomyLevel' => 'occupation',
            'catalogNode' => $ids['occupation'],
        ]);
        $this->actingAs($admin)
            ->delete($occupationRoute, ['confirmed' => '1'])
            ->assertRedirect(route('admin.catalog.index'))
            ->assertSessionHas('success');
        $this->assertDatabaseMissing('category_yandex_occupations', [
            'category_id' => $ids['category'],
            'occupation_id' => $ids['occupation'],
        ], 'sqlite');
        $this->assertDatabaseHas('yandex_occupations', ['id' => $ids['occupation']], 'sqlite');
        $this->assertDatabaseHas('yandex_specializations', [
            'id' => $ids['specialization'],
            'occupation_id' => $ids['occupation'],
        ], 'sqlite');
    }

    public function test_shared_node_can_be_unlinked_then_reattached_without_duplicate(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);
        $ids = $this->seedHierarchy();
        $otherGroup = $this->insertCategory('shared-service', 'Вторая группа');
        $this->parserDb()->table('category_yandex_services')->insert([
            'category_id' => $otherGroup,
            'service_id' => $ids['service'],
            'sort_order' => 20,
        ]);
        $destroyRoute = route('admin.catalog.destroy', [
            'category' => $ids['category'],
            'taxonomyLevel' => 'service',
            'catalogNode' => $ids['service'],
        ]);

        $this->actingAs($admin)
            ->delete($destroyRoute, ['confirmed' => '1'])
            ->assertRedirect(route('admin.catalog.index'))
            ->assertSessionHas('success');

        $this->assertDatabaseHas('yandex_services', ['id' => $ids['service']], 'sqlite');
        $this->assertDatabaseMissing('category_yandex_services', [
            'category_id' => $ids['category'],
            'service_id' => $ids['service'],
        ], 'sqlite');
        $this->assertDatabaseHas('category_yandex_services', [
            'category_id' => $otherGroup,
            'service_id' => $ids['service'],
        ], 'sqlite');

        $this->actingAs($admin)
            ->post(route('admin.catalog.store'), $this->payloadForService($ids, ['sort_order' => 95]))
            ->assertRedirect(route('admin.catalog.index', ['group' => $ids['category']]))
            ->assertSessionHas('success');
        $this->assertSame(1, $this->parserDb()->table('yandex_services')->where('external_number_id', 303)->count());
        $this->assertDatabaseHas('category_yandex_services', [
            'category_id' => $ids['category'],
            'service_id' => $ids['service'],
            'sort_order' => 95,
        ], 'sqlite');
    }

    public function test_store_reattaches_only_an_exact_orphan_node(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);
        $ids = $this->seedHierarchy();
        $destroyRoute = route('admin.catalog.destroy', [
            'category' => $ids['category'],
            'taxonomyLevel' => 'service',
            'catalogNode' => $ids['service'],
        ]);
        $this->actingAs($admin)
            ->delete($destroyRoute, ['confirmed' => '1'])
            ->assertRedirect(route('admin.catalog.index'));

        $this->actingAs($admin)
            ->post(route('admin.catalog.store'), $this->payloadForService($ids, ['sort_order' => 90]))
            ->assertRedirect(route('admin.catalog.index', ['group' => $ids['category']]))
            ->assertSessionHas('success');
        $this->assertSame(1, $this->parserDb()->table('yandex_services')->where('external_number_id', 303)->count());
        $this->assertDatabaseHas('category_yandex_services', [
            'category_id' => $ids['category'],
            'service_id' => $ids['service'],
            'sort_order' => 90,
        ], 'sqlite');

        $this->actingAs($admin)
            ->delete($destroyRoute, ['confirmed' => '1'])
            ->assertRedirect(route('admin.catalog.index'));
        $this->actingAs($admin)
            ->postJson(route('admin.catalog.store'), $this->payloadForService($ids, [
                'name' => 'Несовпадающее название',
            ]))
            ->assertUnprocessable()
            ->assertJsonValidationErrors('external_number_id');
    }

    public function test_parent_options_hide_orphans_but_keep_ancestors_of_mapped_descendants(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);
        $group = $this->insertCategory('parents', 'Группа родителей');
        $occupation = $this->insertTaxonomy('yandex_occupations', [
            'external_number_id' => 700,
            'slug' => '/orphan/occupation',
            'name' => 'Скрытое направление',
            'source_url' => 'https://uslugi.yandex.ru/category/orphan/occupation--700',
            'verification_status' => 'confirmed',
        ]);
        $specialization = $this->insertTaxonomy('yandex_specializations', [
            'occupation_id' => $occupation,
            'external_number_id' => 701,
            'slug' => '/orphan/specialization',
            'name' => 'Скрытая специализация',
            'source_url' => 'https://uslugi.yandex.ru/category/orphan/specialization--701',
            'verification_status' => 'confirmed',
        ]);
        $service = $this->insertTaxonomy('yandex_services', [
            'specialization_id' => $specialization,
            'external_number_id' => 702,
            'slug' => '/orphan/service',
            'name' => 'Связанная услуга',
            'source_url' => 'https://uslugi.yandex.ru/category/orphan/service--702',
            'verification_status' => 'confirmed',
        ]);

        $this->actingAs($admin)
            ->get(route('admin.catalog.create'))
            ->assertOk()
            ->assertDontSee('Скрытое направление')
            ->assertDontSee('Скрытая специализация');

        $this->parserDb()->table('category_yandex_services')->insert([
            'category_id' => $group,
            'service_id' => $service,
            'sort_order' => 10,
        ]);
        $this->actingAs($admin)
            ->get(route('admin.catalog.create'))
            ->assertOk()
            ->assertSee('Скрытое направление')
            ->assertSee('Скрытая специализация');
    }

    /**
     * Заполнить минимальную иерархию с активной услугой для CRUD-тестов.
     *
     * @return array{category: int, occupation: int, specialization: int, service: int}
     */
    private function seedHierarchy(): array
    {
        $category = $this->insertCategory('plumbers', 'Сантехники');
        $occupation = $this->insertTaxonomy('yandex_occupations', [
            'external_number_id' => 101,
            'external_id_raw' => '/remont',
            'slug' => '/remont/santehnika',
            'name' => 'Ремонт и строительство',
            'source_url' => 'https://uslugi.yandex.ru/category/remont/santehnika--101',
            'verification_status' => 'confirmed',
        ]);
        $specialization = $this->insertTaxonomy('yandex_specializations', [
            'occupation_id' => $occupation,
            'external_number_id' => 202,
            'external_id_raw' => '/santehnika',
            'slug' => '/remont/santehnicheskie-raboty',
            'name' => 'Сантехнические работы',
            'source_url' => 'https://uslugi.yandex.ru/category/remont/santehnicheskie-raboty--202',
            'verification_status' => 'discovered',
        ]);
        $service = $this->insertTaxonomy('yandex_services', [
            'specialization_id' => $specialization,
            'external_number_id' => 303,
            'external_id_raw' => '/montazh-smesitelya',
            'slug' => '/remont/smesitel',
            'name' => 'Монтаж смесителя',
            'source_url' => 'https://uslugi.yandex.ru/category/remont/smesitel--303',
            'verification_status' => 'confirmed',
        ]);

        $now = '2026-09-02 10:00:00';
        $this->parserDb()->table('parser_categories')->insert([
            'category_id' => $category,
            'seed_paths' => json_encode(['remont/smesitel--303']),
            'is_active' => true,
            'sort_order' => 10,
            'created_at' => $now,
            'updated_at' => $now,
        ]);
        $this->parserDb()->table('parser_category_targets')->insert([
            'category_id' => $category,
            'taxonomy_level' => 'service',
            'source_rubric_number_id' => 303,
            'relative_path' => 'remont/smesitel--303',
            'is_active' => true,
            'sort_order' => 10,
            'created_at' => $now,
            'updated_at' => $now,
        ]);
        $this->parserDb()->table('category_yandex_occupations')->insert([
            'category_id' => $category,
            'occupation_id' => $occupation,
            'sort_order' => 10,
        ]);
        $this->parserDb()->table('category_yandex_specializations')->insert([
            'category_id' => $category,
            'specialization_id' => $specialization,
            'sort_order' => 20,
        ]);
        $this->parserDb()->table('category_yandex_services')->insert([
            'category_id' => $category,
            'service_id' => $service,
            'sort_order' => 30,
        ]);

        return compact('category', 'occupation', 'specialization', 'service');
    }

    /**
     * Вернуть корректные данные новой услуги.
     *
     * @param  array<string, mixed>  $overrides
     * @return array<string, mixed>
     */
    private function validPayload(array $overrides = []): array
    {
        return array_merge([
            'category_id' => '',
            'taxonomy_level' => 'service',
            'parent_specialization_id' => '',
            'name' => 'Новая услуга',
            'external_id_raw' => '/novaya-usluga',
            'external_number_id' => 909,
            'slug' => '/remont/novaya-usluga',
            'source_url' => 'https://uslugi.yandex.ru/category/remont/novaya-usluga--909',
            'verification_status' => 'confirmed',
            'sort_order' => 70,
        ], $overrides);
    }

    /**
     * Вернуть текущие поля тестовой услуги для запроса обновления.
     *
     * @param  array<string, int>  $ids
     * @param  array<string, mixed>  $overrides
     * @return array<string, mixed>
     */
    private function payloadForService(array $ids, array $overrides = []): array
    {
        return array_merge([
            'category_id' => $ids['category'],
            'taxonomy_level' => 'service',
            'parent_specialization_id' => $ids['specialization'],
            'name' => 'Монтаж смесителя',
            'external_id_raw' => '/montazh-smesitelya',
            'external_number_id' => 303,
            'slug' => '/remont/smesitel',
            'source_url' => 'https://uslugi.yandex.ru/category/remont/smesitel--303',
            'verification_status' => 'confirmed',
            'sort_order' => 30,
        ], $overrides);
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
            'created_at' => '2026-09-02 10:00:00',
            'updated_at' => '2026-09-02 10:00:00',
        ]);
    }

    /**
     * Создать узел одной из трёх таблиц таксономии.
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
            'created_at' => '2026-09-02 10:00:00',
            'updated_at' => '2026-09-02 10:00:00',
        ], $values));
    }

    /**
     * Создать карточку мастера и старую запись его рубрики для защитного теста.
     */
    private function insertProfessionalEvidence(int $categoryId, int $rubricId, ?string $level): void
    {
        $now = '2026-09-02 10:00:00';
        $professional = (int) $this->parserDb()->table('professionals')->insertGetId([
            'source' => 'uslugi.yandex.ru',
            'source_profile_id' => 'test-profile',
            'profile_url' => 'https://uslugi.yandex.ru/profile/test-profile',
            'full_name' => 'Тестовый мастер',
            'phone' => null,
            'phone_status' => 'missing',
            'city' => null,
            'region' => null,
            'country' => null,
            'age' => null,
            'age_as_of' => '2026-09-02',
            'gender' => null,
            'experience_code' => null,
            'experience_text' => null,
            'photo_url' => null,
            'account_type' => null,
            'content_hash' => str_repeat('a', 64),
            'parser_version' => 'test',
            'first_seen_at' => $now,
            'last_seen_at' => $now,
            'last_scraped_at' => $now,
        ]);
        $this->parserDb()->table('professional_categories')->insert([
            'professional_id' => $professional,
            'category_id' => $categoryId,
            'first_seen_at' => $now,
            'last_seen_at' => $now,
        ]);
        $this->parserDb()->table('professional_category_rubrics')->insert([
            'professional_id' => $professional,
            'category_id' => $categoryId,
            'source_rubric_number_id' => $rubricId,
            'source_rubric_id' => null,
            'source_rubric_seo_id' => null,
            'source_rubric_name' => 'Старая рубрика',
            'source_rubric_level' => $level,
            'experience_code' => null,
            'experience_text' => null,
            'first_seen_at' => $now,
            'last_seen_at' => $now,
        ]);
    }

    /**
     * Сформировать параметры запроса серверной таблицы каталога.
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
     * Вернуть подключение к тестовой базе парсера.
     */
    private function parserDb(): Connection
    {
        return DB::connection((string) config('parser.connection'));
    }
}
