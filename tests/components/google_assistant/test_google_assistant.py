"""The tests for the Google Assistant component."""
# pylint: disable=protected-access
import asyncio
import json

from aiohttp.hdrs import CONTENT_TYPE, AUTHORIZATION
import pytest

from homeassistant import core, const, setup
from homeassistant.components import (
    fan, cover, light, switch, lock, media_player)
from homeassistant.components.climate import const as climate
from homeassistant.const import CLOUD_NEVER_EXPOSED_ENTITIES
from homeassistant.components import google_assistant as ga

from . import DEMO_DEVICES

API_PASSWORD = "test1234"

HA_HEADERS = {
    const.HTTP_HEADER_HA_AUTH: API_PASSWORD,
    CONTENT_TYPE: const.CONTENT_TYPE_JSON,
}

PROJECT_ID = 'hasstest-1234'
CLIENT_ID = 'helloworld'
ACCESS_TOKEN = 'superdoublesecret'


@pytest.fixture
def auth_header(hass_access_token):
    """Generate an HTTP header with bearer token authorization."""
    return {AUTHORIZATION: 'Bearer {}'.format(hass_access_token)}


@pytest.fixture
def assistant_client(loop, hass, aiohttp_client):
    """Create web client for the Google Assistant API."""
    loop.run_until_complete(
        setup.async_setup_component(hass, 'google_assistant', {
            'google_assistant': {
                'project_id': PROJECT_ID,
                'entity_config': {
                    'light.ceiling_lights': {
                        'aliases': ['top lights', 'ceiling lights'],
                        'name': 'Roof Lights',
                    },
                }
            }
        }))

    return loop.run_until_complete(aiohttp_client(hass.http.app))


@pytest.fixture
def hass_fixture(loop, hass):
    """Set up a Home Assistant instance for these tests."""
    # We need to do this to get access to homeassistant/turn_(on,off)
    loop.run_until_complete(setup.async_setup_component(hass, core.DOMAIN, {}))

    loop.run_until_complete(
        setup.async_setup_component(hass, light.DOMAIN, {
            'light': [{
                'platform': 'demo'
            }]
        }))
    loop.run_until_complete(
        setup.async_setup_component(hass, switch.DOMAIN, {
            'switch': [{
                'platform': 'demo'
            }]
        }))
    loop.run_until_complete(
        setup.async_setup_component(hass, cover.DOMAIN, {
            'cover': [{
                'platform': 'demo'
            }],
        }))

    loop.run_until_complete(
        setup.async_setup_component(hass, media_player.DOMAIN, {
            'media_player': [{
                'platform': 'demo'
            }]
        }))

    loop.run_until_complete(
        setup.async_setup_component(hass, fan.DOMAIN, {
            'fan': [{
                'platform': 'demo'
            }]
        }))

    loop.run_until_complete(
        setup.async_setup_component(hass, climate.DOMAIN, {
            'climate': [{
                'platform': 'demo'
            }]
        }))

    loop.run_until_complete(
        setup.async_setup_component(hass, lock.DOMAIN, {
            'lock': [{
                'platform': 'demo'
            }]
        }))

    return hass

# pylint: disable=redefined-outer-name


@asyncio.coroutine
def test_sync_request(hass_fixture, assistant_client, auth_header):
    """Test a sync request."""
    reqid = '5711642932632160983'
    data = {'requestId': reqid, 'inputs': [{'intent': 'action.devices.SYNC'}]}
    result = yield from assistant_client.post(
        ga.const.GOOGLE_ASSISTANT_API_ENDPOINT,
        data=json.dumps(data),
        headers=auth_header)
    assert result.status == 200
    body = yield from result.json()
    assert body.get('requestId') == reqid
    devices = body['payload']['devices']
    assert (
        sorted([dev['id'] for dev in devices])
        == sorted([dev['id'] for dev in DEMO_DEVICES]))

    for dev in devices:
        assert dev['id'] not in CLOUD_NEVER_EXPOSED_ENTITIES

    for dev, demo in zip(
            sorted(devices, key=lambda d: d['id']),
            sorted(DEMO_DEVICES, key=lambda d: d['id'])):
        assert dev['name'] == demo['name']
        assert set(dev['traits']) == set(demo['traits'])
        assert dev['type'] == demo['type']
        if 'attributes' in demo:
            assert dev['attributes'] == demo['attributes']


@asyncio.coroutine
def test_query_request(hass_fixture, assistant_client, auth_header):
    """Test a query request."""
    reqid = '5711642932632160984'
    data = {
        'requestId':
        reqid,
        'inputs': [{
            'intent': 'action.devices.QUERY',
            'payload': {
                'devices': [{
                    'id': "light.ceiling_lights",
                }, {
                    'id': "light.bed_light",
                }, {
                    'id': "light.kitchen_lights",
                }, {
                    'id': 'media_player.lounge_room',
                }]
            }
        }]
    }
    result = yield from assistant_client.post(
        ga.const.GOOGLE_ASSISTANT_API_ENDPOINT,
        data=json.dumps(data),
        headers=auth_header)
    assert result.status == 200
    body = yield from result.json()
    assert body.get('requestId') == reqid
    devices = body['payload']['devices']
    assert len(devices) == 4
    assert devices['light.bed_light']['on'] is False
    assert devices['light.ceiling_lights']['on'] is True
    assert devices['light.ceiling_lights']['brightness'] == 70
    assert devices['light.kitchen_lights']['color']['spectrumHsv'] == {
        'hue': 345,
        'saturation': 0.75,
        'value': 0.7058823529411765,
    }
    assert devices['light.kitchen_lights']['color']['temperatureK'] == 4166
    assert devices['media_player.lounge_room']['on'] is True


@asyncio.coroutine
def test_query_climate_request(hass_fixture, assistant_client, auth_header):
    """Test a query request."""
    reqid = '5711642932632160984'
    data = {
        'requestId':
        reqid,
        'inputs': [{
            'intent': 'action.devices.QUERY',
            'payload': {
                'devices': [
                    {'id': 'climate.hvac'},
                    {'id': 'climate.heatpump'},
                    {'id': 'climate.ecobee'},
                ]
            }
        }]
    }
    result = yield from assistant_client.post(
        ga.const.GOOGLE_ASSISTANT_API_ENDPOINT,
        data=json.dumps(data),
        headers=auth_header)
    assert result.status == 200
    body = yield from result.json()
    assert body.get('requestId') == reqid
    devices = body['payload']['devices']
    assert len(devices) == 3
    assert devices['climate.heatpump'] == {
        'online': True,
        'thermostatTemperatureSetpoint': 20.0,
        'thermostatTemperatureAmbient': 25.0,
        'thermostatMode': 'heat',
    }
    assert devices['climate.ecobee'] == {
        'online': True,
        'thermostatTemperatureSetpointHigh': 24,
        'thermostatTemperatureAmbient': 23,
        'thermostatMode': 'heatcool',
        'thermostatTemperatureSetpointLow': 21
    }
    assert devices['climate.hvac'] == {
        'online': True,
        'thermostatTemperatureSetpoint': 21,
        'thermostatTemperatureAmbient': 22,
        'thermostatMode': 'cool',
        'thermostatHumidityAmbient': 54,
    }


@asyncio.coroutine
def test_query_climate_request_f(hass_fixture, assistant_client, auth_header):
    """Test a query request."""
    # Mock demo devices as fahrenheit to see if we convert to celsius
    hass_fixture.config.units.temperature_unit = const.TEMP_FAHRENHEIT
    for entity_id in ('climate.hvac', 'climate.heatpump', 'climate.ecobee'):
        state = hass_fixture.states.get(entity_id)
        attr = dict(state.attributes)
        hass_fixture.states.async_set(entity_id, state.state, attr)

    reqid = '5711642932632160984'
    data = {
        'requestId':
        reqid,
        'inputs': [{
            'intent': 'action.devices.QUERY',
            'payload': {
                'devices': [
                    {'id': 'climate.hvac'},
                    {'id': 'climate.heatpump'},
                    {'id': 'climate.ecobee'},
                ]
            }
        }]
    }
    result = yield from assistant_client.post(
        ga.const.GOOGLE_ASSISTANT_API_ENDPOINT,
        data=json.dumps(data),
        headers=auth_header)
    assert result.status == 200
    body = yield from result.json()
    assert body.get('requestId') == reqid
    devices = body['payload']['devices']
    assert len(devices) == 3
    assert devices['climate.heatpump'] == {
        'online': True,
        'thermostatTemperatureSetpoint': -6.7,
        'thermostatTemperatureAmbient': -3.9,
        'thermostatMode': 'heat',
    }
    assert devices['climate.ecobee'] == {
        'online': True,
        'thermostatTemperatureSetpointHigh': -4.4,
        'thermostatTemperatureAmbient': -5,
        'thermostatMode': 'heatcool',
        'thermostatTemperatureSetpointLow': -6.1,
    }
    assert devices['climate.hvac'] == {
        'online': True,
        'thermostatTemperatureSetpoint': -6.1,
        'thermostatTemperatureAmbient': -5.6,
        'thermostatMode': 'cool',
        'thermostatHumidityAmbient': 54,
    }
    hass_fixture.config.units.temperature_unit = const.TEMP_CELSIUS


@asyncio.coroutine
def test_execute_request(hass_fixture, assistant_client, auth_header):
    """Test an execute request."""
    reqid = '5711642932632160985'
    data = {
        'requestId':
        reqid,
        'inputs': [{
            'intent': 'action.devices.EXECUTE',
            'payload': {
                "commands": [{
                    "devices": [{
                        "id": "light.ceiling_lights",
                    }, {
                        "id": "switch.decorative_lights",
                    }, {
                        "id": "media_player.lounge_room",
                    }],
                    "execution": [{
                        "command": "action.devices.commands.OnOff",
                        "params": {
                            "on": False
                        }
                    }]
                }, {
                    "devices": [{
                        "id": "media_player.walkman",
                    }],
                    "execution": [{
                        "command":
                        "action.devices.commands.setVolume",
                        "params": {
                            "volumeLevel": 70
                        }
                    }]
                }, {
                    "devices": [{
                        "id": "light.kitchen_lights",
                    }],
                    "execution": [{
                        "command": "action.devices.commands.ColorAbsolute",
                        "params": {
                            "color": {
                                "spectrumRGB": 16711680
                            }
                        }
                    }]
                }, {
                    "devices": [{
                        "id": "light.bed_light"
                    }],
                    "execution": [{
                        "command": "action.devices.commands.ColorAbsolute",
                        "params": {
                            "color": {
                                "spectrumRGB": 65280
                            }
                        }
                    }, {
                        "command": "action.devices.commands.ColorAbsolute",
                        "params": {
                            "color": {
                                "temperature": 4700
                            }
                        }
                    }]
                }]
            }
        }]
    }
    result = yield from assistant_client.post(
        ga.const.GOOGLE_ASSISTANT_API_ENDPOINT,
        data=json.dumps(data),
        headers=auth_header)
    assert result.status == 200
    body = yield from result.json()
    assert body.get('requestId') == reqid
    commands = body['payload']['commands']
    assert len(commands) == 6

    assert not any(result['status'] == 'ERROR' for result in commands)

    ceiling = hass_fixture.states.get('light.ceiling_lights')
    assert ceiling.state == 'off'

    kitchen = hass_fixture.states.get('light.kitchen_lights')
    assert kitchen.attributes.get(light.ATTR_RGB_COLOR) == (255, 0, 0)

    bed = hass_fixture.states.get('light.bed_light')
    assert bed.attributes.get(light.ATTR_COLOR_TEMP) == 212
    assert bed.attributes.get(light.ATTR_RGB_COLOR) == (0, 255, 0)

    assert hass_fixture.states.get('switch.decorative_lights').state == 'off'

    walkman = hass_fixture.states.get('media_player.walkman')
    assert walkman.state == 'playing'
    assert walkman.attributes.get(media_player.ATTR_MEDIA_VOLUME_LEVEL) == 0.7

    lounge = hass_fixture.states.get('media_player.lounge_room')
    assert lounge.state == 'off'
