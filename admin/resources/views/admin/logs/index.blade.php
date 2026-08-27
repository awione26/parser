@extends('app')

@section('title', 'Журнал событий')

@section('css')
    <link rel="stylesheet" href="{{ asset('plugins/datatables-bs4/css/dataTables.bootstrap4.min.css') }}">
    <link rel="stylesheet" href="{{ asset('plugins/datatables-responsive/css/responsive.bootstrap4.min.css') }}">
    <style>
        #parser-logs td.log-error { max-width: 560px; overflow-wrap: anywhere; white-space: normal; }
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
                <form id="log-filters" autocomplete="off">
                    <div class="row align-items-end">
                        <div class="col-lg-3 col-md-6 form-group">
                            <label class="filter-label" for="filter-result">Результат</label>
                            <select id="filter-result" class="custom-select">
                                <option value="">Все результаты</option>
                                <option value="success">Успех</option>
                                <option value="failure">Неуспех</option>
                                <option value="running">Выполняется</option>
                            </select>
                        </div>
                        <div class="col-lg-3 col-md-6 form-group">
                            <label class="filter-label" for="filter-resource">Ресурс</label>
                            <input id="filter-resource" class="form-control" type="text" maxlength="255" placeholder="uslugi.yandex.ru">
                        </div>
                        <div class="col-lg-2 col-md-4 form-group">
                            <label class="filter-label" for="filter-started-from">Запущен с</label>
                            <input id="filter-started-from" class="form-control" type="date">
                        </div>
                        <div class="col-lg-2 col-md-4 form-group">
                            <label class="filter-label" for="filter-started-to">по</label>
                            <input id="filter-started-to" class="form-control" type="date">
                        </div>
                        <div class="col-lg-2 col-md-4 form-group">
                            <button type="submit" class="btn btn-primary mr-2"><i class="fas fa-search mr-1" aria-hidden="true"></i>Применить</button>
                            <button id="reset-log-filters" type="button" class="btn btn-outline-secondary">Сбросить</button>
                        </div>
                    </div>
                </form>
            </div>
        </div>

        <div class="card">
            <div class="card-body">
                <div id="log-table-error" class="alert alert-danger d-none" role="alert">
                    Не удалось загрузить журнал. Проверьте соединение с БД парсера.
                </div>
                <div class="table-responsive">
                    <table id="parser-logs" class="table table-bordered table-hover w-100">
                        <caption class="sr-only">Журнал запусков парсера</caption>
                        <thead>
                        <tr>
                            <th>Время запуска</th>
                            <th>Результат</th>
                            <th>Причина ошибки</th>
                            <th>Ресурс</th>
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
    function filterValues() {
        return {
            result: $('#filter-result').val() || '',
            resource: $('#filter-resource').val().trim(),
            started_from: $('#filter-started-from').val() || '',
            started_to: $('#filter-started-to').val() || ''
        };
    }

    const table = $('#parser-logs').DataTable({
        processing: true,
        serverSide: true,
        searching: false,
        responsive: true,
        pageLength: 25,
        lengthMenu: [25, 50, 100],
        order: [[0, 'desc']],
        ajax: {
            url: @json(route('admin.datatable.logs')),
            data: function (data) {
                Object.assign(data, filterValues());
            },
            error: function () {
                $('#log-table-error').removeClass('d-none');
            }
        },
        language: {
            processing: 'Загрузка…', lengthMenu: 'Показывать по _MENU_',
            info: 'Записи _START_–_END_ из _TOTAL_', infoEmpty: 'Нет записей', infoFiltered: '(из _MAX_)',
            zeroRecords: 'Ничего не найдено', emptyTable: 'Запуски парсера пока не зарегистрированы',
            paginate: { first: 'Первая', last: 'Последняя', next: 'Следующая', previous: 'Предыдущая' }
        },
        columns: [
            {data: 'started_at', name: 'started_at'},
            {data: 'result', name: 'result'},
            {data: 'error_reason', name: 'error_reason', className: 'log-error', orderable: false},
            {data: 'resource', name: 'resource'}
        ]
    });

    $('#log-filters').on('submit', function (event) {
        event.preventDefault();
        $('#log-table-error').addClass('d-none');
        table.draw();
    });

    $('#reset-log-filters').on('click', function () {
        document.getElementById('log-filters').reset();
        $('#log-table-error').addClass('d-none');
        table.draw();
    });
});
</script>
@endsection
