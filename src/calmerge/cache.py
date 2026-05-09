import logging
import math
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime

MIN_TTL = 300.0  # 5 minutes

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    content: bytes
    fetched_at: float
    ttl: float
    etag: str | None
    last_modified: str | None


class SourceCache:
    def __init__(self) -> None:
        self._store: dict[str, CacheEntry] = {}

    def get(self, url: str) -> CacheEntry | None:
        entry = self._store.get(url)
        if entry is None:
            logger.trace("Cache get '%s': not found", url)  # type: ignore[attr-defined]
            return None
        elapsed = time.monotonic() - entry.fetched_at
        if elapsed < entry.ttl:
            logger.trace("Cache get '%s': fresh (%.0fs remaining)", url, entry.ttl - elapsed)  # type: ignore[attr-defined]
            return entry
        logger.trace("Cache get '%s': stale (expired %.0fs ago)", url, elapsed - entry.ttl)  # type: ignore[attr-defined]
        return None

    def get_stale(self, url: str) -> CacheEntry | None:
        return self._store.get(url)

    def set(self, url: str, entry: CacheEntry) -> None:
        logger.trace(
            "Cache set '%s' ttl=%s",
            url,
            "inf" if not math.isfinite(entry.ttl) else f"{entry.ttl:.0f}s",
        )  # type: ignore[attr-defined]
        self._store[url] = entry

    def invalidate(self, url: str) -> None:
        self._store.pop(url, None)


def parse_cache_ttl(headers: dict[str, str]) -> float:
    cc = headers.get("cache-control", "") or headers.get("Cache-Control", "")
    if cc:
        tokens = [t.strip().lower() for t in cc.split(",")]
        for token in tokens:
            if token in ("no-store", "no-cache"):
                return 0.0
        for token in tokens:
            if token.startswith("max-age="):
                try:
                    return float(token[len("max-age=") :])
                except ValueError:
                    pass

    expires = headers.get("expires", "") or headers.get("Expires", "")
    if expires:
        try:
            expires_dt = parsedate_to_datetime(expires)
            ttl = expires_dt.timestamp() - time.time()
            return max(0.0, ttl)
        except Exception:
            pass

    return math.inf
