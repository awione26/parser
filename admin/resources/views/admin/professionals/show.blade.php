@extends('app')

@section('title', $title)

@section('content')
<section class="content">
    <div class="container-fluid">
        <div class="d-flex justify-content-between mb-3">
            <a href="{{ route('admin.professionals.index') }}" class="btn btn-outline-secondary"><i class="fas fa-arrow-left mr-2" aria-hidden="true"></i>К списку</a>
            @if(Auth::user()->isAdmin())
                <button id="delete-professional" type="button" class="btn btn-danger" data-url="{{ route('admin.professionals.destroy', $professional) }}">
                    <i class="fas fa-trash mr-2" aria-hidden="true"></i>Удалить мастера
                </button>
            @endif
        </div>
        <div class="row">
            <div class="col-lg-4">
                <div class="card card-primary card-outline">
                    <div class="card-body box-profile text-center">
                        @if($photoUrl)
                            <img class="profile-avatar-lg mb-3" src="{{ $photoUrl }}" alt="Фото: {{ $professional->full_name ?: 'мастер' }}" referrerpolicy="no-referrer">
                        @else
                            <span class="profile-initials-lg mb-3">{{ \App\Support\ProfessionalPresenter::initials($professional->full_name) }}</span>
                        @endif
                        <h2 class="h4">{{ $professional->full_name ?: 'Имя не указано' }}</h2>
                        <p class="text-muted">ID источника: {{ $professional->source_profile_id }}</p>
                        @if($profileUrl)
                            <a class="btn btn-primary btn-block" href="{{ $profileUrl }}" target="_blank" rel="noopener noreferrer"><i class="fas fa-external-link-alt mr-2" aria-hidden="true"></i>Открыть на {{ $professional->source }}</a>
                        @endif
                    </div>
                </div>
                <div class="card">
                    <div class="card-header"><h2 class="card-title font-weight-bold">Служебные данные</h2></div>
                    <div class="card-body">
                        <div class="detail-label">Впервые найден</div><div class="detail-value">{{ $professional->first_seen_at?->format('d.m.Y H:i') ?? '—' }}</div>
                        <div class="detail-label">Последний раз найден</div><div class="detail-value">{{ $professional->last_seen_at?->format('d.m.Y H:i') ?? '—' }}</div>
                        <div class="detail-label">Последний парсинг</div><div class="detail-value">{{ $professional->last_scraped_at?->format('d.m.Y H:i') ?? '—' }}</div>
                        <div class="detail-label">Версия парсера</div><div class="detail-value mb-0">{{ $professional->parser_version ?: '—' }}</div>
                    </div>
                </div>
            </div>
            <div class="col-lg-8">
                <div class="card">
                    <div class="card-header"><h2 class="card-title font-weight-bold">Контактные данные и профиль</h2></div>
                    <div class="card-body">
                        <div class="row">
                            <div class="col-md-6"><div class="detail-label">ФИО</div><div class="detail-value">{{ $professional->full_name ?: '—' }}</div></div>
                            <div class="col-md-6">
                                <div class="detail-label">Телефон</div>
                                <div class="detail-value">
                                    @if($hasPhone && Auth::user()->isAdmin())
                                        <button id="reveal-phone" type="button" class="btn btn-outline-secondary" data-url="{{ route('admin.professionals.phone', $professional) }}"><i class="fas fa-phone mr-2" aria-hidden="true"></i>Показать телефон</button>
                                    @else
                                        {{ \App\Support\ProfessionalPresenter::phoneStatus($professional->phone_status) }}
                                    @endif
                                </div>
                            </div>
                            <div class="col-md-6"><div class="detail-label">Локация</div><div class="detail-value">{{ \App\Support\ProfessionalPresenter::location($professional) }}</div></div>
                            <div class="col-md-3"><div class="detail-label">Возраст</div><div class="detail-value">{{ $professional->age ?? '—' }} @if($professional->age_as_of)<small class="text-muted d-block">на {{ $professional->age_as_of->format('d.m.Y') }}</small>@endif</div></div>
                            <div class="col-md-3"><div class="detail-label">Пол</div><div class="detail-value">{{ \App\Support\ProfessionalPresenter::gender($professional->gender) }}</div></div>
                            <div class="col-md-6"><div class="detail-label">Опыт</div><div class="detail-value">{{ $professional->experience_text ?: '—' }}</div></div>
                            <div class="col-md-6"><div class="detail-label">Статус телефона</div><div class="detail-value">{{ \App\Support\ProfessionalPresenter::phoneStatus($professional->phone_status) }}</div></div>
                            <div class="col-12"><div class="detail-label">Категории</div><div class="detail-value">@forelse($professional->categories as $category)<span class="badge badge-primary mr-1 mb-1 p-2">{{ $category->name }}</span>@empty — @endforelse</div></div>
                        </div>
                    </div>
                </div>

                <div class="card">
                    <div class="card-header"><h2 class="card-title font-weight-bold">Опыт по исходным рубрикам</h2></div>
                    <div class="card-body p-0">
                        <div class="table-responsive">
                            <table class="table table-hover mb-0">
                                <thead><tr><th>Категория</th><th>Рубрика</th><th>Опыт</th><th>ID</th></tr></thead>
                                <tbody>
                                @forelse($professional->rubrics as $rubric)
                                    <tr><td>{{ $rubric->category?->name ?: '—' }}</td><td>{{ $rubric->source_rubric_name ?: $rubric->source_rubric_seo_id ?: '—' }}</td><td>{{ $rubric->experience_text ?: '—' }}</td><td>{{ $rubric->source_rubric_number_id }}</td></tr>
                                @empty
                                    <tr><td colspan="4" class="text-center text-muted py-4">Детализация опыта отсутствует</td></tr>
                                @endforelse
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</section>
@endsection

@section('js')
<script>
document.getElementById('delete-professional')?.addEventListener('click', async function () {
    const button = this;
    const confirmation = await Swal.fire({
        title: 'Удалить мастера?',
        text: 'Карточка и её связи категорий будут удалены. После нового парсинга карточка может появиться снова.',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#dc3545',
        confirmButtonText: 'Удалить',
        cancelButtonText: 'Отмена',
        reverseButtons: true
    });
    if (!confirmation.isConfirmed) return;
    button.disabled = true;
    try {
        const response = await fetch(button.dataset.url, {
            method: 'DELETE',
            headers: {
                'X-CSRF-TOKEN': document.querySelector('meta[name="csrf-token"]').content,
                'Accept': 'application/json'
            }
        });
        const payload = await response.json().catch(function () { return {}; });
        if (!response.ok) throw new Error(payload.message || `Ошибка удаления (${response.status})`);
        window.location.assign(@json(route('admin.professionals.index')));
    } catch (error) {
        button.disabled = false;
        toastr.error(error.message);
    }
});

document.getElementById('reveal-phone')?.addEventListener('click', async function () {
    const button = this;
    button.disabled = true;
    try {
        const response = await fetch(button.dataset.url, {method:'POST', headers:{'X-CSRF-TOKEN':document.querySelector('meta[name="csrf-token"]').content, 'Accept':'application/json'}});
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.message || 'Телефон недоступен');
        button.textContent = payload.phone;
        button.disabled = false;
        button.title = 'Нажмите, чтобы скопировать';
        button.addEventListener('click', async () => { await navigator.clipboard.writeText(payload.phone); toastr.success('Телефон скопирован'); }, {once:true});
    } catch (error) { button.disabled = false; toastr.error(error.message); }
}, {once:true});
</script>
@endsection
