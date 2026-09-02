<?php

namespace Tests\Feature;

use App\Models\User;
use DOMDocument;
use DOMElement;
use DOMXPath;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\DB;
use Tests\Concerns\CreatesParserSchema;
use Tests\TestCase;

class ProfessionalCatalogFilterGroupsTest extends TestCase
{
    use CreatesParserSchema;
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        config()->set('parser.connection', 'sqlite');
        $this->createParserSchema();
    }

    public function test_catalog_targets_are_grouped_in_parser_order_with_stable_target_order(): void
    {
        $this->actingAs(User::factory()->create(['role' => User::ROLE_VIEWER]));
        $now = '2026-09-02 12:00:00';

        $laterGroup = $this->seedGroup('Альфа-группа', 'alpha-group', 20, $now);
        $firstGroup = $this->seedGroup('Яндекс-группа', 'yandex-group', 10, $now);

        $this->seedSpecializationTarget(
            categoryId: $firstGroup,
            rubricId: 3002,
            name: 'Альфа-категория',
            targetSortOrder: 20,
            now: $now,
        );
        $this->seedSpecializationTarget(
            categoryId: $firstGroup,
            rubricId: 3001,
            name: 'Яндекс-категория',
            targetSortOrder: 10,
            now: $now,
        );
        $this->seedSpecializationTarget(
            categoryId: $laterGroup,
            rubricId: 4001,
            name: 'Единственная категория',
            targetSortOrder: 10,
            now: $now,
        );
        $sharedSpecialization = $this->seedSpecializationTarget(
            categoryId: $laterGroup,
            rubricId: 4002,
            name: 'Общая категория',
            targetSortOrder: 20,
            now: $now,
        );
        $this->linkSpecializationTarget(
            categoryId: $firstGroup,
            specializationId: $sharedSpecialization,
            rubricId: 4002,
            targetSortOrder: 30,
            now: $now,
        );
        $this->seedUnlinkedSpecializationTarget(
            categoryId: $firstGroup,
            rubricId: 5001,
            now: $now,
        );

        $response = $this->get(route('admin.professionals.index'));
        $response->assertOk()
            ->assertViewHas('catalogTargetGroups', function (Collection $groups): bool {
                if ($groups->pluck('name')->all() !== [
                    'Яндекс-группа',
                    'Альфа-группа',
                ]) {
                    return false;
                }

                return $groups[0]->targets->pluck('token')->all() === [
                    'specialization:3001',
                    'specialization:3002',
                    'specialization:4002',
                ]
                    && $groups[1]->targets->pluck('token')->all() === [
                        'specialization:4001',
                        'specialization:4002',
                    ];
            });

        $document = new DOMDocument;
        $previousErrors = libxml_use_internal_errors(true);
        $loaded = $document->loadHTML('<?xml encoding="UTF-8">'.$response->getContent());
        libxml_clear_errors();
        libxml_use_internal_errors($previousErrors);
        $this->assertTrue($loaded);

        $xpath = new DOMXPath($document);
        $optgroups = $xpath->query('//*[@id="filter-category"]/optgroup');
        $this->assertNotFalse($optgroups);
        $this->assertCount(2, $optgroups);
        $this->assertSame('Яндекс-группа', $optgroups->item(0)?->attributes?->getNamedItem('label')?->nodeValue);
        $this->assertSame('Альфа-группа', $optgroups->item(1)?->attributes?->getNamedItem('label')?->nodeValue);

        foreach ($optgroups as $optgroup) {
            $this->assertInstanceOf(DOMElement::class, $optgroup);
            $this->assertFalse($optgroup->hasAttribute('value'));
        }

        $firstGroupOptions = $xpath->query('./option', $optgroups->item(0));
        $secondGroupOptions = $xpath->query('./option', $optgroups->item(1));
        $rootOptions = $xpath->query('//*[@id="filter-category"]/option');
        $this->assertNotFalse($firstGroupOptions);
        $this->assertNotFalse($secondGroupOptions);
        $this->assertNotFalse($rootOptions);
        $this->assertSame(
            ['specialization:3001', 'specialization:3002', 'specialization:4002'],
            $this->optionValues($firstGroupOptions),
        );
        $this->assertSame(
            ['specialization:4001', 'specialization:4002'],
            $this->optionValues($secondGroupOptions),
        );
        $this->assertSame([''], $this->optionValues($rootOptions));
        $this->assertStringNotContainsString('specialization:5001', $response->getContent());
    }

    /**
     * Создать группу мастеров с конфигурацией парсера.
     */
    private function seedGroup(string $name, string $key, int $sortOrder, string $now): int
    {
        $categoryId = DB::connection('sqlite')->table('categories')->insertGetId([
            'key' => $key,
            'name' => $name,
            'created_at' => $now,
            'updated_at' => $now,
        ]);
        DB::connection('sqlite')->table('parser_categories')->insert([
            'category_id' => $categoryId,
            'seed_paths' => json_encode([]),
            'is_active' => true,
            'sort_order' => $sortOrder,
            'created_at' => $now,
            'updated_at' => $now,
        ]);

        return $categoryId;
    }

    /**
     * Добавить в группу одну категорию Яндекса и цель парсинга.
     */
    private function seedSpecializationTarget(
        int $categoryId,
        int $rubricId,
        string $name,
        int $targetSortOrder,
        string $now,
    ): int {
        $specializationId = DB::connection('sqlite')
            ->table('yandex_specializations')
            ->insertGetId([
                'occupation_id' => null,
                'external_id_raw' => "/category-{$rubricId}",
                'external_number_id' => $rubricId,
                'slug' => "/category-{$rubricId}",
                'name' => $name,
                'source_url' => "https://uslugi.yandex.ru/category/category-{$rubricId}--{$rubricId}",
                'verification_status' => 'confirmed',
                'created_at' => $now,
                'updated_at' => $now,
            ]);
        $this->linkSpecializationTarget(
            categoryId: $categoryId,
            specializationId: $specializationId,
            rubricId: $rubricId,
            targetSortOrder: $targetSortOrder,
            now: $now,
        );

        return $specializationId;
    }

    /**
     * Связать существующий узел каталога с группой и целью парсинга.
     */
    private function linkSpecializationTarget(
        int $categoryId,
        int $specializationId,
        int $rubricId,
        int $targetSortOrder,
        string $now,
    ): void {
        DB::connection('sqlite')->table('category_yandex_specializations')->insert([
            'category_id' => $categoryId,
            'specialization_id' => $specializationId,
            'sort_order' => $targetSortOrder,
        ]);
        DB::connection('sqlite')->table('parser_category_targets')->insert([
            'category_id' => $categoryId,
            'taxonomy_level' => 'specialization',
            'source_rubric_number_id' => $rubricId,
            'relative_path' => "category-{$rubricId}--{$rubricId}",
            'is_active' => true,
            'sort_order' => $targetSortOrder,
            'created_at' => $now,
            'updated_at' => $now,
        ]);
    }

    /**
     * Создать stale-цель без точной M:N-связи с группой.
     */
    private function seedUnlinkedSpecializationTarget(int $categoryId, int $rubricId, string $now): void
    {
        DB::connection('sqlite')->table('yandex_specializations')->insert([
            'occupation_id' => null,
            'external_id_raw' => "/stale-{$rubricId}",
            'external_number_id' => $rubricId,
            'slug' => "/stale-{$rubricId}",
            'name' => 'Несвязанная категория',
            'source_url' => "https://uslugi.yandex.ru/category/stale-{$rubricId}--{$rubricId}",
            'verification_status' => 'confirmed',
            'created_at' => $now,
            'updated_at' => $now,
        ]);
        DB::connection('sqlite')->table('parser_category_targets')->insert([
            'category_id' => $categoryId,
            'taxonomy_level' => 'specialization',
            'source_rubric_number_id' => $rubricId,
            'relative_path' => "stale-{$rubricId}--{$rubricId}",
            'is_active' => true,
            'sort_order' => 40,
            'created_at' => $now,
            'updated_at' => $now,
        ]);
    }

    /**
     * @return list<string>
     */
    private function optionValues(\DOMNodeList $options): array
    {
        $values = [];
        foreach ($options as $option) {
            if ($option instanceof DOMElement) {
                $values[] = $option->getAttribute('value');
            }
        }

        return $values;
    }
}
