<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="robots" content="noindex,nofollow">
    <meta name="csrf-token" content="{{ csrf_token() }}">
    <title>{{ config('app.name') }} — @yield('title', $title ?? 'Админка')</title>

    <link rel="stylesheet" href="{{ asset('plugins/fontawesome-free/css/all.min.css') }}">
    <link rel="stylesheet" href="{{ asset('plugins/sweetalert2/sweetalert2.min.css') }}">
    <link rel="stylesheet" href="{{ asset('plugins/toastr/toastr.min.css') }}">
    <link rel="stylesheet" href="{{ asset('dist/css/adminlte.min.css') }}">
    <style>
        :root { --brand-accent: #ffcc00; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
        .brand-link { border-bottom-color: rgba(255,255,255,.12) !important; }
        .brand-mark { align-items:center; background:var(--brand-accent); border-radius:9px; color:#171717; display:inline-flex; font-weight:800; height:34px; justify-content:center; margin-right:9px; width:34px; }
        .content-wrapper { background:#f4f6f9; }
        .profile-avatar, .profile-initials { border-radius:50%; height:46px; object-fit:cover; width:46px; }
        .profile-avatar-lg, .profile-initials-lg { border-radius:16px; height:128px; object-fit:cover; width:128px; }
        .profile-initials, .profile-initials-lg { align-items:center; background:#e9ecef; color:#495057; display:inline-flex; font-weight:700; justify-content:center; }
        .profile-initials-lg { font-size:2rem; }
        .table td { vertical-align:middle; }
        .filter-label { color:#495057; font-size:.82rem; font-weight:600; margin-bottom:.25rem; }
        .detail-label { color:#6c757d; font-size:.78rem; letter-spacing:.03em; margin-bottom:.2rem; text-transform:uppercase; }
        .detail-value { margin-bottom:1.15rem; overflow-wrap:anywhere; }
        .nav-sidebar .nav-link > p { white-space:normal; }
        .btn, .form-control, .custom-select { min-height:38px; }
        .btn-sm { min-height:31px; }
        :focus-visible { outline:3px solid rgba(0,123,255,.35); outline-offset:2px; }
        @media (max-width:575.98px) { .content-header h1 { font-size:1.5rem; } }
    </style>
    @yield('css')
</head>
<body class="hold-transition sidebar-mini layout-fixed">
<div class="wrapper">
    <nav class="main-header navbar navbar-expand navbar-white navbar-light">
        <ul class="navbar-nav">
            <li class="nav-item">
                <button class="nav-link btn btn-link" data-widget="pushmenu" type="button" aria-label="Открыть меню">
                    <i class="fas fa-bars" aria-hidden="true"></i>
                </button>
            </li>
        </ul>
        <ul class="navbar-nav ml-auto align-items-center">
            <li class="nav-item mr-2 text-muted d-none d-sm-block">
                {{ Auth::user()->login }}
            </li>
            <li class="nav-item">
                <form method="post" action="{{ route('logout') }}">
                    @csrf
                    <button class="nav-link btn btn-link" type="submit" title="Выйти" aria-label="Выйти">
                        <i class="fas fa-sign-out-alt" aria-hidden="true"></i>
                    </button>
                </form>
            </li>
        </ul>
    </nav>

    <aside class="main-sidebar sidebar-dark-primary elevation-4">
        <a href="{{ route('admin.dashboard.index') }}" class="brand-link">
            <span class="brand-mark">Я</span>
            <span class="brand-text font-weight-light">Парсер мастеров</span>
        </a>

        <div class="sidebar">
            <div class="user-panel mt-3 pb-3 mb-3">
                <div class="info d-block pl-1">
                    <span class="d-block text-white">{{ Auth::user()->name }}</span>
                    <small class="text-muted">{{ Auth::user()->roleLabel() }}</small>
                </div>
            </div>

            <nav class="mt-2" aria-label="Основная навигация">
                <ul class="nav nav-pills nav-sidebar flex-column" role="menu">
                    <li class="nav-item">
                        <a href="{{ route('admin.dashboard.index') }}" class="nav-link{{ Request::is('cp') ? ' active' : '' }}">
                            <i class="nav-icon fas fa-chart-pie" aria-hidden="true"></i>
                            <p>Обзор</p>
                        </a>
                    </li>
                    <li class="nav-item">
                        <a href="{{ route('admin.professionals.index') }}" class="nav-link{{ Request::is('cp/professionals*') ? ' active' : '' }}">
                            <i class="nav-icon fas fa-address-card" aria-hidden="true"></i>
                            <p>Спарсенные данные</p>
                        </a>
                    </li>
                    @if(Auth::user()->isAdmin())
                        <li class="nav-item">
                            <a href="{{ route('admin.logs.index') }}" class="nav-link{{ Request::is('cp/logs*') ? ' active' : '' }}">
                                <i class="nav-icon fas fa-clipboard-list" aria-hidden="true"></i>
                                <p>Журнал событий</p>
                            </a>
                        </li>
                        <li class="nav-item">
                            <a href="{{ route('admin.admin.index') }}" class="nav-link{{ Request::is('cp/administrators*') ? ' active' : '' }}">
                                <i class="nav-icon fas fa-user-shield" aria-hidden="true"></i>
                                <p>Администраторы</p>
                            </a>
                        </li>
                    @endif
                </ul>
            </nav>
        </div>
    </aside>

    <div class="content-wrapper">
        <section class="content-header">
            <div class="container-fluid">
                <div class="row mb-2 align-items-center">
                    <div class="col-sm-7"><h1 class="m-0">{{ $title }}</h1></div>
                    <div class="col-sm-5">
                        <ol class="breadcrumb float-sm-right mb-0">
                            <li class="breadcrumb-item"><a href="{{ route('admin.dashboard.index') }}">Админка</a></li>
                            <li class="breadcrumb-item active">{{ $title }}</li>
                        </ol>
                    </div>
                </div>
                @include('notifications')
            </div>
        </section>

        @yield('content')
    </div>

    <footer class="main-footer">
        <strong>Реестр мастеров &copy; {{ date('Y') }}</strong>
        <span class="float-right d-none d-sm-inline text-muted">Удаление и экспорт доступны администраторам</span>
    </footer>
</div>

<script src="{{ asset('plugins/jquery/jquery.min.js') }}"></script>
<script src="{{ asset('plugins/bootstrap/js/bootstrap.bundle.min.js') }}"></script>
<script src="{{ asset('plugins/sweetalert2/sweetalert2.min.js') }}"></script>
<script src="{{ asset('plugins/toastr/toastr.min.js') }}"></script>
<script src="{{ asset('dist/js/adminlte.min.js') }}"></script>
@yield('js')
</body>
</html>
