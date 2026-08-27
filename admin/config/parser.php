<?php

return [
    /*
    |--------------------------------------------------------------------------
    | Parser-owned data
    |--------------------------------------------------------------------------
    |
    | Models in App\Models use this connection. Alembic manages their schema;
    | the admin panel may read parser data and its event log. Administrators may
    | delete complete profiles and update the fixed parser settings whitelist.
    |
    */
    'connection' => env('PARSER_DB_CONNECTION', 'parser'),
];
