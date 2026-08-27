# Third-party notices

The Laravel administration panel in `admin/` is based on
[`janickiy/laravel13_adminpanel`](https://github.com/janickiy/laravel13_adminpanel/tree/69ca06aa94e55cf23e2ca7c28527fee921f9abb9),
commit `69ca06aa94e55cf23e2ca7c28527fee921f9abb9` (retrieved 2026-08-26).
Its `composer.json` declares the project license as MIT.

The bundled interface assets include AdminLTE, Bootstrap, DataTables, Font Awesome,
SweetAlert2 and other libraries. Their own license files and notices remain under
`admin/public/plugins/` and `admin/public/dist/` where supplied upstream.

`docker/parser/seccomp_profile.json` is vendored byte-for-byte from
[Microsoft Playwright v1.62.0](https://github.com/microsoft/playwright/blob/e3950d9c140d007bd52853b45813c6274b24e36f/utils/docker/seccomp_profile.json)
(Apache-2.0). Its SHA-256 is
`cc3e61cabda6bbc1e53e54d27ba4d55a9d3be829b6dd1a596f4a7b31b1cc7849`.
