<?php

namespace App\Http\Controllers\Admin;

use Illuminate\Contracts\View\View;

class ParserLogController extends Controller
{
    public function __construct()
    {
        parent::__construct();
        $this->middleware('permission:admin');
    }

    /**
     * Показать страницу журнала запусков парсера.
     */
    public function index(): View
    {
        return view('admin.logs.index', [
            'title' => 'Журнал событий',
        ]);
    }
}
