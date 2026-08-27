<?php

namespace App\Http\Controllers\Admin;

use App\Http\Requests\Admin\ParserSetting\UpdateRequest;
use App\Models\ParserSetting;
use App\Support\ParserSettings;
use Carbon\CarbonImmutable;
use Illuminate\Contracts\View\View;
use Illuminate\Http\RedirectResponse;
use Illuminate\Support\Facades\DB;

final class ParserSettingController extends Controller
{
    public function __construct()
    {
        parent::__construct();
        $this->middleware('permission:admin');
    }

    /**
     * Показать только поддерживаемые параметры запуска парсера.
     */
    public function index(): View
    {
        $stored = ParserSetting::query()
            ->whereIn('key', ParserSettings::keys())
            ->pluck('value', 'key')
            ->all();

        return view('admin.settings.index', [
            'title' => 'Настройки',
            'settings' => ParserSettings::withDefaults($stored),
        ]);
    }

    /**
     * Атомарно создать отсутствующие строки и обновить разрешённые настройки.
     */
    public function update(UpdateRequest $request): RedirectResponse
    {
        $values = ParserSettings::normalize($request->validated());
        $now = CarbonImmutable::now('UTC')->format('Y-m-d H:i:s');
        $rows = [];
        foreach ($values as $key => $value) {
            $rows[] = [
                'key' => $key,
                'value' => $value,
                'created_at' => $now,
                'updated_at' => $now,
            ];
        }

        $setting = new ParserSetting;
        DB::connection($setting->getConnectionName())->transaction(
            fn () => $setting->newQuery()->upsert(
                $rows,
                ['key'],
                ['value', 'updated_at'],
            ),
        );

        return redirect()
            ->route('admin.settings.index')
            ->with('success', 'Настройки парсера сохранены. Они применятся при следующем запуске.');
    }
}
