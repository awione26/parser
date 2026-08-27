<?php

namespace App\Http\Controllers\Admin;

use App\Exports\ProfessionalXlsxExporter;
use App\Models\Professional;
use App\Support\ProfessionalFilters;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\StreamedResponse;

final class ProfessionalExportController extends Controller
{
    public function __construct(private readonly ProfessionalXlsxExporter $exporter)
    {
        parent::__construct();

        $this->middleware('permission:admin');
    }

    /**
     * Скачивает текущую отфильтрованную выборку мастеров как Excel-файл.
     */
    public function __invoke(Request $request): StreamedResponse
    {
        $query = Professional::query();
        ProfessionalFilters::apply($query, $request);

        $filename = 'masters-'.now()->format('Y-m-d-His').'.xlsx';

        return response()->streamDownload(
            fn () => $this->exporter->write($query),
            $filename,
            [
                'Cache-Control' => 'no-store, private',
                'Content-Type' => 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'X-Accel-Buffering' => 'no',
            ],
        );
    }
}
