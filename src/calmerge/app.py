import argparse
import logging
import math
import os
from pathlib import Path

import httpx
from flask import Flask, Response, abort

from .cache import SourceCache
from .config import AppConfig, load_config
from .fetcher import fetch_source
from .merger import compute_min_ttl, merge_calendars

logger = logging.getLogger(__name__)


def create_app(config_path: Path | None = None) -> Flask:
    app = Flask(__name__)

    resolved_path = config_path or Path(os.environ.get("CALMERGE_CONFIG", "config.toml"))
    app_config = load_config(resolved_path)
    app.config["CALMERGE_CONFIG"] = app_config
    app.extensions["calmerge_cache"] = SourceCache()
    app.extensions["calmerge_http"] = httpx.Client(
        timeout=httpx.Timeout(30.0),
        follow_redirects=True,
        headers={"User-Agent": "calmerge/0.1"},
    )

    @app.get("/<name>.ics")
    def serve_calendar(name: str) -> Response:
        config: AppConfig = app.config["CALMERGE_CONFIG"]
        cal_config = config.calendars_by_name.get(name)
        if cal_config is None:
            abort(404)

        cache: SourceCache = app.extensions["calmerge_cache"]
        http_client: httpx.Client = app.extensions["calmerge_http"]

        source_bytes = []
        for source in cal_config.sources:
            data = fetch_source(source, cache, http_client)
            if data is not None:
                source_bytes.append((source, data))
            else:
                logger.warning("Source '%s' for calendar '%s' returned no data", source.id, name)

        if not source_bytes:
            abort(503)

        ics_bytes = merge_calendars(cal_config, source_bytes)

        ttls = []
        for source in cal_config.sources:
            if source.url:
                entry = cache.get_stale(source.url)
                ttls.append(entry.ttl if entry is not None else math.inf)
            else:
                ttls.append(math.inf)

        min_ttl = compute_min_ttl(ttls)

        headers: dict[str, str] = {"Content-Type": "text/calendar; charset=utf-8"}
        if min_ttl == 0.0:
            headers["Cache-Control"] = "no-cache"
        elif min_ttl != math.inf:
            headers["Cache-Control"] = f"max-age={int(min_ttl)}"

        return Response(ics_bytes, headers=headers)

    @app.get("/health")
    def health() -> Response:
        return Response("ok", content_type="text/plain")

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="calmerge calendar aggregator")
    parser.add_argument("--config", type=Path, default=None, help="Path to config.toml")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000, help="Port to listen on (default: 5000)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    app = create_app(config_path=args.config)
    app.run(host=args.host, port=args.port)
