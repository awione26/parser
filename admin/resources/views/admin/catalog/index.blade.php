@extends('app')

@section('title', $title)

@section('css')
    <style>
        .catalog-node { min-width: 190px; }
        .catalog-node code, .catalog-slug { overflow-wrap: anywhere; white-space: normal; }
        .catalog-group { min-width: 155px; }
        .catalog-status { min-width: 135px; }
        .catalog-parsing { min-width: 170px; }
        .catalog-actions { min-width: 105px; }
    </style>
@endsection

@section('content')
    <section class="content">
        <div class="container-fluid">
            <div class="alert alert-info">
                <i class="fas fa-info-circle mr-1" aria-hidden="true"></i>
                Яндекс.Каталог является единственным источником категорий для массового парсинга
                Яндекс Услуг. Включить можно только проверенную строку с согласованными
                slug, числовым ID и канонической ссылкой на uslugi.yandex.ru. Телефоны
                при массовом обходе каталога не извлекаются.
            </div>

            <div class="card card-outline card-info">
                <div class="card-header">
                    <h2 class="card-title">
                        <i class="fas fa-filter mr-1" aria-hidden="true"></i>
                        Фильтры
                    </h2>
                </div>
                <div class="card-body">
                    <form method="get" action="{{ route('admin.catalog.index') }}">
                        <div class="form-row align-items-end">
                            <div class="form-group col-xl-3 col-md-6">
                                <label class="filter-label" for="catalog-q">Поиск</label>
                                <input
                                    id="catalog-q"
                                    type="search"
                                    name="q"
                                    value="{{ $filters['q'] ?? '' }}"
                                    class="form-control"
                                    maxlength="200"
                                    placeholder="Название, slug или ID"
                                >
                            </div>
                            <div class="form-group col-xl-3 col-md-6">
                                <label class="filter-label" for="catalog-group">Группа мастеров</label>
                                <select id="catalog-group" name="group" class="custom-select">
                                    <option value="">Все группы</option>
                                    @foreach ($groups as $group)
                                        <option
                                            value="{{ $group->id }}"
                                            @selected((string) ($filters['group'] ?? '') === (string) $group->id)
                                        >
                                            {{ $group->name }}
                                        </option>
                                    @endforeach
                                </select>
                            </div>
                            <div class="form-group col-xl-2 col-md-4">
                                <label class="filter-label" for="catalog-status">Статус проверки</label>
                                <select id="catalog-status" name="status" class="custom-select">
                                    <option value="">Все статусы</option>
                                    @foreach ($statusOptions as $value => $label)
                                        <option value="{{ $value }}" @selected(($filters['status'] ?? '') === $value)>
                                            {{ $label }}
                                        </option>
                                    @endforeach
                                </select>
                            </div>
                            <div class="form-group col-xl-2 col-md-4">
                                <label class="filter-label" for="catalog-has-id">Внешний ID</label>
                                <select id="catalog-has-id" name="has_id" class="custom-select">
                                    <option value="">Неважно</option>
                                    <option value="1" @selected(($filters['has_id'] ?? '') === '1')>Есть</option>
                                    <option value="0" @selected(($filters['has_id'] ?? '') === '0')>Нет</option>
                                </select>
                            </div>
                            <div class="form-group col-xl-2 col-md-4">
                                <label class="filter-label" for="catalog-used">Участие в парсинге</label>
                                <select id="catalog-used" name="used_for_parsing" class="custom-select">
                                    <option value="">Неважно</option>
                                    <option value="1" @selected(($filters['used_for_parsing'] ?? '') === '1')>Участвует</option>
                                    <option value="0" @selected(($filters['used_for_parsing'] ?? '') === '0')>Не участвует</option>
                                </select>
                            </div>
                        </div>
                        <div class="d-flex flex-wrap justify-content-end">
                            <a href="{{ route('admin.catalog.index') }}" class="btn btn-outline-secondary mr-2">
                                Сбросить
                            </a>
                            <button type="submit" class="btn btn-info">
                                <i class="fas fa-search mr-1" aria-hidden="true"></i>
                                Применить
                            </button>
                        </div>
                    </form>
                </div>
            </div>

            <div class="card">
                <div class="card-header d-flex flex-wrap align-items-center justify-content-between">
                    <span>Найдено строк: <strong>{{ $rows->total() }}</strong></span>
                    <a href="{{ route('admin.catalog.create') }}" class="btn btn-primary btn-sm">
                        <i class="fas fa-plus mr-1" aria-hidden="true"></i>
                        Добавить категорию
                    </a>
                </div>
                <div class="card-body p-0">
                    <div class="table-responsive">
                        <table class="table table-bordered table-striped table-hover mb-0">
                            <caption class="sr-only">
                                Нормализованный каталог направлений, специализаций и услуг Яндекса
                            </caption>
                            <thead>
                            <tr>
                                <th scope="col">Группа</th>
                                <th scope="col">Направление / occupationId</th>
                                <th scope="col">Специализация / specId</th>
                                <th scope="col">Услуга / serviceId</th>
                                <th scope="col">Slug / URL</th>
                                <th scope="col">Статус</th>
                                <th scope="col">Парсинг</th>
                                <th scope="col">Действия</th>
                            </tr>
                            </thead>
                            <tbody>
                            @forelse ($rows as $row)
                                <tr>
                                    <td class="catalog-group">
                                        <strong>{{ $row->category_name }}</strong>
                                        <div><code>{{ $row->category_key }}</code></div>
                                    </td>
                                    <td class="catalog-node">
                                        @if ($row->occupation_name)
                                            <div>{{ $row->occupation_name }}</div>
                                            @if ($row->occupation_external_id_raw)
                                                <small class="d-block text-muted">
                                                    occupationId: <code>{{ $row->occupation_external_id_raw }}</code>
                                                </small>
                                            @endif
                                            @if ($row->occupation_external_number_id)
                                                <small class="text-muted">№ {{ $row->occupation_external_number_id }}</small>
                                            @endif
                                        @else
                                            <span class="text-muted">—</span>
                                        @endif
                                    </td>
                                    <td class="catalog-node">
                                        @if ($row->specialization_name)
                                            <div>{{ $row->specialization_name }}</div>
                                            @if ($row->specialization_external_id_raw)
                                                <small class="d-block text-muted">
                                                    specId: <code>{{ $row->specialization_external_id_raw }}</code>
                                                </small>
                                            @endif
                                            @if ($row->specialization_external_number_id)
                                                <small class="text-muted">№ {{ $row->specialization_external_number_id }}</small>
                                            @endif
                                        @else
                                            <span class="text-muted">—</span>
                                        @endif
                                    </td>
                                    <td class="catalog-node">
                                        @if ($row->service_name)
                                            <div>{{ $row->service_name }}</div>
                                            @if ($row->service_external_id_raw)
                                                <small class="d-block text-muted">
                                                    serviceId: <code>{{ $row->service_external_id_raw }}</code>
                                                </small>
                                            @endif
                                            @if ($row->service_external_number_id)
                                                <small class="text-muted">№ {{ $row->service_external_number_id }}</small>
                                            @endif
                                        @else
                                            <span class="text-muted">—</span>
                                        @endif
                                    </td>
                                    <td>
                                        @if ($row->target_slug)
                                            <code class="catalog-slug">{{ $row->target_slug }}</code>
                                        @else
                                            <span class="text-muted">slug не указан</span>
                                        @endif
                                        @if ($row->safe_source_url)
                                            <div class="mt-1">
                                                <a
                                                    href="{{ $row->safe_source_url }}"
                                                    target="_blank"
                                                    rel="noopener noreferrer nofollow"
                                                >
                                                    Открыть на uslugi.yandex.ru
                                                    <i class="fas fa-external-link-alt ml-1" aria-hidden="true"></i>
                                                </a>
                                            </div>
                                        @endif
                                    </td>
                                    <td class="catalog-status">
                                        <span class="badge badge-{{ $row->status_badge }}">
                                            {{ $row->status_label }}
                                        </span>
                                        <small class="d-block text-muted mt-1">
                                            @switch($row->taxonomy_level)
                                                @case('occupation') Направление @break
                                                @case('specialization') Специализация @break
                                                @case('service') Услуга @break
                                            @endswitch
                                        </small>
                                    </td>
                                    <td class="catalog-parsing">
                                        @if ($row->used_for_parsing)
                                            <span class="badge badge-success mb-2">
                                                <i class="fas fa-check mr-1" aria-hidden="true"></i>
                                                В парсинге
                                            </span>
                                        @else
                                            <span class="badge badge-light border mb-2">Не участвует</span>
                                        @endif

                                        @if ($row->can_toggle_parsing)
                                            <form
                                                method="post"
                                                action="{{ route('admin.catalog.parsing', [
                                                    'category' => $row->category_id,
                                                    'taxonomyLevel' => $row->taxonomy_level,
                                                    'catalogNode' => $row->target_catalog_id,
                                                ]) }}"
                                            >
                                                @csrf
                                                @method('PATCH')
                                                <input
                                                    type="hidden"
                                                    name="is_active"
                                                    value="{{ $row->used_for_parsing ? '0' : '1' }}"
                                                >
                                                <button
                                                    type="submit"
                                                    class="btn btn-sm {{ $row->used_for_parsing ? 'btn-outline-danger' : 'btn-outline-success' }}"
                                                >
                                                    {{ $row->used_for_parsing ? 'Исключить' : 'Включить' }}
                                                </button>
                                            </form>
                                        @else
                                            <small class="d-block text-muted">
                                                Недоступно: статус, slug, URL или ID не подтверждены
                                            </small>
                                        @endif
                                    </td>
                                    <td class="catalog-actions text-nowrap">
                                        <a
                                            href="{{ route('admin.catalog.edit', [
                                                'category' => $row->category_id,
                                                'taxonomyLevel' => $row->taxonomy_level,
                                                'catalogNode' => $row->target_catalog_id,
                                            ]) }}"
                                            class="btn btn-sm btn-primary"
                                            aria-label="Редактировать {{ $row->target_catalog_id }}"
                                        >
                                            <i class="fas fa-edit" aria-hidden="true"></i>
                                            <span class="sr-only">Редактировать</span>
                                        </a>
                                        <form
                                            method="post"
                                            class="d-inline"
                                            action="{{ route('admin.catalog.destroy', [
                                                'category' => $row->category_id,
                                                'taxonomyLevel' => $row->taxonomy_level,
                                                'catalogNode' => $row->target_catalog_id,
                                            ]) }}"
                                            onsubmit="return confirm('Удалить категорию из выбранной группы? Цель парсинга будет отключена, а справочный узел сохранится для истории.');"
                                        >
                                            @csrf
                                            @method('DELETE')
                                            <input type="hidden" name="confirmed" value="1">
                                            <button
                                                type="submit"
                                                class="btn btn-sm btn-danger"
                                                aria-label="Удалить {{ $row->target_catalog_id }}"
                                            >
                                                <i class="fas fa-trash" aria-hidden="true"></i>
                                                <span class="sr-only">Удалить</span>
                                            </button>
                                        </form>
                                    </td>
                                </tr>
                            @empty
                                <tr>
                                    <td colspan="8" class="text-center py-4">
                                        По заданным фильтрам записи не найдены.
                                    </td>
                                </tr>
                            @endforelse
                            </tbody>
                        </table>
                    </div>
                </div>
                @if ($rows->hasPages())
                    <div class="card-footer clearfix">
                        {{ $rows->onEachSide(1)->links('pagination::bootstrap-4') }}
                    </div>
                @endif
            </div>
        </div>
    </section>
@endsection
