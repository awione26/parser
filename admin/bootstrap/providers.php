<?php

use App\Providers\AppServiceProvider;
use Yajra\DataTables\ButtonsServiceProvider;
use Yajra\DataTables\DataTablesServiceProvider;
use Yajra\DataTables\HtmlServiceProvider;

return [
    AppServiceProvider::class,
    DataTablesServiceProvider::class,
    ButtonsServiceProvider::class,
    DataTablesServiceProvider::class,
    HtmlServiceProvider::class,
];
