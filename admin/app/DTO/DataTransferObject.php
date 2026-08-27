<?php

namespace App\DTO;

interface DataTransferObject
{
    /**
     * @return array<string, mixed>
     */
    public function toArray(): array;
}
