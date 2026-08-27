@extends('app')

@section('title', 'Обзор')

@section('content')
<section class="content">
    <div class="container-fluid">
        @unless($databaseAvailable)
            <div class="alert alert-danger" role="alert">
                <h2 class="h5"><i class="fas fa-database mr-2" aria-hidden="true"></i>База парсера недоступна</h2>
                <p class="mb-0">Проверьте параметры <code>PARSER_DB_*</code> и наличие миграций Alembic.</p>
            </div>
        @endunless

        <div class="row">
            <div class="col-lg-3 col-6">
                <div class="small-box bg-info">
                    <div class="inner"><h3>{{ number_format($stats['total'], 0, ',', ' ') }}</h3><p>Всего мастеров</p></div>
                    <div class="icon"><i class="fas fa-users" aria-hidden="true"></i></div>
                    <a href="{{ route('admin.professionals.index') }}" class="small-box-footer">Открыть реестр <i class="fas fa-arrow-circle-right" aria-hidden="true"></i></a>
                </div>
            </div>
            <div class="col-lg-3 col-6">
                <div class="small-box bg-success">
                    <div class="inner"><h3>{{ number_format($stats['with_phone'], 0, ',', ' ') }}</h3><p>С телефоном</p></div>
                    <div class="icon"><i class="fas fa-phone" aria-hidden="true"></i></div>
                    <span class="small-box-footer">Раскрытие журналируется</span>
                </div>
            </div>
            <div class="col-lg-3 col-6">
                <div class="small-box bg-warning">
                    <div class="inner"><h3>{{ number_format($stats['without_phone'], 0, ',', ' ') }}</h3><p>Без телефона</p></div>
                    <div class="icon"><i class="fas fa-phone-slash" aria-hidden="true"></i></div>
                    <span class="small-box-footer">Номер не опубликован</span>
                </div>
            </div>
            <div class="col-lg-3 col-6">
                <div class="small-box bg-secondary">
                    <div class="inner"><h3>{{ number_format($stats['cities'], 0, ',', ' ') }}</h3><p>Городов</p></div>
                    <div class="icon"><i class="fas fa-map-marker-alt" aria-hidden="true"></i></div>
                    <span class="small-box-footer">Уникальные значения</span>
                </div>
            </div>
        </div>

        <div class="row">
            <div class="col-lg-7">
                <div class="card">
                    <div class="card-header"><h2 class="card-title font-weight-bold">Категории</h2></div>
                    <div class="card-body p-0">
                        <div class="table-responsive">
                            <table class="table table-hover mb-0">
                                <thead><tr><th>Категория</th><th class="text-right">Мастеров</th></tr></thead>
                                <tbody>
                                @forelse($categories as $category)
                                    <tr><td>{{ $category->name }}</td><td class="text-right">{{ number_format($category->professionals_count, 0, ',', ' ') }}</td></tr>
                                @empty
                                    <tr><td colspan="2" class="text-center text-muted py-4">Категории пока не загружены</td></tr>
                                @endforelse
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
            <div class="col-lg-5">
                <div class="card">
                    <div class="card-header">
                        <h2 class="card-title font-weight-bold">Последние карточки</h2>
                        <div class="card-tools text-muted small">
                            Обновлено: {{ $stats['last_scraped_at'] ? \Illuminate\Support\Carbon::parse($stats['last_scraped_at'])->format('d.m.Y H:i') : '—' }}
                        </div>
                    </div>
                    <div class="list-group list-group-flush">
                        @forelse($recent as $professional)
                            <a class="list-group-item list-group-item-action" href="{{ route('admin.professionals.show', $professional) }}">
                                <strong class="d-block">{{ $professional->full_name ?: 'Без имени' }}</strong>
                                <small class="text-muted">{{ $professional->city ?: 'Локация не указана' }} · {{ $professional->last_scraped_at?->format('d.m.Y H:i') }}</small>
                            </a>
                        @empty
                            <div class="list-group-item text-muted text-center py-4">Данных пока нет</div>
                        @endforelse
                    </div>
                </div>
            </div>
        </div>
    </div>
</section>
@endsection
