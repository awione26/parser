<?php

namespace App\Http\Traits;

trait StaticTableName
{
    public static function getTableName(): string
    {
        return with(new static)->getTable();
    }
}
