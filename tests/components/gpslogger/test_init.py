"""The tests the for GPSLogger device tracker platform."""
from unittest.mock import Mock, patch

import pytest

from homeassistant import data_entry_flow
from homeassistant.components import gpslogger, zone
from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN)
from homeassistant.components.gpslogger import DOMAIN, TRACKER_UPDATE
from homeassistant.const import (
    HTTP_OK, HTTP_UNPROCESSABLE_ENTITY, STATE_HOME, STATE_NOT_HOME)
from homeassistant.helpers.dispatcher import DATA_DISPATCHER
from homeassistant.setup import async_setup_component

HOME_LATITUDE = 37.239622
HOME_LONGITUDE = -115.815811

# pylint: disable=redefined-outer-name


@pytest.fixture(autouse=True)
def mock_dev_track(mock_device_tracker_conf):
    """Mock device tracker config loading."""
    pass


@pytest.fixture
async def gpslogger_client(loop, hass, aiohttp_client):
    """Mock client for GPSLogger (unauthenticated)."""
    assert await async_setup_component(
        hass, 'persistent_notification', {})

    assert await async_setup_component(
        hass, DOMAIN, {
            DOMAIN: {}
        })

    await hass.async_block_till_done()

    with patch('homeassistant.components.device_tracker.legacy.update_config'):
        return await aiohttp_client(hass.http.app)


@pytest.fixture(autouse=True)
async def setup_zones(loop, hass):
    """Set up Zone config in HA."""
    assert await async_setup_component(
        hass, zone.DOMAIN, {
            'zone': {
                'name': 'Home',
                'latitude': HOME_LATITUDE,
                'longitude': HOME_LONGITUDE,
                'radius': 100,
            }})
    await hass.async_block_till_done()


@pytest.fixture
async def webhook_id(hass, gpslogger_client):
    """Initialize the GPSLogger component and get the webhook_id."""
    hass.config.api = Mock(base_url='http://example.com')
    result = await hass.config_entries.flow.async_init(DOMAIN, context={
        'source': 'user'
    })
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM, result

    result = await hass.config_entries.flow.async_configure(
        result['flow_id'], {})
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    await hass.async_block_till_done()
    return result['result'].data['webhook_id']


async def test_missing_data(hass, gpslogger_client, webhook_id):
    """Test missing data."""
    url = '/api/webhook/{}'.format(webhook_id)

    data = {
        'latitude': 1.0,
        'longitude': 1.1,
        'device': '123',
    }

    # No data
    req = await gpslogger_client.post(url)
    await hass.async_block_till_done()
    assert req.status == HTTP_UNPROCESSABLE_ENTITY

    # No latitude
    copy = data.copy()
    del copy['latitude']
    req = await gpslogger_client.post(url, data=copy)
    await hass.async_block_till_done()
    assert req.status == HTTP_UNPROCESSABLE_ENTITY

    # No device
    copy = data.copy()
    del copy['device']
    req = await gpslogger_client.post(url, data=copy)
    await hass.async_block_till_done()
    assert req.status == HTTP_UNPROCESSABLE_ENTITY


async def test_enter_and_exit(hass, gpslogger_client, webhook_id):
    """Test when there is a known zone."""
    url = '/api/webhook/{}'.format(webhook_id)

    data = {
        'latitude': HOME_LATITUDE,
        'longitude': HOME_LONGITUDE,
        'device': '123',
    }

    # Enter the Home
    req = await gpslogger_client.post(url, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    state_name = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                                data['device'])).state
    assert STATE_HOME == state_name

    # Enter Home again
    req = await gpslogger_client.post(url, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    state_name = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                                data['device'])).state
    assert STATE_HOME == state_name

    data['longitude'] = 0
    data['latitude'] = 0

    # Enter Somewhere else
    req = await gpslogger_client.post(url, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    state_name = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                                data['device'])).state
    assert STATE_NOT_HOME == state_name

    dev_reg = await hass.helpers.device_registry.async_get_registry()
    assert len(dev_reg.devices) == 1

    ent_reg = await hass.helpers.entity_registry.async_get_registry()
    assert len(ent_reg.entities) == 1


async def test_enter_with_attrs(hass, gpslogger_client, webhook_id):
    """Test when additional attributes are present."""
    url = '/api/webhook/{}'.format(webhook_id)

    data = {
        'latitude': 1.0,
        'longitude': 1.1,
        'device': '123',
        'accuracy': 10.5,
        'battery': 10,
        'speed': 100,
        'direction': 105.32,
        'altitude': 102,
        'provider': 'gps',
        'activity': 'running'
    }

    req = await gpslogger_client.post(url, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    state = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                           data['device']))
    assert state.state == STATE_NOT_HOME
    assert state.attributes['gps_accuracy'] == 10.5
    assert state.attributes['battery_level'] == 10.0
    assert state.attributes['speed'] == 100.0
    assert state.attributes['direction'] == 105.32
    assert state.attributes['altitude'] == 102.0
    assert state.attributes['provider'] == 'gps'
    assert state.attributes['activity'] == 'running'

    data = {
        'latitude': HOME_LATITUDE,
        'longitude': HOME_LONGITUDE,
        'device': '123',
        'accuracy': 123,
        'battery': 23,
        'speed': 23,
        'direction': 123,
        'altitude': 123,
        'provider': 'gps',
        'activity': 'idle'
    }

    req = await gpslogger_client.post(url, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    state = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                           data['device']))
    assert state.state == STATE_HOME
    assert state.attributes['gps_accuracy'] == 123
    assert state.attributes['battery_level'] == 23
    assert state.attributes['speed'] == 23
    assert state.attributes['direction'] == 123
    assert state.attributes['altitude'] == 123
    assert state.attributes['provider'] == 'gps'
    assert state.attributes['activity'] == 'idle'


@pytest.mark.xfail(
    reason='The device_tracker component does not support unloading yet.'
)
async def test_load_unload_entry(hass, gpslogger_client, webhook_id):
    """Test that the appropriate dispatch signals are added and removed."""
    url = '/api/webhook/{}'.format(webhook_id)
    data = {
        'latitude': HOME_LATITUDE,
        'longitude': HOME_LONGITUDE,
        'device': '123',
    }

    # Enter the Home
    req = await gpslogger_client.post(url, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    state_name = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                                data['device'])).state
    assert STATE_HOME == state_name
    assert len(hass.data[DATA_DISPATCHER][TRACKER_UPDATE]) == 1

    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert await gpslogger.async_unload_entry(hass, entry)
    await hass.async_block_till_done()
    assert not hass.data[DATA_DISPATCHER][TRACKER_UPDATE]
