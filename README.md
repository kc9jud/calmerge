# calmerge

A lightweight HTTP service that merges multiple `.ics` calendars into a single shareable URL. Supports full event details or free/busy-only mode to share availability without leaking event details.

## Features

- Serves one or more named calendar endpoints (`/work.ics`, `/availability.ics`, etc.)
- Each endpoint aggregates any number of source calendars (URLs or local files)
- **Free/busy mode**: strips SUMMARY, DESCRIPTION, LOCATION, ORGANIZER and other personal fields — keeps only timing information
- Respects `Cache-Control` and `Expires` headers from remote sources; propagates minimum TTL to callers
- On-demand generation — no background workers; ideal for reverse proxy + systemd socket activation

## Quick start

```bash
# Install
uv sync

# Configure
cp config.toml.example config.toml
$EDITOR config.toml

# Run (development)
uv run calmerge --config config.toml
```

Your calendars are now available at `http://127.0.0.1:5000/<name>.ics`.

## Configuration

See `config.toml.example` for a fully annotated example. The key concepts:

```toml
[defaults]
freebusy = false

[[calendars]]
name = "availability"        # → /availability.ics
freebusy = true              # strip personal details
sources = [
    { url = "https://calendar.example.com/work.ics", id = "work" },
    { file = "/home/user/personal.ics", id = "personal" },
]
```

- `id` is required on every source and is used as a UID namespace prefix
- `freebusy = true` replaces all SUMMARY values with "Busy" and removes DESCRIPTION, LOCATION, ORGANIZER, ATTENDEE, and other personal fields

Set the config path via `--config` flag or `CALMERGE_CONFIG` environment variable.

## Docker

### Standalone (no nginx)

```bash
cp config.toml.example config.toml
$EDITOR config.toml
docker compose up -d
```

The service binds to `127.0.0.1:8080`. Calendars are available at `http://127.0.0.1:8080/<name>.ics`.

### With nginx reverse proxy

```bash
docker compose -f docker-compose.nginx.yml up -d
```

nginx listens on port 80. Calendars are served at `http://your-host/calmerge/<name>.ics`. The calmerge container has no public port — only nginx can reach it.

If you mount local calendar files, add a volume to the `calmerge` service in the compose file, e.g.:

```yaml
volumes:
  - ./config.toml:/config/config.toml:ro
  - /home/user/calendars:/calendars:ro
```

### Pre-built image

A Docker image is automatically published to the GitHub Container Registry on every push to `main` and on version tags:

```bash
docker pull ghcr.io/kc9jud/calmerge:main
docker pull ghcr.io/kc9jud/calmerge:v1.2.3
```

To use the pre-built image instead of building locally, replace `build: .` with `image: ghcr.io/kc9jud/calmerge:main` in the compose file.

## Production deployment

### gunicorn (standalone)

```bash
CALMERGE_CONFIG=/etc/calmerge/config.toml \
  gunicorn --workers 1 --bind unix:/run/calmerge/calmerge.sock --timeout 60 \
    "calmerge.app:create_app()"
```

Single worker is recommended so all requests share the same in-memory source cache.

### systemd socket activation

For homelab use where the process should only run when polled:

```ini
# /etc/systemd/system/calmerge.socket
[Socket]
ListenStream=/run/calmerge/calmerge.sock

[Install]
WantedBy=sockets.target
```

```ini
# /etc/systemd/system/calmerge.service
[Unit]
Description=calmerge calendar aggregator
Requires=calmerge.socket

[Service]
User=calmerge
WorkingDirectory=/opt/calmerge
Environment=CALMERGE_CONFIG=/etc/calmerge/config.toml
ExecStart=/opt/calmerge/.venv/bin/gunicorn \
    --workers 1 --bind fd://0 --timeout 60 \
    "calmerge.app:create_app()"
Restart=on-failure
```

```bash
systemctl enable --now calmerge.socket
```

The process starts on the first incoming connection and systemd restarts it on failure.

### nginx example

```nginx
location ~ ^/[a-z][a-z0-9_-]*\.ics$ {
    proxy_pass http://unix:/run/calmerge/calmerge.sock;
    proxy_set_header Host $host;
    proxy_read_timeout 65s;
}
```
