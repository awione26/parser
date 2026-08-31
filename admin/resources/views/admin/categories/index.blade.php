@extends('app')

@section('title', $title)

@section('content')
    <section class="content">
        <div class="container-fluid">
            <div class="alert alert-info">
                <i class="fas fa-info-circle mr-1" aria-hidden="true"></i>
                Активные категории участвуют в следующем запуске парсера. Удаление исключает
                категорию из плана, но сохраняет её и прежние связи мастеров в истории.
            </div>

            <div class="card">
                <div class="card-header d-flex align-items-center justify-content-between">
                    <span>Всего: {{ $rows->count() }}</span>
                    <a href="{{ route('admin.categories.create') }}" class="btn btn-info btn-sm">
                        <i class="fas fa-plus" aria-hidden="true"></i>
                        Добавить
                    </a>
                </div>

                <div class="card-body p-0">
                    <div class="table-responsive">
                        <table class="table table-bordered table-striped table-hover mb-0">
                            <caption class="sr-only">Категории, настроенные для обхода парсером</caption>
                            <thead>
                            <tr>
                                <th scope="col" class="text-nowrap">Порядок</th>
                                <th scope="col">Категория</th>
                                <th scope="col">Пути рубрик</th>
                                <th scope="col">Состояние</th>
                                <th scope="col" class="text-nowrap">Действия</th>
                            </tr>
                            </thead>
                            <tbody>
                            @forelse ($rows as $row)
                                <tr>
                                    <td>{{ $row->sort_order }}</td>
                                    <td>
                                        <strong>{{ $row->category->name }}</strong>
                                        <div><code>{{ $row->category->key }}</code></div>
                                        @if ($row->category->note)
                                            <small class="text-muted">{{ $row->category->note }}</small>
                                        @endif
                                    </td>
                                    <td>
                                        <details>
                                            <summary>{{ count($row->seed_paths ?? []) }} шт.</summary>
                                            <ul class="mb-0 mt-2 pl-3">
                                                @foreach (($row->seed_paths ?? []) as $path)
                                                    <li><code>{{ $path }}</code></li>
                                                @endforeach
                                            </ul>
                                        </details>
                                    </td>
                                    <td>
                                        @if ($row->is_active)
                                            <span class="badge badge-success">Активна</span>
                                        @else
                                            <span class="badge badge-secondary">Отключена</span>
                                        @endif
                                    </td>
                                    <td class="text-nowrap">
                                        <a
                                            href="{{ route('admin.categories.edit', $row) }}"
                                            class="btn btn-sm btn-primary"
                                            aria-label="Редактировать {{ $row->category->name }}"
                                        >
                                            <i class="fas fa-edit" aria-hidden="true"></i>
                                            <span class="sr-only">Редактировать</span>
                                        </a>

                                        <form
                                            action="{{ route('admin.categories.activation', $row) }}"
                                            method="post"
                                            class="d-inline"
                                        >
                                            @csrf
                                            @method('PATCH')
                                            <input type="hidden" name="is_active" value="{{ $row->is_active ? '0' : '1' }}">
                                            <button
                                                type="submit"
                                                class="btn btn-sm {{ $row->is_active ? 'btn-warning' : 'btn-success' }}"
                                                aria-label="{{ $row->is_active ? 'Отключить' : 'Включить' }} {{ $row->category->name }}"
                                            >
                                                <i class="fas {{ $row->is_active ? 'fa-pause' : 'fa-play' }}" aria-hidden="true"></i>
                                                <span class="sr-only">{{ $row->is_active ? 'Отключить' : 'Включить' }}</span>
                                            </button>
                                        </form>

                                        <form
                                            action="{{ route('admin.categories.destroy', $row) }}"
                                            method="post"
                                            class="d-inline"
                                            onsubmit="return confirm('Удалить категорию из плана парсинга? Исторические данные мастеров останутся.');"
                                        >
                                            @csrf
                                            @method('DELETE')
                                            <button
                                                type="submit"
                                                class="btn btn-sm btn-danger"
                                                aria-label="Удалить {{ $row->category->name }} из плана парсинга"
                                            >
                                                <i class="fas fa-trash" aria-hidden="true"></i>
                                                <span class="sr-only">Удалить</span>
                                            </button>
                                        </form>
                                    </td>
                                </tr>
                            @empty
                                <tr>
                                    <td colspan="5" class="text-center py-4">
                                        Категории для парсинга пока не настроены.
                                    </td>
                                </tr>
                            @endforelse
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </section>
@endsection
