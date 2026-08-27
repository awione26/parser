@extends('app')

@section('title', 'Настройки')

@section('css')
<style>
    .settings-page {
        --settings-border: #e3e8ef;
        --settings-muted: #6c757d;
        --settings-soft-bg: #f8fafc;
    }

    .settings-page .settings-notice {
        align-items: flex-start;
        border: 0;
        border-left: 4px solid #17a2b8;
        box-shadow: 0 1px 3px rgba(0, 0, 0, .08);
        display: flex;
        margin-bottom: 1.25rem;
    }

    .settings-page .settings-notice > i {
        font-size: 1.1rem;
        margin-top: .15rem;
    }

    .settings-page .settings-card {
        border: 1px solid var(--settings-border);
        border-radius: .45rem;
        box-shadow: 0 2px 8px rgba(31, 45, 61, .06);
        height: calc(100% - 1.25rem);
        margin-bottom: 1.25rem;
        overflow: hidden;
    }

    .settings-page .settings-card .card-header {
        align-items: center;
        background: #fff;
        border-bottom: 1px solid var(--settings-border);
        display: flex;
        min-height: 64px;
        padding: .9rem 1.25rem;
    }

    .settings-page .settings-card .card-body {
        padding: 1.25rem;
    }

    .settings-page .settings-card-icon {
        align-items: center;
        background: rgba(0, 123, 255, .1);
        border-radius: .45rem;
        color: #007bff;
        display: inline-flex;
        flex: 0 0 38px;
        height: 38px;
        justify-content: center;
        margin-right: .8rem;
        width: 38px;
    }

    .settings-page .settings-card-title {
        font-size: 1rem;
        font-weight: 700;
        line-height: 1.25;
        margin: 0;
    }

    .settings-page .settings-card-subtitle {
        color: var(--settings-muted);
        display: block;
        font-size: .78rem;
        line-height: 1.3;
        margin-top: .15rem;
    }

    .settings-page .form-group > label {
        color: #343a40;
        font-size: .875rem;
        font-weight: 600;
        margin-bottom: .4rem;
    }

    .settings-page .form-control {
        border-color: #ced4da;
        border-radius: .35rem;
    }

    .settings-page .form-control:focus {
        border-color: #80bdff;
        box-shadow: 0 0 0 .18rem rgba(0, 123, 255, .12);
    }

    .settings-page .settings-switch {
        background: var(--settings-soft-bg);
        border: 1px solid var(--settings-border);
        border-radius: .4rem;
        min-height: 76px;
        padding: .9rem 1rem .85rem 3.45rem;
    }

    .settings-page .settings-input-panel {
        background: var(--settings-soft-bg);
        border: 1px solid var(--settings-border);
        border-radius: .4rem;
        padding: .75rem 1rem;
    }

    .settings-page .settings-switch .custom-control-label {
        cursor: pointer;
        display: block;
        font-size: .9rem;
        font-weight: 600;
        line-height: 1.35;
    }

    .settings-page .settings-switch-description {
        color: var(--settings-muted);
        display: block;
        font-size: .78rem;
        font-weight: 400;
        line-height: 1.35;
        margin-top: .25rem;
    }

    .settings-page .settings-phone-note {
        background: #fffaf0;
        border: 1px solid #f6dfaa;
        border-radius: .4rem;
        color: #68521d;
        display: flex;
        font-size: .8rem;
        line-height: 1.5;
        margin-top: .25rem;
        padding: .9rem 1rem;
    }

    .settings-page .settings-phone-note > i {
        color: #d39e00;
        flex: 0 0 auto;
        margin-right: .7rem;
        margin-top: .2rem;
    }

    .settings-page .settings-actions {
        align-items: center;
        background: #fff;
        border: 1px solid var(--settings-border);
        border-top: 3px solid #007bff;
        border-radius: .45rem;
        box-shadow: 0 3px 10px rgba(31, 45, 61, .08);
        display: flex;
        justify-content: space-between;
        margin-bottom: 1.5rem;
        padding: 1rem 1.25rem;
    }

    .settings-page .settings-actions-title {
        color: #343a40;
        display: block;
        font-size: .95rem;
        font-weight: 700;
    }

    .settings-page .settings-actions-help {
        color: var(--settings-muted);
        display: block;
        font-size: .8rem;
        margin-top: .15rem;
    }

    .settings-page .settings-submit {
        border-radius: .35rem;
        box-shadow: 0 2px 5px rgba(0, 123, 255, .22);
        flex: 0 0 auto;
        font-weight: 600;
        margin-left: 1.25rem;
        min-width: 210px;
        padding: .65rem 1.15rem;
    }

    @media (min-width: 1200px) {
        .settings-page .settings-network-field > label {
            align-items: flex-end;
            display: flex;
            min-height: 2.5em;
        }
    }

    @media (max-width: 767.98px) {
        .settings-page .settings-card .card-header,
        .settings-page .settings-card .card-body {
            padding-left: 1rem;
            padding-right: 1rem;
        }

        .settings-page .settings-actions {
            align-items: stretch;
            flex-direction: column;
        }

        .settings-page .settings-submit {
            margin-left: 0;
            margin-top: 1rem;
            width: 100%;
        }
    }
</style>
@endsection

@section('content')
<section class="content settings-page">
    <div class="container-fluid">
        <div class="alert alert-info settings-notice" role="status">
            <i class="fas fa-info-circle mr-2" aria-hidden="true"></i>
            <div>
                Изменения применятся при следующем запуске парсера. Письменное разрешение
                на сбор контактных данных оформляется отдельно и не является настройкой парсера.
            </div>
        </div>

        <form method="post" action="{{ route('admin.settings.update') }}">
            @csrf
            @method('PUT')

            <div class="card settings-card">
                <div class="card-header">
                    <span class="settings-card-icon" aria-hidden="true"><i class="fas fa-id-card"></i></span>
                    <div>
                        <h2 class="settings-card-title">Основные параметры</h2>
                        <span class="settings-card-subtitle">Идентификация парсера и регион поиска</span>
                    </div>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-lg-8 form-group mb-lg-0">
                            <label for="setting-user-agent">User-Agent</label>
                            <input
                                id="setting-user-agent"
                                name="SCRAPER_USER_AGENT"
                                class="form-control @error('SCRAPER_USER_AGENT') is-invalid @enderror"
                                type="text"
                                maxlength="512"
                                required
                                value="{{ old('SCRAPER_USER_AGENT', $settings['SCRAPER_USER_AGENT']) }}"
                                aria-describedby="setting-user-agent-help"
                            >
                            @error('SCRAPER_USER_AGENT')<div class="invalid-feedback">{{ $message }}</div>@enderror
                            <small id="setting-user-agent-help" class="form-text text-muted">
                                От 3 до 512 печатных ASCII-символов. Укажите идентификатор клиента и контакт оператора.
                            </small>
                        </div>

                        <div class="col-lg-4 form-group mb-0">
                            <label for="setting-geo">География Яндекса</label>
                            <input
                                id="setting-geo"
                                name="SCRAPER_GEO"
                                class="form-control @error('SCRAPER_GEO') is-invalid @enderror"
                                type="text"
                                maxlength="128"
                                required
                                placeholder="213-moscow"
                                value="{{ old('SCRAPER_GEO', $settings['SCRAPER_GEO']) }}"
                                aria-describedby="setting-geo-help"
                            >
                            @error('SCRAPER_GEO')<div class="invalid-feedback">{{ $message }}</div>@enderror
                            <small id="setting-geo-help" class="form-text text-muted">
                                Формат: числовой ID и slug, например <code>213-moscow</code>.
                            </small>
                        </div>
                    </div>
                </div>
            </div>

            <div class="card settings-card">
                <div class="card-header">
                    <span class="settings-card-icon" aria-hidden="true"><i class="fas fa-tachometer-alt"></i></span>
                    <div>
                        <h2 class="settings-card-title">Сеть и ограничения запросов</h2>
                        <span class="settings-card-subtitle">Интервалы, тайм-ауты и повторные обращения</span>
                    </div>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-xl-3 col-md-6 form-group settings-network-field">
                            <label for="setting-min-delay">Минимальная задержка, сек.</label>
                            <input
                                id="setting-min-delay"
                                name="SCRAPER_MIN_DELAY_SECONDS"
                                class="form-control @error('SCRAPER_MIN_DELAY_SECONDS') is-invalid @enderror"
                                type="number"
                                min="0"
                                max="3600"
                                step="any"
                                required
                                value="{{ old('SCRAPER_MIN_DELAY_SECONDS', $settings['SCRAPER_MIN_DELAY_SECONDS']) }}"
                            >
                            @error('SCRAPER_MIN_DELAY_SECONDS')<div class="invalid-feedback">{{ $message }}</div>@enderror
                        </div>
                        <div class="col-xl-3 col-md-6 form-group settings-network-field">
                            <label for="setting-max-delay">Максимальная задержка, сек.</label>
                            <input
                                id="setting-max-delay"
                                name="SCRAPER_MAX_DELAY_SECONDS"
                                class="form-control @error('SCRAPER_MAX_DELAY_SECONDS') is-invalid @enderror"
                                type="number"
                                min="0"
                                max="3600"
                                step="any"
                                required
                                value="{{ old('SCRAPER_MAX_DELAY_SECONDS', $settings['SCRAPER_MAX_DELAY_SECONDS']) }}"
                            >
                            @error('SCRAPER_MAX_DELAY_SECONDS')<div class="invalid-feedback">{{ $message }}</div>@enderror
                        </div>
                        <div class="col-xl-3 col-md-6 form-group settings-network-field">
                            <label for="setting-timeout">HTTP-тайм-аут, сек.</label>
                            <input
                                id="setting-timeout"
                                name="SCRAPER_TIMEOUT_SECONDS"
                                class="form-control @error('SCRAPER_TIMEOUT_SECONDS') is-invalid @enderror"
                                type="number"
                                min="0.001"
                                max="300"
                                step="any"
                                required
                                value="{{ old('SCRAPER_TIMEOUT_SECONDS', $settings['SCRAPER_TIMEOUT_SECONDS']) }}"
                            >
                            @error('SCRAPER_TIMEOUT_SECONDS')<div class="invalid-feedback">{{ $message }}</div>@enderror
                        </div>
                        <div class="col-xl-3 col-md-6 form-group settings-network-field">
                            <label for="setting-retries">Повторные попытки</label>
                            <input
                                id="setting-retries"
                                name="SCRAPER_MAX_RETRIES"
                                class="form-control @error('SCRAPER_MAX_RETRIES') is-invalid @enderror"
                                type="number"
                                min="0"
                                max="10"
                                step="1"
                                required
                                value="{{ old('SCRAPER_MAX_RETRIES', $settings['SCRAPER_MAX_RETRIES']) }}"
                            >
                            @error('SCRAPER_MAX_RETRIES')<div class="invalid-feedback">{{ $message }}</div>@enderror
                        </div>
                    </div>

                    @php($respectRobots = old('SCRAPER_RESPECT_ROBOTS', $settings['SCRAPER_RESPECT_ROBOTS']))
                    <input type="hidden" name="SCRAPER_RESPECT_ROBOTS" value="0">
                    <div class="custom-control custom-switch settings-switch">
                        <input
                            id="setting-respect-robots"
                            name="SCRAPER_RESPECT_ROBOTS"
                            class="custom-control-input @error('SCRAPER_RESPECT_ROBOTS') is-invalid @enderror"
                            type="checkbox"
                            value="1"
                            @checked(App\Support\ParserSettings::booleanValue($respectRobots))
                        >
                        <label class="custom-control-label" for="setting-respect-robots">
                            Соблюдать robots.txt
                            <span class="settings-switch-description">Парсер проверяет правила ресурса перед выполнением сетевых запросов.</span>
                        </label>
                        @error('SCRAPER_RESPECT_ROBOTS')<div class="invalid-feedback">{{ $message }}</div>@enderror
                    </div>
                </div>
            </div>

            <div class="row">
                <div class="col-xl-8">
                    <div class="card settings-card">
                        <div class="card-header">
                            <span class="settings-card-icon" aria-hidden="true"><i class="fas fa-phone-alt"></i></span>
                            <div>
                                <h2 class="settings-card-title">Телефоны и браузер</h2>
                                <span class="settings-card-subtitle">Параметры браузерного получения контактных данных</span>
                            </div>
                        </div>
                        <div class="card-body">
                            <div class="row">
                                <div class="col-lg-4 mb-3">
                                    <div class="form-group settings-input-panel h-100 mb-0">
                                        <label for="setting-phone-timeout">Тайм-аут телефона, сек.</label>
                                        <input
                                            id="setting-phone-timeout"
                                            name="SCRAPER_PHONE_TIMEOUT_SECONDS"
                                            class="form-control @error('SCRAPER_PHONE_TIMEOUT_SECONDS') is-invalid @enderror"
                                            type="number"
                                            min="0.001"
                                            max="300"
                                            step="any"
                                            required
                                            value="{{ old('SCRAPER_PHONE_TIMEOUT_SECONDS', $settings['SCRAPER_PHONE_TIMEOUT_SECONDS']) }}"
                                        >
                                        @error('SCRAPER_PHONE_TIMEOUT_SECONDS')<div class="invalid-feedback">{{ $message }}</div>@enderror
                                    </div>
                                </div>
                                <div class="col-lg-4 mb-3">
                                    @php($collectPhone = old('SCRAPER_COLLECT_PHONE', $settings['SCRAPER_COLLECT_PHONE']))
                                    <input type="hidden" name="SCRAPER_COLLECT_PHONE" value="0">
                                    <div class="custom-control custom-switch settings-switch h-100">
                                        <input
                                            id="setting-collect-phone"
                                            name="SCRAPER_COLLECT_PHONE"
                                            class="custom-control-input @error('SCRAPER_COLLECT_PHONE') is-invalid @enderror"
                                            type="checkbox"
                                            value="1"
                                            @checked(App\Support\ParserSettings::booleanValue($collectPhone))
                                        >
                                        <label class="custom-control-label" for="setting-collect-phone">
                                            Получать телефоны
                                            <span class="settings-switch-description">Запускать браузерный сбор доступных номеров.</span>
                                        </label>
                                        @error('SCRAPER_COLLECT_PHONE')<div class="invalid-feedback">{{ $message }}</div>@enderror
                                    </div>
                                </div>
                                <div class="col-lg-4 mb-3">
                                    @php($phoneHeadless = old('SCRAPER_PHONE_HEADLESS', $settings['SCRAPER_PHONE_HEADLESS']))
                                    <input type="hidden" name="SCRAPER_PHONE_HEADLESS" value="0">
                                    <div class="custom-control custom-switch settings-switch h-100">
                                        <input
                                            id="setting-phone-headless"
                                            name="SCRAPER_PHONE_HEADLESS"
                                            class="custom-control-input @error('SCRAPER_PHONE_HEADLESS') is-invalid @enderror"
                                            type="checkbox"
                                            value="1"
                                            @checked(App\Support\ParserSettings::booleanValue($phoneHeadless))
                                        >
                                        <label class="custom-control-label" for="setting-phone-headless">
                                            Скрытый режим браузера
                                            <span class="settings-switch-description">Запускать браузер без графического интерфейса.</span>
                                        </label>
                                        @error('SCRAPER_PHONE_HEADLESS')<div class="invalid-feedback">{{ $message }}</div>@enderror
                                    </div>
                                </div>
                            </div>

                            <div class="settings-phone-note">
                                <i class="fas fa-exclamation-triangle" aria-hidden="true"></i>
                                <div>
                                    При <code>SCRAPER_RESPECT_ROBOTS=true</code> раскрытие телефона блокируется;
                                    отключайте эту защиту, только если это прямо предусмотрено разрешением.
                                    Значение <code>SCRAPER_PHONE_HEADLESS=false</code> не работает в Docker без
                                    настроенного графического <code>DISPLAY</code>.
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="col-xl-4">
                    <div class="card settings-card">
                        <div class="card-header">
                            <span class="settings-card-icon" aria-hidden="true"><i class="fas fa-users"></i></span>
                            <div>
                                <h2 class="settings-card-title">Типы профилей</h2>
                                <span class="settings-card-subtitle">Состав результатов парсинга</span>
                            </div>
                        </div>
                        <div class="card-body">
                            @php($includeOrganizations = old('SCRAPER_INCLUDE_ORGANIZATIONS', $settings['SCRAPER_INCLUDE_ORGANIZATIONS']))
                            <input type="hidden" name="SCRAPER_INCLUDE_ORGANIZATIONS" value="0">
                            <div class="custom-control custom-switch settings-switch">
                                <input
                                    id="setting-include-organizations"
                                    name="SCRAPER_INCLUDE_ORGANIZATIONS"
                                    class="custom-control-input @error('SCRAPER_INCLUDE_ORGANIZATIONS') is-invalid @enderror"
                                    type="checkbox"
                                    value="1"
                                    @checked(App\Support\ParserSettings::booleanValue($includeOrganizations))
                                >
                                <label class="custom-control-label" for="setting-include-organizations">
                                    Включать организации
                                    <span class="settings-switch-description">У организаций обычно отсутствуют ФИО, возраст и пол.</span>
                                </label>
                                @error('SCRAPER_INCLUDE_ORGANIZATIONS')<div class="invalid-feedback">{{ $message }}</div>@enderror
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="settings-actions">
                <div>
                    <span class="settings-actions-title">Сохранение параметров</span>
                    <span class="settings-actions-help">Новые значения начнут действовать при следующем запуске парсера.</span>
                </div>
                <button type="submit" class="btn btn-primary settings-submit">
                    <i class="fas fa-save mr-2" aria-hidden="true"></i>Сохранить настройки
                </button>
            </div>
        </form>
    </div>
</section>
@endsection
