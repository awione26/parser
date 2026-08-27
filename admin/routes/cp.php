<?php

use App\Http\Controllers\Admin\AdminController;
use App\Http\Controllers\Admin\AuthController;
use App\Http\Controllers\Admin\DashboardController;
use App\Http\Controllers\Admin\DataTableController;
use App\Http\Controllers\Admin\ParserLogController;
use App\Http\Controllers\Admin\ParserSettingController;
use App\Http\Controllers\Admin\PhoneController;
use App\Http\Controllers\Admin\ProfessionalController;
use App\Http\Controllers\Admin\ProfessionalDeletionController;
use App\Http\Controllers\Admin\ProfessionalExportController;
use Illuminate\Support\Facades\Route;

Route::middleware('guest')->group(function (): void {
    Route::get('login', [AuthController::class, 'showLoginForm'])->name('login');
    Route::post('login', [AuthController::class, 'login'])->name('login.submit');
});

Route::middleware('auth')->group(function (): void {
    Route::post('logout', [AuthController::class, 'logout'])->name('logout');

    Route::get('', [DashboardController::class, 'index'])->name('admin.dashboard.index');

    Route::middleware('permission:admin')->group(function (): void {
        Route::get('logs', [ParserLogController::class, 'index'])
            ->name('admin.logs.index');
        Route::get('datatable/logs', [DataTableController::class, 'logs'])
            ->name('admin.datatable.logs');
        Route::get('settings', [ParserSettingController::class, 'index'])
            ->name('admin.settings.index');
        Route::put('settings', [ParserSettingController::class, 'update'])
            ->name('admin.settings.update');
    });

    Route::get('professionals', [ProfessionalController::class, 'index'])
        ->name('admin.professionals.index');
    Route::middleware('permission:admin')->group(function (): void {
        Route::get('professionals/export', ProfessionalExportController::class)
            ->name('admin.professionals.export');
        Route::delete('professionals/bulk', [ProfessionalDeletionController::class, 'bulkDestroy'])
            ->name('admin.professionals.bulk-destroy');
        Route::delete('professionals/{professional}', [ProfessionalDeletionController::class, 'destroy'])
            ->whereNumber('professional')
            ->name('admin.professionals.destroy');
    });
    Route::get('professionals/{professional}', [ProfessionalController::class, 'show'])
        ->whereNumber('professional')
        ->name('admin.professionals.show');
    Route::get('datatable/professionals', [DataTableController::class, 'professionals'])
        ->name('admin.datatable.professionals');

    Route::post('professionals/{professional}/phone', [PhoneController::class, 'show'])
        ->whereNumber('professional')
        ->middleware('permission:admin')
        ->name('admin.professionals.phone');

    Route::middleware('permission:admin')->prefix('administrators')->group(function (): void {
        Route::get('', [AdminController::class, 'index'])->name('admin.admin.index');
        Route::get('create', [AdminController::class, 'create'])->name('admin.admin.create');
        Route::post('', [AdminController::class, 'store'])->name('admin.admin.store');
        Route::get('{id}/edit', [AdminController::class, 'edit'])
            ->whereNumber('id')
            ->name('admin.admin.edit');
        Route::put('{id}', [AdminController::class, 'update'])
            ->whereNumber('id')
            ->name('admin.admin.update');
        Route::delete('{id}', [AdminController::class, 'destroy'])
            ->whereNumber('id')
            ->name('admin.admin.destroy');
    });
});
