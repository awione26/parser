<?php

return [
    /*
    |--------------------------------------------------------------------------
    | Parser-owned data
    |--------------------------------------------------------------------------
    |
    | Models in App\Models use this connection. Alembic manages their schema;
    | the admin panel may read parser data and its event log. Administrators may
    | delete complete profiles, update the fixed settings whitelist and manage
    | the parser_categories rows that define the category crawl plan.
    |
    */
    'connection' => env('PARSER_DB_CONNECTION', 'parser'),
];
