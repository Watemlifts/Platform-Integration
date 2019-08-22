"""The tests for the webdav calendar component."""
import datetime
from unittest.mock import MagicMock, Mock

from asynctest import patch
from caldav.objects import Event
import pytest

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.setup import async_setup_component
from homeassistant.util import dt

# pylint: disable=redefined-outer-name

DEVICE_DATA = {
    "name": "Private Calendar",
    "device_id": "Private Calendar",
}

EVENTS = [
    """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//E-Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:1
DTSTAMP:20171125T000000Z
DTSTART:20171127T170000Z
DTEND:20171127T180000Z
SUMMARY:This is a normal event
LOCATION:Hamburg
DESCRIPTION:Surprisingly rainy
END:VEVENT
END:VCALENDAR
""",
    """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Global Dynamics.//CalDAV Client//EN
BEGIN:VEVENT
UID:2
DTSTAMP:20171125T000000Z
DTSTART:20171127T100000Z
DTEND:20171127T110000Z
SUMMARY:This is an offset event !!-02:00
LOCATION:Hamburg
DESCRIPTION:Surprisingly shiny
END:VEVENT
END:VCALENDAR
""",
    """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Global Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:3
DTSTAMP:20171125T000000Z
DTSTART:20171127
DTEND:20171128
SUMMARY:This is an all day event
LOCATION:Hamburg
DESCRIPTION:What a beautiful day
END:VEVENT
END:VCALENDAR
""",
    """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Global Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:4
DTSTAMP:20171125T000000Z
DTSTART:20171127
SUMMARY:This is an event without dtend or duration
LOCATION:Hamburg
DESCRIPTION:What an endless day
END:VEVENT
END:VCALENDAR
""",
    """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Global Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:5
DTSTAMP:20171125T000000Z
DTSTART:20171127
DURATION:PT1H
SUMMARY:This is an event with duration
LOCATION:Hamburg
DESCRIPTION:What a day
END:VEVENT
END:VCALENDAR
""",
    """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Global Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:6
DTSTAMP:20171125T000000Z
DTSTART:20171127T100000Z
DURATION:PT1H
SUMMARY:This is an event with duration
LOCATION:Hamburg
DESCRIPTION:What a day
END:VEVENT
END:VCALENDAR
""",
    """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Global Corp.//CalDAV Client//EN
BEGIN:VEVENT
UID:7
DTSTART;TZID=America/Los_Angeles:20171127T083000
DTSTAMP:20180301T020053Z
DTEND;TZID=America/Los_Angeles:20171127T093000
SUMMARY:Enjoy the sun
LOCATION:San Francisco
DESCRIPTION:Sunny day
END:VEVENT
END:VCALENDAR
"""

]

CALDAV_CONFIG = {
    "platform": "caldav",
    "url": "http://test.local",
    "custom_calendars": [],
}


@pytest.fixture(autouse=True)
def mock_http(hass):
    """Mock the http component."""
    hass.http = Mock()


@pytest.fixture
def mock_dav_client():
    """Mock the dav client."""
    patch_dav_client = patch(
        'caldav.DAVClient', return_value=_mocked_dav_client('First', 'Second'))
    with patch_dav_client as dav_client:
        yield dav_client


@pytest.fixture(name='calendar')
def mock_private_cal():
    """Mock a private calendar."""
    _calendar = _mock_calendar("Private")
    calendars = [_calendar]
    client = _mocked_dav_client(calendars=calendars)
    patch_dav_client = patch('caldav.DAVClient', return_value=client)
    with patch_dav_client:
        yield _calendar


def _local_datetime(hours, minutes):
    """Build a datetime object for testing in the correct timezone."""
    return dt.as_local(datetime.datetime(2017, 11, 27, hours, minutes, 0))


def _mocked_dav_client(*names, calendars=None):
    """Mock requests.get invocations."""
    if calendars is None:
        calendars = [_mock_calendar(name) for name in names]
    principal = Mock()
    principal.calendars = MagicMock(return_value=calendars)

    client = Mock()
    client.principal = MagicMock(return_value=principal)
    return client


def _mock_calendar(name):
    events = []
    for idx, event in enumerate(EVENTS):
        events.append(Event(None, "%d.ics" % idx, event, None, str(idx)))

    calendar = Mock()
    calendar.date_search = MagicMock(return_value=events)
    calendar.name = name
    return calendar


async def test_setup_component(hass, mock_dav_client):
    """Test setup component with calendars."""
    assert await async_setup_component(
        hass, 'calendar', {'calendar': CALDAV_CONFIG})
    await hass.async_block_till_done()

    state = hass.states.get('calendar.first')
    assert state.name == "First"
    state = hass.states.get('calendar.second')
    assert state.name == "Second"


async def test_setup_component_with_no_calendar_matching(
        hass, mock_dav_client):
    """Test setup component with wrong calendar."""
    config = dict(CALDAV_CONFIG)
    config['calendars'] = ['none']

    assert await async_setup_component(hass, 'calendar', {'calendar': config})
    await hass.async_block_till_done()

    all_calendar_states = hass.states.async_entity_ids('calendar')
    assert not all_calendar_states


async def test_setup_component_with_a_calendar_match(hass, mock_dav_client):
    """Test setup component with right calendar."""
    config = dict(CALDAV_CONFIG)
    config['calendars'] = ['Second']

    assert await async_setup_component(hass, 'calendar', {'calendar': config})
    await hass.async_block_till_done()

    all_calendar_states = hass.states.async_entity_ids('calendar')
    assert len(all_calendar_states) == 1
    state = hass.states.get('calendar.second')
    assert state.name == 'Second'


async def test_setup_component_with_one_custom_calendar(hass, mock_dav_client):
    """Test setup component with custom calendars."""
    config = dict(CALDAV_CONFIG)
    config['custom_calendars'] = [{
        'name': 'HomeOffice',
        'calendar': 'Second',
        'search': 'HomeOffice',
    }]

    assert await async_setup_component(hass, 'calendar', {'calendar': config})
    await hass.async_block_till_done()

    all_calendar_states = hass.states.async_entity_ids('calendar')
    assert len(all_calendar_states) == 1
    state = hass.states.get('calendar.second_homeoffice')
    assert state.name == 'HomeOffice'


@patch('homeassistant.util.dt.now', return_value=_local_datetime(17, 45))
async def test_ongoing_event(mock_now, hass, calendar):
    """Test that the ongoing event is returned."""
    assert await async_setup_component(
        hass, 'calendar', {'calendar': CALDAV_CONFIG})
    await hass.async_block_till_done()

    state = hass.states.get('calendar.private')
    assert state.name == calendar.name
    assert state.state == STATE_ON
    assert dict(state.attributes) == {
        "friendly_name": "Private",
        "message": "This is a normal event",
        "all_day": False,
        'offset_reached': False,
        "start_time": "2017-11-27 17:00:00",
        "end_time": "2017-11-27 18:00:00",
        "location": "Hamburg",
        "description": "Surprisingly rainy",
    }


@patch('homeassistant.util.dt.now', return_value=_local_datetime(17, 30))
async def test_just_ended_event(mock_now, hass, calendar):
    """Test that the next ongoing event is returned."""
    assert await async_setup_component(
        hass, 'calendar', {'calendar': CALDAV_CONFIG})
    await hass.async_block_till_done()

    state = hass.states.get('calendar.private')
    assert state.name == calendar.name
    assert state.state == STATE_ON
    assert dict(state.attributes) == {
        "friendly_name": "Private",
        "message": "This is a normal event",
        "all_day": False,
        "offset_reached": False,
        "start_time": "2017-11-27 17:00:00",
        "end_time": "2017-11-27 18:00:00",
        "location": "Hamburg",
        "description": "Surprisingly rainy",
    }


@patch('homeassistant.util.dt.now', return_value=_local_datetime(17, 00))
async def test_ongoing_event_different_tz(mock_now, hass, calendar):
    """Test that the ongoing event with another timezone is returned."""
    assert await async_setup_component(
        hass, 'calendar', {'calendar': CALDAV_CONFIG})
    await hass.async_block_till_done()

    state = hass.states.get('calendar.private')
    assert state.name == calendar.name
    assert state.state == STATE_ON
    assert dict(state.attributes) == {
        "friendly_name": "Private",
        "message": "Enjoy the sun",
        "all_day": False,
        "offset_reached": False,
        "start_time": "2017-11-27 16:30:00",
        "description": "Sunny day",
        "end_time": "2017-11-27 17:30:00",
        "location": "San Francisco",
    }


@patch('homeassistant.util.dt.now', return_value=_local_datetime(8, 30))
async def test_ongoing_event_with_offset(mock_now, hass, calendar):
    """Test that the offset is taken into account."""
    assert await async_setup_component(
        hass, 'calendar', {'calendar': CALDAV_CONFIG})
    await hass.async_block_till_done()

    state = hass.states.get('calendar.private')
    assert state.name == calendar.name
    assert state.state == STATE_OFF
    assert dict(state.attributes) == {
        "friendly_name": "Private",
        "message": "This is an offset event",
        "all_day": False,
        "offset_reached": True,
        "start_time": "2017-11-27 10:00:00",
        "end_time": "2017-11-27 11:00:00",
        "location": "Hamburg",
        "description": "Surprisingly shiny",
    }


@patch('homeassistant.util.dt.now', return_value=_local_datetime(12, 00))
async def test_matching_filter(mock_now, hass, calendar):
    """Test that the matching event is returned."""
    config = dict(CALDAV_CONFIG)
    config['custom_calendars'] = [{
        'name': 'Private',
        'calendar': 'Private',
        'search': 'This is a normal event',
    }]

    assert await async_setup_component(
        hass, 'calendar', {'calendar': config})
    await hass.async_block_till_done()

    state = hass.states.get('calendar.private_private')
    assert state.name == calendar.name
    assert state.state == STATE_OFF
    assert dict(state.attributes) == {
        "friendly_name": "Private",
        "message": "This is a normal event",
        "all_day": False,
        "offset_reached": False,
        "start_time": "2017-11-27 17:00:00",
        "end_time": "2017-11-27 18:00:00",
        "location": "Hamburg",
        "description": "Surprisingly rainy",
    }


@patch('homeassistant.util.dt.now', return_value=_local_datetime(12, 00))
async def test_matching_filter_real_regexp(mock_now, hass, calendar):
    """Test that the event matching the regexp is returned."""
    config = dict(CALDAV_CONFIG)
    config['custom_calendars'] = [{
        'name': 'Private',
        'calendar': 'Private',
        'search': r'.*rainy',
    }]

    assert await async_setup_component(
        hass, 'calendar', {'calendar': config})
    await hass.async_block_till_done()

    state = hass.states.get('calendar.private_private')
    assert state.name == calendar.name
    assert state.state == STATE_OFF
    assert dict(state.attributes) == {
        "friendly_name": "Private",
        "message": "This is a normal event",
        "all_day": False,
        "offset_reached": False,
        "start_time": "2017-11-27 17:00:00",
        "end_time": "2017-11-27 18:00:00",
        "location": "Hamburg",
        "description": "Surprisingly rainy",
    }


@patch('homeassistant.util.dt.now', return_value=_local_datetime(20, 00))
async def test_filter_matching_past_event(mock_now, hass, calendar):
    """Test that the matching past event is not returned."""
    config = dict(CALDAV_CONFIG)
    config['custom_calendars'] = [{
        'name': 'Private',
        'calendar': 'Private',
        'search': 'This is a normal event',
    }]

    assert await async_setup_component(
        hass, 'calendar', {'calendar': config})
    await hass.async_block_till_done()

    state = hass.states.get('calendar.private_private')
    assert state.name == calendar.name
    assert state.state == 'off'


@patch('homeassistant.util.dt.now', return_value=_local_datetime(12, 00))
async def test_no_result_with_filtering(mock_now, hass, calendar):
    """Test that nothing is returned since nothing matches."""
    config = dict(CALDAV_CONFIG)
    config['custom_calendars'] = [{
        'name': 'Private',
        'calendar': 'Private',
        'search': 'This is a non-existing event',
    }]

    assert await async_setup_component(
        hass, 'calendar', {'calendar': config})
    await hass.async_block_till_done()

    state = hass.states.get('calendar.private_private')
    assert state.name == calendar.name
    assert state.state == 'off'


@patch('homeassistant.util.dt.now', return_value=_local_datetime(17, 30))
async def test_all_day_event_returned(mock_now, hass, calendar):
    """Test that the event lasting the whole day is returned."""
    config = dict(CALDAV_CONFIG)
    config['custom_calendars'] = [{
        'name': 'Private',
        'calendar': 'Private',
        'search': '.*',
    }]

    assert await async_setup_component(
        hass, 'calendar', {'calendar': config})
    await hass.async_block_till_done()

    state = hass.states.get('calendar.private_private')
    assert state.name == calendar.name
    assert state.state == STATE_ON
    assert dict(state.attributes) == {
        "friendly_name": "Private",
        "message": "This is an all day event",
        "all_day": True,
        "offset_reached": False,
        "start_time": "2017-11-27 00:00:00",
        "end_time": "2017-11-28 00:00:00",
        "location": "Hamburg",
        "description": "What a beautiful day",
    }
