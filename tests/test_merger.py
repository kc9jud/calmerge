import math

from icalendar import Calendar

from calmerge.config import CalendarConfig, SourceConfig
from calmerge.merger import compute_min_ttl, merge_calendars


def make_source(id="src"):
    return SourceConfig(id=id, url=f"https://example.com/{id}.ics")


def make_calendar_config(freebusy=False, sources=None, participant=None):
    if sources is None:
        sources = [make_source()]
    return CalendarConfig(name="test", freebusy=freebusy, sources=sources, participant=participant)


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


def test_freebusy_keeps_rrule():
    config = make_calendar_config(freebusy=True)
    source = make_source("s1")
    raw = make_ics([{**SAMPLE_EVENT, "RRULE": "FREQ=WEEKLY;COUNT=4"}])
    result = merge_calendars(config, [(source, raw)])
    cal = Calendar.from_ical(result)
    event = list(cal.walk("VEVENT"))[0]
    assert "RRULE" in event


def test_freebusy_keeps_recurrence_id():
    config = make_calendar_config(freebusy=True)
    source = make_source("s1")
    master = {**SAMPLE_EVENT, "RRULE": "FREQ=WEEKLY;COUNT=4"}
    exception = {
        **SAMPLE_EVENT,
        "DTSTART": "20260108T120000Z",
        "DTEND": "20260108T130000Z",
        "RECURRENCE-ID": "20260108T100000Z",
    }
    raw = make_ics([master, exception])
    result = merge_calendars(config, [(source, raw)])
    cal = Calendar.from_ical(result)
    events = list(cal.walk("VEVENT"))
    recurrence_ids = [e.get("RECURRENCE-ID") for e in events]
    assert any(r is not None for r in recurrence_ids)


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


def test_merge_skips_invalid_ics_source():
    config = make_calendar_config(sources=[make_source("s1"), make_source("s2")])
    valid_raw = make_ics([SAMPLE_EVENT])
    invalid_raw = b"THIS IS NOT VALID ICS DATA"
    result = merge_calendars(
        config, [(make_source("s1"), valid_raw), (make_source("s2"), invalid_raw)]
    )
    cal = Calendar.from_ical(result)
    assert len(list(cal.walk("VEVENT"))) == 1


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


# --- participant status ---

ATTENDEE_EVENT = {
    **SAMPLE_EVENT,
    "ATTENDEE;PARTSTAT=ACCEPTED": "mailto:john@example.com",
    "ATTENDEE;PARTSTAT=TENTATIVE": "mailto:jane@example.com",
}


def make_ics_with_attendees(partstat: str, email: str = "john@example.com") -> bytes:
    event_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Test//Test//EN",
        "BEGIN:VEVENT",
        f"UID:{SAMPLE_EVENT['UID']}",
        f"DTSTART:{SAMPLE_EVENT['DTSTART']}",
        f"DTEND:{SAMPLE_EVENT['DTEND']}",
        f"SUMMARY:{SAMPLE_EVENT['SUMMARY']}",
        f"STATUS:CONFIRMED",
        f"ATTENDEE;PARTSTAT={partstat}:mailto:{email}",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(event_lines).encode()


def test_participant_accepted_sets_confirmed():
    config = make_calendar_config(participant="john@example.com")
    raw = make_ics_with_attendees("ACCEPTED")
    result = merge_calendars(config, [(make_source("s1"), raw)])
    event = list(Calendar.from_ical(result).walk("VEVENT"))[0]
    assert str(event["STATUS"]) == "CONFIRMED"


def test_participant_tentative_sets_tentative():
    config = make_calendar_config(participant="john@example.com")
    raw = make_ics_with_attendees("TENTATIVE")
    result = merge_calendars(config, [(make_source("s1"), raw)])
    event = list(Calendar.from_ical(result).walk("VEVENT"))[0]
    assert str(event["STATUS"]) == "TENTATIVE"


def test_participant_declined_sets_cancelled():
    config = make_calendar_config(participant="john@example.com")
    raw = make_ics_with_attendees("DECLINED")
    result = merge_calendars(config, [(make_source("s1"), raw)])
    event = list(Calendar.from_ical(result).walk("VEVENT"))[0]
    assert str(event["STATUS"]) == "CANCELLED"


def test_participant_needs_action_sets_tentative():
    config = make_calendar_config(participant="john@example.com")
    raw = make_ics_with_attendees("NEEDS-ACTION")
    result = merge_calendars(config, [(make_source("s1"), raw)])
    event = list(Calendar.from_ical(result).walk("VEVENT"))[0]
    assert str(event["STATUS"]) == "TENTATIVE"


def test_participant_not_found_keeps_original_status():
    config = make_calendar_config(participant="other@example.com")
    raw = make_ics_with_attendees("ACCEPTED", email="john@example.com")
    result = merge_calendars(config, [(make_source("s1"), raw)])
    event = list(Calendar.from_ical(result).walk("VEVENT"))[0]
    assert str(event["STATUS"]) == "CONFIRMED"


def test_participant_no_attendees_keeps_original_status():
    config = make_calendar_config(participant="john@example.com")
    raw = make_ics([{**SAMPLE_EVENT, "STATUS": "CONFIRMED"}])
    result = merge_calendars(config, [(make_source("s1"), raw)])
    event = list(Calendar.from_ical(result).walk("VEVENT"))[0]
    assert str(event["STATUS"]) == "CONFIRMED"


def test_participant_status_applied_in_freebusy_mode():
    config = make_calendar_config(freebusy=True, participant="john@example.com")
    raw = make_ics_with_attendees("TENTATIVE")
    result = merge_calendars(config, [(make_source("s1"), raw)])
    event = list(Calendar.from_ical(result).walk("VEVENT"))[0]
    assert str(event["STATUS"]) == "TENTATIVE"
    assert str(event["SUMMARY"]) == "Busy"


def test_participant_status_applied_in_passthrough_mode():
    config = make_calendar_config(freebusy=False, participant="john@example.com")
    raw = make_ics_with_attendees("DECLINED")
    result = merge_calendars(config, [(make_source("s1"), raw)])
    event = list(Calendar.from_ical(result).walk("VEVENT"))[0]
    assert str(event["STATUS"]) == "CANCELLED"


def test_no_participant_configured_leaves_status_unchanged():
    config = make_calendar_config(participant=None)
    raw = make_ics_with_attendees("TENTATIVE")
    result = merge_calendars(config, [(make_source("s1"), raw)])
    event = list(Calendar.from_ical(result).walk("VEVENT"))[0]
    assert str(event["STATUS"]) == "CONFIRMED"


# --- compute_min_ttl ---


def test_compute_min_ttl_all_inf():
    assert compute_min_ttl([math.inf, math.inf]) == math.inf


def test_compute_min_ttl_empty():
    assert compute_min_ttl([]) == math.inf


def test_compute_min_ttl_with_zero():
    assert compute_min_ttl([300.0, 0.0, math.inf]) == 300.0


def test_compute_min_ttl_mixed():
    assert compute_min_ttl([300.0, 60.0, math.inf]) == 300.0


def test_compute_min_ttl_single_finite():
    assert compute_min_ttl([120.0]) == 300.0
