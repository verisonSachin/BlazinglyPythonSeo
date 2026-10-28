# WebPageTest compatibility backend

Python/FastAPI replacement for the legacy PHP backend of this repository.

**Guiding constraint: the filesystem is the database.** Test results live under
`php_original/www/results/YY/MM/DD/<shard>/<id>/`, coordination state under
`php_original/www/tmp/`, and agent job files under `php_original/www/work/jobs/`.
This package must read and write those formats exactly as `www/common_lib.inc`
does; it must not introduce a database as a source of truth.

The reference PHP tree is located at runtime by `app/core/layout.py`, which
accepts either `./www` or `./php_original/www` and honours `WPT_WWW_ROOT` /
`WPT_SETTINGS_DIR` overrides.

## Layout

```
app/core/      settings (PHP-INI compatible), paths, cache, errors
app/storage/   testinfo files, gzip, queue, locks, testers, state markers
app/domain/    test IDs, test metadata, result parsing, metrics
app/api/       FastAPI routers (compat routes mirror the legacy .php paths)
app/jobs/      cron replacements
tests/         unit + differential tests (run against local PHP 8.5)
```

## Development

This package is managed with [uv](https://docs.astral.sh/uv/). `uv.lock` is the
source of truth for resolved versions.

```bash
uv sync                 # create .venv from uv.lock
uv run pytest           # full suite
uv run uvicorn app.main:app --reload
```

Add a dependency with `uv add <package>`; add a dev-only tool with
`uv add --dev <package>`. Do not hand-edit `uv.lock`.

Differential tests execute the local `php` binary to produce expected values for
`parse_ini_file` and are skipped when PHP is unavailable.

## Compatibility rules already encoded

* `parse_ini_file` semantics (booleans, quoting, `;` vs `#`, `${ENV}`).
* Settings merge order: `settings.ini` -> `common/settings.ini` -> `server/settings.ini`.
* Settings cache TTL 60s, server-secret TTL 3600s (60s when absent).
* `GetTestPath` layout for modern, sharded and legacy (`olddir`/`oldsubdir`) IDs.
* `ShardKey` / `GenerateTestID` / `ValidateTestId` behaviour.
* Cookie names: `sha256(sha1(name + cookie_secret) + server_secret)`.
* `testinfo.ini` is CRLF with duplicate-free key order and no quoting.
