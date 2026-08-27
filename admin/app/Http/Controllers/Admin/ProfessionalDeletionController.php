<?php

namespace App\Http\Controllers\Admin;

use App\Http\Requests\Admin\Professional\BulkDeleteRequest;
use App\Http\Requests\Admin\Professional\DeleteRequest;
use App\Models\Professional;
use Illuminate\Http\JsonResponse;
use Illuminate\Support\Facades\DB;

final class ProfessionalDeletionController extends Controller
{
    public function __construct()
    {
        parent::__construct();

        $this->middleware('permission:admin');
    }

    /**
     * Удаляет одного мастера и возвращает фактическое количество удалённых записей.
     */
    public function destroy(DeleteRequest $request, Professional $professional): JsonResponse
    {
        $deleted = $this->deleteIds([(int) $professional->getKey()]);

        return response()->json([
            'deleted' => $deleted,
            'message' => $deleted === 1 ? 'Мастер удалён.' : 'Мастер уже отсутствует.',
        ]);
    }

    /**
     * Удаляет отмеченных мастеров одной транзакцией на соединении базы парсера.
     */
    public function bulkDestroy(BulkDeleteRequest $request): JsonResponse
    {
        $ids = array_map('intval', $request->validated('ids'));
        $deleted = $this->deleteIds($ids);

        return response()->json([
            'deleted' => $deleted,
            'message' => "Удалено мастеров: {$deleted}.",
        ]);
    }

    /**
     * Удаляет только строки мастеров; связанные категории и рубрики удаляет FK cascade.
     *
     * @param  list<int>  $ids
     */
    private function deleteIds(array $ids): int
    {
        $professional = new Professional;

        return (int) DB::connection($professional->getConnectionName())->transaction(
            fn (): int => $professional->newQuery()->whereKey($ids)->delete(),
        );
    }
}
