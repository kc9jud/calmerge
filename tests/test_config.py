import pytest

from calmerge.config import AppConfig, load_config


def write_toml(tmp_path, content: str):
    p = tmp_path / "config.toml"
    p.write_text(content)
    return p


def test_load_minimal_config(tmp_path):
    p = write_toml(
        tmp_path,
        """
[[calendars]]
name = "work"
freebusy = false
sources = [
    { url = "https://example.com/work.ics", id = "work" },
]
""",
    )
    config = load_config(p)
    assert isinstance(config, AppConfig)
    assert len(config.calendars) == 1
    cal = config.calendars[0]
    assert cal.name == "work"
    assert cal.freebusy is False
    assert len(cal.sources) == 1
    assert cal.sources[0].url == "https://example.com/work.ics"
    assert cal.sources[0].id == "work"


def test_freebusy_default_false(tmp_path):
    p = write_toml(
        tmp_path,
        """
[[calendars]]
name = "cal"
sources = [{ url = "https://example.com/cal.ics", id = "cal" }]
""",
    )
    config = load_config(p)
    assert config.calendars[0].freebusy is False


def test_freebusy_default_from_defaults(tmp_path):
    p = write_toml(
        tmp_path,
        """
[defaults]
freebusy = true

[[calendars]]
name = "cal"
sources = [{ url = "https://example.com/cal.ics", id = "cal" }]
""",
    )
    config = load_config(p)
    assert config.calendars[0].freebusy is True


def test_freebusy_calendar_overrides_default(tmp_path):
    p = write_toml(
        tmp_path,
        """
[defaults]
freebusy = true

[[calendars]]
name = "cal"
freebusy = false
sources = [{ url = "https://example.com/cal.ics", id = "cal" }]
""",
    )
    config = load_config(p)
    assert config.calendars[0].freebusy is False


def test_file_source(tmp_path):
    p = write_toml(
        tmp_path,
        """
[[calendars]]
name = "home"
sources = [{ file = "/home/user/personal.ics", id = "personal" }]
""",
    )
    config = load_config(p)
    src = config.calendars[0].sources[0]
    assert src.file is not None
    assert src.file.name == "personal.ics"
    assert src.url is None


def test_calendars_by_name(tmp_path):
    p = write_toml(
        tmp_path,
        """
[[calendars]]
name = "work"
sources = [{ url = "https://example.com/work.ics", id = "work" }]

[[calendars]]
name = "home"
sources = [{ url = "https://example.com/home.ics", id = "home" }]
""",
    )
    config = load_config(p)
    assert "work" in config.calendars_by_name
    assert "home" in config.calendars_by_name
    assert config.calendars_by_name["work"].name == "work"


def test_unknown_calendar_not_in_lookup(tmp_path):
    p = write_toml(
        tmp_path,
        """
[[calendars]]
name = "work"
sources = [{ url = "https://example.com/work.ics", id = "work" }]
""",
    )
    config = load_config(p)
    assert "personal" not in config.calendars_by_name


def test_source_id_required_raises(tmp_path):
    p = write_toml(
        tmp_path,
        """
[[calendars]]
name = "work"
sources = [{ url = "https://example.com/work.ics" }]
""",
    )
    with pytest.raises(ValueError, match="id"):
        load_config(p)


def test_both_url_and_file_raises(tmp_path):
    p = write_toml(
        tmp_path,
        """
[[calendars]]
name = "work"
sources = [{ url = "https://example.com/work.ics", file = "/tmp/work.ics", id = "work" }]
""",
    )
    with pytest.raises(ValueError, match="not both"):
        load_config(p)


def test_neither_url_nor_file_raises(tmp_path):
    p = write_toml(
        tmp_path,
        """
[[calendars]]
name = "work"
sources = [{ id = "work" }]
""",
    )
    with pytest.raises(ValueError, match="url.*file|file.*url"):
        load_config(p)


def test_missing_calendar_name_raises(tmp_path):
    p = write_toml(
        tmp_path,
        """
[[calendars]]
sources = [{ url = "https://example.com/work.ics", id = "work" }]
""",
    )
    with pytest.raises(ValueError, match="name"):
        load_config(p)


def test_multiple_sources(tmp_path):
    p = write_toml(
        tmp_path,
        """
[[calendars]]
name = "combined"
freebusy = true
sources = [
    { url = "https://example.com/work.ics", id = "work" },
    { file = "/home/user/personal.ics", id = "personal" },
]
""",
    )
    config = load_config(p)
    cal = config.calendars[0]
    assert len(cal.sources) == 2
    assert cal.sources[0].id == "work"
    assert cal.sources[1].id == "personal"
