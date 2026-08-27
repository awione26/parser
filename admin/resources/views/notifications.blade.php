@if (Session::has('message'))
    <div class="alert alert-warning">
        <button class="close" data-dismiss="alert">
            ×
        </button>
        <i class="fa fa-exclamation-triangle" aria-hidden="true"></i>
        {{ Session::get('message') }}.
    </div>
@endif

@if (session('success'))
    <div class="alert alert-success">
        <button class="close" data-dismiss="alert">
            ×
        </button>
        <i class="fa-fw fa fa-check"></i>
        {{ session('success') }}
    </div>
@endif

@if (session('error'))
    <div class="alert alert-danger">
        <button class="close" data-dismiss="alert">
            ×
        </button>
        <i class="fas fa-times" aria-hidden="true"></i>
        {{ session('error') }}
    </div>
@endif

@if ($errors->any())
    <div class="alert alert-danger">
        <button class="close" data-dismiss="alert">
            ×
        </button>
        <i class="fas fa-times" aria-hidden="true"></i>
        <strong>Ошибки</strong>
        <ul>
            @foreach ($errors->all() as $error)
                <li>{{ $error }}</li>
            @endforeach
        </ul>
    </div>
@endif
