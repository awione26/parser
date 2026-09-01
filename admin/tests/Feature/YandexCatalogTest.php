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

        $this->actingAs($viewer)
            ->get(route('admin.catalog.index'))
            ->assertForbidden();

        $this->actingAs($viewer)
            ->get(route('admin.professionals.index'))
            ->assertOk()
            ->assertDontSee(route('admin.catalog.index'), false);

        $this->actingAs($admin)
            ->get(route('admin.catalog.index'))
            ->assertOk()
            ->assertSee('Каталог Яндекса')
            ->assertSee('Найдено строк:');
    }

    public function test_catalog_renders_hierarchy_escapes_data_and_allows_only_canonical_urls(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);
        $ids = $this->seedHierarchy();

        $response = $this->actingAs($admin)
            ->get(route('admin.catalog.index'))
            ->assertOk()
            ->assertSee('Найдено строк: <strong>3</strong>', false)
            ->assertSee('Сантехники')
            ->assertSee('Сантехнические работы')
            ->assertSee('&lt;script&gt;Монтаж смесителя&lt;/script&gt;', false)
            ->assertDontSee('<script>Монтаж смесителя</script>', false)
            ->assertSee('https://uslugi.yandex.ru/category/remont/santehnika--101', false)
            ->assertSee('rel="noopener noreferrer nofollow"', false)
            ->assertDontSee('javascript:alert(1)', false)
            ->assertDontSee('utm_source', false)
            ->assertSee('В парсинге');

        $this->assertSame(3, $response->viewData('rows')->total());
        $this->assertSame($ids['category'], $response->viewData('groups')->first()->id);
    }

    public function test_server_side_filters_and_fixed_pagination_are_applied(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);
        $ids = $this->seedHierarchy();

        $filtered = $this->actingAs($admin)
            ->get(route('admin.catalog.index', [
                'group' => (string) $ids['category'],
                'status' => 'confirmed',
                'has_id' => '1',
                'used_for_parsing' => '1',
            ]))
            ->assertOk()
            ->assertSee('&lt;script&gt;Монтаж смесителя&lt;/script&gt;', false);

        $this->assertSame(1, $filtered->viewData('rows')->total());

        $this->actingAs($admin)
            ->get(route('admin.catalog.index', [
                'q' => '101',
                'used_for_parsing' => '0',
            ]))
            ->assertOk()
            ->assertSee('Сантехники')
            ->assertDontSee('&lt;script&gt;Монтаж смесителя&lt;/script&gt;', false);

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
            ->get(route('admin.catalog.index', ['group' => $categoryId]))
            ->assertOk()
            ->viewData('rows');

        $this->assertSame(50, $page->count());
        $this->assertSame(51, $page->total());
        $this->assertSame(2, $page->lastPage());
    }

    public function test_invalid_catalog_filters_are_rejected(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);

        $this->actingAs($admin)
            ->getJson(route('admin.catalog.index', [
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

    public function test_categories_page_shows_catalog_counts_and_filtered_link(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);
        $ids = $this->seedHierarchy();

        $this->actingAs($admin)
            ->get(route('admin.categories.index'))
            ->assertOk()
            ->assertSee('Н: 1')
            ->assertSee('С: 1')
            ->assertSee('У: 1')
            ->assertSee(route('admin.catalog.index', ['group' => $ids['category']]), false);
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
            'slug' => 'remont-i-stroitelstvo',
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
            'slug' => 'montazh-smesitelya',
            'name' => '<script>Монтаж смесителя</script>',
            'source_url' => 'https://uslugi.yandex.ru/category/remont/smesitel--303?utm_source=test',
            'verification_status' => 'confirmed',
        ]);

        $this->parserDb()->table('parser_categories')->insert([
            'category_id' => $categoryId,
            'seed_paths' => json_encode(['category/remont/smesitel--303']),
            'is_active' => true,
            'sort_order' => 10,
            'created_at' => '2026-09-01 10:00:00',
            'updated_at' => '2026-09-01 10:00:00',
        ]);
        $this->parserDb()->table('parser_category_targets')->insert([
            'category_id' => $categoryId,
            'taxonomy_level' => 'service',
            'source_rubric_number_id' => 303,
            'relative_path' => 'category/remont/smesitel--303',
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
     * Вернуть query builder отдельной тестовой базы парсера.
     */
    private function parserDb(): Connection
    {
        return DB::connection((string) config('parser.connection'));
    }
}
