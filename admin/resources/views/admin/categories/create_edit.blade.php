@extends('app')

@section('title', $title)

@section('content')
    @php
        $isEdit = isset($row);
        $paths = old('seed_paths', $isEdit ? ($row->seed_paths ?? []) : []);
        $paths = is_array($paths) ? implode("\n", $paths) : $paths;
    @endphp

    <section class="content">
        <div class="container-fluid">
            <div class="card card-primary">
                <form
                    action="{{ $isEdit ? route('admin.categories.update', $row) : route('admin.categories.store') }}"
                    method="post"
                    novalidate
                >
                    @csrf
                    @if ($isEdit)
                        @method('PUT')
                    @endif

                    <div class="card-body">
                        <p><span aria-hidden="true">*</span> — обязательные поля.</p>

                        <div class="form-group">
                            <label for="category-key">Технический ключ <span aria-hidden="true">*</span></label>
                            @if ($isEdit)
                                <input
                                    id="category-key"
                                    class="form-control"
                                    type="text"
                                    value="{{ $row->category->key }}"
                                    readonly
                                    aria-describedby="category-key-help"
                                >
                            @else
                                <input
                                    id="category-key"
                                    name="key"
                                    class="form-control @error('key') is-invalid @enderror"
                                    type="text"
                                    maxlength="64"
                                    required
                                    value="{{ old('key') }}"
                                    placeholder="plumbers"
                                    aria-describedby="category-key-help @error('key') category-key-error @enderror"
                                >
                                @error('key')
                                    <div id="category-key-error" class="invalid-feedback">{{ $message }}</div>
                                @enderror
                            @endif
                            <small id="category-key-help" class="form-text text-muted">
                                Стабильный ключ из строчных латинских букв, цифр и подчёркиваний.
                                После добавления изменить его нельзя.
                            </small>
                        </div>

                        <div class="form-group">
                            <label for="category-name">Название <span aria-hidden="true">*</span></label>
                            <input
                                id="category-name"
                                name="name"
                                class="form-control @error('name') is-invalid @enderror"
                                type="text"
                                maxlength="255"
                                required
                                value="{{ old('name', $isEdit ? $row->category->name : '') }}"
                                @error('name') aria-describedby="category-name-error" @enderror
                            >
                            @error('name')
                                <div id="category-name-error" class="invalid-feedback">{{ $message }}</div>
                            @enderror
                        </div>

                        <div class="form-group">
                            <label for="category-paths">Относительные пути рубрик <span aria-hidden="true">*</span></label>
                            <textarea
                                id="category-paths"
                                name="seed_paths"
                                class="form-control @error('seed_paths') is-invalid @enderror @error('seed_paths.*') is-invalid @enderror"
                                rows="8"
                                required
                                placeholder="remont-i-stroitelstvo/santehnicheskie-rabotyi-i-otoplenie--1844"
                                aria-describedby="category-paths-help @error('seed_paths') category-paths-error @enderror @error('seed_paths.*') category-paths-item-error @enderror"
                            >{{ $paths }}</textarea>
                            @error('seed_paths')
                                <div id="category-paths-error" class="invalid-feedback">{{ $message }}</div>
                            @enderror
                            @error('seed_paths.*')
                                <div id="category-paths-item-error" class="invalid-feedback">{{ $message }}</div>
                            @enderror
                            <small id="category-paths-help" class="form-text text-muted">
                                Один путь на строку, без домена, начального слеша, query-параметров и географии.
                                Каждый путь должен заканчиваться числовым ID вида <code>--1844</code>.
                            </small>
                        </div>

                        <div class="form-group">
                            <label for="category-note">Примечание</label>
                            <textarea
                                id="category-note"
                                name="note"
                                class="form-control @error('note') is-invalid @enderror"
                                rows="3"
                                maxlength="5000"
                                @error('note') aria-describedby="category-note-error" @enderror
                            >{{ old('note', $isEdit ? $row->category->note : '') }}</textarea>
                            @error('note')
                                <div id="category-note-error" class="invalid-feedback">{{ $message }}</div>
                            @enderror
                        </div>

                        <div class="row">
                            <div class="col-md-4 form-group mb-md-0">
                                <label for="category-sort-order">Порядок <span aria-hidden="true">*</span></label>
                                <input
                                    id="category-sort-order"
                                    name="sort_order"
                                    class="form-control @error('sort_order') is-invalid @enderror"
                                    type="number"
                                    min="0"
                                    max="2147483647"
                                    required
                                    value="{{ old('sort_order', $isEdit ? $row->sort_order : $nextSortOrder) }}"
                                    @error('sort_order') aria-describedby="category-sort-order-error" @enderror
                                >
                                @error('sort_order')
                                    <div id="category-sort-order-error" class="invalid-feedback">{{ $message }}</div>
                                @enderror
                            </div>
                            <div class="col-md-8 form-group mb-0 d-flex align-items-end">
                                <div class="custom-control custom-switch mb-2">
                                    <input type="hidden" name="is_active" value="0">
                                    <input
                                        id="category-is-active"
                                        name="is_active"
                                        class="custom-control-input @error('is_active') is-invalid @enderror"
                                        type="checkbox"
                                        value="1"
                                        @checked((bool) old('is_active', $isEdit ? $row->is_active : true))
                                    >
                                    <label class="custom-control-label" for="category-is-active">
                                        Использовать при парсинге
                                    </label>
                                    @error('is_active')
                                        <div class="invalid-feedback d-block">{{ $message }}</div>
                                    @enderror
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="card-footer d-flex justify-content-between">
                        <button type="submit" class="btn btn-primary">
                            {{ $isEdit ? 'Сохранить' : 'Добавить категорию' }}
                        </button>
                        <a class="btn btn-default" href="{{ route('admin.categories.index') }}">Назад</a>
                    </div>
                </form>
            </div>
        </div>
    </section>
@endsection
