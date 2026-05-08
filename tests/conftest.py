import pytest

from calmerge.app import create_app

URL_WORK = "https://example.com/work.ics"
URL_HOME = "https://example.com/home.ics"

SAMPLE_ICS = (
    b"BEGIN:VCALENDAR\r\n"
    b"VERSION:2.0\r\n"
    b"PRODID:-//Test//Test//EN\r\n"
    b"BEGIN:VEVENT\r\n"
    b"UID:uid-001@example.com\r\n"
    b"DTSTART:20260101T100000Z\r\n"
    b"DTEND:20260101T110000Z\r\n"
    b"SUMMARY:Team Meeting\r\n"
    b"DESCRIPTION:Discuss Q1\r\n"
    b"END:VEVENT\r\n"
    b"END:VCALENDAR\r\n"
)


@pytest.fixture
def app_config(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f"""
[defaults]
freebusy = false

[[calendars]]
name = "work"
freebusy = false
sources = [
    {{ url = "{URL_WORK}", id = "work" }},
]

[[calendars]]
name = "combined"
freebusy = true
sources = [
    {{ url = "{URL_WORK}", id = "work" }},
    {{ url = "{URL_HOME}", id = "home" }},
]
"""
    )
    return config_path


@pytest.fixture
def flask_app(app_config):
    app = create_app(config_path=app_config)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(flask_app):
    return flask_app.test_client()
