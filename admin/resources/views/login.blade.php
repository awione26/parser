<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="robots" content="noindex,nofollow">
    <meta name="csrf-token" content="{{ csrf_token() }}">
    <title>Вход в панель управления</title>

    <link rel="stylesheet" href="{{ asset('plugins/fontawesome-free/css/all.min.css') }}">
    <link rel="stylesheet" href="{{ asset('plugins/icheck-bootstrap/icheck-bootstrap.min.css') }}">
    <link rel="stylesheet" href="{{ asset('dist/css/adminlte.min.css') }}">
</head>
<body class="hold-transition login-page">
<main class="login-box" aria-labelledby="login-title">
    <div class="card card-outline card-primary">
        <div class="card-header text-center">
            <strong id="login-title">Парсер мастеров</strong>
        </div>

        <div class="card-body">
            <p class="login-box-msg">Введите логин и пароль</p>

            <form action="{{ route('login.submit') }}" method="post" novalidate>
                @csrf

                <div class="input-group mb-3">
                    <label class="sr-only" for="login">Логин</label>
                    <input
                        id="login"
                        type="text"
                        name="login"
                        value="{{ old('login') }}"
                        class="form-control @error('login') is-invalid @enderror"
                        placeholder="Логин"
                        autocomplete="username"
                        maxlength="255"
                        required
                        autofocus
                        aria-invalid="{{ $errors->has('login') ? 'true' : 'false' }}"
                        @error('login') aria-describedby="login-error" @enderror
                    >
                    <div class="input-group-append" aria-hidden="true">
                        <div class="input-group-text"><span class="fas fa-user"></span></div>
                    </div>
                    @error('login')
                        <div id="login-error" class="invalid-feedback d-block">{{ $message }}</div>
                    @enderror
                </div>

                <div class="input-group mb-3">
                    <label class="sr-only" for="password">Пароль</label>
                    <input
                        id="password"
                        type="password"
                        name="password"
                        class="form-control @error('password') is-invalid @enderror"
                        placeholder="Пароль"
                        autocomplete="current-password"
                        required
                        aria-invalid="{{ $errors->has('password') ? 'true' : 'false' }}"
                        @error('password') aria-describedby="password-error" @enderror
                    >
                    <div class="input-group-append" aria-hidden="true">
                        <div class="input-group-text"><span class="fas fa-lock"></span></div>
                    </div>
                    @error('password')
                        <div id="password-error" class="invalid-feedback d-block">{{ $message }}</div>
                    @enderror
                </div>

                <div class="row align-items-center">
                    <div class="col-7">
                        <div class="icheck-primary">
                            <input
                                id="remember"
                                type="checkbox"
                                name="remember"
                                value="1"
                                @checked(old('remember'))
                            >
                            <label for="remember">Запомнить меня</label>
                        </div>
                    </div>
                    <div class="col-5">
                        <button type="submit" class="btn btn-primary btn-block">Войти</button>
                    </div>
                </div>
            </form>
        </div>
    </div>
</main>

<script src="{{ asset('plugins/jquery/jquery.min.js') }}"></script>
<script src="{{ asset('plugins/bootstrap/js/bootstrap.bundle.min.js') }}"></script>
<script src="{{ asset('dist/js/adminlte.min.js') }}"></script>
</body>
</html>
