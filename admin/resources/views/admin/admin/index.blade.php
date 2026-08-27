@extends('app')

@section('title', $title)

@section('content')
    <section class="content">
        <div class="container-fluid">
            <div class="card">
                <div class="card-header d-flex align-items-center justify-content-between">
                    <span>Всего: {{ $rows->total() }}</span>
                    <a href="{{ route('admin.admin.create') }}" class="btn btn-info btn-sm">
                        <span class="fas fa-plus" aria-hidden="true"></span>
                        Добавить
                    </a>
                </div>

                <div class="card-body p-0">
                    <div class="table-responsive">
                        <table class="table table-bordered table-striped mb-0">
                            <caption class="sr-only">Список администраторов и наблюдателей</caption>
                            <thead>
                            <tr>
                                <th scope="col">Логин</th>
                                <th scope="col">Имя</th>
                                <th scope="col">Роль</th>
                                <th scope="col">Создан</th>
                                <th scope="col" class="text-nowrap">Действия</th>
                            </tr>
                            </thead>
                            <tbody>
                            @forelse ($rows as $row)
                                <tr>
                                    <td>
                                        {{ $row->login }}
                                        @if ((int) $row->id === (int) Auth::id())
                                            <span class="badge badge-secondary">Вы</span>
                                        @endif
                                    </td>
                                    <td>{{ $row->name }}</td>
                                    <td>{{ App\Models\User::$role_name[$row->role] ?? $row->role }}</td>
                                    <td class="text-nowrap">{{ $row->created_at?->format('d.m.Y H:i') ?? '—' }}</td>
                                    <td class="text-nowrap">
                                        <a
                                            href="{{ route('admin.admin.edit', ['id' => $row->id]) }}"
                                            class="btn btn-sm btn-primary"
                                            aria-label="Редактировать {{ $row->login }}"
                                        >
                                            <span class="fas fa-edit" aria-hidden="true"></span>
                                            <span class="sr-only">Редактировать</span>
                                        </a>

                                        @if ((int) $row->id !== (int) Auth::id())
                                            <form
                                                action="{{ route('admin.admin.destroy', ['id' => $row->id]) }}"
                                                method="post"
                                                class="d-inline"
                                                onsubmit="return confirm('Удалить этого администратора?');"
                                            >
                                                @csrf
                                                @method('DELETE')
                                                <button
                                                    type="submit"
                                                    class="btn btn-sm btn-danger"
                                                    aria-label="Удалить {{ $row->login }}"
                                                >
                                                    <span class="fas fa-trash" aria-hidden="true"></span>
                                                    <span class="sr-only">Удалить</span>
                                                </button>
                                            </form>
                                        @endif
                                    </td>
                                </tr>
                            @empty
                                <tr>
                                    <td colspan="5" class="text-center py-4">Администраторы не найдены.</td>
                                </tr>
                            @endforelse
                            </tbody>
                        </table>
                    </div>
                </div>

                @if ($rows->hasPages())
                    <div class="card-footer">
                        {{ $rows->onEachSide(1)->links('pagination::bootstrap-4') }}
                    </div>
                @endif
            </div>
        </div>
    </section>
@endsection
