<?php

namespace App\Http\Controllers\Admin;

use App\Models\Category;
use App\Models\Professional;
use Illuminate\Contracts\View\View;
use Throwable;

class DashboardController extends Controller
{
    public function index(): View
    {
        $stats = [
            'total' => 0,
            'with_phone' => 0,
            'without_phone' => 0,
            'cities' => 0,
            'last_scraped_at' => null,
        ];
        $categories = collect();
        $recent = collect();
        $databaseAvailable = true;

        try {
            $stats['total'] = Professional::query()->count();
            $stats['with_phone'] = Professional::query()
                ->whereNotNull('phone')
                ->where('phone', '<>', '')
                ->count();
            $stats['without_phone'] = $stats['total'] - $stats['with_phone'];
            $stats['cities'] = Professional::query()
                ->whereNotNull('city')
                ->where('city', '<>', '')
                ->distinct()
                ->count('city');
            $stats['last_scraped_at'] = Professional::query()->max('last_scraped_at');

            $categories = Category::query()
                ->withCount('professionals')
                ->orderByDesc('professionals_count')
                ->orderBy('name')
                ->get();

            $recent = Professional::query()
                ->select(['id', 'full_name', 'city', 'source', 'last_scraped_at'])
                ->latest('last_scraped_at')
                ->limit(6)
                ->get();
        } catch (Throwable $exception) {
            report($exception);
            $databaseAvailable = false;
        }

        return view('admin.dashboard.index', [
            'title' => 'Обзор',
            'stats' => $stats,
            'categories' => $categories,
            'recent' => $recent,
            'databaseAvailable' => $databaseAvailable,
        ]);
    }
}
