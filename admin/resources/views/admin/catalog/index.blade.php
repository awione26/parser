@extends('app')

@section('title', $title)

@section('css')
    <link rel="stylesheet" href="{{ asset('plugins/datatables-bs4/css/dataTables.bootstrap4.min.css') }}">
    <link rel="stylesheet" href="{{ asset('plugins/datatables-responsive/css/responsive.bootstrap4.min.css') }}">
    <style>
        #yandex-catalog td { vertical-align: top; }
        #yandex-catalog td.catalog-node { min-width: 190px; }
        #yandex-catalog td.catalog-node code,
        #yandex-catalog td.catalog-slug { overflow-wrap: anywhere; white-space: normal; }
        #yandex-catalog td.catalog-group { min-width: 155px; }
        #yandex-catalog td.catalog-status { min-width: 135px; }
        #yandex-catalog td.catalog-parsing { min-width: 170px; }
        #yandex-catalog td.catalog-actions { min-width: 105px; }

        .catalog-filter-actions {
            display: flex;
            gap: .5rem;
            justify-content: flex-end;
        }

        .catalog-filter-actions .btn { min-width: 120px; }

        @media (max-width: 575.98px) {
            .catalog-filter-actions .btn {
                flex: 1 1 0;
                min-width: 0;
            }
        }
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
                    <h2 class="card-title font-weight-bold">
                        <i class="fas fa-filter mr-2" aria-hidden="true"></i>
                        Фильтры
                    </h2>
                    <div class="card-tools">
                        <button
                            type="button"
                            class="btn btn-tool"
                            data-card-widget="collapse"
                            aria-label="Свернуть фильтры"
                        >
                            <i class="fas fa-minus" aria-hidden="true"></i>
                        </button>
                    </div>
                </div>
                <div class="card-body">
                    <form id="catalog-filters" autocomplete="off">
                        <div class="form-row align-items-end">
                            <div class="form-group col-xl-3 col-md-6">
                                <label class="filter-label" for="catalog-q">Поиск</label>
                                <input
                                    id="catalog-q"
                                    type="search"
                                    value="{{ $filters['q'] ?? '' }}"
                                    class="form-control"
                                    maxlength="200"
                                    placeholder="Название, slug или ID"
                                >
                            </div>
                            <div class="form-group col-xl-3 col-md-6">
                                <label class="filter-label" for="catalog-group">Группа мастеров</label>
                                <select id="catalog-group" class="custom-select">
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
                                <select id="catalog-status" class="custom-select">
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
                                <select id="catalog-has-id" class="custom-select">
                                    <option value="">Неважно</option>
                                    <option value="1" @selected(($filters['has_id'] ?? '') === '1')>Есть</option>
                                    <option value="0" @selected(($filters['has_id'] ?? '') === '0')>Нет</option>
                                </select>
                            </div>
                            <div class="form-group col-xl-2 col-md-4">
                                <label class="filter-label" for="catalog-used">Участие в парсинге</label>
                                <select id="catalog-used" class="custom-select">
                                    <option value="">Неважно</option>
                                    <option value="1" @selected(($filters['used_for_parsing'] ?? '') === '1')>Участвует</option>
                                    <option value="0" @selected(($filters['used_for_parsing'] ?? '') === '0')>Не участвует</option>
                                </select>
                            </div>
                        </div>
                        <div class="catalog-filter-actions">
                            <button type="submit" class="btn btn-info">
                                <i class="fas fa-search mr-1" aria-hidden="true"></i>
                                Применить
                            </button>
                            <button id="reset-catalog-filters" type="button" class="btn btn-outline-secondary">
                                Сбросить
                            </button>
                        </div>
                    </form>
                </div>
            </div>

            <div class="card">
                <div class="card-header d-flex flex-wrap align-items-center justify-content-end">
                    <a href="{{ route('admin.catalog.create') }}" class="btn btn-primary btn-sm">
                        <i class="fas fa-plus mr-1" aria-hidden="true"></i>
                        Добавить категорию
                    </a>
                </div>
                <div class="card-body">
                    <div id="catalog-table-error" class="alert alert-danger d-none" role="alert">
                        Не удалось загрузить Яндекс.Каталог. Проверьте соединение с БД парсера.
                    </div>
                    <div class="table-responsive">
                        <table id="yandex-catalog" class="table table-bordered table-striped table-hover w-100">
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
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </section>
@endsection

@section('js')
    <script src="{{ asset('plugins/datatables/jquery.dataTables.min.js') }}"></script>
    <script src="{{ asset('plugins/datatables-bs4/js/dataTables.bootstrap4.min.js') }}"></script>
    <script src="{{ asset('plugins/datatables-responsive/js/dataTables.responsive.min.js') }}"></script>
    <script src="{{ asset('plugins/datatables-responsive/js/responsive.bootstrap4.min.js') }}"></script>
    <script>
        $(function () {
            const catalog = $('#yandex-catalog');

            function filterValues() {
                return {
                    q: $('#catalog-q').val().trim(),
                    group: $('#catalog-group').val() || '',
                    status: $('#catalog-status').val() || '',
                    has_id: $('#catalog-has-id').val() || '',
                    used_for_parsing: $('#catalog-used').val() || ''
                };
            }

            catalog.on('preXhr.dt', function () {
                $('#catalog-table-error').addClass('d-none');
            });

            catalog.on('xhr.dt', function (event, settings, json) {
                if (json) {
                    $('#catalog-table-error').addClass('d-none');
                }
            });

            const table = catalog.DataTable({
                processing: true,
                serverSide: true,
                searching: false,
                responsive: true,
                autoWidth: false,
                pageLength: 25,
                lengthMenu: [25, 50, 100],
                order: [[0, 'asc']],
                ajax: {
                    url: @json(route('admin.datatable.catalog')),
                    data: function (data) {
                        Object.assign(data, filterValues());
                    },
                    error: function () {
                        $('#catalog-table-error').removeClass('d-none');
                    }
                },
                language: {
                    processing: 'Загрузка…',
                    lengthMenu: 'Показывать по _MENU_',
                    info: 'Записи _START_–_END_ из _TOTAL_',
                    infoEmpty: 'Нет записей',
                    infoFiltered: '(из _MAX_)',
                    zeroRecords: 'Ничего не найдено',
                    emptyTable: 'Категории пока не добавлены',
                    paginate: {
                        first: 'Первая',
                        last: 'Последняя',
                        next: 'Следующая',
                        previous: 'Предыдущая'
                    }
                },
                columns: [
                    {data: 'group', name: 'category_name', className: 'catalog-group', searchable: false},
                    {data: 'occupation', name: 'occupation_name', className: 'catalog-node', searchable: false},
                    {data: 'specialization', name: 'specialization_name', className: 'catalog-node', searchable: false},
                    {data: 'service', name: 'service_name', className: 'catalog-node', searchable: false},
                    {data: 'slug_url', name: 'target_slug', className: 'catalog-slug', searchable: false},
                    {data: 'status', name: 'target_verification_status', className: 'catalog-status', searchable: false},
                    {data: 'parsing', name: 'used_for_parsing', className: 'catalog-parsing', searchable: false},
                    {
                        data: 'actions',
                        className: 'catalog-actions text-nowrap',
                        orderable: false,
                        searchable: false
                    }
                ]
            });

            $('#catalog-filters').on('submit', function (event) {
                event.preventDefault();
                $('#catalog-table-error').addClass('d-none');
                table.draw();
            });

            $('#reset-catalog-filters').on('click', function () {
                $('#catalog-q, #catalog-group, #catalog-status, #catalog-has-id, #catalog-used').val('');
                $('#catalog-table-error').addClass('d-none');
                table.draw();
            });
        });
    </script>
@endsection
