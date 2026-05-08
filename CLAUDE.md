# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**calmerge** is a lightweight Python HTTP service that merges multiple `.ics` calendar files/URLs into a single endpoint. It is designed to sit behind a reverse proxy (nginx, Caddy, etc.) and serve on demand — no background workers or scheduled refresh.

## Setup

```bash
uv sync --extra dev   # install all dependencies including dev tools
```

## Running

Development server (Werkzeug, not for production):
```bash
uv run calmerge --config config.toml
# or
CALMERGE_CONFIG=config.toml uv run flask --app calmerge.app:create_app run
```

Production (gunicorn, single worker recommended for cache locality):
```bash
CALMERGE_CONFIG=/etc/calmerge/config.toml \
  uv run gunicorn --workers 1 --bind 127.0.0.1:5000 --timeout 60 \
    "calmerge.app:create_app()"
```

See `config.toml.example` for configuration format.

## Tests

```bash
uv run pytest                           # run all tests
uv run pytest tests/test_merger.py -v  # run a specific file
uv run pytest -k test_freebusy         # run matching tests
```

## Linter

```bash
uv run ruff check .     # lint
uv run ruff format .    # format
uv run ruff check --fix .  # auto-fix lint issues
```

## Architecture

```
src/calmerge/
├── app.py      Flask application factory; routes GET /<name>.ics and GET /health
├── config.py   TOML config loading; AppConfig / CalendarConfig / SourceConfig dataclasses
├── cache.py    In-memory TTL cache (SourceCache) for remote .ics URLs; parse_cache_ttl()
├── fetcher.py  fetch_source() — reads from URL (with HTTP caching) or local file
└── merger.py   merge_calendars() — parses, deduplicates VTIMEZONEs, prefixes UIDs,
                optionally anonymizes events (freebusy mode); compute_min_ttl()
```

### Data flow

1. `GET /<name>.ics` hits `app.py:serve_calendar`
2. Looks up `CalendarConfig` by name from `AppConfig` (loaded at startup from `config.toml`)
3. Calls `fetch_source()` for each source — checks `SourceCache` first, then HTTP/file
4. `merge_calendars()` combines results: deduplicates VTIMEZONEs, prefixes UIDs (`id:original_uid`), and strips personal data if `freebusy=true`
5. Minimum TTL across sources becomes the `Cache-Control` header on the response

### Key design decisions

- **`id` is required on every source** — used as the UID namespace prefix to avoid collisions across calendars
- **`freebusy` is per calendar, not per source** — all sources in a calendar are treated uniformly
- **In-memory cache** — per-worker; cache locality is why single gunicorn worker is recommended
- **Never raises in fetch_source** — source failures are logged as warnings; remaining sources are merged
- **File sources are re-read on every request** — mtime check is implicit; file I/O is cheap relative to HTTP
