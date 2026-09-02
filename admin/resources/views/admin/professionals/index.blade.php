@extends('app')

@section('title', 'Спарсенные данные')

@section('css')
    <link rel="stylesheet" href="{{ asset('plugins/datatables-bs4/css/dataTables.bootstrap4.min.css') }}">
    <link rel="stylesheet" href="{{ asset('plugins/datatables-responsive/css/responsive.bootstrap4.min.css') }}">
    <style>
        #professionals .selection-column { text-align:center; width:42px; }
        #professionals .professional-checkbox, #select-current-page { height:18px; width:18px; }
    </style>
@endsection

@section('content')
<section class="content">
    <div class="container-fluid">
        <div class="card card-outline card-primary">
            <div class="card-header">
                <h2 class="card-title font-weight-bold"><i class="fas fa-filter mr-2" aria-hidden="true"></i>Фильтры</h2>
                <div class="card-tools">
                    <button type="button" class="btn btn-tool" data-card-widget="collapse" aria-label="Свернуть фильтры"><i class="fas fa-minus" aria-hidden="true"></i></button>
                </div>
            </div>
            <div class="card-body">
                <form id="filters" autocomplete="off">
                    <div class="row">
                        <div class="col-lg-4 col-md-6 form-group">
                            <label class="filter-label" for="filter-search">ФИО, локация или ID профиля</label>
                            <input id="filter-search" class="form-control" type="search" placeholder="Начните вводить…">
                        </div>
                        <div class="col-lg-3 col-md-6 form-group">
                            <label class="filter-label" for="filter-category">Категория Яндекс.Каталога</label>
                            <select id="filter-category" class="custom-select">
                                <option value="">Все категории</option>
                                @foreach($catalogTargets as $target)
                                    <option value="{{ $target->token }}">
                                        {{ $target->name }} (№ {{ $target->external_number_id }})
                                    </option>
                                @endforeach
                            </select>
                        </div>
                        <div class="col-lg-2 col-md-4 form-group">
                            <label class="filter-label" for="filter-gender">Пол</label>
                            <select id="filter-gender" class="custom-select">
                                <option value="">Любой</option><option value="male">Мужской</option><option value="female">Женский</option><option value="other">Другой</option><option value="unknown">Не указан</option>
                            </select>
                        </div>
                        <div class="col-lg-3 col-md-4 form-group">
                            <label class="filter-label" for="filter-source">Ресурс</label>
                            <select id="filter-source" class="custom-select">
                                <option value="">Все ресурсы</option>
                                @foreach($sources as $source)<option value="{{ $source }}">{{ $source }}</option>@endforeach
                            </select>
                        </div>
                    </div>
                    <div class="row">
                        <div class="col-lg-2 col-md-4 form-group"><label class="filter-label" for="filter-country">Страна</label><input id="filter-country" class="form-control" type="text"></div>
                        <div class="col-lg-2 col-md-4 form-group"><label class="filter-label" for="filter-region">Область</label><input id="filter-region" class="form-control" type="text"></div>
                        <div class="col-lg-2 col-md-4 form-group"><label class="filter-label" for="filter-city">Город</label><input id="filter-city" class="form-control" type="text"></div>
                        <div class="col-lg-1 col-6 form-group"><label class="filter-label" for="filter-age-from">Возраст от</label><input id="filter-age-from" class="form-control" type="number" min="0" max="120"></div>
                        <div class="col-lg-1 col-6 form-group"><label class="filter-label" for="filter-age-to">до</label><input id="filter-age-to" class="form-control" type="number" min="0" max="120"></div>
                        <div class="col-lg-2 col-md-4 form-group"><label class="filter-label" for="filter-experience">Опыт от, лет</label><input id="filter-experience" class="form-control" type="number" min="0" max="80"></div>
                        <div class="col-lg-2 col-md-4 form-group">
                            <label class="filter-label" for="filter-has-phone">Телефон</label>
                            <select id="filter-has-phone" class="custom-select"><option value="">Любой</option><option value="yes">Есть</option><option value="no">Нет</option></select>
                        </div>
                    </div>
                    <div class="row align-items-end">
                        @if(Auth::user()->isAdmin())
                            <div class="col-lg-3 col-md-6 form-group"><label class="filter-label" for="filter-phone">Точный номер телефона</label><input id="filter-phone" class="form-control" type="tel" placeholder="+79991234567"></div>
                        @endif
                        <div class="col-lg-2 col-md-3 form-group"><label class="filter-label" for="filter-date-from">Спарсено с</label><input id="filter-date-from" class="form-control" type="date"></div>
                        <div class="col-lg-2 col-md-3 form-group"><label class="filter-label" for="filter-date-to">по</label><input id="filter-date-to" class="form-control" type="date"></div>
                        <div class="col-lg-3 col-md-6 form-group">
                            <button type="submit" class="btn btn-primary mr-2"><i class="fas fa-search mr-1" aria-hidden="true"></i>Применить</button>
                            <button id="reset-filters" type="button" class="btn btn-outline-secondary">Сбросить</button>
                        </div>
                    </div>
                </form>
            </div>
        </div>

        <div class="card">
            <div class="card-body">
                @if(Auth::user()->isAdmin())
                    <div class="d-flex flex-wrap align-items-center justify-content-between mb-3">
                        <div class="mb-2 mb-sm-0">
                            <button id="delete-selected" type="button" class="btn btn-danger mr-2" disabled>
                                <i class="fas fa-trash mr-1" aria-hidden="true"></i>Удалить выбранных
                            </button>
                            <span id="selected-count" class="text-muted" aria-live="polite">Выбрано: 0</span>
                        </div>
                        <a id="export-professionals" class="btn btn-success" href="{{ route('admin.professionals.export') }}">
                            <i class="fas fa-file-excel mr-1" aria-hidden="true"></i>Экспорт в Excel
                        </a>
                    </div>
                @endif
                <div id="table-error" class="alert alert-danger d-none" role="alert">Не удалось загрузить данные. Проверьте соединение с БД парсера.</div>
                <div class="table-responsive">
                    <table id="professionals" class="table table-bordered table-hover w-100">
                        <thead><tr>@if(Auth::user()->isAdmin())<th class="selection-column"><input id="select-current-page" type="checkbox" aria-label="Выбрать всех мастеров на текущей странице"></th>@endif<th>Фото</th><th>ФИО</th><th>Телефон</th><th>Локация</th><th>Возраст</th><th>Пол</th><th>Опыт</th><th>Яндекс.Категории</th><th>Ресурс</th><th>Спарсено</th><th>Действия</th></tr></thead>
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
    const csrf = document.querySelector('meta[name="csrf-token"]').content;
    const canManage = @json(Auth::user()->isAdmin());
    const bulkDeleteUrl = @json(Auth::user()->isAdmin() ? route('admin.professionals.bulk-destroy') : null);
    const exportUrl = @json(Auth::user()->isAdmin() ? route('admin.professionals.export') : null);
    const maxSelection = 500;
    const selectedIds = new Set();

    function filterValues() {
        return {
            search: $('#filter-search').val() || '',
            catalog_target: $('#filter-category').val() || '',
            gender: $('#filter-gender').val() || '',
            source: $('#filter-source').val() || '',
            country: $('#filter-country').val() || '',
            region: $('#filter-region').val() || '',
            city: $('#filter-city').val() || '',
            age_from: $('#filter-age-from').val() || '',
            age_to: $('#filter-age-to').val() || '',
            experience_from: $('#filter-experience').val() || '',
            has_phone: $('#filter-has-phone').val() || '',
            phone: $('#filter-phone').val() || '',
            scraped_from: $('#filter-date-from').val() || '',
            scraped_to: $('#filter-date-to').val() || ''
        };
    }

    function appendFilters(params) {
        const filters = filterValues();
        Object.entries(filters).forEach(function ([key, value]) {
            if (value !== '') params.set(key === 'search' ? 'search[value]' : key, value);
        });
    }

    function clearSelection() {
        selectedIds.clear();
        updateSelectionControls();
    }

    function updateSelectionControls() {
        if (!canManage) return;
        const boxes = Array.from(document.querySelectorAll('#professionals .professional-checkbox'));
        boxes.forEach(function (box) { box.checked = selectedIds.has(Number(box.value)); });
        const checkedOnPage = boxes.filter(function (box) { return box.checked; }).length;
        const master = document.getElementById('select-current-page');
        master.checked = boxes.length > 0 && checkedOnPage === boxes.length;
        master.indeterminate = checkedOnPage > 0 && checkedOnPage < boxes.length;
        document.getElementById('delete-selected').disabled = selectedIds.size === 0;
        document.getElementById('selected-count').textContent = `Выбрано: ${selectedIds.size} из ${maxSelection}`;
    }

    async function requestJson(url, options) {
        const response = await fetch(url, options);
        const payload = await response.json().catch(function () { return {}; });
        if (!response.ok) {
            const validationMessage = payload.errors
                ? Object.values(payload.errors).flat()[0]
                : null;
            throw new Error(validationMessage || payload.message || `Ошибка запроса (${response.status})`);
        }
        return payload;
    }

    async function confirmDeletion(title, text) {
        const result = await Swal.fire({
            title: title,
            text: text,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#dc3545',
            confirmButtonText: 'Удалить',
            cancelButtonText: 'Отмена',
            reverseButtons: true
        });
        return result.isConfirmed;
    }

    const columns = [];
    if (canManage) {
        columns.push({
            data: 'id',
            name: 'id',
            className: 'selection-column',
            orderable: false,
            searchable: false,
            render: function (data, type) {
                const id = Number(data);
                if (type !== 'display') return id;
                return `<input class="professional-checkbox" type="checkbox" value="${id}" aria-label="Выбрать мастера #${id}">`;
            }
        });
    }
    columns.push(
        {data:'photo', name:'photo_url', orderable:false, searchable:false},
        {data:'full_name', name:'full_name'},
        {data:'phone', name:'phone_status', orderable:false, searchable:false},
        {data:'location', name:'city', orderable:false, searchable:false},
        {data:'age_display', name:'age'},
        {data:'gender', name:'gender'},
        {data:'experience', name:'experience_code'},
        {data:'categories_display', name:'categories', orderable:false, searchable:false},
        {data:'resource', name:'source', orderable:false, searchable:false},
        {data:'scraped_at', name:'last_scraped_at'},
        {data:'action', name:'action', orderable:false, searchable:false}
    );

    const table = $('#professionals').DataTable({
        processing: true,
        serverSide: true,
        searching: false,
        responsive: true,
        searchDelay: 350,
        pageLength: 25,
        lengthMenu: [25, 50, 100],
        order: [[canManage ? 10 : 9, 'desc']],
        ajax: {
            url: @json(route('admin.datatable.professionals')),
            data: function (data) {
                const filters = filterValues();
                data.search.value = filters.search;
                Object.entries(filters).forEach(function ([key, value]) {
                    if (key !== 'search') data[key] = value;
                });
            },
            error: function () { $('#table-error').removeClass('d-none'); }
        },
        language: {
            processing: 'Загрузка…', search: 'Поиск:', lengthMenu: 'Показывать по _MENU_',
            info: 'Записи _START_–_END_ из _TOTAL_', infoEmpty: 'Нет записей', infoFiltered: '(из _MAX_)',
            zeroRecords: 'Ничего не найдено', emptyTable: 'Данные пока не загружены',
            paginate: { first: 'Первая', last: 'Последняя', next: 'Следующая', previous: 'Предыдущая' }
        },
        columns: columns,
        drawCallback: updateSelectionControls
    });

    $('#filters').on('submit', function (event) {
        event.preventDefault();
        clearSelection();
        $('#table-error').addClass('d-none');
        table.draw();
    });
    $('#reset-filters').on('click', function () {
        document.getElementById('filters').reset();
        clearSelection();
        table.search('').draw();
    });

    $('#professionals tbody').on('click', '.professional-checkbox', function (event) {
        event.stopPropagation();
    });

    $('#professionals').on('change', '.professional-checkbox', function () {
        const id = Number(this.value);
        if (this.checked && !selectedIds.has(id) && selectedIds.size >= maxSelection) {
            this.checked = false;
            toastr.warning(`За один раз можно выбрать не более ${maxSelection} мастеров.`);
        } else if (this.checked) {
            selectedIds.add(id);
        } else {
            selectedIds.delete(id);
        }
        updateSelectionControls();
    });

    $('#select-current-page').on('change', function () {
        const shouldSelect = this.checked;
        let limitReached = false;
        document.querySelectorAll('#professionals .professional-checkbox').forEach(function (box) {
            const id = Number(box.value);
            if (shouldSelect && !selectedIds.has(id)) {
                if (selectedIds.size >= maxSelection) {
                    limitReached = true;
                    return;
                }
                selectedIds.add(id);
            } else if (!shouldSelect) {
                selectedIds.delete(id);
            }
        });
        if (limitReached) toastr.warning(`За один раз можно выбрать не более ${maxSelection} мастеров.`);
        updateSelectionControls();
    });

    $('#professionals').on('click', '.js-delete-professional', async function () {
        const button = this;
        const id = Number(button.dataset.id);
        const confirmed = await confirmDeletion(
            'Удалить мастера?',
            `${button.dataset.name} будет удалён вместе со связями категорий. После нового парсинга карточка может появиться снова.`
        );
        if (!confirmed) return;
        button.disabled = true;
        try {
            const payload = await requestJson(button.dataset.url, {
                method: 'DELETE',
                headers: {'X-CSRF-TOKEN': csrf, 'Accept': 'application/json'}
            });
            selectedIds.delete(id);
            toastr.success(payload.message);
            table.ajax.reload(updateSelectionControls, false);
        } catch (error) {
            button.disabled = false;
            toastr.error(error.message);
        }
    });

    $('#delete-selected').on('click', async function () {
        const button = this;
        const ids = Array.from(selectedIds);
        if (ids.length === 0) return;
        const confirmed = await confirmDeletion(
            `Удалить мастеров: ${ids.length}?`,
            'Будут удалены все отмеченные карточки и их связи категорий. Отменить это действие нельзя.'
        );
        if (!confirmed) return;
        button.disabled = true;
        try {
            const payload = await requestJson(bulkDeleteUrl, {
                method: 'DELETE',
                headers: {
                    'X-CSRF-TOKEN': csrf,
                    'Accept': 'application/json',
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ids: ids})
            });
            clearSelection();
            toastr.success(payload.message);
            table.ajax.reload(updateSelectionControls, false);
        } catch (error) {
            button.disabled = false;
            toastr.error(error.message);
        }
    });

    $('#export-professionals').on('click', function (event) {
        event.preventDefault();
        const url = new URL(exportUrl, window.location.origin);
        appendFilters(url.searchParams);
        window.location.assign(url.toString());
    });

    $('#professionals').on('click', '.js-reveal-phone', async function () {
        const button = this;
        button.disabled = true;
        try {
            const response = await fetch(button.dataset.url, {method:'POST', headers:{'X-CSRF-TOKEN':csrf, 'Accept':'application/json'}});
            const payload = await response.json();
            if (!response.ok) throw new Error(payload.message || 'Телефон недоступен');
            button.textContent = payload.phone;
            button.classList.remove('btn-outline-secondary');
            button.classList.add('btn-light');
            button.title = 'Нажмите, чтобы скопировать';
            button.disabled = false;
            button.onclick = async function () {
                await navigator.clipboard.writeText(payload.phone);
                toastr.success('Телефон скопирован');
            };
        } catch (error) {
            button.disabled = false;
            toastr.error(error.message);
        }
    });
});
</script>
@endsection
