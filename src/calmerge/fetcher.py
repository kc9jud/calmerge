import logging
import math
import time
from pathlib import Path

import httpx

from . import TRACE
from .cache import MIN_TTL, CacheEntry, SourceCache, parse_cache_ttl
from .config import SourceConfig

logger = logging.getLogger(__name__)


def fetch_source(
    source: SourceConfig,
    cache: SourceCache,
    http_client: httpx.Client,
) -> bytes | None:
    try:
        if source.url:
            return _fetch_url(source.url, cache, http_client)
        if source.file:
            return _fetch_file(source.file)
    except Exception:
        logger.warning("Unexpected error fetching source '%s'", source.id, exc_info=True)
    return None


def _fetch_url(
    url: str,
    cache: SourceCache,
    http_client: httpx.Client,
) -> bytes | None:
    logger.trace("Checking source cache for '%s'", url)  # type: ignore[attr-defined]
    fresh = cache.get(url)
    if fresh is not None:
        logger.debug("Source cache hit for '%s'", url)
        return fresh.content

    logger.debug("Source cache miss for '%s', fetching", url)
    stale = cache.get_stale(url)

    headers: dict[str, str] = {}
    if stale is not None:
        if stale.etag:
            headers["If-None-Match"] = stale.etag
        elif stale.last_modified:
            headers["If-Modified-Since"] = stale.last_modified

    try:
        response = http_client.get(url, headers=headers)
    except Exception as exc:
        logger.warning("Failed to fetch '%s': %s", url, exc)
        return stale.content if stale is not None else None

    if response.status_code == 304:
        if stale is not None:
            ttl = max(parse_cache_ttl(dict(response.headers)), MIN_TTL)
            # Reset the TTL by updating fetched_at
            updated = CacheEntry(
                content=stale.content,
                fetched_at=time.monotonic(),
                ttl=ttl,
                etag=stale.etag,
                last_modified=stale.last_modified,
            )
            cache.set(url, updated)
            logger.debug("304 for '%s', refreshed cache entry with ttl=%s", url, "inf" if not math.isfinite(ttl) else f"{ttl:.0f}s")
            return stale.content
        logger.warning("Got 304 for '%s' but no cached content available", url)
        return None

    if response.status_code == 200:
        resp_headers = dict(response.headers)
        ttl = max(parse_cache_ttl(resp_headers), MIN_TTL)
        entry = CacheEntry(
            content=response.content,
            fetched_at=time.monotonic(),
            ttl=ttl,
            etag=response.headers.get("etag"),
            last_modified=response.headers.get("last-modified"),
        )
        cache.set(url, entry)
        logger.debug("Fetched '%s': %d bytes, ttl=%s", url, len(response.content), "inf" if not math.isfinite(ttl) else f"{ttl:.0f}s")
        return response.content

    logger.warning("Unexpected status %d for '%s'", response.status_code, url)
    return stale.content if stale is not None else None


def _fetch_file(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError as exc:
        logger.warning("Failed to read file '%s': %s", path, exc)
        return None
