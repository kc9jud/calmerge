import copy
import logging
import math

from icalendar import Calendar, Event

from .cache import MIN_TTL
from .config import CalendarConfig, SourceConfig

logger = logging.getLogger(__name__)

FREEBUSY_KEEP_PROPS = frozenset(
    {
        "DTSTART",
        "DTEND",
        "DURATION",
        "RRULE",
        "RDATE",
        "EXDATE",
        "STATUS",
        "TRANSP",
        "UID",
        "DTSTAMP",
        "LAST-MODIFIED",
        "SEQUENCE",
    }
)


def merge_calendars(
    calendar_config: CalendarConfig,
    source_bytes: list[tuple[SourceConfig, bytes]],
) -> bytes:
    output = Calendar()
    output.add("PRODID", "-//calmerge//calmerge//EN")
    output.add("VERSION", "2.0")
    output.add("CALSCALE", "GREGORIAN")

    tzones: dict[str, object] = {}
    events: list[Event] = []

    for source_config, raw in source_bytes:
        cal = _parse_calendar(raw)
        if cal is None:
            continue

        for component in cal.subcomponents:
            if component.name == "VTIMEZONE":
                tzid = str(component["TZID"])
                if tzid not in tzones:
                    tzones[tzid] = component

        for component in cal.walk("VEVENT"):
            original_uid = str(component.get("UID", f"no-uid-{id(component)}"))
            new_uid = f"{source_config.id}:{original_uid}"

            if calendar_config.freebusy:
                event = _anonymize_event(component, new_uid)
            else:
                event = _copy_event(component, new_uid)

            events.append(event)

    for tz in tzones.values():
        output.add_component(tz)

    for event in events:
        output.add_component(event)

    return output.to_ical()


def _anonymize_event(event: Event, new_uid: str) -> Event:
    new_event = Event()
    for key in list(event.keys()):
        key_upper = key.upper()
        if key_upper in FREEBUSY_KEEP_PROPS and key_upper != "UID":
            new_event[key] = event[key]
    new_event.add("UID", new_uid)
    new_event.add("SUMMARY", "Busy")
    return new_event


def _copy_event(event: Event, new_uid: str) -> Event:
    new_event = copy.deepcopy(event)
    if "UID" in new_event:
        del new_event["UID"]
    new_event.add("UID", new_uid)
    return new_event


def _parse_calendar(raw: bytes) -> Calendar | None:
    try:
        return Calendar.from_ical(raw)
    except Exception as exc:
        logger.warning("Failed to parse calendar: %s", exc)
        return None


def compute_min_ttl(ttls: list[float]) -> float:
    if not ttls:
        return math.inf
    if any(t == 0.0 for t in ttls):
        return MIN_TTL
    finite = [t for t in ttls if math.isfinite(t)]
    if not finite:
        return math.inf
    return max(min(finite), MIN_TTL)
