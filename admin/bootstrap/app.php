<?php

use App\Http\Middleware\AdminSecurityHeaders;
use App\Http\Middleware\CheckPermission;
use Illuminate\Foundation\Application;
use Illuminate\Foundation\Configuration\Exceptions;
use Illuminate\Foundation\Configuration\Middleware;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;

return Application::configure(basePath: dirname(__DIR__))
    ->withRouting(
        web: __DIR__.'/../routes/web.php',
        commands: __DIR__.'/../routes/console.php',
        health: '/up',
        then: function (): void {
            Route::middleware(['web', AdminSecurityHeaders::class])
                ->prefix('cp')
                ->group(base_path('routes/cp.php'));
        },
    )
    ->withMiddleware(function (Middleware $middleware): void {
        $middleware->alias([
            'permission' => CheckPermission::class,
        ]);
        $middleware->redirectGuestsTo(fn (Request $request) => $request->expectsJson() ? null : route('login'));
    })
    ->withExceptions(function (Exceptions $exceptions): void {})->create();
