@extends('app')

@section('title', $title)

@section('content')
    @php($isEdit = isset($row))

    <section class="content">
        <div class="container-fluid">
            <div class="card card-primary">
                <form
                    action="{{ $isEdit ? route('admin.admin.update', ['id' => $row->id]) : route('admin.admin.store') }}"
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
                            <label for="name">Имя <span aria-hidden="true">*</span></label>
                            <input
                                id="name"
                                type="text"
                                name="name"
                                value="{{ old('name', $row->name ?? '') }}"
                                class="form-control @error('name') is-invalid @enderror"
                                maxlength="255"
                                autocomplete="name"
                                required
                                @error('name') aria-describedby="name-error" @enderror
                            >
                            @error('name')
                                <div id="name-error" class="invalid-feedback">{{ $message }}</div>
                            @enderror
                        </div>

                        <div class="form-group">
                            <label for="login">Логин <span aria-hidden="true">*</span></label>
                            <input
                                id="login"
                                type="text"
                                name="login"
                                value="{{ old('login', $row->login ?? '') }}"
                                class="form-control @error('login') is-invalid @enderror"
                                minlength="3"
                                maxlength="255"
                                autocomplete="username"
                                required
                                @error('login') aria-describedby="admin-login-error" @enderror
                            >
                            @error('login')
                                <div id="admin-login-error" class="invalid-feedback">{{ $message }}</div>
                            @enderror
                        </div>

                        <div class="form-group">
                            <label for="role">Роль <span aria-hidden="true">*</span></label>
                            <select
                                id="role"
                                name="role"
                                class="custom-select @error('role') is-invalid @enderror"
                                required
                                @error('role') aria-describedby="role-error" @enderror
                            >
                                @foreach ($options as $value => $label)
                                    <option
                                        value="{{ $value }}"
                                        @selected(old('role', $row->role ?? App\Models\User::ROLE_VIEWER) === $value)
                                    >{{ $label }}</option>
                                @endforeach
                            </select>
                            @error('role')
                                <div id="role-error" class="invalid-feedback">{{ $message }}</div>
                            @enderror
                        </div>

                        <div class="form-group">
                            <label for="password">
                                Пароль @unless($isEdit)<span aria-hidden="true">*</span>@endunless
                            </label>
                            <input
                                id="password"
                                type="password"
                                name="password"
                                class="form-control @error('password') is-invalid @enderror"
                                minlength="12"
                                autocomplete="new-password"
                                @unless($isEdit) required @endunless
                                aria-describedby="password-help @error('password') password-admin-error @enderror"
                            >
                            <small id="password-help" class="form-text text-muted">
                                Минимум 12 символов{{ $isEdit ? '; оставьте пустым, чтобы не менять' : '' }}.
                            </small>
                            @error('password')
                                <div id="password-admin-error" class="invalid-feedback">{{ $message }}</div>
                            @enderror
                        </div>

                        <div class="form-group">
                            <label for="password_confirmation">
                                Повтор пароля @unless($isEdit)<span aria-hidden="true">*</span>@endunless
                            </label>
                            <input
                                id="password_confirmation"
                                type="password"
                                name="password_confirmation"
                                class="form-control"
                                minlength="12"
                                autocomplete="new-password"
                                @unless($isEdit) required @endunless
                            >
                        </div>
                    </div>

                    <div class="card-footer d-flex justify-content-between">
                        <button type="submit" class="btn btn-primary">
                            {{ $isEdit ? 'Сохранить' : 'Добавить' }}
                        </button>
                        <a class="btn btn-default" href="{{ route('admin.admin.index') }}">Назад</a>
                    </div>
                </form>
            </div>
        </div>
    </section>
@endsection
