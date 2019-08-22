"""Test event helpers."""
# pylint: disable=protected-access
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch

from astral import Astral
import pytest

from homeassistant.core import callback
from homeassistant.setup import async_setup_component
import homeassistant.core as ha
from homeassistant.const import MATCH_ALL
from homeassistant.helpers.event import (
    async_call_later,
    async_track_point_in_time,
    async_track_point_in_utc_time,
    async_track_same_state,
    async_track_state_change,
    async_track_sunrise,
    async_track_sunset,
    async_track_template,
    async_track_time_change,
    async_track_time_interval,
    async_track_utc_time_change,
)
from homeassistant.helpers.template import Template
from homeassistant.components import sun
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed

DEFAULT_TIME_ZONE = dt_util.DEFAULT_TIME_ZONE


def teardown():
    """Stop everything that was started."""
    dt_util.set_default_time_zone(DEFAULT_TIME_ZONE)


def _send_time_changed(hass, now):
    """Send a time changed event."""
    hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: now})


async def test_track_point_in_time(hass):
    """Test track point in time."""
    before_birthday = datetime(1985, 7, 9, 12, 0, 0, tzinfo=dt_util.UTC)
    birthday_paulus = datetime(1986, 7, 9, 12, 0, 0, tzinfo=dt_util.UTC)
    after_birthday = datetime(1987, 7, 9, 12, 0, 0, tzinfo=dt_util.UTC)

    runs = []

    async_track_point_in_utc_time(
        hass, callback(lambda x: runs.append(1)), birthday_paulus)

    _send_time_changed(hass, before_birthday)
    await hass.async_block_till_done()
    assert len(runs) == 0

    _send_time_changed(hass, birthday_paulus)
    await hass.async_block_till_done()
    assert len(runs) == 1

    # A point in time tracker will only fire once, this should do nothing
    _send_time_changed(hass, birthday_paulus)
    await hass.async_block_till_done()
    assert len(runs) == 1

    async_track_point_in_utc_time(
        hass, callback(lambda x: runs.append(1)), birthday_paulus)

    _send_time_changed(hass, after_birthday)
    await hass.async_block_till_done()
    assert len(runs) == 2

    unsub = async_track_point_in_time(
        hass, callback(lambda x: runs.append(1)), birthday_paulus)
    unsub()

    _send_time_changed(hass, after_birthday)
    await hass.async_block_till_done()
    assert len(runs) == 2


async def test_track_state_change(hass):
    """Test track_state_change."""
    # 2 lists to track how often our callbacks get called
    specific_runs = []
    wildcard_runs = []
    wildercard_runs = []

    def specific_run_callback(entity_id, old_state, new_state):
        specific_runs.append(1)

    async_track_state_change(
        hass, 'light.Bowl', specific_run_callback, 'on', 'off')

    @ha.callback
    def wildcard_run_callback(entity_id, old_state, new_state):
        wildcard_runs.append((old_state, new_state))

    async_track_state_change(hass, 'light.Bowl', wildcard_run_callback)

    @asyncio.coroutine
    def wildercard_run_callback(entity_id, old_state, new_state):
        wildercard_runs.append((old_state, new_state))

    async_track_state_change(hass, MATCH_ALL, wildercard_run_callback)

    # Adding state to state machine
    hass.states.async_set("light.Bowl", "on")
    await hass.async_block_till_done()
    assert len(specific_runs) == 0
    assert len(wildcard_runs) == 1
    assert len(wildercard_runs) == 1
    assert wildcard_runs[-1][0] is None
    assert wildcard_runs[-1][1] is not None

    # Set same state should not trigger a state change/listener
    hass.states.async_set('light.Bowl', 'on')
    await hass.async_block_till_done()
    assert len(specific_runs) == 0
    assert len(wildcard_runs) == 1
    assert len(wildercard_runs) == 1

    # State change off -> on
    hass.states.async_set('light.Bowl', 'off')
    await hass.async_block_till_done()
    assert len(specific_runs) == 1
    assert len(wildcard_runs) == 2
    assert len(wildercard_runs) == 2

    # State change off -> off
    hass.states.async_set('light.Bowl', 'off', {"some_attr": 1})
    await hass.async_block_till_done()
    assert len(specific_runs) == 1
    assert len(wildcard_runs) == 3
    assert len(wildercard_runs) == 3

    # State change off -> on
    hass.states.async_set('light.Bowl', 'on')
    await hass.async_block_till_done()
    assert len(specific_runs) == 1
    assert len(wildcard_runs) == 4
    assert len(wildercard_runs) == 4

    hass.states.async_remove('light.bowl')
    await hass.async_block_till_done()
    assert len(specific_runs) == 1
    assert len(wildcard_runs) == 5
    assert len(wildercard_runs) == 5
    assert wildcard_runs[-1][0] is not None
    assert wildcard_runs[-1][1] is None
    assert wildercard_runs[-1][0] is not None
    assert wildercard_runs[-1][1] is None

    # Set state for different entity id
    hass.states.async_set('switch.kitchen', 'on')
    await hass.async_block_till_done()
    assert len(specific_runs) == 1
    assert len(wildcard_runs) == 5
    assert len(wildercard_runs) == 6


async def test_track_template(hass):
    """Test tracking template."""
    specific_runs = []
    wildcard_runs = []
    wildercard_runs = []

    template_condition = Template(
        "{{states.switch.test.state == 'on'}}",
        hass
    )
    template_condition_var = Template(
        "{{states.switch.test.state == 'on' and test == 5}}",
        hass
    )

    hass.states.async_set('switch.test', 'off')

    def specific_run_callback(entity_id, old_state, new_state):
        specific_runs.append(1)

    async_track_template(hass, template_condition, specific_run_callback)

    @ha.callback
    def wildcard_run_callback(entity_id, old_state, new_state):
        wildcard_runs.append((old_state, new_state))

    async_track_template(hass, template_condition, wildcard_run_callback)

    @asyncio.coroutine
    def wildercard_run_callback(entity_id, old_state, new_state):
        wildercard_runs.append((old_state, new_state))

    async_track_template(
        hass, template_condition_var, wildercard_run_callback,
        {'test': 5})

    hass.states.async_set('switch.test', 'on')
    await hass.async_block_till_done()

    assert len(specific_runs) == 1
    assert len(wildcard_runs) == 1
    assert len(wildercard_runs) == 1

    hass.states.async_set('switch.test', 'on')
    await hass.async_block_till_done()

    assert len(specific_runs) == 1
    assert len(wildcard_runs) == 1
    assert len(wildercard_runs) == 1

    hass.states.async_set('switch.test', 'off')
    await hass.async_block_till_done()

    assert len(specific_runs) == 1
    assert len(wildcard_runs) == 1
    assert len(wildercard_runs) == 1

    hass.states.async_set('switch.test', 'off')
    await hass.async_block_till_done()

    assert len(specific_runs) == 1
    assert len(wildcard_runs) == 1
    assert len(wildercard_runs) == 1

    hass.states.async_set('switch.test', 'on')
    await hass.async_block_till_done()

    assert len(specific_runs) == 2
    assert len(wildcard_runs) == 2
    assert len(wildercard_runs) == 2


async def test_track_same_state_simple_trigger(hass):
    """Test track_same_change with trigger simple."""
    thread_runs = []
    callback_runs = []
    coroutine_runs = []
    period = timedelta(minutes=1)

    def thread_run_callback():
        thread_runs.append(1)

    async_track_same_state(
        hass, period, thread_run_callback,
        lambda _, _2, to_s: to_s.state == 'on',
        entity_ids='light.Bowl')

    @ha.callback
    def callback_run_callback():
        callback_runs.append(1)

    async_track_same_state(
        hass, period, callback_run_callback,
        lambda _, _2, to_s: to_s.state == 'on',
        entity_ids='light.Bowl')

    @asyncio.coroutine
    def coroutine_run_callback():
        coroutine_runs.append(1)

    async_track_same_state(
        hass, period, coroutine_run_callback,
        lambda _, _2, to_s: to_s.state == 'on')

    # Adding state to state machine
    hass.states.async_set("light.Bowl", "on")
    await hass.async_block_till_done()
    assert len(thread_runs) == 0
    assert len(callback_runs) == 0
    assert len(coroutine_runs) == 0

    # change time to track and see if they trigger
    future = dt_util.utcnow() + period
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()
    assert len(thread_runs) == 1
    assert len(callback_runs) == 1
    assert len(coroutine_runs) == 1


async def test_track_same_state_simple_no_trigger(hass):
    """Test track_same_change with no trigger."""
    callback_runs = []
    period = timedelta(minutes=1)

    @ha.callback
    def callback_run_callback():
        callback_runs.append(1)

    async_track_same_state(
        hass, period, callback_run_callback,
        lambda _, _2, to_s: to_s.state == 'on',
        entity_ids='light.Bowl')

    # Adding state to state machine
    hass.states.async_set("light.Bowl", "on")
    await hass.async_block_till_done()
    assert len(callback_runs) == 0

    # Change state on state machine
    hass.states.async_set("light.Bowl", "off")
    await hass.async_block_till_done()
    assert len(callback_runs) == 0

    # change time to track and see if they trigger
    future = dt_util.utcnow() + period
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()
    assert len(callback_runs) == 0


async def test_track_same_state_simple_trigger_check_funct(hass):
    """Test track_same_change with trigger and check funct."""
    callback_runs = []
    check_func = []
    period = timedelta(minutes=1)

    @ha.callback
    def callback_run_callback():
        callback_runs.append(1)

    @ha.callback
    def async_check_func(entity, from_s, to_s):
        check_func.append((entity, from_s, to_s))
        return True

    async_track_same_state(
        hass, period, callback_run_callback,
        entity_ids='light.Bowl', async_check_same_func=async_check_func)

    # Adding state to state machine
    hass.states.async_set("light.Bowl", "on")
    await hass.async_block_till_done()
    assert len(callback_runs) == 0
    assert check_func[-1][2].state == 'on'
    assert check_func[-1][0] == 'light.bowl'

    # change time to track and see if they trigger
    future = dt_util.utcnow() + period
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()
    assert len(callback_runs) == 1


async def test_track_time_interval(hass):
    """Test tracking time interval."""
    specific_runs = []

    utc_now = dt_util.utcnow()
    unsub = async_track_time_interval(
        hass, lambda x: specific_runs.append(1),
        timedelta(seconds=10)
    )

    _send_time_changed(hass, utc_now + timedelta(seconds=5))
    await hass.async_block_till_done()
    assert len(specific_runs) == 0

    _send_time_changed(hass, utc_now + timedelta(seconds=13))
    await hass.async_block_till_done()
    assert len(specific_runs) == 1

    _send_time_changed(hass, utc_now + timedelta(minutes=20))
    await hass.async_block_till_done()
    assert len(specific_runs) == 2

    unsub()

    _send_time_changed(hass, utc_now + timedelta(seconds=30))
    await hass.async_block_till_done()
    assert len(specific_runs) == 2


async def test_track_sunrise(hass):
    """Test track the sunrise."""
    latitude = 32.87336
    longitude = 117.22743

    # Setup sun component
    hass.config.latitude = latitude
    hass.config.longitude = longitude
    assert await async_setup_component(hass, sun.DOMAIN, {
        sun.DOMAIN: {sun.CONF_ELEVATION: 0}})

    # Get next sunrise/sunset
    astral = Astral()
    utc_now = datetime(2014, 5, 24, 12, 0, 0, tzinfo=dt_util.UTC)
    utc_today = utc_now.date()

    mod = -1
    while True:
        next_rising = (astral.sunrise_utc(
            utc_today + timedelta(days=mod), latitude, longitude))
        if next_rising > utc_now:
            break
        mod += 1

    # Track sunrise
    runs = []
    with patch('homeassistant.util.dt.utcnow', return_value=utc_now):
        unsub = async_track_sunrise(hass, lambda: runs.append(1))

    offset_runs = []
    offset = timedelta(minutes=30)
    with patch('homeassistant.util.dt.utcnow', return_value=utc_now):
        unsub2 = async_track_sunrise(hass, lambda: offset_runs.append(1),
                                     offset)

    # run tests
    _send_time_changed(hass, next_rising - offset)
    await hass.async_block_till_done()
    assert len(runs) == 0
    assert len(offset_runs) == 0

    _send_time_changed(hass, next_rising)
    await hass.async_block_till_done()
    assert len(runs) == 1
    assert len(offset_runs) == 0

    _send_time_changed(hass, next_rising + offset)
    await hass.async_block_till_done()
    assert len(runs) == 1
    assert len(offset_runs) == 1

    unsub()
    unsub2()

    _send_time_changed(hass, next_rising + offset)
    await hass.async_block_till_done()
    assert len(runs) == 1
    assert len(offset_runs) == 1


async def test_track_sunrise_update_location(hass):
    """Test track the sunrise."""
    # Setup sun component
    hass.config.latitude = 32.87336
    hass.config.longitude = 117.22743
    assert await async_setup_component(hass, sun.DOMAIN, {
        sun.DOMAIN: {sun.CONF_ELEVATION: 0}})

    # Get next sunrise
    astral = Astral()
    utc_now = datetime(2014, 5, 24, 12, 0, 0, tzinfo=dt_util.UTC)
    utc_today = utc_now.date()

    mod = -1
    while True:
        next_rising = (astral.sunrise_utc(
            utc_today + timedelta(days=mod),
            hass.config.latitude, hass.config.longitude))
        if next_rising > utc_now:
            break
        mod += 1

    # Track sunrise
    runs = []
    with patch('homeassistant.util.dt.utcnow', return_value=utc_now):
        async_track_sunrise(hass, lambda: runs.append(1))

    # Mimick sunrise
    _send_time_changed(hass, next_rising)
    await hass.async_block_till_done()
    assert len(runs) == 1

    # Move!
    with patch('homeassistant.util.dt.utcnow', return_value=utc_now):
        await hass.config.async_update(
            latitude=40.755931,
            longitude=-73.984606,
        )
        await hass.async_block_till_done()

    # Mimick sunrise
    _send_time_changed(hass, next_rising)
    await hass.async_block_till_done()
    # Did not increase
    assert len(runs) == 1

    # Get next sunrise
    mod = -1
    while True:
        next_rising = (astral.sunrise_utc(
            utc_today + timedelta(days=mod),
            hass.config.latitude, hass.config.longitude))
        if next_rising > utc_now:
            break
        mod += 1

    # Mimick sunrise at new location
    _send_time_changed(hass, next_rising)
    await hass.async_block_till_done()
    assert len(runs) == 2


async def test_track_sunset(hass):
    """Test track the sunset."""
    latitude = 32.87336
    longitude = 117.22743

    # Setup sun component
    hass.config.latitude = latitude
    hass.config.longitude = longitude
    assert await async_setup_component(hass, sun.DOMAIN, {
        sun.DOMAIN: {sun.CONF_ELEVATION: 0}})

    # Get next sunrise/sunset
    astral = Astral()
    utc_now = datetime(2014, 5, 24, 12, 0, 0, tzinfo=dt_util.UTC)
    utc_today = utc_now.date()

    mod = -1
    while True:
        next_setting = (astral.sunset_utc(
            utc_today + timedelta(days=mod), latitude, longitude))
        if next_setting > utc_now:
            break
        mod += 1

    # Track sunset
    runs = []
    with patch('homeassistant.util.dt.utcnow', return_value=utc_now):
        unsub = async_track_sunset(hass, lambda: runs.append(1))

    offset_runs = []
    offset = timedelta(minutes=30)
    with patch('homeassistant.util.dt.utcnow', return_value=utc_now):
        unsub2 = async_track_sunset(
            hass, lambda: offset_runs.append(1), offset)

    # Run tests
    _send_time_changed(hass, next_setting - offset)
    await hass.async_block_till_done()
    assert len(runs) == 0
    assert len(offset_runs) == 0

    _send_time_changed(hass, next_setting)
    await hass.async_block_till_done()
    assert len(runs) == 1
    assert len(offset_runs) == 0

    _send_time_changed(hass, next_setting + offset)
    await hass.async_block_till_done()
    assert len(runs) == 1
    assert len(offset_runs) == 1

    unsub()
    unsub2()

    _send_time_changed(hass, next_setting + offset)
    await hass.async_block_till_done()
    assert len(runs) == 1
    assert len(offset_runs) == 1


async def test_async_track_time_change(hass):
    """Test tracking time change."""
    wildcard_runs = []
    specific_runs = []

    unsub = async_track_time_change(hass,
                                    lambda x: wildcard_runs.append(1))
    unsub_utc = async_track_utc_time_change(
        hass, lambda x: specific_runs.append(1), second=[0, 30])

    _send_time_changed(hass, datetime(2014, 5, 24, 12, 0, 0))
    await hass.async_block_till_done()
    assert len(specific_runs) == 1
    assert len(wildcard_runs) == 1

    _send_time_changed(hass, datetime(2014, 5, 24, 12, 0, 15))
    await hass.async_block_till_done()
    assert len(specific_runs) == 1
    assert len(wildcard_runs) == 2

    _send_time_changed(hass, datetime(2014, 5, 24, 12, 0, 30))
    await hass.async_block_till_done()
    assert len(specific_runs) == 2
    assert len(wildcard_runs) == 3

    unsub()
    unsub_utc()

    _send_time_changed(hass, datetime(2014, 5, 24, 12, 0, 30))
    await hass.async_block_till_done()
    assert len(specific_runs) == 2
    assert len(wildcard_runs) == 3


async def test_periodic_task_minute(hass):
    """Test periodic tasks per minute."""
    specific_runs = []

    unsub = async_track_utc_time_change(
        hass, lambda x: specific_runs.append(1), minute='/5',
        second=0)

    _send_time_changed(hass, datetime(2014, 5, 24, 12, 0, 0))
    await hass.async_block_till_done()
    assert len(specific_runs) == 1

    _send_time_changed(hass, datetime(2014, 5, 24, 12, 3, 0))
    await hass.async_block_till_done()
    assert len(specific_runs) == 1

    _send_time_changed(hass, datetime(2014, 5, 24, 12, 5, 0))
    await hass.async_block_till_done()
    assert len(specific_runs) == 2

    unsub()

    _send_time_changed(hass, datetime(2014, 5, 24, 12, 5, 0))
    await hass.async_block_till_done()
    assert len(specific_runs) == 2


async def test_periodic_task_hour(hass):
    """Test periodic tasks per hour."""
    specific_runs = []

    unsub = async_track_utc_time_change(
        hass, lambda x: specific_runs.append(1), hour='/2',
        minute=0, second=0)

    _send_time_changed(hass, datetime(2014, 5, 24, 22, 0, 0))
    await hass.async_block_till_done()
    assert len(specific_runs) == 1

    _send_time_changed(hass, datetime(2014, 5, 24, 23, 0, 0))
    await hass.async_block_till_done()
    assert len(specific_runs) == 1

    _send_time_changed(hass, datetime(2014, 5, 25, 0, 0, 0))
    await hass.async_block_till_done()
    assert len(specific_runs) == 2

    _send_time_changed(hass, datetime(2014, 5, 25, 1, 0, 0))
    await hass.async_block_till_done()
    assert len(specific_runs) == 2

    _send_time_changed(hass, datetime(2014, 5, 25, 2, 0, 0))
    await hass.async_block_till_done()
    assert len(specific_runs) == 3

    unsub()

    _send_time_changed(hass, datetime(2014, 5, 25, 2, 0, 0))
    await hass.async_block_till_done()
    assert len(specific_runs) == 3


async def test_periodic_task_wrong_input(hass):
    """Test periodic tasks with wrong input."""
    specific_runs = []

    with pytest.raises(ValueError):
        async_track_utc_time_change(
            hass, lambda x: specific_runs.append(1), hour='/two')

    _send_time_changed(hass, datetime(2014, 5, 2, 0, 0, 0))
    await hass.async_block_till_done()
    assert len(specific_runs) == 0


async def test_periodic_task_clock_rollback(hass):
    """Test periodic tasks with the time rolling backwards."""
    specific_runs = []

    unsub = async_track_utc_time_change(
        hass, lambda x: specific_runs.append(1), hour='/2', minute=0,
        second=0)

    _send_time_changed(hass, datetime(2014, 5, 24, 22, 0, 0))
    await hass.async_block_till_done()
    assert len(specific_runs) == 1

    _send_time_changed(hass, datetime(2014, 5, 24, 23, 0, 0))
    await hass.async_block_till_done()
    assert len(specific_runs) == 1

    _send_time_changed(hass, datetime(2014, 5, 24, 22, 0, 0))
    await hass.async_block_till_done()
    assert len(specific_runs) == 2

    _send_time_changed(hass, datetime(2014, 5, 24, 0, 0, 0))
    await hass.async_block_till_done()
    assert len(specific_runs) == 3

    _send_time_changed(hass, datetime(2014, 5, 25, 2, 0, 0))
    await hass.async_block_till_done()
    assert len(specific_runs) == 4

    unsub()

    _send_time_changed(hass, datetime(2014, 5, 25, 2, 0, 0))
    await hass.async_block_till_done()
    assert len(specific_runs) == 4


async def test_periodic_task_duplicate_time(hass):
    """Test periodic tasks not triggering on duplicate time."""
    specific_runs = []

    unsub = async_track_utc_time_change(
        hass, lambda x: specific_runs.append(1), hour='/2', minute=0,
        second=0)

    _send_time_changed(hass, datetime(2014, 5, 24, 22, 0, 0))
    await hass.async_block_till_done()
    assert len(specific_runs) == 1

    _send_time_changed(hass, datetime(2014, 5, 24, 22, 0, 0))
    await hass.async_block_till_done()
    assert len(specific_runs) == 1

    _send_time_changed(hass, datetime(2014, 5, 25, 0, 0, 0))
    await hass.async_block_till_done()
    assert len(specific_runs) == 2

    unsub()


async def test_periodic_task_entering_dst(hass):
    """Test periodic task behavior when entering dst."""
    tz = dt_util.get_time_zone('Europe/Vienna')
    dt_util.set_default_time_zone(tz)
    specific_runs = []

    unsub = async_track_time_change(
        hass, lambda x: specific_runs.append(1), hour=2, minute=30,
        second=0)

    _send_time_changed(hass, tz.localize(datetime(2018, 3, 25, 1, 50, 0)))
    await hass.async_block_till_done()
    assert len(specific_runs) == 0

    _send_time_changed(hass, tz.localize(datetime(2018, 3, 25, 3, 50, 0)))
    await hass.async_block_till_done()
    assert len(specific_runs) == 0

    _send_time_changed(hass, tz.localize(datetime(2018, 3, 26, 1, 50, 0)))
    await hass.async_block_till_done()
    assert len(specific_runs) == 0

    _send_time_changed(hass, tz.localize(datetime(2018, 3, 26, 2, 50, 0)))
    await hass.async_block_till_done()
    assert len(specific_runs) == 1

    unsub()


async def test_periodic_task_leaving_dst(hass):
    """Test periodic task behavior when leaving dst."""
    tz = dt_util.get_time_zone('Europe/Vienna')
    dt_util.set_default_time_zone(tz)
    specific_runs = []

    unsub = async_track_time_change(
        hass, lambda x: specific_runs.append(1), hour=2, minute=30,
        second=0)

    _send_time_changed(hass, tz.localize(datetime(2018, 10, 28, 2, 5, 0),
                                         is_dst=False))
    await hass.async_block_till_done()
    assert len(specific_runs) == 0

    _send_time_changed(hass, tz.localize(datetime(2018, 10, 28, 2, 55, 0),
                                         is_dst=False))
    await hass.async_block_till_done()
    assert len(specific_runs) == 1

    _send_time_changed(hass, tz.localize(datetime(2018, 10, 28, 2, 5, 0),
                                         is_dst=True))
    await hass.async_block_till_done()
    assert len(specific_runs) == 1

    _send_time_changed(hass, tz.localize(datetime(2018, 10, 28, 2, 55, 0),
                                         is_dst=True))
    await hass.async_block_till_done()
    assert len(specific_runs) == 2

    unsub()


async def test_call_later(hass):
    """Test calling an action later."""
    def action():
        pass
    now = datetime(2017, 12, 19, 15, 40, 0, tzinfo=dt_util.UTC)

    with patch('homeassistant.helpers.event'
               '.async_track_point_in_utc_time') as mock, \
            patch('homeassistant.util.dt.utcnow', return_value=now):
        async_call_later(hass, 3, action)

    assert len(mock.mock_calls) == 1
    p_hass, p_action, p_point = mock.mock_calls[0][1]
    assert p_hass is hass
    assert p_action is action
    assert p_point == now + timedelta(seconds=3)


async def test_async_call_later(hass):
    """Test calling an action later."""
    def action():
        pass
    now = datetime(2017, 12, 19, 15, 40, 0, tzinfo=dt_util.UTC)

    with patch('homeassistant.helpers.event'
               '.async_track_point_in_utc_time') as mock, \
            patch('homeassistant.util.dt.utcnow', return_value=now):
        remove = async_call_later(hass, 3, action)

    assert len(mock.mock_calls) == 1
    p_hass, p_action, p_point = mock.mock_calls[0][1]
    assert p_hass is hass
    assert p_action is action
    assert p_point == now + timedelta(seconds=3)
    assert remove is mock()
