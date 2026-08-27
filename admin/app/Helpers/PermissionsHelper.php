<?php

namespace App\Helpers;

use Illuminate\Support\Facades\Auth;

class PermissionsHelper
{
    public static function has_permission(string $permissions = ''): bool
    {
        $user = Auth::user();
        if ($user === null) {
            return false;
        }

        if ($user->isAdmin()) {
            return true;
        }

        return in_array($user->role, array_filter(explode('|', $permissions)), true);
    }
}
