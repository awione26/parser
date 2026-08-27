@extends('app')

@section('title', 'Настройки')

@section('content')
<section class="content">
    <div class="container-fluid">
        <div class="alert alert-info" role="status">
            <i class="fas fa-info-circle mr-2" aria-hidden="true"></i>
            Изменения применятся при следующем запуске парсера. Разрешения оператора
            <code>YANDEX_*</code> здесь не изменяются.
        </div>

        <form method="post" action="{{ route('admin.settings.update') }}">
            @csrf
            @method('PUT')

            <div class="card card-outline card-primary">
                <div class="card-header">
                    <h2 class="card-title font-weight-bold">Основные параметры</h2>
                </div>
                <div class="card-body">
                    <div class="form-group">
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

                    <div class="form-group mb-0">
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
                        <small id="setting-geo-help" class="form-text text-muted">Формат: числовой ID и slug, например <code>213-moscow</code>.</small>
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <h2 class="card-title font-weight-bold">Сеть и ограничения запросов</h2>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-lg-3 col-md-6 form-group">
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
                        <div class="col-lg-3 col-md-6 form-group">
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
                        <div class="col-lg-3 col-md-6 form-group">
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
                        <div class="col-lg-3 col-md-6 form-group">
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
                    <div class="custom-control custom-switch">
                        <input
                            id="setting-respect-robots"
                            name="SCRAPER_RESPECT_ROBOTS"
                            class="custom-control-input @error('SCRAPER_RESPECT_ROBOTS') is-invalid @enderror"
                            type="checkbox"
                            value="1"
                            @checked(App\Support\ParserSettings::booleanValue($respectRobots))
                        >
                        <label class="custom-control-label" for="setting-respect-robots">Соблюдать robots.txt</label>
                        @error('SCRAPER_RESPECT_ROBOTS')<div class="invalid-feedback">{{ $message }}</div>@enderror
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <h2 class="card-title font-weight-bold">Телефоны и браузер</h2>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-lg-4 form-group">
                            <label for="setting-phone-timeout">Тайм-аут получения телефона, сек.</label>
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

                    <div class="row">
                        <div class="col-lg-4 mb-3 mb-lg-0">
                            @php($collectPhone = old('SCRAPER_COLLECT_PHONE', $settings['SCRAPER_COLLECT_PHONE']))
                            <input type="hidden" name="SCRAPER_COLLECT_PHONE" value="0">
                            <div class="custom-control custom-switch">
                                <input
                                    id="setting-collect-phone"
                                    name="SCRAPER_COLLECT_PHONE"
                                    class="custom-control-input @error('SCRAPER_COLLECT_PHONE') is-invalid @enderror"
                                    type="checkbox"
                                    value="1"
                                    @checked(App\Support\ParserSettings::booleanValue($collectPhone))
                                >
                                <label class="custom-control-label" for="setting-collect-phone">Получать телефоны</label>
                                @error('SCRAPER_COLLECT_PHONE')<div class="invalid-feedback">{{ $message }}</div>@enderror
                            </div>
                        </div>
                        <div class="col-lg-4">
                            @php($phoneHeadless = old('SCRAPER_PHONE_HEADLESS', $settings['SCRAPER_PHONE_HEADLESS']))
                            <input type="hidden" name="SCRAPER_PHONE_HEADLESS" value="0">
                            <div class="custom-control custom-switch">
                                <input
                                    id="setting-phone-headless"
                                    name="SCRAPER_PHONE_HEADLESS"
                                    class="custom-control-input @error('SCRAPER_PHONE_HEADLESS') is-invalid @enderror"
                                    type="checkbox"
                                    value="1"
                                    @checked(App\Support\ParserSettings::booleanValue($phoneHeadless))
                                >
                                <label class="custom-control-label" for="setting-phone-headless">Скрытый режим браузера</label>
                                @error('SCRAPER_PHONE_HEADLESS')<div class="invalid-feedback">{{ $message }}</div>@enderror
                            </div>
                        </div>
                    </div>
                    <small class="form-text text-muted mt-3">
                        Получение телефонов требует контейнера <code>parser-phone</code>, включённых
                        <code>YANDEX_OPERATOR_PERMISSION</code> и <code>YANDEX_PHONE_PERMISSION</code>,
                        а также явно разрешённого оператором режима работы с <code>robots.txt</code>.
                        При <code>SCRAPER_RESPECT_ROBOTS=true</code> раскрытие телефона блокируется;
                        отключайте эту защиту только в пределах письменного разрешения.
                        Значение <code>SCRAPER_PHONE_HEADLESS=false</code> не работает в Docker без
                        настроенного графического <code>DISPLAY</code>.
                    </small>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <h2 class="card-title font-weight-bold">Типы профилей</h2>
                </div>
                <div class="card-body">
                    @php($includeOrganizations = old('SCRAPER_INCLUDE_ORGANIZATIONS', $settings['SCRAPER_INCLUDE_ORGANIZATIONS']))
                    <input type="hidden" name="SCRAPER_INCLUDE_ORGANIZATIONS" value="0">
                    <div class="custom-control custom-switch">
                        <input
                            id="setting-include-organizations"
                            name="SCRAPER_INCLUDE_ORGANIZATIONS"
                            class="custom-control-input @error('SCRAPER_INCLUDE_ORGANIZATIONS') is-invalid @enderror"
                            type="checkbox"
                            value="1"
                            @checked(App\Support\ParserSettings::booleanValue($includeOrganizations))
                        >
                        <label class="custom-control-label" for="setting-include-organizations">Включать организации</label>
                        @error('SCRAPER_INCLUDE_ORGANIZATIONS')<div class="invalid-feedback">{{ $message }}</div>@enderror
                    </div>
                    <small class="form-text text-muted">У организаций обычно отсутствуют ФИО, возраст и пол.</small>
                </div>
            </div>

            <div class="d-flex justify-content-end mb-4">
                <button type="submit" class="btn btn-primary">
                    <i class="fas fa-save mr-1" aria-hidden="true"></i>Сохранить настройки
                </button>
            </div>
        </form>
    </div>
</section>
@endsection
