<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Database\Query\Builder;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Testing\TestResponse;
use OpenSpout\Common\Entity\Cell;
use OpenSpout\Common\Entity\Cell\StringCell;
use OpenSpout\Reader\XLSX\Reader;
use Symfony\Component\HttpFoundation\BinaryFileResponse;
use Symfony\Component\HttpFoundation\StreamedResponse;
use Tests\Concerns\CreatesParserSchema;
use Tests\TestCase;
use ZipArchive;

class ProfessionalManagementTest extends TestCase
{
    use CreatesParserSchema;
    use RefreshDatabase;

    private int $categorySequence = 0;

    private int $professionalSequence = 0;

    /** @var array<int, int> */
    private array $categoryRubricIds = [];

    protected function setUp(): void
    {
        parent::setUp();

        config()->set('parser.connection', 'sqlite');
        $this->createParserSchema();
    }

    public function test_guest_cannot_delete_professionals(): void
    {
        $professionalId = $this->seedProfessional();

        $this->delete(route('admin.professionals.destroy', $professionalId))
            ->assertRedirect(route('login'));

        $this->delete(route('admin.professionals.bulk-destroy'), [
            'ids' => [$professionalId],
        ])->assertRedirect(route('login'));

        $this->assertProfessionalExists($professionalId);
    }

    public function test_viewer_cannot_delete_professionals(): void
    {
        $viewer = User::factory()->create(['role' => User::ROLE_VIEWER]);
        $professionalId = $this->seedProfessional();

        $this->actingAs($viewer)
            ->deleteJson(route('admin.professionals.destroy', $professionalId))
            ->assertForbidden();

        $this->actingAs($viewer)
            ->deleteJson(route('admin.professionals.bulk-destroy'), [
                'ids' => [$professionalId],
            ])
            ->assertForbidden();

        $this->assertProfessionalExists($professionalId);
    }

    public function test_admin_can_delete_one_professional_with_category_links_and_rubrics(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);
        $categoryId = $this->seedCategory();
        $deletedId = $this->seedProfessional([], $categoryId);
        $remainingId = $this->seedProfessional([], $categoryId);

        $this->actingAs($admin)
            ->deleteJson(route('admin.professionals.destroy', $deletedId))
            ->assertOk()
            ->assertJsonPath('deleted', 1);

        $this->assertDatabaseMissing('professionals', ['id' => $deletedId], $this->parserConnection());
        $this->assertDatabaseMissing('professional_categories', [
            'professional_id' => $deletedId,
        ], $this->parserConnection());
        $this->assertDatabaseMissing('professional_category_rubrics', [
            'professional_id' => $deletedId,
        ], $this->parserConnection());

        $this->assertProfessionalExists($remainingId);
        $this->assertDatabaseHas('professional_categories', [
            'professional_id' => $remainingId,
            'category_id' => $categoryId,
        ], $this->parserConnection());
        $this->assertDatabaseHas('professional_category_rubrics', [
            'professional_id' => $remainingId,
            'category_id' => $categoryId,
        ], $this->parserConnection());
        $this->assertDatabaseHas('categories', ['id' => $categoryId], $this->parserConnection());
    }

    public function test_admin_can_bulk_delete_only_selected_professionals(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);
        $categoryId = $this->seedCategory();
        $firstDeletedId = $this->seedProfessional([], $categoryId);
        $remainingId = $this->seedProfessional([], $categoryId);
        $secondDeletedId = $this->seedProfessional([], $categoryId);

        $this->actingAs($admin)
            ->deleteJson(route('admin.professionals.bulk-destroy'), [
                'ids' => [$firstDeletedId, $secondDeletedId],
            ])
            ->assertOk()
            ->assertJsonPath('deleted', 2);

        foreach ([$firstDeletedId, $secondDeletedId] as $deletedId) {
            $this->assertDatabaseMissing('professionals', ['id' => $deletedId], $this->parserConnection());
            $this->assertDatabaseMissing('professional_categories', [
                'professional_id' => $deletedId,
            ], $this->parserConnection());
            $this->assertDatabaseMissing('professional_category_rubrics', [
                'professional_id' => $deletedId,
            ], $this->parserConnection());
        }

        $this->assertProfessionalExists($remainingId);
        $this->assertDatabaseHas('professional_categories', [
            'professional_id' => $remainingId,
            'category_id' => $categoryId,
        ], $this->parserConnection());
        $this->assertDatabaseHas('professional_category_rubrics', [
            'professional_id' => $remainingId,
            'category_id' => $categoryId,
        ], $this->parserConnection());
    }

    public function test_bulk_delete_rejects_empty_duplicate_and_non_integer_ids(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);
        $professionalId = $this->seedProfessional();

        $invalidPayloads = [
            [],
            ['ids' => []],
            ['ids' => [$professionalId, $professionalId]],
            ['ids' => ['not-an-integer']],
        ];

        foreach ($invalidPayloads as $payload) {
            $this->actingAs($admin)
                ->deleteJson(route('admin.professionals.bulk-destroy'), $payload)
                ->assertUnprocessable();

            $this->assertProfessionalExists($professionalId);
        }
    }

    public function test_bulk_delete_rejects_more_than_500_ids(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);
        $professionalId = $this->seedProfessional();

        $this->actingAs($admin)
            ->deleteJson(route('admin.professionals.bulk-destroy'), [
                'ids' => array_fill(0, 501, $professionalId),
            ])
            ->assertUnprocessable()
            ->assertJsonValidationErrors('ids');

        $this->assertProfessionalExists($professionalId);
    }

    public function test_bulk_delete_rejects_nonexistent_id_without_partial_delete(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);
        $professionalId = $this->seedProfessional();

        $this->actingAs($admin)
            ->deleteJson(route('admin.professionals.bulk-destroy'), [
                'ids' => [$professionalId, 999_999],
            ])
            ->assertUnprocessable()
            ->assertJsonValidationErrors('ids.1');

        $this->assertProfessionalExists($professionalId);
    }

    public function test_delete_routes_require_a_valid_csrf_token(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);
        $singleId = $this->seedProfessional();
        $bulkId = $this->seedProfessional();
        $testingEnvironment = $this->app['env'];
        $token = 'known-test-csrf-token';

        $this->app['env'] = 'production';

        try {
            $this->actingAs($admin)
                ->withSession(['_token' => $token])
                ->deleteJson(route('admin.professionals.destroy', $singleId))
                ->assertStatus(419);

            $this->actingAs($admin)
                ->withSession(['_token' => $token])
                ->deleteJson(route('admin.professionals.bulk-destroy'), [
                    'ids' => [$bulkId],
                ])
                ->assertStatus(419);

            $this->assertProfessionalExists($singleId);
            $this->assertProfessionalExists($bulkId);

            $this->actingAs($admin)
                ->withSession(['_token' => $token])
                ->withHeader('X-CSRF-TOKEN', $token)
                ->deleteJson(route('admin.professionals.destroy', $singleId))
                ->assertOk();

            $this->actingAs($admin)
                ->withSession(['_token' => $token])
                ->withHeader('X-CSRF-TOKEN', $token)
                ->deleteJson(route('admin.professionals.bulk-destroy'), [
                    'ids' => [$bulkId],
                ])
                ->assertOk();
        } finally {
            $this->app['env'] = $testingEnvironment;
        }

        $this->assertDatabaseMissing('professionals', ['id' => $singleId], $this->parserConnection());
        $this->assertDatabaseMissing('professionals', ['id' => $bulkId], $this->parserConnection());
    }

    public function test_management_controls_are_visible_only_to_admin(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);
        $viewer = User::factory()->create(['role' => User::ROLE_VIEWER]);

        $this->actingAs($admin)
            ->get(route('admin.professionals.index'))
            ->assertOk()
            ->assertSee('Удалить выбранных')
            ->assertSee('Экспорт', false);

        $this->actingAs($viewer)
            ->get(route('admin.professionals.index'))
            ->assertOk()
            ->assertDontSee('Удалить выбранных')
            ->assertDontSee(route('admin.professionals.export'), false)
            ->assertDontSee(route('admin.professionals.bulk-destroy'), false);
    }

    public function test_export_is_available_only_to_admin(): void
    {
        $professionalId = $this->seedProfessional();

        $this->get(route('admin.professionals.export'))
            ->assertRedirect(route('login'));

        $viewer = User::factory()->create(['role' => User::ROLE_VIEWER]);

        $this->actingAs($viewer)
            ->get(route('admin.professionals.export'))
            ->assertForbidden();

        $this->assertProfessionalExists($professionalId);
    }

    public function test_admin_downloads_xlsx_with_expected_headers_and_safe_string_cells(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);
        $this->seedProfessional([
            'full_name' => '=formula',
            'phone' => '+79991234567',
            'city' => 'Москва',
            'region' => 'Москва',
            'country' => 'Россия',
            'age' => 38,
            'gender' => 'male',
            'experience_text' => 'Более 10 лет',
            'photo_url' => 'https://avatars.mds.yandex.net/get-ydo/fixture',
            'source' => 'uslugi.yandex.ru',
        ]);

        $response = $this->actingAs($admin)
            ->get(route('admin.professionals.export'))
            ->assertOk();

        $this->assertSame(
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            $response->headers->get('Content-Type'),
        );
        $this->assertMatchesRegularExpression(
            '/\Aattachment;\s*filename="?[^"]+\.xlsx"?\z/i',
            (string) $response->headers->get('Content-Disposition'),
        );

        $rows = $this->readWorkbook($response);

        $this->assertCount(2, $rows);
        $this->assertSame([
            'ФИО',
            'Телефон',
            'Город',
            'Область',
            'Страна',
            'Возраст',
            'Пол',
            'Опыт',
            'Фото',
            'Ресурс',
        ], $this->cellValues($rows[0]));

        $this->assertSame('=formula', $rows[1][0]->getValue());
        $this->assertSame('+79991234567', $rows[1][1]->getValue());
        $this->assertInstanceOf(StringCell::class, $rows[1][1]);
    }

    public function test_export_applies_registry_filters_and_ignores_unmatched_rows(): void
    {
        $admin = User::factory()->create(['role' => User::ROLE_ADMIN]);
        $matchingCategoryId = $this->seedCategory(['name' => 'Сантехники']);
        $otherCategoryId = $this->seedCategory(['name' => 'Электрики']);

        $this->seedProfessional([
            'full_name' => 'Иван Нужный',
            'city' => 'Москва',
        ], $matchingCategoryId);
        $this->seedProfessional([
            'full_name' => 'Иван Другой город',
            'city' => 'Казань',
        ], $matchingCategoryId);
        $this->seedProfessional([
            'full_name' => 'Иван Другая категория',
            'city' => 'Москва',
        ], $otherCategoryId);
        $this->seedProfessional([
            'full_name' => 'Пётр Не совпал с поиском',
            'city' => 'Москва',
        ], $matchingCategoryId);

        $response = $this->actingAs($admin)->get(route('admin.professionals.export', [
            'search' => ['value' => 'Иван'],
            'catalog_target' => 'specialization:'.$this->categoryRubricIds[$matchingCategoryId],
            'city' => 'Москва',
        ]));

        $response->assertOk();
        $rows = $this->readWorkbook($response);

        $this->assertCount(2, $rows);
        $this->assertSame('Иван Нужный', $rows[1][0]->getValue());
    }

    /**
     * @param  array<string, mixed>  $overrides
     */
    private function seedCategory(array $overrides = []): int
    {
        $this->categorySequence++;
        $now = '2026-08-27 12:00:00';

        $categoryId = (int) $this->parserTable('categories')->insertGetId(array_merge([
            'key' => "category-{$this->categorySequence}",
            'name' => "Категория {$this->categorySequence}",
            'note' => null,
            'created_at' => $now,
            'updated_at' => $now,
        ], $overrides));
        $rubricId = 20_000 + $this->categorySequence;
        $specializationId = (int) $this->parserTable('yandex_specializations')->insertGetId([
            'occupation_id' => null,
            'external_id_raw' => "/specialization/{$rubricId}",
            'external_number_id' => $rubricId,
            'slug' => "specialization-{$rubricId}",
            'name' => "Яндекс категория {$this->categorySequence}",
            'source_url' => "https://uslugi.yandex.ru/213-moscow/category/catalog/specialization-{$rubricId}--{$rubricId}",
            'verification_status' => 'confirmed',
            'created_at' => $now,
            'updated_at' => $now,
        ]);
        $this->parserTable('category_yandex_specializations')->insert([
            'category_id' => $categoryId,
            'specialization_id' => $specializationId,
            'sort_order' => 10,
        ]);
        $relativePath = "catalog/specialization-{$rubricId}--{$rubricId}";
        $this->parserTable('parser_categories')->insert([
            'category_id' => $categoryId,
            'seed_paths' => json_encode([$relativePath]),
            'is_active' => true,
            'sort_order' => $this->categorySequence * 10,
            'created_at' => $now,
            'updated_at' => $now,
        ]);
        $this->parserTable('parser_category_targets')->insert([
            'category_id' => $categoryId,
            'taxonomy_level' => 'specialization',
            'source_rubric_number_id' => $rubricId,
            'relative_path' => $relativePath,
            'is_active' => true,
            'sort_order' => 10,
            'created_at' => $now,
            'updated_at' => $now,
        ]);
        $this->categoryRubricIds[$categoryId] = $rubricId;

        return $categoryId;
    }

    /**
     * @param  array<string, mixed>  $overrides
     */
    private function seedProfessional(array $overrides = [], ?int $categoryId = null): int
    {
        $this->professionalSequence++;
        $sequence = $this->professionalSequence;
        $now = '2026-08-27 12:00:00';

        $professionalId = (int) $this->parserTable('professionals')->insertGetId(array_merge([
            'source' => 'uslugi.yandex.ru',
            'source_profile_id' => "worker-{$sequence}",
            'profile_url' => "https://uslugi.yandex.ru/profile/Worker-{$sequence}",
            'full_name' => "Мастер {$sequence}",
            'phone' => "+7999000000{$sequence}",
            'phone_status' => 'published',
            'city' => 'Москва',
            'region' => 'Москва',
            'country' => 'Россия',
            'age' => 38,
            'age_as_of' => '2026-08-27',
            'gender' => 'male',
            'experience_code' => 11,
            'experience_text' => 'Более 10 лет',
            'photo_url' => "https://avatars.mds.yandex.net/get-ydo/{$sequence}",
            'account_type' => 'person',
            'content_hash' => str_repeat((string) ($sequence % 10), 64),
            'parser_version' => '1.0.0',
            'first_seen_at' => $now,
            'last_seen_at' => $now,
            'last_scraped_at' => $now,
        ], $overrides));

        if ($categoryId !== null) {
            $rubricId = $this->categoryRubricIds[$categoryId];
            $this->parserTable('professional_categories')->insert([
                'professional_id' => $professionalId,
                'category_id' => $categoryId,
                'first_seen_at' => $now,
                'last_seen_at' => $now,
            ]);
            $this->parserTable('professional_category_rubrics')->insert([
                'professional_id' => $professionalId,
                'category_id' => $categoryId,
                'source_rubric_number_id' => $rubricId,
                'source_rubric_level' => 'specialization',
                'source_rubric_id' => "/rubric/{$rubricId}",
                'source_rubric_seo_id' => "rubric-{$rubricId}",
                'source_rubric_name' => "Название профиля {$sequence}",
                'experience_code' => 11,
                'experience_text' => 'Более 10 лет',
                'first_seen_at' => $now,
                'last_seen_at' => $now,
            ]);
        }

        return $professionalId;
    }

    private function parserConnection(): string
    {
        return (string) config('parser.connection');
    }

    private function parserTable(string $table): Builder
    {
        return DB::connection($this->parserConnection())->table($table);
    }

    private function assertProfessionalExists(int $professionalId): void
    {
        $this->assertDatabaseHas('professionals', [
            'id' => $professionalId,
        ], $this->parserConnection());
    }

    /**
     * @return list<list<Cell>>
     */
    private function readWorkbook(TestResponse $response): array
    {
        $path = tempnam(sys_get_temp_dir(), 'professionals-xlsx-');
        $this->assertNotFalse($path);
        $content = $this->responseContent($response);
        $this->assertStringStartsWith('PK', $content);
        file_put_contents($path, $content);
        $this->assertWorkbookHasNoFormulaNodes($path);

        $reader = new Reader;
        $rows = [];

        try {
            $reader->open($path);

            foreach ($reader->getSheetIterator() as $sheet) {
                foreach ($sheet->getRowIterator() as $row) {
                    $rows[] = $row->getCells();
                }

                break;
            }
        } finally {
            $reader->close();
            @unlink($path);
        }

        return $rows;
    }

    private function assertWorkbookHasNoFormulaNodes(string $path): void
    {
        $archive = new ZipArchive;
        $this->assertTrue($archive->open($path));

        try {
            for ($index = 0; $index < $archive->numFiles; $index++) {
                $name = (string) $archive->getNameIndex($index);
                if (! str_starts_with($name, 'xl/worksheets/') || ! str_ends_with($name, '.xml')) {
                    continue;
                }

                $xml = $archive->getFromIndex($index);
                $this->assertIsString($xml);
                $this->assertDoesNotMatchRegularExpression(
                    '/<(?:[A-Za-z_][A-Za-z0-9_.-]*:)?f(?:\s|>)/',
                    $xml,
                    "Лист {$name} не должен содержать исполняемые формулы.",
                );
            }
        } finally {
            $archive->close();
        }
    }

    private function responseContent(TestResponse $response): string
    {
        if ($response->baseResponse instanceof StreamedResponse) {
            return $response->streamedContent();
        }

        if ($response->baseResponse instanceof BinaryFileResponse) {
            return (string) file_get_contents($response->baseResponse->getFile()->getPathname());
        }

        return (string) $response->getContent();
    }

    /**
     * @param  list<Cell>  $cells
     * @return list<bool|\DateInterval|\DateTimeInterface|float|int|string|null>
     */
    private function cellValues(array $cells): array
    {
        return array_map(static fn (Cell $cell): mixed => $cell->getValue(), $cells);
    }
}
