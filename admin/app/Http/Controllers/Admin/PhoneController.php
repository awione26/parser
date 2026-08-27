<?php

namespace App\Http\Controllers\Admin;

use App\Models\Professional;
use App\Support\PhoneNumber;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Symfony\Component\HttpFoundation\Response;

class PhoneController extends Controller
{
    public function show(Request $request, Professional $professional): JsonResponse
    {
        $phone = $professional->phone;
        if (! PhoneNumber::isValid($phone)) {
            return response()->json(
                ['message' => 'Телефон недоступен или имеет неверный формат.'],
                Response::HTTP_UNPROCESSABLE_ENTITY,
            );
        }

        DB::table('phone_access_logs')->insert([
            'user_id' => $request->user()->id,
            'professional_id' => $professional->id,
            'action' => 'reveal',
            'created_at' => now(),
        ]);

        return response()->json(['phone' => $phone]);
    }
}
