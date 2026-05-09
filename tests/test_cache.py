import math
import time

from freezegun import freeze_time

from calmerge.cache import CacheEntry, SourceCache, parse_cache_ttl


def make_entry(content=b"data", ttl=60.0, etag=None, last_modified=None):
    return CacheEntry(
        content=content,
        fetched_at=time.monotonic(),
        ttl=ttl,
        etag=etag,
        last_modified=last_modified,
    )


def test_get_returns_none_on_miss():
    cache = SourceCache()
    assert cache.get("https://example.com/cal.ics") is None


def test_get_returns_entry_when_fresh():
    cache = SourceCache()
    entry = make_entry(ttl=3600.0)
    cache.set("https://example.com/cal.ics", entry)
    result = cache.get("https://example.com/cal.ics")
    assert result is entry


def test_get_returns_none_when_expired(monkeypatch):
    cache = SourceCache()
    entry = CacheEntry(
        content=b"data",
        fetched_at=time.monotonic() - 120,  # fetched 120s ago
        ttl=60.0,  # TTL was 60s
        etag=None,
        last_modified=None,
    )
    cache.set("https://example.com/cal.ics", entry)
    assert cache.get("https://example.com/cal.ics") is None


def test_get_stale_returns_expired_entry():
    cache = SourceCache()
    entry = CacheEntry(
        content=b"data",
        fetched_at=time.monotonic() - 120,
        ttl=60.0,
        etag=None,
        last_modified=None,
    )
    cache.set("https://example.com/cal.ics", entry)
    assert cache.get_stale("https://example.com/cal.ics") is entry


def test_get_stale_returns_none_on_miss():
    cache = SourceCache()
    assert cache.get_stale("https://example.com/cal.ics") is None


def test_invalidate_removes_entry():
    cache = SourceCache()
    cache.set("https://example.com/cal.ics", make_entry())
    cache.invalidate("https://example.com/cal.ics")
    assert cache.get_stale("https://example.com/cal.ics") is None


def test_invalidate_missing_key_is_noop():
    cache = SourceCache()
    cache.invalidate("https://example.com/missing.ics")  # should not raise


# --- parse_cache_ttl ---


def test_parse_cache_ttl_max_age():
    assert parse_cache_ttl({"Cache-Control": "max-age=300"}) == 300.0


def test_parse_cache_ttl_max_age_lowercase():
    assert parse_cache_ttl({"cache-control": "max-age=3600"}) == 3600.0


def test_parse_cache_ttl_no_cache():
    assert parse_cache_ttl({"Cache-Control": "no-cache"}) == 0.0


def test_parse_cache_ttl_no_store():
    assert parse_cache_ttl({"Cache-Control": "no-store"}) == 0.0


def test_parse_cache_ttl_no_store_with_max_age():
    assert parse_cache_ttl({"Cache-Control": "no-store, max-age=300"}) == 0.0


@freeze_time("2026-01-01 12:00:00")
def test_parse_cache_ttl_expires_future():
    ttl = parse_cache_ttl({"Expires": "Thu, 01 Jan 2026 13:00:00 GMT"})
    assert abs(ttl - 3600.0) < 2.0


@freeze_time("2026-01-01 12:00:00")
def test_parse_cache_ttl_expires_past():
    ttl = parse_cache_ttl({"Expires": "Thu, 01 Jan 2026 11:00:00 GMT"})
    assert ttl == 0.0


def test_parse_cache_ttl_no_headers():
    assert parse_cache_ttl({}) == math.inf


def test_parse_cache_ttl_max_age_takes_priority_over_expires():
    result = parse_cache_ttl(
        {
            "Cache-Control": "max-age=120",
            "Expires": "Thu, 01 Jan 2026 13:00:00 GMT",
        }
    )
    assert result == 120.0


def test_parse_cache_ttl_zero_max_age():
    assert parse_cache_ttl({"Cache-Control": "max-age=0"}) == 0.0


def test_parse_cache_ttl_malformed_max_age():
    assert parse_cache_ttl({"Cache-Control": "max-age=notanumber"}) == math.inf


def test_parse_cache_ttl_malformed_expires():
    assert parse_cache_ttl({"Expires": "not-a-valid-date"}) == math.inf
