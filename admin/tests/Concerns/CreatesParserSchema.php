<?php

namespace Tests\Concerns;

use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

trait CreatesParserSchema
{
    protected function createParserSchema(): void
    {
        $schema = Schema::connection((string) config('parser.connection'));

        $schema->create('logs', function (Blueprint $table): void {
            $table->id();
            $table->dateTime('started_at');
            $table->dateTime('finished_at')->nullable();
            $table->string('result', 16)->nullable();
            $table->text('error_reason')->nullable();
            $table->string('resource', 255);
            $table->index('started_at');
            $table->index(['result', 'started_at']);
            $table->index(['resource', 'started_at']);
        });

        $schema->create('categories', function (Blueprint $table): void {
            $table->id();
            $table->string('key')->unique();
            $table->string('name');
            $table->text('note')->nullable();
            $table->timestamps();
        });

        $schema->create('professionals', function (Blueprint $table): void {
            $table->id();
            $table->string('source');
            $table->string('source_profile_id');
            $table->text('profile_url');
            $table->string('full_name')->nullable();
            $table->string('phone', 32)->nullable();
            $table->string('phone_status', 32)->default('missing');
            $table->string('city')->nullable();
            $table->string('region')->nullable();
            $table->string('country')->nullable();
            $table->smallInteger('age')->nullable();
            $table->date('age_as_of');
            $table->string('gender', 16)->nullable();
            $table->smallInteger('experience_code')->nullable();
            $table->string('experience_text', 64)->nullable();
            $table->text('photo_url')->nullable();
            $table->string('account_type', 32)->nullable();
            $table->string('content_hash', 64);
            $table->string('parser_version', 32);
            $table->dateTime('first_seen_at');
            $table->dateTime('last_seen_at');
            $table->dateTime('last_scraped_at');
            $table->unique(['source', 'source_profile_id']);
        });

        $schema->create('professional_categories', function (Blueprint $table): void {
            $table->unsignedBigInteger('professional_id');
            $table->unsignedBigInteger('category_id');
            $table->dateTime('first_seen_at');
            $table->dateTime('last_seen_at');
            $table->primary(['professional_id', 'category_id']);
            $table->foreign('professional_id')
                ->references('id')
                ->on('professionals')
                ->cascadeOnDelete();
            $table->foreign('category_id')
                ->references('id')
                ->on('categories')
                ->cascadeOnDelete();
        });

        $schema->create('professional_category_rubrics', function (Blueprint $table): void {
            $table->unsignedBigInteger('professional_id');
            $table->unsignedBigInteger('category_id');
            $table->integer('source_rubric_number_id');
            $table->string('source_rubric_id')->nullable();
            $table->string('source_rubric_seo_id')->nullable();
            $table->string('source_rubric_name')->nullable();
            $table->smallInteger('experience_code')->nullable();
            $table->string('experience_text', 64)->nullable();
            $table->dateTime('first_seen_at');
            $table->dateTime('last_seen_at');
            $table->primary(['professional_id', 'category_id', 'source_rubric_number_id']);
            $table->foreign(['professional_id', 'category_id'])
                ->references(['professional_id', 'category_id'])
                ->on('professional_categories')
                ->cascadeOnDelete();
        });
    }
}
