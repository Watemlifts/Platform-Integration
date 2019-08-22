"""The tests for the utility_meter sensor platform."""
import logging

from datetime import timedelta
from unittest.mock import patch
from contextlib import contextmanager

from tests.common import async_fire_time_changed
from homeassistant.const import EVENT_HOMEASSISTANT_START, ATTR_ENTITY_ID
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util
from homeassistant.components.utility_meter.const import (
    DOMAIN, SERVICE_SELECT_TARIFF, ATTR_TARIFF)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN

_LOGGER = logging.getLogger(__name__)


@contextmanager
def alter_time(retval):
    """Manage multiple time mocks."""
    patch1 = patch("homeassistant.util.dt.utcnow", return_value=retval)
    patch2 = patch("homeassistant.util.dt.now", return_value=retval)

    with patch1, patch2:
        yield


async def test_state(hass):
    """Test utility sensor state."""
    config = {
        'utility_meter': {
            'energy_bill': {
                'source': 'sensor.energy',
                'tariffs': ['onpeak', 'midpeak', 'offpeak']},
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)
    assert await async_setup_component(hass, SENSOR_DOMAIN, config)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    entity_id = config[DOMAIN]['energy_bill']['source']
    hass.states.async_set(entity_id, 2, {"unit_of_measurement": "kWh"})
    await hass.async_block_till_done()

    now = dt_util.utcnow() + timedelta(seconds=10)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.states.async_set(entity_id, 3, {"unit_of_measurement": "kWh"},
                              force_update=True)
        await hass.async_block_till_done()

    state = hass.states.get('sensor.energy_bill_onpeak')
    assert state is not None
    assert state.state == '1'

    state = hass.states.get('sensor.energy_bill_midpeak')
    assert state is not None
    assert state.state == '0'

    state = hass.states.get('sensor.energy_bill_offpeak')
    assert state is not None
    assert state.state == '0'

    await hass.services.async_call(DOMAIN, SERVICE_SELECT_TARIFF, {
        ATTR_ENTITY_ID: 'utility_meter.energy_bill', ATTR_TARIFF: 'offpeak'
        }, blocking=True)

    await hass.async_block_till_done()

    now = dt_util.utcnow() + timedelta(seconds=20)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.states.async_set(entity_id, 6, {"unit_of_measurement": "kWh"},
                              force_update=True)
        await hass.async_block_till_done()

    state = hass.states.get('sensor.energy_bill_onpeak')
    assert state is not None
    assert state.state == '1'

    state = hass.states.get('sensor.energy_bill_midpeak')
    assert state is not None
    assert state.state == '0'

    state = hass.states.get('sensor.energy_bill_offpeak')
    assert state is not None
    assert state.state == '3'


async def test_net_consumption(hass):
    """Test utility sensor state."""
    config = {
        'utility_meter': {
            'energy_bill': {
                'source': 'sensor.energy',
                'net_consumption': True
            }
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)
    assert await async_setup_component(hass, SENSOR_DOMAIN, config)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    entity_id = config[DOMAIN]['energy_bill']['source']
    hass.states.async_set(entity_id, 2, {"unit_of_measurement": "kWh"})
    await hass.async_block_till_done()

    now = dt_util.utcnow() + timedelta(seconds=10)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.states.async_set(entity_id, 1, {"unit_of_measurement": "kWh"},
                              force_update=True)
        await hass.async_block_till_done()

    state = hass.states.get('sensor.energy_bill')
    assert state is not None

    assert state.state == '-1'


async def test_non_net_consumption(hass):
    """Test utility sensor state."""
    config = {
        'utility_meter': {
            'energy_bill': {
                'source': 'sensor.energy',
                'net_consumption': False
            }
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)
    assert await async_setup_component(hass, SENSOR_DOMAIN, config)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    entity_id = config[DOMAIN]['energy_bill']['source']
    hass.states.async_set(entity_id, 2, {"unit_of_measurement": "kWh"})
    await hass.async_block_till_done()

    now = dt_util.utcnow() + timedelta(seconds=10)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.states.async_set(entity_id, 1, {"unit_of_measurement": "kWh"},
                              force_update=True)
        await hass.async_block_till_done()

    state = hass.states.get('sensor.energy_bill')
    assert state is not None

    assert state.state == '0'


def gen_config(cycle, offset=None):
    """Generate configuration."""
    config = {
        'utility_meter': {
            'energy_bill': {
                'source': 'sensor.energy',
                'cycle': cycle
            }
        }
    }

    if offset:
        config['utility_meter']['energy_bill']['offset'] = {
            'days': offset.days,
            'seconds': offset.seconds
        }
    return config


async def _test_self_reset(hass, config, start_time, expect_reset=True):
    """Test energy sensor self reset."""
    assert await async_setup_component(hass, DOMAIN, config)
    assert await async_setup_component(hass, SENSOR_DOMAIN, config)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    entity_id = config[DOMAIN]['energy_bill']['source']

    now = dt_util.parse_datetime(start_time)
    with alter_time(now):
        async_fire_time_changed(hass, now)
        hass.states.async_set(entity_id, 1, {"unit_of_measurement": "kWh"})
        await hass.async_block_till_done()

    now += timedelta(seconds=30)
    with alter_time(now):
        async_fire_time_changed(hass, now)
        hass.states.async_set(entity_id, 3, {"unit_of_measurement": "kWh"},
                              force_update=True)
        await hass.async_block_till_done()

    now += timedelta(seconds=30)
    with alter_time(now):
        async_fire_time_changed(hass, now)
        await hass.async_block_till_done()
        hass.states.async_set(entity_id, 6, {"unit_of_measurement": "kWh"},
                              force_update=True)
        await hass.async_block_till_done()

    state = hass.states.get('sensor.energy_bill')
    if expect_reset:
        assert state.attributes.get('last_period') == '2'
        assert state.state == '3'
    else:
        assert state.attributes.get('last_period') == 0
        assert state.state == '5'


async def test_self_reset_hourly(hass):
    """Test hourly reset of meter."""
    await _test_self_reset(hass, gen_config('hourly'),
                           "2017-12-31T23:59:00.000000+00:00")


async def test_self_reset_daily(hass):
    """Test daily reset of meter."""
    await _test_self_reset(hass, gen_config('daily'),
                           "2017-12-31T23:59:00.000000+00:00")


async def test_self_reset_weekly(hass):
    """Test weekly reset of meter."""
    await _test_self_reset(hass, gen_config('weekly'),
                           "2017-12-31T23:59:00.000000+00:00")


async def test_self_reset_monthly(hass):
    """Test monthly reset of meter."""
    await _test_self_reset(hass, gen_config('monthly'),
                           "2017-12-31T23:59:00.000000+00:00")


async def test_self_reset_yearly(hass):
    """Test yearly reset of meter."""
    await _test_self_reset(hass, gen_config('yearly'),
                           "2017-12-31T23:59:00.000000+00:00")


async def test_self_no_reset_yearly(hass):
    """Test yearly reset of meter does not occur after 1st January."""
    await _test_self_reset(hass, gen_config('yearly'),
                           "2018-01-01T23:59:00.000000+00:00",
                           expect_reset=False)


async def test_reset_yearly_offset(hass):
    """Test yearly reset of meter."""
    await _test_self_reset(hass,
                           gen_config('yearly', timedelta(days=1, minutes=10)),
                           "2018-01-02T00:09:00.000000+00:00")


async def test_no_reset_yearly_offset(hass):
    """Test yearly reset of meter."""
    await _test_self_reset(hass, gen_config('yearly', timedelta(31)),
                           "2018-01-30T23:59:00.000000+00:00",
                           expect_reset=False)
