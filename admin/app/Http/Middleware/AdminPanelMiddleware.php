<?php

namespace App\Http\Middleware;

use Illuminate\Auth\Middleware\Authenticate as Middleware;
use Illuminate\Http\Request;

class AdminPanelMiddleware extends Middleware
{
    /**
     * Get the path the user should be redirected to when they are not authenticated.
     *
     * @return string|null
     */
    protected function redirectTo(Request $request)
    {
        if (! $request->expectsJson()) {
            return route('login');
        }
    }
}
