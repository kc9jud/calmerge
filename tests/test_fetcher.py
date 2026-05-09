import time
from pathlib import Path

import httpx

from calmerge.cache import CacheEntry, SourceCache
from calmerge.config import SourceConfig
from calmerge.fetcher import _fetch_file, _fetch_url, fetch_source

URL = "https://example.com/cal.ics"
SAMPLE = b"BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n"


def make_source(url=None, file=None, id="test"):
    return SourceConfig(id=id, url=url, file=file)


# --- _fetch_url ---


def test_fetch_url_success(httpx_mock):
    httpx_mock.add_response(url=URL, content=SAMPLE, headers={"Cache-Control": "max-age=300"})
    cache = SourceCache()
    client = httpx.Client()
    result = _fetch_url(URL, cache, client)
    assert result == SAMPLE
    entry = cache.get_stale(URL)
    assert entry is not None
    assert entry.content == SAMPLE
    assert entry.ttl == 300.0


def test_fetch_url_cache_hit(httpx_mock):
    cache = SourceCache()
    entry = CacheEntry(
        content=SAMPLE,
        fetched_at=time.monotonic(),
        ttl=3600.0,
        etag=None,
        last_modified=None,
    )
    cache.set(URL, entry)
    client = httpx.Client()
    result = _fetch_url(URL, cache, client)
    assert result == SAMPLE
    assert len(httpx_mock.get_requests()) == 0


def test_fetch_url_conditional_304(httpx_mock):
    httpx_mock.add_response(url=URL, status_code=304, headers={"Cache-Control": "max-age=600"})
    cache = SourceCache()
    stale_entry = CacheEntry(
        content=SAMPLE,
        fetched_at=time.monotonic() - 400,
        ttl=300.0,
        etag='"abc123"',
        last_modified=None,
    )
    cache.set(URL, stale_entry)
    client = httpx.Client()
    result = _fetch_url(URL, cache, client)
    assert result == SAMPLE
    req = httpx_mock.get_requests()[0]
    assert req.headers.get("if-none-match") == '"abc123"'
    updated = cache.get_stale(URL)
    assert updated.ttl == 600.0


def test_fetch_url_conditional_200_replaces_stale(httpx_mock):
    new_content = b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nEND:VCALENDAR\r\n"
    httpx_mock.add_response(url=URL, content=new_content, headers={"Cache-Control": "max-age=120"})
    cache = SourceCache()
    stale_entry = CacheEntry(
        content=SAMPLE,
        fetched_at=time.monotonic() - 400,
        ttl=300.0,
        etag=None,
        last_modified="Mon, 01 Jan 2026 00:00:00 GMT",
    )
    cache.set(URL, stale_entry)
    client = httpx.Client()
    result = _fetch_url(URL, cache, client)
    assert result == new_content
    req = httpx_mock.get_requests()[0]
    assert req.headers.get("if-modified-since") == "Mon, 01 Jan 2026 00:00:00 GMT"


def test_fetch_url_network_error_no_cache(httpx_mock):
    httpx_mock.add_exception(httpx.ConnectError("refused"))
    cache = SourceCache()
    client = httpx.Client()
    result = _fetch_url(URL, cache, client)
    assert result is None


def test_fetch_url_network_error_returns_stale(httpx_mock):
    httpx_mock.add_exception(httpx.ConnectError("refused"))
    cache = SourceCache()
    stale_entry = CacheEntry(
        content=SAMPLE,
        fetched_at=time.monotonic() - 400,
        ttl=300.0,
        etag=None,
        last_modified=None,
    )
    cache.set(URL, stale_entry)
    client = httpx.Client()
    result = _fetch_url(URL, cache, client)
    assert result == SAMPLE


def test_fetch_url_http_500_no_cache(httpx_mock):
    httpx_mock.add_response(url=URL, status_code=500)
    cache = SourceCache()
    client = httpx.Client()
    result = _fetch_url(URL, cache, client)
    assert result is None


def test_fetch_url_http_500_returns_stale(httpx_mock):
    httpx_mock.add_response(url=URL, status_code=500)
    cache = SourceCache()
    stale_entry = CacheEntry(
        content=SAMPLE,
        fetched_at=time.monotonic() - 400,
        ttl=300.0,
        etag=None,
        last_modified=None,
    )
    cache.set(URL, stale_entry)
    client = httpx.Client()
    result = _fetch_url(URL, cache, client)
    assert result == SAMPLE


def test_fetch_url_etag_stored(httpx_mock):
    httpx_mock.add_response(
        url=URL, content=SAMPLE, headers={"ETag": '"xyz"', "Cache-Control": "max-age=60"}
    )
    cache = SourceCache()
    client = httpx.Client()
    _fetch_url(URL, cache, client)
    entry = cache.get_stale(URL)
    assert entry.etag == '"xyz"'


# --- _fetch_file ---


def test_fetch_file_success(tmp_path):
    f = tmp_path / "cal.ics"
    f.write_bytes(SAMPLE)
    result = _fetch_file(f)
    assert result == SAMPLE


def test_fetch_file_missing(tmp_path):
    result = _fetch_file(tmp_path / "nonexistent.ics")
    assert result is None


def test_fetch_file_returns_none_on_permission_error(tmp_path, monkeypatch):
    f = tmp_path / "cal.ics"
    f.write_bytes(SAMPLE)

    def raise_permission(self):
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "read_bytes", raise_permission)
    result = _fetch_file(f)
    assert result is None


# --- fetch_source ---


def test_fetch_source_url(httpx_mock):
    httpx_mock.add_response(url=URL, content=SAMPLE)
    cache = SourceCache()
    client = httpx.Client()
    source = make_source(url=URL)
    result = fetch_source(source, cache, client)
    assert result == SAMPLE


def test_fetch_source_file(tmp_path):
    f = tmp_path / "cal.ics"
    f.write_bytes(SAMPLE)
    cache = SourceCache()
    client = httpx.Client()
    source = make_source(file=f)
    result = fetch_source(source, cache, client)
    assert result == SAMPLE


def test_fetch_source_failure_returns_none(httpx_mock):
    httpx_mock.add_exception(httpx.ConnectError("refused"))
    cache = SourceCache()
    client = httpx.Client()
    source = make_source(url=URL)
    result = fetch_source(source, cache, client)
    assert result is None


def test_fetch_url_304_without_cached_content(httpx_mock):
    httpx_mock.add_response(url=URL, status_code=304)
    cache = SourceCache()
    client = httpx.Client()
    result = _fetch_url(URL, cache, client)
    assert result is None


def test_fetch_source_unexpected_exception(monkeypatch):
    from calmerge import fetcher

    def boom(url, cache, http_client):
        raise RuntimeError("unexpected!")

    monkeypatch.setattr(fetcher, "_fetch_url", boom)
    cache = SourceCache()
    client = httpx.Client()
    source = make_source(url=URL)
    result = fetch_source(source, cache, client)
    assert result is None
