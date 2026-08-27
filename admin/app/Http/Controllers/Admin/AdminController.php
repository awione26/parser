<?php

namespace App\Http\Controllers\Admin;

use App\Http\Requests\Admin\Admin\DeleteRequest;
use App\Http\Requests\Admin\Admin\EditRequest;
use App\Http\Requests\Admin\Admin\StoreRequest;
use App\Repositories\UserRepository;
use DomainException;
use Illuminate\Http\RedirectResponse;
use Illuminate\Support\Facades\Auth;
use Illuminate\View\View;

class AdminController extends Controller
{
    public function __construct(
        private UserRepository $userRepository,
    ) {
        parent::__construct();
        $this->middleware('permission:admin');
    }

    public function index(): View
    {
        $rows = $this->userRepository->paginateForAdmin();

        return view('admin.admin.index', compact('rows'))
            ->with('title', 'Администраторы');
    }

    public function create(): View
    {
        $options = $this->userRepository->roleOptions();

        return view('admin.admin.create_edit', compact('options'))
            ->with('title', 'Добавить администратора');
    }

    public function store(StoreRequest $request): RedirectResponse
    {
        $this->userRepository->createFromArray($request->validated());

        return redirect()->route('admin.admin.index')->with('success', 'Информация успешно добавлена!');
    }

    public function edit(int $id): View
    {
        $row = $this->userRepository->find($id);

        if (! $row) {
            abort(404);
        }

        $options = $this->userRepository->roleOptions();

        return view('admin.admin.create_edit', compact('row', 'options'))
            ->with('title', 'Редактировать администратора');
    }

    public function update(EditRequest $request, int $id): RedirectResponse
    {
        try {
            if (! $this->userRepository->updateFromArray($request->validated())) {
                abort(404);
            }
        } catch (DomainException $exception) {
            return redirect()
                ->back()
                ->withInput($request->safe()->except(['password', 'password_confirmation']))
                ->withErrors(['role' => $exception->getMessage()]);
        }

        return redirect()->route('admin.admin.index')->with('success', 'Данные успешно обновлены!');
    }

    public function destroy(DeleteRequest $request, int $id): RedirectResponse
    {
        try {
            if (! $this->userRepository->deleteSafely($request->integer('id'), (int) Auth::id())) {
                abort(404);
            }
        } catch (DomainException $exception) {
            return redirect()
                ->route('admin.admin.index')
                ->with('error', $exception->getMessage());
        }

        return redirect()
            ->route('admin.admin.index')
            ->with('success', 'Администратор удалён.');
    }
}
