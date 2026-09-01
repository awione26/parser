<?php

namespace Tests\Feature;

use App\Models\Category;
use App\Models\ParserCategory;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Hash;
use Tests\Concerns\CreatesParserSchema;
use Tests\TestCase;

class ParserCategoryManagementTest extends TestCase
{
    use CreatesParserSchema;
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();

        config()->set('parser.connection', 'sqlite');
        $this->createParserSchema();
    }

    public function test_only_administrators_can_manage_parser_categories(): void
    {
        $row = $this->createParserCategory();
        $viewer = $this->createUser('viewer', User::ROLE_VIEWER);

        $this->get(route('admin.categories.index'))->assertRedirect(route('login'));

        $this->actingAs($viewer)->get(route('admin.categories.index'))->assertForbidden();
        $this->actingAs($viewer)->get(route('admin.categories.create'))->assertForbidden();
        $this->actingAs($viewer)->post(route('admin.categories.store'), $this->validPayload('new_key'))
            ->assertForbidden();
        $this->actingAs($viewer)->get(route('admin.categories.edit', $row))->assertForbidden();
        $this->actingAs($viewer)->put(route('admin.categories.update', $row), $this->validUpdatePayload())
            ->assertForbidden();
        $this->actingAs($viewer)->patch(route('admin.categories.activation', $row), ['is_active' => '0'])
            ->assertForbidden();
        $this->actingAs($viewer)->delete(route('admin.categories.destroy', $row))->assertForbidden();

        $this->actingAs($viewer)
            ->get(route('admin.professionals.index'))
            ->assertOk()
            ->assertDontSee(route('admin.categories.index'), false);
    }

    public function test_index_lists_eleven_categories_without_datatables_and_escapes_values(): void
    {
        $admin = $this->createUser('admin', User::ROLE_ADMIN);
        $names = [
            'designers' => 'Дизайнеры',
            'estimators' => 'Сметчики',
            'plumbers' => 'Сантехники',
            'electricians' => 'Электрики',
            'carpenters' => 'Плотники',
            'furniture_assemblers' => 'Сборщики мебели',
            'finishers' => 'Отделочники',
            'appliance_repair' => 'Мастера по ремонту бытовой техники',
            'window_repair' => 'Мастера по ремонту окон',
            'locks_and_doors' => 'Мастера по замкам и дверям',
            'low_voltage' => '<script>Мастера по слаботочным системам</script>',
        ];

        $position = 0;
        foreach ($names as $key => $name) {
            $position++;
            $this->createParserCategory(
                $key,
                $name,
                $position * 10,
                1000 + $position,
            );
        }

        $response = $this->actingAs($admin)
            ->get(route('admin.categories.index'))
            ->assertOk()
            ->assertSee('Всего: 11')
            ->assertSee(route('admin.categories.create'), false)
            ->assertDontSee('jquery.dataTables.min.js', false)
            ->assertDontSee('<script>Мастера по слаботочным системам</script>', false)
            ->assertSee('&lt;script&gt;Мастера по слаботочным системам&lt;/script&gt;', false);

        foreach (array_keys($names) as $key) {
            $response->assertSee($key);
        }
    }

    public function test_admin_can_reuse_historical_category_when_creating_configuration(): void
    {
        $admin = $this->createUser('admin', User::ROLE_ADMIN);
        $historical = $this->createCategory('carpenters', 'Старое название', 'Старое примечание');

        $this->actingAs($admin)
            ->post(route('admin.categories.store'), [
                ...$this->validPayload(' CARPENTERS '),
                'name' => ' Плотники ',
                'note' => ' Новое примечание ',
                'seed_paths' => "remont-i-stroitelstvo/plotniki--101\nremont-i-stroitelstvo/stolyary--102\n",
            ])
            ->assertRedirect(route('admin.categories.index'))
            ->assertSessionHas('success');

        $historical->refresh();
        $configuration = ParserCategory::query()->findOrFail($historical->id);

        $this->assertSame('carpenters', $historical->key);
        $this->assertSame('Плотники', $historical->name);
        $this->assertSame('Новое примечание', $historical->note);
        $this->assertSame([
            'remont-i-stroitelstvo/plotniki--101',
            'remont-i-stroitelstvo/stolyary--102',
        ], $configuration->seed_paths);
        $this->assertTrue($configuration->is_active);
        $this->assertSame(10, $configuration->sort_order);
        $this->assertSame(1, Category::query()->where('key', 'carpenters')->count());
    }

    public function test_admin_can_create_a_new_master_category_and_configuration(): void
    {
        $admin = $this->createUser('admin', User::ROLE_ADMIN);

        $this->actingAs($admin)
            ->post(route('admin.categories.store'), $this->validPayload('new_category'))
            ->assertRedirect(route('admin.categories.index'));

        $category = Category::query()->where('key', 'new_category')->firstOrFail();
        $this->assertNotNull(ParserCategory::query()->find($category->id));
    }

    public function test_configured_key_and_unsafe_fields_are_rejected(): void
    {
        $admin = $this->createUser('admin', User::ROLE_ADMIN);
        $this->createParserCategory('plumbers');

        $this->actingAs($admin)
            ->from(route('admin.categories.create'))
            ->post(route('admin.categories.store'), $this->validPayload('plumbers'))
            ->assertRedirect(route('admin.categories.create'))
            ->assertSessionHasErrors('key');

        $this->actingAs($admin)
            ->from(route('admin.categories.create'))
            ->post(route('admin.categories.store'), [
                ...$this->validPayload('bad-key'),
                'seed_paths' => 'https://evil.example/category--123',
                'name' => "Недопустимое\x7Fназвание",
                'sort_order' => '2147483648',
                'is_active' => 'yes',
            ])
            ->assertRedirect(route('admin.categories.create'))
            ->assertSessionHasErrors(['key', 'name', 'seed_paths.0', 'sort_order', 'is_active']);

        $this->assertSame(1, ParserCategory::query()->count());
    }

    public function test_reserved_parser_keys_are_rejected(): void
    {
        $admin = $this->createUser('admin', User::ROLE_ADMIN);

        foreach (['all', 'manual'] as $key) {
            $this->actingAs($admin)
                ->from(route('admin.categories.create'))
                ->post(route('admin.categories.store'), $this->validPayload($key))
                ->assertRedirect(route('admin.categories.create'))
                ->assertSessionHasErrors('key');
        }

        $this->assertSame(0, ParserCategory::query()->count());
    }

    public function test_absolute_traversal_query_and_non_numeric_seed_paths_are_rejected(): void
    {
        $admin = $this->createUser('admin', User::ROLE_ADMIN);
        $invalidPaths = [
            '/category/path--123',
            '../category/path--123',
            'category/path',
            'category/path--0',
            'category/path--123?from=test',
        ];

        foreach ($invalidPaths as $path) {
            $this->actingAs($admin)
                ->from(route('admin.categories.create'))
                ->post(route('admin.categories.store'), [
                    ...$this->validPayload('safe_key'),
                    'seed_paths' => $path,
                ])
                ->assertRedirect(route('admin.categories.create'))
                ->assertSessionHasErrors('seed_paths.0');
        }

        $this->assertSame(0, ParserCategory::query()->count());
    }

    public function test_admin_can_update_category_but_cannot_change_its_key(): void
    {
        $admin = $this->createUser('admin', User::ROLE_ADMIN);
        $row = $this->createParserCategory('plumbers', 'Сантехники');

        $this->actingAs($admin)
            ->put(route('admin.categories.update', $row), [
                ...$this->validUpdatePayload(),
                'name' => 'Сантехники и отопление',
                'note' => '',
                'seed_paths' => "category/plumbers--201\ncategory/heating--202",
                'is_active' => '0',
                'sort_order' => '25',
            ])
            ->assertRedirect(route('admin.categories.index'));

        $row->refresh();
        $row->category->refresh();
        $this->assertSame('plumbers', $row->category->key);
        $this->assertSame('Сантехники и отопление', $row->category->name);
        $this->assertNull($row->category->note);
        $this->assertFalse($row->is_active);
        $this->assertSame(25, $row->sort_order);

        $this->actingAs($admin)
            ->from(route('admin.categories.edit', $row))
            ->put(route('admin.categories.update', $row), [
                ...$this->validUpdatePayload(),
                'key' => 'changed_key',
            ])
            ->assertRedirect(route('admin.categories.edit', $row))
            ->assertSessionHasErrors('key');

        $this->assertSame('plumbers', $row->category->fresh()->key);
    }

    public function test_create_and_update_reject_rubric_id_used_by_another_category(): void
    {
        $admin = $this->createUser('admin', User::ROLE_ADMIN);
        $this->createParserCategory('plumbers', 'Сантехники', 10, 123);

        $this->actingAs($admin)
            ->from(route('admin.categories.create'))
            ->post(route('admin.categories.store'), [
                ...$this->validPayload('electricians'),
                'seed_paths' => 'category/electricians--123',
            ])
            ->assertRedirect(route('admin.categories.create'))
            ->assertSessionHasErrors('seed_paths.0');

        $this->actingAs($admin)
            ->from(route('admin.categories.create'))
            ->post(route('admin.categories.store'), [
                ...$this->validPayload('electricians'),
                'seed_paths' => "category/electricians--456\ncategory/alternate-electricians--456",
            ])
            ->assertRedirect(route('admin.categories.create'))
            ->assertSessionHasErrors('seed_paths.1');

        $other = $this->createParserCategory('electricians', 'Электрики', 20, 456);
        $this->actingAs($admin)
            ->from(route('admin.categories.edit', $other))
            ->put(route('admin.categories.update', $other), [
                ...$this->validUpdatePayload(),
                'seed_paths' => 'another/category-path--123',
            ])
            ->assertRedirect(route('admin.categories.edit', $other))
            ->assertSessionHasErrors('seed_paths.0');

        $this->assertSame(['category/electricians--456'], $other->fresh()->seed_paths);
    }

    public function test_activation_is_idempotent_and_delete_keeps_master_category_for_readding(): void
    {
        $admin = $this->createUser('admin', User::ROLE_ADMIN);
        $row = $this->createParserCategory('plumbers');
        $categoryId = $row->category_id;

        $this->actingAs($admin)
            ->patch(route('admin.categories.activation', $row), ['is_active' => '0'])
            ->assertRedirect(route('admin.categories.index'));
        $this->actingAs($admin)
            ->patch(route('admin.categories.activation', $row), ['is_active' => '0'])
            ->assertRedirect(route('admin.categories.index'));
        $this->assertFalse($row->fresh()->is_active);

        $this->actingAs($admin)
            ->delete(route('admin.categories.destroy', $row))
            ->assertRedirect(route('admin.categories.index'));

        $this->assertNull(ParserCategory::query()->find($categoryId));
        $this->assertNotNull(Category::query()->find($categoryId));

        $this->actingAs($admin)
            ->post(route('admin.categories.store'), $this->validPayload('plumbers'))
            ->assertRedirect(route('admin.categories.index'));

        $this->assertSame($categoryId, ParserCategory::query()->findOrFail($categoryId)->category_id);
    }

    public function test_category_form_atomically_replaces_normalized_parser_targets(): void
    {
        $admin = $this->createUser('admin', User::ROLE_ADMIN);
        DB::connection('sqlite')->table('yandex_occupations')->insert([
            'external_id_raw' => '/remont-i-stroitel_stvo',
            'external_number_id' => 201,
            'slug' => 'remont-i-stroitelstvo',
            'name' => 'Ремонт и строительство',
            'source_url' => null,
            'verification_status' => 'confirmed',
            'created_at' => '2026-09-01 10:00:00',
            'updated_at' => '2026-09-01 10:00:00',
        ]);
        DB::connection('sqlite')->table('yandex_services')->insert([
            'specialization_id' => null,
            'external_id_raw' => '/montazh',
            'external_number_id' => 202,
            'slug' => 'montazh',
            'name' => 'Монтаж',
            'source_url' => null,
            'verification_status' => 'discovered',
            'created_at' => '2026-09-01 10:00:00',
            'updated_at' => '2026-09-01 10:00:00',
        ]);

        $this->actingAs($admin)
            ->post(route('admin.categories.store'), [
                ...$this->validPayload('normalized'),
                'seed_paths' => "category/remont--201\ncategory/unknown--999",
            ])
            ->assertRedirect(route('admin.categories.index'));

        $row = ParserCategory::query()->whereHas(
            'category',
            fn ($query) => $query->where('key', 'normalized'),
        )->firstOrFail();
        $this->assertDatabaseHas('parser_category_targets', [
            'category_id' => $row->category_id,
            'source_rubric_number_id' => 201,
            'taxonomy_level' => 'occupation',
            'sort_order' => 10,
        ], 'sqlite');
        $this->assertDatabaseHas('parser_category_targets', [
            'category_id' => $row->category_id,
            'source_rubric_number_id' => 999,
            'taxonomy_level' => 'unknown',
            'sort_order' => 20,
        ], 'sqlite');

        $this->actingAs($admin)
            ->put(route('admin.categories.update', $row), [
                ...$this->validUpdatePayload(),
                'seed_paths' => 'category/montazh--202',
            ])
            ->assertRedirect(route('admin.categories.index'));

        $this->assertDatabaseCount('parser_category_targets', 1, 'sqlite');
        $this->assertDatabaseMissing('parser_category_targets', [
            'category_id' => $row->category_id,
            'source_rubric_number_id' => 201,
        ], 'sqlite');
        $this->assertDatabaseHas('parser_category_targets', [
            'category_id' => $row->category_id,
            'source_rubric_number_id' => 202,
            'taxonomy_level' => 'service',
            'relative_path' => 'category/montazh--202',
        ], 'sqlite');
    }

    /**
     * @return array<string, string>
     */
    private function validPayload(string $key): array
    {
        return [
            'key' => $key,
            'name' => 'Новая категория',
            'note' => 'Примечание',
            'seed_paths' => 'category/new-category--123',
            'is_active' => '1',
            'sort_order' => '10',
        ];
    }

    /**
     * @return array<string, string>
     */
    private function validUpdatePayload(): array
    {
        return [
            'name' => 'Обновлённая категория',
            'note' => 'Обновлённое примечание',
            'seed_paths' => 'category/updated-category--321',
            'is_active' => '1',
            'sort_order' => '20',
        ];
    }

    private function createUser(string $login, string $role): User
    {
        return User::query()->create([
            'name' => ucfirst($login),
            'login' => $login,
            'role' => $role,
            'password' => Hash::make('Correct Horse Battery 123!'),
        ]);
    }

    private function createCategory(string $key, string $name, ?string $note = null): Category
    {
        $now = '2026-08-31 10:00:00';
        $category = new Category;
        $category->forceFill([
            'key' => $key,
            'name' => $name,
            'note' => $note,
            'created_at' => $now,
            'updated_at' => $now,
        ])->save();

        return $category;
    }

    private function createParserCategory(
        string $key = 'plumbers',
        string $name = 'Сантехники',
        int $sortOrder = 10,
        int $rubricId = 123,
    ): ParserCategory {
        $category = $this->createCategory($key, $name);
        $configuration = new ParserCategory;
        $configuration->forceFill([
            'category_id' => $category->id,
            'seed_paths' => ["category/{$key}--{$rubricId}"],
            'is_active' => true,
            'sort_order' => $sortOrder,
            'created_at' => '2026-08-31 10:00:00',
            'updated_at' => '2026-08-31 10:00:00',
        ])->save();

        return $configuration;
    }
}
