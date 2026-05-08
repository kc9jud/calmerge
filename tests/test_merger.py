from icalendar import Calendar

from calmerge.config import CalendarConfig, SourceConfig
from calmerge.merger import compute_min_ttl, merge_calendars


def make_source(id="src"):
    return SourceConfig(id=id, url=f"https://example.com/{id}.ics")


def make_calendar_config(freebusy=False, sources=None):
    if sources is None:
        sources = [make_source()]
    return CalendarConfig(name="test", freebusy=freebusy, sources=sources)


def make_ics(
    events: list[dict],
    tzid: str | None = None,
    calname: str = "Test Calendar",
) -> bytes:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Test//Test//EN",
        "CALSCALE:GREGORIAN",
    ]
    if tzid:
        lines += [
            "BEGIN:VTIMEZONE",
            f"TZID:{tzid}",
            "BEGIN:STANDARD",
            "DTSTART:19701025T030000",
            "TZOFFSETFROM:+0200",
            "TZOFFSETTO:+0100",
            "END:STANDARD",
            "END:VTIMEZONE",
        ]
    for ev in events:
        lines += ["BEGIN:VEVENT"]
        for k, v in ev.items():
            lines.append(f"{k}:{v}")
        lines += ["END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines).encode()


SAMPLE_EVENT = {
    "UID": "uid-001@example.com",
    "DTSTART": "20260101T100000Z",
    "DTEND": "20260101T110000Z",
    "SUMMARY": "Team Meeting",
    "DESCRIPTION": "Discuss Q1 goals",
    "LOCATION": "Conference Room A",
    "ORGANIZER": "mailto:boss@example.com",
}


# --- merge_calendars ---


def test_merge_single_source_returns_events():
    config = make_calendar_config()
    source = make_source("s1")
    raw = make_ics([SAMPLE_EVENT, {**SAMPLE_EVENT, "UID": "uid-002@example.com"}])
    result = merge_calendars(config, [(source, raw)])
    cal = Calendar.from_ical(result)
    events = list(cal.walk("VEVENT"))
    assert len(events) == 2


def test_merge_multiple_sources():
    config = make_calendar_config(sources=[make_source("s1"), make_source("s2")])
    raw1 = make_ics([SAMPLE_EVENT])
    raw2 = make_ics([{**SAMPLE_EVENT, "UID": "uid-002@example.com"}])
    result = merge_calendars(config, [(make_source("s1"), raw1), (make_source("s2"), raw2)])
    cal = Calendar.from_ical(result)
    events = list(cal.walk("VEVENT"))
    assert len(events) == 2


def test_uid_prefixed_with_source_id():
    config = make_calendar_config()
    source = make_source("work")
    raw = make_ics([SAMPLE_EVENT])
    result = merge_calendars(config, [(source, raw)])
    cal = Calendar.from_ical(result)
    event = list(cal.walk("VEVENT"))[0]
    assert str(event["UID"]) == "work:uid-001@example.com"


def test_uid_prefix_deduplication():
    config = make_calendar_config(sources=[make_source("s1"), make_source("s2")])
    same_uid_event = SAMPLE_EVENT.copy()
    raw1 = make_ics([same_uid_event])
    raw2 = make_ics([same_uid_event])
    result = merge_calendars(config, [(make_source("s1"), raw1), (make_source("s2"), raw2)])
    cal = Calendar.from_ical(result)
    uids = [str(e["UID"]) for e in cal.walk("VEVENT")]
    assert len(set(uids)) == 2
    assert "s1:uid-001@example.com" in uids
    assert "s2:uid-001@example.com" in uids


def test_freebusy_replaces_summary():
    config = make_calendar_config(freebusy=True)
    source = make_source("s1")
    raw = make_ics([SAMPLE_EVENT])
    result = merge_calendars(config, [(source, raw)])
    cal = Calendar.from_ical(result)
    event = list(cal.walk("VEVENT"))[0]
    assert str(event["SUMMARY"]) == "Busy"


def test_freebusy_strips_description():
    config = make_calendar_config(freebusy=True)
    source = make_source("s1")
    raw = make_ics([SAMPLE_EVENT])
    result = merge_calendars(config, [(source, raw)])
    cal = Calendar.from_ical(result)
    event = list(cal.walk("VEVENT"))[0]
    assert "DESCRIPTION" not in event


def test_freebusy_strips_location():
    config = make_calendar_config(freebusy=True)
    source = make_source("s1")
    raw = make_ics([SAMPLE_EVENT])
    result = merge_calendars(config, [(source, raw)])
    cal = Calendar.from_ical(result)
    event = list(cal.walk("VEVENT"))[0]
    assert "LOCATION" not in event


def test_freebusy_strips_organizer():
    config = make_calendar_config(freebusy=True)
    source = make_source("s1")
    raw = make_ics([SAMPLE_EVENT])
    result = merge_calendars(config, [(source, raw)])
    cal = Calendar.from_ical(result)
    event = list(cal.walk("VEVENT"))[0]
    assert "ORGANIZER" not in event


def test_freebusy_keeps_dtstart():
    config = make_calendar_config(freebusy=True)
    source = make_source("s1")
    raw = make_ics([SAMPLE_EVENT])
    result = merge_calendars(config, [(source, raw)])
    cal = Calendar.from_ical(result)
    event = list(cal.walk("VEVENT"))[0]
    assert "DTSTART" in event


def test_freebusy_keeps_dtend():
    config = make_calendar_config(freebusy=True)
    source = make_source("s1")
    raw = make_ics([SAMPLE_EVENT])
    result = merge_calendars(config, [(source, raw)])
    cal = Calendar.from_ical(result)
    event = list(cal.walk("VEVENT"))[0]
    assert "DTEND" in event


def test_full_details_keeps_summary():
    config = make_calendar_config(freebusy=False)
    source = make_source("s1")
    raw = make_ics([SAMPLE_EVENT])
    result = merge_calendars(config, [(source, raw)])
    cal = Calendar.from_ical(result)
    event = list(cal.walk("VEVENT"))[0]
    assert str(event["SUMMARY"]) == "Team Meeting"


def test_full_details_keeps_description():
    config = make_calendar_config(freebusy=False)
    source = make_source("s1")
    raw = make_ics([SAMPLE_EVENT])
    result = merge_calendars(config, [(source, raw)])
    cal = Calendar.from_ical(result)
    event = list(cal.walk("VEVENT"))[0]
    assert "DESCRIPTION" in event


def test_vtimezone_deduplication():
    config = make_calendar_config(sources=[make_source("s1"), make_source("s2")])
    raw1 = make_ics([SAMPLE_EVENT], tzid="America/New_York")
    raw2 = make_ics([{**SAMPLE_EVENT, "UID": "uid-002@example.com"}], tzid="America/New_York")
    result = merge_calendars(config, [(make_source("s1"), raw1), (make_source("s2"), raw2)])
    cal = Calendar.from_ical(result)
    tzones = [c for c in cal.subcomponents if c.name == "VTIMEZONE"]
    assert len(tzones) == 1


def test_vtimezone_different_tzids():
    config = make_calendar_config(sources=[make_source("s1"), make_source("s2")])
    raw1 = make_ics([SAMPLE_EVENT], tzid="America/New_York")
    raw2 = make_ics([{**SAMPLE_EVENT, "UID": "uid-002@example.com"}], tzid="Europe/Berlin")
    result = merge_calendars(config, [(make_source("s1"), raw1), (make_source("s2"), raw2)])
    cal = Calendar.from_ical(result)
    tzones = [c for c in cal.subcomponents if c.name == "VTIMEZONE"]
    tzids = {str(tz["TZID"]) for tz in tzones}
    assert tzids == {"America/New_York", "Europe/Berlin"}


def test_empty_sources_returns_valid_calendar():
    config = make_calendar_config()
    result = merge_calendars(config, [])
    cal = Calendar.from_ical(result)
    assert list(cal.walk("VEVENT")) == []


def test_output_is_valid_ics():
    config = make_calendar_config()
    source = make_source("s1")
    raw = make_ics([SAMPLE_EVENT])
    result = merge_calendars(config, [(source, raw)])
    assert isinstance(result, bytes)
    cal = Calendar.from_ical(result)
    assert cal["VERSION"] == "2.0"


def test_timezones_emitted_before_events():
    config = make_calendar_config()
    source = make_source("s1")
    raw = make_ics([SAMPLE_EVENT], tzid="America/New_York")
    result = merge_calendars(config, [(source, raw)])
    cal = Calendar.from_ical(result)
    names = [c.name for c in cal.subcomponents]
    tz_idx = names.index("VTIMEZONE")
    ev_idx = names.index("VEVENT")
    assert tz_idx < ev_idx


# --- compute_min_ttl ---


def test_compute_min_ttl_all_inf():
    assert compute_min_ttl([float("inf"), float("inf")]) == float("inf")


def test_compute_min_ttl_empty():
    assert compute_min_ttl([]) == float("inf")


def test_compute_min_ttl_with_zero():
    assert compute_min_ttl([300.0, 0.0, float("inf")]) == 0.0


def test_compute_min_ttl_mixed():
    assert compute_min_ttl([300.0, 60.0, float("inf")]) == 60.0


def test_compute_min_ttl_single_finite():
    assert compute_min_ttl([120.0]) == 120.0
