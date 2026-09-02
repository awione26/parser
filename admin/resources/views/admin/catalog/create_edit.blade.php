@extends('app')

@section('title', $title)

@section('content')
    @php
        $isEdit = isset($row) && $row !== null;
        $level = $isEdit ? $selectedLevel : old('taxonomy_level', 'occupation');
        $categoryId = old('category_id', $selectedCategory->id ?? '');
        $occupationParentId = old(
            'parent_occupation_id',
            $isEdit && $selectedLevel === 'specialization' ? $row->occupation_id : '',
        );
        $specializationParentId = old(
            'parent_specialization_id',
            $isEdit && $selectedLevel === 'service' ? $row->specialization_id : '',
        );
    @endphp

    <section class="content">
        <div class="container-fluid">
            @if ($isEdit && $isShared)
                <div class="alert alert-warning">
                    <i class="fas fa-exclamation-triangle mr-1" aria-hidden="true"></i>
                    Этот узел связан с несколькими группами мастеров. Чтобы не изменить данные
                    в других группах, глобальные поля доступны только для чтения. Можно изменить
                    текущую группу, порядок или удалить только эту привязку.
                </div>
            @endif

            <div class="card card-primary">
                <form
                    method="post"
                    action="{{ $isEdit
                        ? route('admin.catalog.update', [
                            'category' => $selectedCategory->id,
                            'taxonomyLevel' => $selectedLevel,
                            'catalogNode' => $row->id,
                        ])
                        : route('admin.catalog.store') }}"
                    novalidate
                >
                    @csrf
                    @if ($isEdit)
                        @method('PUT')
                    @endif

                    <div class="card-body">
                        <p class="text-muted"><span aria-hidden="true">*</span> — обязательные поля.</p>

                        <div class="form-row">
                            <div class="form-group col-lg-6">
                                <label for="catalog-category">Группа мастеров <span aria-hidden="true">*</span></label>
                                <select
                                    id="catalog-category"
                                    name="category_id"
                                    class="custom-select @error('category_id') is-invalid @enderror"
                                    required
                                    @error('category_id') aria-describedby="catalog-category-error" @enderror
                                >
                                    <option value="">Выберите группу</option>
                                    @foreach ($groups as $group)
                                        <option value="{{ $group->id }}" @selected((string) $categoryId === (string) $group->id)>
                                            {{ $group->name }}
                                        </option>
                                    @endforeach
                                </select>
                                @error('category_id')
                                    <div id="catalog-category-error" class="invalid-feedback">{{ $message }}</div>
                                @enderror
                            </div>

                            <div class="form-group col-lg-6">
                                <label for="catalog-level">Уровень каталога <span aria-hidden="true">*</span></label>
                                @if ($isEdit)
                                    <input type="hidden" name="taxonomy_level" value="{{ $selectedLevel }}">
                                @endif
                                <select
                                    id="catalog-level"
                                    name="{{ $isEdit ? '' : 'taxonomy_level' }}"
                                    class="custom-select @error('taxonomy_level') is-invalid @enderror"
                                    required
                                    @disabled($isEdit)
                                    @error('taxonomy_level') aria-describedby="catalog-level-error" @enderror
                                >
                                    @foreach ($levelOptions as $value => $label)
                                        <option value="{{ $value }}" @selected($level === $value)>{{ $label }}</option>
                                    @endforeach
                                </select>
                                @error('taxonomy_level')
                                    <div id="catalog-level-error" class="invalid-feedback">{{ $message }}</div>
                                @enderror
                            </div>
                        </div>

                        <div
                            id="occupation-parent-field"
                            class="form-group catalog-parent-field"
                            data-level="specialization"
                            @if ($level !== 'specialization') hidden @endif
                        >
                            <label for="catalog-occupation-parent">Родительское направление <span aria-hidden="true">*</span></label>
                            @if ($isEdit && $isShared && $selectedLevel === 'specialization')
                                <input type="hidden" name="parent_occupation_id" value="{{ $row->occupation_id }}">
                            @endif
                            <select
                                id="catalog-occupation-parent"
                                name="parent_occupation_id"
                                class="custom-select @error('parent_id') is-invalid @enderror"
                                @disabled($isEdit && $isShared)
                                @if ($isEdit && $isShared) data-locked="true" @endif
                            >
                                <option value="">Выберите направление</option>
                                @foreach ($occupations as $occupation)
                                    <option
                                        value="{{ $occupation->id }}"
                                        @selected((string) $occupationParentId === (string) $occupation->id)
                                    >
                                        {{ $occupation->name }} (ID {{ $occupation->external_number_id }})
                                    </option>
                                @endforeach
                            </select>
                            @error('parent_id')
                                <div class="invalid-feedback">{{ $message }}</div>
                            @enderror
                        </div>

                        <div
                            id="specialization-parent-field"
                            class="form-group catalog-parent-field"
                            data-level="service"
                            @if ($level !== 'service') hidden @endif
                        >
                            <label for="catalog-specialization-parent">Родительская специализация <span aria-hidden="true">*</span></label>
                            @if ($isEdit && $isShared && $selectedLevel === 'service')
                                <input type="hidden" name="parent_specialization_id" value="{{ $row->specialization_id }}">
                            @endif
                            <select
                                id="catalog-specialization-parent"
                                name="parent_specialization_id"
                                class="custom-select @error('parent_id') is-invalid @enderror"
                                @disabled($isEdit && $isShared)
                                @if ($isEdit && $isShared) data-locked="true" @endif
                            >
                                <option value="">Выберите специализацию</option>
                                @foreach ($specializations as $specialization)
                                    <option
                                        value="{{ $specialization->id }}"
                                        @selected((string) $specializationParentId === (string) $specialization->id)
                                    >
                                        {{ $specialization->name }} (ID {{ $specialization->external_number_id }})
                                    </option>
                                @endforeach
                            </select>
                            @error('parent_id')
                                <div class="invalid-feedback">{{ $message }}</div>
                            @enderror
                        </div>

                        <div class="form-row">
                            <div class="form-group col-lg-8">
                                <label for="catalog-name">Название <span aria-hidden="true">*</span></label>
                                <input
                                    id="catalog-name"
                                    type="text"
                                    name="name"
                                    value="{{ old('name', $row->name ?? '') }}"
                                    class="form-control @error('name') is-invalid @enderror"
                                    maxlength="255"
                                    required
                                    @readonly($isEdit && $isShared)
                                >
                                @error('name')<div class="invalid-feedback">{{ $message }}</div>@enderror
                            </div>
                            <div class="form-group col-lg-4">
                                <label for="catalog-number-id">Числовой ID <span aria-hidden="true">*</span></label>
                                <input
                                    id="catalog-number-id"
                                    type="number"
                                    name="external_number_id"
                                    value="{{ old('external_number_id', $row->external_number_id ?? '') }}"
                                    class="form-control @error('external_number_id') is-invalid @enderror"
                                    min="1"
                                    max="2147483647"
                                    required
                                    @readonly($isEdit)
                                >
                                @if ($isEdit)
                                    <small class="form-text text-muted">ID существующей категории не изменяется.</small>
                                @endif
                                @error('external_number_id')<div class="invalid-feedback">{{ $message }}</div>@enderror
                            </div>
                        </div>

                        <div class="form-group">
                            <label for="catalog-raw-id">ID из параметра Яндекса</label>
                            <input
                                id="catalog-raw-id"
                                type="text"
                                name="external_id_raw"
                                value="{{ old('external_id_raw', $row->external_id_raw ?? '') }}"
                                class="form-control @error('external_id_raw') is-invalid @enderror"
                                maxlength="255"
                                placeholder="Например, /remont-i-stroitel_stvo"
                                @readonly($isEdit && $isShared)
                            >
                            @error('external_id_raw')<div class="invalid-feedback">{{ $message }}</div>@enderror
                        </div>

                        <div class="form-group">
                            <label for="catalog-slug">Slug <span aria-hidden="true">*</span></label>
                            <input
                                id="catalog-slug"
                                type="text"
                                name="slug"
                                value="{{ old('slug', $row->slug ?? '') }}"
                                class="form-control @error('slug') is-invalid @enderror"
                                maxlength="512"
                                placeholder="/remont/santehnika"
                                required
                                @readonly($isEdit && $isShared)
                                aria-describedby="catalog-slug-help"
                            >
                            <small id="catalog-slug-help" class="form-text text-muted">
                                Начинается с /; суффикс <code>--ID</code> добавлять не нужно.
                            </small>
                            @error('slug')<div class="invalid-feedback">{{ $message }}</div>@enderror
                        </div>

                        <div class="form-group">
                            <label for="catalog-source-url">Ссылка на Яндекс.Каталог <span aria-hidden="true">*</span></label>
                            <input
                                id="catalog-source-url"
                                type="url"
                                name="source_url"
                                value="{{ old('source_url', $row->source_url ?? '') }}"
                                class="form-control @error('source_url') is-invalid @enderror"
                                maxlength="1024"
                                placeholder="https://uslugi.yandex.ru/category/remont/santehnika--123"
                                required
                                @readonly($isEdit && $isShared)
                            >
                            @error('source_url')<div class="invalid-feedback">{{ $message }}</div>@enderror
                        </div>

                        <div class="form-row">
                            <div class="form-group col-lg-6">
                                <label for="catalog-status">Статус проверки <span aria-hidden="true">*</span></label>
                                @if ($isEdit && $isShared)
                                    <input type="hidden" name="verification_status" value="{{ $row->verification_status }}">
                                @endif
                                <select
                                    id="catalog-status"
                                    name="verification_status"
                                    class="custom-select @error('verification_status') is-invalid @enderror"
                                    required
                                    @disabled($isEdit && $isShared)
                                >
                                    @foreach ($statusOptions as $value => $label)
                                        <option
                                            value="{{ $value }}"
                                            @selected(old('verification_status', $row->verification_status ?? 'confirmed') === $value)
                                        >{{ $label }}</option>
                                    @endforeach
                                </select>
                                @error('verification_status')<div class="invalid-feedback">{{ $message }}</div>@enderror
                            </div>
                            <div class="form-group col-lg-6">
                                <label for="catalog-sort-order">Порядок в группе <span aria-hidden="true">*</span></label>
                                <input
                                    id="catalog-sort-order"
                                    type="number"
                                    name="sort_order"
                                    value="{{ old('sort_order', $sortOrder) }}"
                                    class="form-control @error('sort_order') is-invalid @enderror"
                                    min="0"
                                    max="2147483647"
                                    required
                                >
                                @error('sort_order')<div class="invalid-feedback">{{ $message }}</div>@enderror
                            </div>
                        </div>
                    </div>

                    <div class="card-footer d-flex flex-wrap justify-content-between">
                        <button type="submit" class="btn btn-primary mr-2">
                            <i class="fas fa-save mr-1" aria-hidden="true"></i>
                            {{ $isEdit ? 'Сохранить изменения' : 'Добавить категорию' }}
                        </button>
                        <a href="{{ route('admin.catalog.index') }}" class="btn btn-default">Отмена</a>
                    </div>
                </form>
            </div>

            @if ($isEdit)
                <div class="card card-outline card-danger">
                    <div class="card-body d-flex flex-wrap align-items-center justify-content-between">
                        <div class="mr-3">
                            <strong>Удаление категории</strong>
                            <div class="text-muted">
                                Категория исчезнет из выбранной группы и плана парсинга. Сам справочный
                                узел сохранится, чтобы не потерять историю и результаты уже запущенного обхода.
                            </div>
                        </div>
                        <form
                            method="post"
                            action="{{ route('admin.catalog.destroy', [
                                'category' => $selectedCategory->id,
                                'taxonomyLevel' => $selectedLevel,
                                'catalogNode' => $row->id,
                            ]) }}"
                            onsubmit="return confirm('Удалить категорию из выбранной группы? Справочный узел останется в базе для истории.');"
                        >
                            @csrf
                            @method('DELETE')
                            <input type="hidden" name="confirmed" value="1">
                            <button type="submit" class="btn btn-danger">
                                <i class="fas fa-trash mr-1" aria-hidden="true"></i>
                                Удалить категорию
                            </button>
                        </form>
                    </div>
                </div>
            @endif
        </div>
    </section>
@endsection

@section('js')
    <script>
        (function () {
            const level = document.getElementById('catalog-level');
            const fields = document.querySelectorAll('.catalog-parent-field');
            if (!level || !fields.length) {
                return;
            }

            const refreshParents = function () {
                fields.forEach(function (field) {
                    const visible = field.dataset.level === level.value;
                    field.hidden = !visible;
                    const select = field.querySelector('select');
                    if (select && !select.dataset.locked) {
                        select.disabled = !visible;
                        select.required = visible;
                    }
                });
            };

            level.addEventListener('change', refreshParents);
            refreshParents();
        })();
    </script>
@endsection
