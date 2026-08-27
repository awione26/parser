<?php

return [
    /*
    |--------------------------------------------------------------------------
    | Parser-owned data
    |--------------------------------------------------------------------------
    |
    | Models in App\Models use this connection. Alembic manages their schema;
    | the admin panel may read parser data and its event log, and administrators
    | may delete complete professional records.
    |
    */
    'connection' => env('PARSER_DB_CONNECTION', 'parser'),
];
