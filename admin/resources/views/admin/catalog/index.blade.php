@extends('app')

@section('title', $title)

@section('css')
    <style>
        .catalog-node { min-width: 190px; }
        .catalog-node code, .catalog-slug { overflow-wrap: anywhere; white-space: normal; }
        .catalog-group { min-width: 155px; }
        .catalog-status { min-width: 135px; }
    </style>
@endsection

@section('content')
    <section class="content">
        <div class="container-fluid">
            <div class="alert alert-info">
                <i class="fas fa-info-circle mr-1" aria-hidden="true"></i>
                Read-only справочник построен по данным Яндекс Услуг. Строки направлений,
                специализаций и услуг показаны отдельно; отметка «В парсинге» означает,
                что активная цель входит в текущий план обхода.
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
                <div class="card-header">
                    Найдено строк: <strong>{{ $rows->total() }}</strong>
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
                                    <td class="text-nowrap">
                                        @if ($row->used_for_parsing)
                                            <span class="badge badge-success">
                                                <i class="fas fa-check mr-1" aria-hidden="true"></i>
                                                В парсинге
                                            </span>
                                        @else
                                            <span class="badge badge-light border">Не участвует</span>
                                        @endif
                                    </td>
                                </tr>
                            @empty
                                <tr>
                                    <td colspan="7" class="text-center py-4">
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
