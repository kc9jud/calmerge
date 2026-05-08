import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime


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
            return None
        if time.monotonic() - entry.fetched_at < entry.ttl:
            return entry
        return None

    def get_stale(self, url: str) -> CacheEntry | None:
        return self._store.get(url)

    def set(self, url: str, entry: CacheEntry) -> None:
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

    return float("inf")
