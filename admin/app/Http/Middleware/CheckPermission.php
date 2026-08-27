<?php

namespace App\Http\Middleware;

use App\Helpers\PermissionsHelper;
use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

class CheckPermission
{
    protected PermissionsHelper $helper;

    /**
     * Creates a new instance of the middleware.
     */
    public function __construct(PermissionsHelper $helper)
    {
        $this->helper = $helper;
    }

    /**
     * @return mixed|void
     */
    public function handle(Request $request, Closure $next, string $permissions): Response
    {
        if ($this->helper->has_permission($permissions)) {
            return $next($request);
        }

        abort(403);
    }
}
