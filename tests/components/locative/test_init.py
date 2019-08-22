"""The tests the for Locative device tracker platform."""
from unittest.mock import patch, Mock

import pytest

from homeassistant import data_entry_flow
from homeassistant.components import locative
from homeassistant.components.device_tracker import \
    DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.locative import DOMAIN, TRACKER_UPDATE
from homeassistant.const import HTTP_OK, HTTP_UNPROCESSABLE_ENTITY
from homeassistant.helpers.dispatcher import DATA_DISPATCHER
from homeassistant.setup import async_setup_component

# pylint: disable=redefined-outer-name


@pytest.fixture(autouse=True)
def mock_dev_track(mock_device_tracker_conf):
    """Mock device tracker config loading."""
    pass


@pytest.fixture
async def locative_client(loop, hass, hass_client):
    """Locative mock client."""
    assert await async_setup_component(
        hass, DOMAIN, {
            DOMAIN: {}
        })
    await hass.async_block_till_done()

    with patch('homeassistant.components.device_tracker.legacy.update_config'):
        return await hass_client()


@pytest.fixture
async def webhook_id(hass, locative_client):
    """Initialize the Geofency component and get the webhook_id."""
    hass.config.api = Mock(base_url='http://example.com')
    result = await hass.config_entries.flow.async_init('locative', context={
        'source': 'user'
    })
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM, result

    result = await hass.config_entries.flow.async_configure(
        result['flow_id'], {})
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    await hass.async_block_till_done()

    return result['result'].data['webhook_id']


async def test_missing_data(locative_client, webhook_id):
    """Test missing data."""
    url = '/api/webhook/{}'.format(webhook_id)

    data = {
        'latitude': 1.0,
        'longitude': 1.1,
        'device': '123',
        'id': 'Home',
        'trigger': 'enter'
    }

    # No data
    req = await locative_client.post(url)
    assert req.status == HTTP_UNPROCESSABLE_ENTITY

    # No latitude
    copy = data.copy()
    del copy['latitude']
    req = await locative_client.post(url, data=copy)
    assert req.status == HTTP_UNPROCESSABLE_ENTITY

    # No device
    copy = data.copy()
    del copy['device']
    req = await locative_client.post(url, data=copy)
    assert req.status == HTTP_UNPROCESSABLE_ENTITY

    # No location
    copy = data.copy()
    del copy['id']
    req = await locative_client.post(url, data=copy)
    assert req.status == HTTP_UNPROCESSABLE_ENTITY

    # No trigger
    copy = data.copy()
    del copy['trigger']
    req = await locative_client.post(url, data=copy)
    assert req.status == HTTP_UNPROCESSABLE_ENTITY

    # Test message
    copy = data.copy()
    copy['trigger'] = 'test'
    req = await locative_client.post(url, data=copy)
    assert req.status == HTTP_OK

    # Test message, no location
    copy = data.copy()
    copy['trigger'] = 'test'
    del copy['id']
    req = await locative_client.post(url, data=copy)
    assert req.status == HTTP_OK

    # Unknown trigger
    copy = data.copy()
    copy['trigger'] = 'foobar'
    req = await locative_client.post(url, data=copy)
    assert req.status == HTTP_UNPROCESSABLE_ENTITY


async def test_enter_and_exit(hass, locative_client, webhook_id):
    """Test when there is a known zone."""
    url = '/api/webhook/{}'.format(webhook_id)

    data = {
        'latitude': 40.7855,
        'longitude': -111.7367,
        'device': '123',
        'id': 'Home',
        'trigger': 'enter'
    }

    # Enter the Home
    req = await locative_client.post(url, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    state_name = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                                data['device'])).state
    assert state_name == 'home'

    data['id'] = 'HOME'
    data['trigger'] = 'exit'

    # Exit Home
    req = await locative_client.post(url, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    state_name = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                                data['device'])).state
    assert state_name == 'not_home'

    data['id'] = 'hOmE'
    data['trigger'] = 'enter'

    # Enter Home again
    req = await locative_client.post(url, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    state_name = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                                data['device'])).state
    assert state_name == 'home'

    data['trigger'] = 'exit'

    # Exit Home
    req = await locative_client.post(url, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    state_name = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                                data['device'])).state
    assert state_name == 'not_home'

    data['id'] = 'work'
    data['trigger'] = 'enter'

    # Enter Work
    req = await locative_client.post(url, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK
    state_name = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                                data['device'])).state
    assert state_name == 'work'


async def test_exit_after_enter(hass, locative_client, webhook_id):
    """Test when an exit message comes after an enter message."""
    url = '/api/webhook/{}'.format(webhook_id)

    data = {
        'latitude': 40.7855,
        'longitude': -111.7367,
        'device': '123',
        'id': 'Home',
        'trigger': 'enter'
    }

    # Enter Home
    req = await locative_client.post(url, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK

    state = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                           data['device']))
    assert state.state == 'home'

    data['id'] = 'Work'

    # Enter Work
    req = await locative_client.post(url, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK

    state = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                           data['device']))
    assert state.state == 'work'

    data['id'] = 'Home'
    data['trigger'] = 'exit'

    # Exit Home
    req = await locative_client.post(url, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK

    state = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                           data['device']))
    assert state.state == 'work'


async def test_exit_first(hass, locative_client, webhook_id):
    """Test when an exit message is sent first on a new device."""
    url = '/api/webhook/{}'.format(webhook_id)

    data = {
        'latitude': 40.7855,
        'longitude': -111.7367,
        'device': 'new_device',
        'id': 'Home',
        'trigger': 'exit'
    }

    # Exit Home
    req = await locative_client.post(url, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK

    state = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                           data['device']))
    assert state.state == 'not_home'


async def test_two_devices(hass, locative_client, webhook_id):
    """Test updating two different devices."""
    url = '/api/webhook/{}'.format(webhook_id)

    data_device_1 = {
        'latitude': 40.7855,
        'longitude': -111.7367,
        'device': 'device_1',
        'id': 'Home',
        'trigger': 'exit'
    }

    # Exit Home
    req = await locative_client.post(url, data=data_device_1)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK

    state = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                           data_device_1['device']))
    assert state.state == 'not_home'

    # Enter Home
    data_device_2 = dict(data_device_1)
    data_device_2['device'] = 'device_2'
    data_device_2['trigger'] = 'enter'
    req = await locative_client.post(url, data=data_device_2)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK

    state = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                           data_device_2['device']))
    assert state.state == 'home'
    state = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                           data_device_1['device']))
    assert state.state == 'not_home'


@pytest.mark.xfail(
    reason='The device_tracker component does not support unloading yet.'
)
async def test_load_unload_entry(hass, locative_client, webhook_id):
    """Test that the appropriate dispatch signals are added and removed."""
    url = '/api/webhook/{}'.format(webhook_id)

    data = {
        'latitude': 40.7855,
        'longitude': -111.7367,
        'device': 'new_device',
        'id': 'Home',
        'trigger': 'exit'
    }

    # Exit Home
    req = await locative_client.post(url, data=data)
    await hass.async_block_till_done()
    assert req.status == HTTP_OK

    state = hass.states.get('{}.{}'.format(DEVICE_TRACKER_DOMAIN,
                                           data['device']))
    assert state.state == 'not_home'
    assert len(hass.data[DATA_DISPATCHER][TRACKER_UPDATE]) == 1

    entry = hass.config_entries.async_entries(DOMAIN)[0]

    await locative.async_unload_entry(hass, entry)
    await hass.async_block_till_done()
    assert not hass.data[DATA_DISPATCHER][TRACKER_UPDATE]
