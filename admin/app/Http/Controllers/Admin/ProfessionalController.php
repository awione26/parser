<?php

namespace App\Http\Controllers\Admin;

use App\Models\Category;
use App\Models\Professional;
use App\Support\PhoneNumber;
use App\Support\ProfessionalPresenter;
use Illuminate\Contracts\View\View;

class ProfessionalController extends Controller
{
    public function index(): View
    {
        return view('admin.professionals.index', [
            'title' => 'Спарсенные данные',
            'categories' => Category::query()->orderBy('name')->get(['id', 'name']),
            'sources' => Professional::query()
                ->whereNotNull('source')
                ->distinct()
                ->orderBy('source')
                ->pluck('source'),
        ]);
    }

    public function show(Professional $professional): View
    {
        $professional->load([
            'categories' => fn ($query) => $query->orderBy('name'),
            'rubrics' => fn ($query) => $query
                ->with('category')
                ->orderBy('category_id')
                ->orderBy('source_rubric_number_id'),
        ]);

        return view('admin.professionals.show', [
            'title' => $professional->full_name ?: 'Карточка мастера',
            'professional' => $professional,
            'hasPhone' => PhoneNumber::isValid($professional->phone),
            'photoUrl' => ProfessionalPresenter::safePhotoUrl($professional->photo_url),
            'profileUrl' => ProfessionalPresenter::safeProfileUrl($professional->profile_url),
        ]);
    }
}
