from icalendar import Calendar

from tests.conftest import SAMPLE_ICS, URL_HOME, URL_WORK


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.data == b"ok"


def test_unknown_calendar_returns_404(client):
    response = client.get("/nonexistent.ics")
    assert response.status_code == 404


def test_known_calendar_returns_200(client, httpx_mock):
    httpx_mock.add_response(url=URL_WORK, content=SAMPLE_ICS)
    response = client.get("/work.ics")
    assert response.status_code == 200


def test_content_type_header(client, httpx_mock):
    httpx_mock.add_response(url=URL_WORK, content=SAMPLE_ICS)
    response = client.get("/work.ics")
    assert "text/calendar" in response.content_type


def test_response_is_parseable_ics(client, httpx_mock):
    httpx_mock.add_response(url=URL_WORK, content=SAMPLE_ICS)
    response = client.get("/work.ics")
    cal = Calendar.from_ical(response.data)
    assert cal["VERSION"] == "2.0"


def test_all_sources_fail_returns_503(client, httpx_mock):
    import httpx as _httpx

    httpx_mock.add_exception(_httpx.ConnectError("refused"), url=URL_WORK)
    httpx_mock.add_exception(_httpx.ConnectError("refused"), url=URL_HOME)
    response = client.get("/combined.ics")
    assert response.status_code == 503


def test_partial_source_failure_returns_200(client, httpx_mock):
    import httpx as _httpx

    httpx_mock.add_response(url=URL_WORK, content=SAMPLE_ICS)
    httpx_mock.add_exception(_httpx.ConnectError("refused"), url=URL_HOME)
    response = client.get("/combined.ics")
    assert response.status_code == 200


def test_cache_control_max_age(client, httpx_mock):
    httpx_mock.add_response(
        url=URL_WORK,
        content=SAMPLE_ICS,
        headers={"Cache-Control": "max-age=300"},
    )
    response = client.get("/work.ics")
    assert response.headers.get("Cache-Control") == "max-age=300"


def test_cache_control_no_cache(client, httpx_mock):
    httpx_mock.add_response(
        url=URL_WORK,
        content=SAMPLE_ICS,
        headers={"Cache-Control": "no-cache"},
    )
    response = client.get("/work.ics")
    assert response.headers.get("Cache-Control") == "max-age=300"


def test_cache_control_omitted_when_no_directives(client, httpx_mock):
    httpx_mock.add_response(url=URL_WORK, content=SAMPLE_ICS)
    response = client.get("/work.ics")
    assert "Cache-Control" not in response.headers


def test_freebusy_calendar_strips_summary(client, httpx_mock):
    httpx_mock.add_response(url=URL_WORK, content=SAMPLE_ICS)
    httpx_mock.add_response(url=URL_HOME, content=SAMPLE_ICS)
    response = client.get("/combined.ics")
    cal = Calendar.from_ical(response.data)
    for event in cal.walk("VEVENT"):
        assert str(event["SUMMARY"]) == "Busy"


def test_full_details_calendar_keeps_summary(client, httpx_mock):
    httpx_mock.add_response(url=URL_WORK, content=SAMPLE_ICS)
    response = client.get("/work.ics")
    cal = Calendar.from_ical(response.data)
    for event in cal.walk("VEVENT"):
        assert str(event["SUMMARY"]) == "Team Meeting"
