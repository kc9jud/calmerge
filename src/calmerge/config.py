import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SourceConfig:
    id: str
    url: str | None = None
    file: Path | None = None


@dataclass
class CalendarConfig:
    name: str
    freebusy: bool
    sources: list[SourceConfig]


@dataclass
class AppConfig:
    calendars: list[CalendarConfig]
    calendars_by_name: dict[str, CalendarConfig] = field(default_factory=dict)


def load_config(path: Path) -> AppConfig:
    with open(path, "rb") as f:
        raw = tomllib.load(f)

    default_freebusy = raw.get("defaults", {}).get("freebusy", False)

    calendars = []
    for cal_raw in raw.get("calendars", []):
        name = cal_raw.get("name")
        if not name:
            raise ValueError("Each [[calendars]] entry must have a 'name' field")

        freebusy = cal_raw.get("freebusy", default_freebusy)

        sources = []
        for src_raw in cal_raw.get("sources", []):
            source_id = src_raw.get("id")
            if not source_id:
                raise ValueError(f"Every source in calendar '{name}' must have an 'id' field")

            url = src_raw.get("url")
            file_path = src_raw.get("file")

            if url and file_path:
                raise ValueError(
                    f"Source '{source_id}' in calendar '{name}' must specify"
                    " 'url' or 'file', not both"
                )
            if not url and not file_path:
                raise ValueError(
                    f"Source '{source_id}' in calendar '{name}' must specify"
                    " either 'url' or 'file'"
                )

            sources.append(
                SourceConfig(
                    id=source_id,
                    url=url,
                    file=Path(file_path) if file_path else None,
                )
            )

        calendars.append(CalendarConfig(name=name, freebusy=freebusy, sources=sources))

    config = AppConfig(calendars=calendars)
    config.calendars_by_name = {cal.name: cal for cal in calendars}
    return config
