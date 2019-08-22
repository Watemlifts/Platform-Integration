"""The tests for the emulated Hue component."""
import asyncio
import json
from ipaddress import ip_address
from unittest.mock import patch

from aiohttp.hdrs import CONTENT_TYPE
import pytest
from tests.common import get_test_instance_port

from homeassistant import const, setup
from homeassistant.components import (
    fan, http, light, script, emulated_hue, media_player, cover, climate)
from homeassistant.components.emulated_hue import Config
from homeassistant.components.emulated_hue.hue_api import (
    HUE_API_STATE_ON, HUE_API_STATE_BRI, HUE_API_STATE_HUE, HUE_API_STATE_SAT,
    HueUsernameView, HueOneLightStateView,
    HueAllLightsStateView, HueOneLightChangeView, HueAllGroupsStateView)
from homeassistant.const import STATE_ON, STATE_OFF

import homeassistant.util.dt as dt_util
from datetime import timedelta
from tests.common import async_fire_time_changed

HTTP_SERVER_PORT = get_test_instance_port()
BRIDGE_SERVER_PORT = get_test_instance_port()

BRIDGE_URL_BASE = 'http://127.0.0.1:{}'.format(BRIDGE_SERVER_PORT) + '{}'
JSON_HEADERS = {CONTENT_TYPE: const.CONTENT_TYPE_JSON}


@pytest.fixture
def hass_hue(loop, hass):
    """Set up a Home Assistant instance for these tests."""
    # We need to do this to get access to homeassistant/turn_(on,off)
    loop.run_until_complete(setup.async_setup_component(
        hass, 'homeassistant', {}))

    loop.run_until_complete(setup.async_setup_component(
        hass, http.DOMAIN,
        {http.DOMAIN: {http.CONF_SERVER_PORT: HTTP_SERVER_PORT}}))

    with patch('homeassistant.components'
               '.emulated_hue.UPNPResponderThread'):
        loop.run_until_complete(
            setup.async_setup_component(hass, emulated_hue.DOMAIN, {
                emulated_hue.DOMAIN: {
                    emulated_hue.CONF_LISTEN_PORT: BRIDGE_SERVER_PORT,
                    emulated_hue.CONF_EXPOSE_BY_DEFAULT: True
                }
            }))

    loop.run_until_complete(
        setup.async_setup_component(hass, light.DOMAIN, {
            'light': [
                {
                    'platform': 'demo',
                }
            ]
        }))

    loop.run_until_complete(
        setup.async_setup_component(hass, script.DOMAIN, {
            'script': {
                'set_kitchen_light': {
                    'sequence': [
                        {
                            'service_template':
                                "light.turn_{{ requested_state }}",
                            'data_template': {
                                'entity_id': 'light.kitchen_lights',
                                'brightness': "{{ requested_level }}"
                                }
                        }
                    ]
                }
            }
        }))

    loop.run_until_complete(
        setup.async_setup_component(hass, climate.DOMAIN, {
            'climate': [
                {
                    'platform': 'demo',
                }
            ]
        }))

    loop.run_until_complete(
        setup.async_setup_component(hass, media_player.DOMAIN, {
            'media_player': [
                {
                    'platform': 'demo',
                }
            ]
        }))

    loop.run_until_complete(
        setup.async_setup_component(hass, fan.DOMAIN, {
            'fan': [
                {
                    'platform': 'demo',
                }
            ]
        }))

    loop.run_until_complete(
        setup.async_setup_component(hass, cover.DOMAIN, {
            'cover': [
                {
                    'platform': 'demo',
                }
            ]
        }))

    # Kitchen light is explicitly excluded from being exposed
    kitchen_light_entity = hass.states.get('light.kitchen_lights')
    attrs = dict(kitchen_light_entity.attributes)
    attrs[emulated_hue.ATTR_EMULATED_HUE] = False
    hass.states.async_set(
        kitchen_light_entity.entity_id, kitchen_light_entity.state,
        attributes=attrs)

    # Ceiling Fan is explicitly excluded from being exposed
    ceiling_fan_entity = hass.states.get('fan.ceiling_fan')
    attrs = dict(ceiling_fan_entity.attributes)
    attrs[emulated_hue.ATTR_EMULATED_HUE_HIDDEN] = True
    hass.states.async_set(
        ceiling_fan_entity.entity_id, ceiling_fan_entity.state,
        attributes=attrs)

    # Expose the script
    script_entity = hass.states.get('script.set_kitchen_light')
    attrs = dict(script_entity.attributes)
    attrs[emulated_hue.ATTR_EMULATED_HUE] = True
    hass.states.async_set(
        script_entity.entity_id, script_entity.state, attributes=attrs
    )

    # Expose cover
    cover_entity = hass.states.get('cover.living_room_window')
    attrs = dict(cover_entity.attributes)
    attrs[emulated_hue.ATTR_EMULATED_HUE_HIDDEN] = False
    hass.states.async_set(
        cover_entity.entity_id, cover_entity.state, attributes=attrs
    )

    # Expose Hvac
    hvac_entity = hass.states.get('climate.hvac')
    attrs = dict(hvac_entity.attributes)
    attrs[emulated_hue.ATTR_EMULATED_HUE_HIDDEN] = False
    hass.states.async_set(
        hvac_entity.entity_id, hvac_entity.state, attributes=attrs
    )

    # Expose HeatPump
    hp_entity = hass.states.get('climate.heatpump')
    attrs = dict(hp_entity.attributes)
    attrs[emulated_hue.ATTR_EMULATED_HUE_HIDDEN] = False
    hass.states.async_set(
        hp_entity.entity_id, hp_entity.state, attributes=attrs
    )

    return hass


@pytest.fixture
def hue_client(loop, hass_hue, aiohttp_client):
    """Create web client for emulated hue api."""
    web_app = hass_hue.http.app
    config = Config(None, {
        emulated_hue.CONF_TYPE: emulated_hue.TYPE_ALEXA,
        emulated_hue.CONF_ENTITIES: {
            'light.bed_light': {
                emulated_hue.CONF_ENTITY_HIDDEN: True
            },
            'cover.living_room_window': {
                emulated_hue.CONF_ENTITY_HIDDEN: False
            }

        }
    })

    HueUsernameView().register(web_app, web_app.router)
    HueAllLightsStateView(config).register(web_app, web_app.router)
    HueOneLightStateView(config).register(web_app, web_app.router)
    HueOneLightChangeView(config).register(web_app, web_app.router)
    HueAllGroupsStateView(config).register(web_app, web_app.router)

    return loop.run_until_complete(aiohttp_client(web_app))


@asyncio.coroutine
def test_discover_lights(hue_client):
    """Test the discovery of lights."""
    result = yield from hue_client.get('/api/username/lights')

    assert result.status == 200
    assert 'application/json' in result.headers['content-type']

    result_json = yield from result.json()

    devices = set(val['uniqueid'] for val in result_json.values())

    # Make sure the lights we added to the config are there
    assert 'light.ceiling_lights' in devices
    assert 'light.bed_light' not in devices
    assert 'script.set_kitchen_light' in devices
    assert 'light.kitchen_lights' not in devices
    assert 'media_player.living_room' in devices
    assert 'media_player.bedroom' in devices
    assert 'media_player.walkman' in devices
    assert 'media_player.lounge_room' in devices
    assert 'fan.living_room_fan' in devices
    assert 'fan.ceiling_fan' not in devices
    assert 'cover.living_room_window' in devices
    assert 'climate.hvac' in devices
    assert 'climate.heatpump' in devices
    assert 'climate.ecobee' not in devices


@asyncio.coroutine
def test_get_light_state(hass_hue, hue_client):
    """Test the getting of light state."""
    # Turn office light on and set to 127 brightness, and set light color
    yield from hass_hue.services.async_call(
        light.DOMAIN, const.SERVICE_TURN_ON,
        {
            const.ATTR_ENTITY_ID: 'light.ceiling_lights',
            light.ATTR_BRIGHTNESS: 127,
            light.ATTR_RGB_COLOR: (1, 2, 7)
        },
        blocking=True)

    office_json = yield from perform_get_light_state(
        hue_client, 'light.ceiling_lights', 200)

    assert office_json['state'][HUE_API_STATE_ON] is True
    assert office_json['state'][HUE_API_STATE_BRI] == 127
    assert office_json['state'][HUE_API_STATE_HUE] == 41869
    assert office_json['state'][HUE_API_STATE_SAT] == 217

    # Check all lights view
    result = yield from hue_client.get('/api/username/lights')

    assert result.status == 200
    assert 'application/json' in result.headers['content-type']

    result_json = yield from result.json()

    assert 'light.ceiling_lights' in result_json
    assert result_json['light.ceiling_lights']['state'][HUE_API_STATE_BRI] == \
        127

    # Turn office light off
    yield from hass_hue.services.async_call(
        light.DOMAIN, const.SERVICE_TURN_OFF,
        {
            const.ATTR_ENTITY_ID: 'light.ceiling_lights'
        },
        blocking=True)

    office_json = yield from perform_get_light_state(
        hue_client, 'light.ceiling_lights', 200)

    assert office_json['state'][HUE_API_STATE_ON] is False
    assert office_json['state'][HUE_API_STATE_BRI] == 0
    assert office_json['state'][HUE_API_STATE_HUE] == 0
    assert office_json['state'][HUE_API_STATE_SAT] == 0

    # Make sure bedroom light isn't accessible
    yield from perform_get_light_state(
        hue_client, 'light.bed_light', 404)

    # Make sure kitchen light isn't accessible
    yield from perform_get_light_state(
        hue_client, 'light.kitchen_lights', 404)


@asyncio.coroutine
def test_put_light_state(hass_hue, hue_client):
    """Test the setting of light states."""
    yield from perform_put_test_on_ceiling_lights(hass_hue, hue_client)

    # Turn the bedroom light on first
    yield from hass_hue.services.async_call(
        light.DOMAIN, const.SERVICE_TURN_ON,
        {const.ATTR_ENTITY_ID: 'light.ceiling_lights',
         light.ATTR_BRIGHTNESS: 153},
        blocking=True)

    ceiling_lights = hass_hue.states.get('light.ceiling_lights')
    assert ceiling_lights.state == STATE_ON
    assert ceiling_lights.attributes[light.ATTR_BRIGHTNESS] == 153

    # update light state through api
    yield from perform_put_light_state(
        hass_hue, hue_client,
        'light.ceiling_lights', True,
        hue=4369, saturation=127, brightness=123)

    # go through api to get the state back
    ceiling_json = yield from perform_get_light_state(
        hue_client, 'light.ceiling_lights', 200)
    assert ceiling_json['state'][HUE_API_STATE_BRI] == 123
    assert ceiling_json['state'][HUE_API_STATE_HUE] == 4369
    assert ceiling_json['state'][HUE_API_STATE_SAT] == 127

    # Go through the API to turn it off
    ceiling_result = yield from perform_put_light_state(
        hass_hue, hue_client,
        'light.ceiling_lights', False)

    ceiling_result_json = yield from ceiling_result.json()

    assert ceiling_result.status == 200
    assert 'application/json' in ceiling_result.headers['content-type']

    assert len(ceiling_result_json) == 1

    # Check to make sure the state changed
    ceiling_lights = hass_hue.states.get('light.ceiling_lights')
    assert ceiling_lights.state == STATE_OFF
    ceiling_json = yield from perform_get_light_state(
        hue_client, 'light.ceiling_lights', 200)
    assert ceiling_json['state'][HUE_API_STATE_BRI] == 0
    assert ceiling_json['state'][HUE_API_STATE_HUE] == 0
    assert ceiling_json['state'][HUE_API_STATE_SAT] == 0

    # Make sure we can't change the bedroom light state
    bedroom_result = yield from perform_put_light_state(
        hass_hue, hue_client,
        'light.bed_light', True)
    assert bedroom_result.status == 404

    # Make sure we can't change the kitchen light state
    kitchen_result = yield from perform_put_light_state(
        hass_hue, hue_client,
        'light.kitchen_light', True)
    assert kitchen_result.status == 404


@asyncio.coroutine
def test_put_light_state_script(hass_hue, hue_client):
    """Test the setting of script variables."""
    # Turn the kitchen light off first
    yield from hass_hue.services.async_call(
        light.DOMAIN, const.SERVICE_TURN_OFF,
        {const.ATTR_ENTITY_ID: 'light.kitchen_lights'},
        blocking=True)

    # Emulated hue converts 0-100% to 0-255.
    level = 23
    brightness = round(level * 255 / 100)

    script_result = yield from perform_put_light_state(
        hass_hue, hue_client,
        'script.set_kitchen_light', True, brightness)

    script_result_json = yield from script_result.json()

    assert script_result.status == 200
    assert len(script_result_json) == 2

    kitchen_light = hass_hue.states.get('light.kitchen_lights')
    assert kitchen_light.state == 'on'
    assert kitchen_light.attributes[light.ATTR_BRIGHTNESS] == level


@asyncio.coroutine
def test_put_light_state_climate_set_temperature(hass_hue, hue_client):
    """Test setting climate temperature."""
    brightness = 19
    temperature = round(brightness / 255 * 100)

    hvac_result = yield from perform_put_light_state(
        hass_hue, hue_client,
        'climate.hvac', True, brightness)

    hvac_result_json = yield from hvac_result.json()

    assert hvac_result.status == 200
    assert len(hvac_result_json) == 2

    hvac = hass_hue.states.get('climate.hvac')
    assert hvac.state == climate.const.STATE_COOL
    assert hvac.attributes[climate.ATTR_TEMPERATURE] == temperature
    assert hvac.attributes[climate.ATTR_OPERATION_MODE] == \
        climate.const.STATE_COOL

    # Make sure we can't change the ecobee temperature since it's not exposed
    ecobee_result = yield from perform_put_light_state(
        hass_hue, hue_client,
        'climate.ecobee', True)
    assert ecobee_result.status == 404


@asyncio.coroutine
def test_put_light_state_climate_turn_on(hass_hue, hue_client):
    """Test inability to turn climate on."""
    yield from hass_hue.services.async_call(
        climate.DOMAIN, const.SERVICE_TURN_OFF,
        {const.ATTR_ENTITY_ID: 'climate.heatpump'},
        blocking=True)

    # Somehow after calling the above service the device gets unexposed,
    # so we need to expose it again
    hp_entity = hass_hue.states.get('climate.heatpump')
    attrs = dict(hp_entity.attributes)
    attrs[emulated_hue.ATTR_EMULATED_HUE_HIDDEN] = False
    hass_hue.states.async_set(
        hp_entity.entity_id, hp_entity.state, attributes=attrs
    )

    hp_result = yield from perform_put_light_state(
        hass_hue, hue_client,
        'climate.heatpump', True)

    hp_result_json = yield from hp_result.json()

    assert hp_result.status == 200
    assert len(hp_result_json) == 1

    hp = hass_hue.states.get('climate.heatpump')
    assert hp.state == STATE_OFF
    assert hp.attributes[climate.ATTR_OPERATION_MODE] == \
        climate.const.STATE_HEAT


@asyncio.coroutine
def test_put_light_state_climate_turn_off(hass_hue, hue_client):
    """Test inability to turn climate off."""
    hp_result = yield from perform_put_light_state(
        hass_hue, hue_client,
        'climate.heatpump', False)

    hp_result_json = yield from hp_result.json()

    assert hp_result.status == 200
    assert len(hp_result_json) == 1

    hp = hass_hue.states.get('climate.heatpump')
    assert hp.state == climate.const.STATE_HEAT
    assert hp.attributes[climate.ATTR_OPERATION_MODE] == \
        climate.const.STATE_HEAT


@asyncio.coroutine
def test_put_light_state_media_player(hass_hue, hue_client):
    """Test turning on media player and setting volume."""
    # Turn the music player off first
    yield from hass_hue.services.async_call(
        media_player.DOMAIN, const.SERVICE_TURN_OFF,
        {const.ATTR_ENTITY_ID: 'media_player.walkman'},
        blocking=True)

    # Emulated hue converts 0.0-1.0 to 0-255.
    level = 0.25
    brightness = round(level * 255)

    mp_result = yield from perform_put_light_state(
        hass_hue, hue_client,
        'media_player.walkman', True, brightness)

    mp_result_json = yield from mp_result.json()

    assert mp_result.status == 200
    assert len(mp_result_json) == 2

    walkman = hass_hue.states.get('media_player.walkman')
    assert walkman.state == 'playing'
    assert walkman.attributes[media_player.ATTR_MEDIA_VOLUME_LEVEL] == level


async def test_close_cover(hass_hue, hue_client):
    """Test opening cover ."""
    COVER_ID = "cover.living_room_window"
    # Turn the office light off first
    await hass_hue.services.async_call(
        cover.DOMAIN, const.SERVICE_CLOSE_COVER,
        {const.ATTR_ENTITY_ID: COVER_ID},
        blocking=True)

    cover_test = hass_hue.states.get(COVER_ID)
    assert cover_test.state == 'closing'

    for _ in range(7):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass_hue, future)
        await hass_hue.async_block_till_done()

    cover_test = hass_hue.states.get(COVER_ID)
    assert cover_test.state == 'closed'

    # Go through the API to turn it on
    cover_result = await perform_put_light_state(
        hass_hue, hue_client,
        COVER_ID, True, 100)

    assert cover_result.status == 200
    assert 'application/json' in cover_result.headers['content-type']

    for _ in range(7):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass_hue, future)
        await hass_hue.async_block_till_done()

    cover_result_json = await cover_result.json()

    assert len(cover_result_json) == 2

    # Check to make sure the state changed
    cover_test_2 = hass_hue.states.get(COVER_ID)
    assert cover_test_2.state == 'open'


async def test_set_position_cover(hass_hue, hue_client):
    """Test setting postion cover ."""
    COVER_ID = "cover.living_room_window"
    # Turn the office light off first
    await hass_hue.services.async_call(
        cover.DOMAIN, const.SERVICE_CLOSE_COVER,
        {const.ATTR_ENTITY_ID: COVER_ID},
        blocking=True)

    cover_test = hass_hue.states.get(COVER_ID)
    assert cover_test.state == 'closing'

    for _ in range(7):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass_hue, future)
        await hass_hue.async_block_till_done()

    cover_test = hass_hue.states.get(COVER_ID)
    assert cover_test.state == 'closed'

    level = 20
    brightness = round(level/100*255)

    # Go through the API to open
    cover_result = await perform_put_light_state(
        hass_hue, hue_client,
        COVER_ID, False, brightness)

    assert cover_result.status == 200
    assert 'application/json' in cover_result.headers['content-type']

    cover_result_json = await cover_result.json()

    assert len(cover_result_json) == 2
    assert True, cover_result_json[0]['success'][
        '/lights/cover.living_room_window/state/on']
    assert cover_result_json[1]['success'][
        '/lights/cover.living_room_window/state/bri'] == level

    for _ in range(100):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass_hue, future)
        await hass_hue.async_block_till_done()

    # Check to make sure the state changed
    cover_test_2 = hass_hue.states.get(COVER_ID)
    assert cover_test_2.state == 'open'
    assert cover_test_2.attributes.get('current_position') == level


@asyncio.coroutine
def test_put_light_state_fan(hass_hue, hue_client):
    """Test turning on fan and setting speed."""
    # Turn the fan off first
    yield from hass_hue.services.async_call(
        fan.DOMAIN, const.SERVICE_TURN_OFF,
        {const.ATTR_ENTITY_ID: 'fan.living_room_fan'},
        blocking=True)

    # Emulated hue converts 0-100% to 0-255.
    level = 43
    brightness = round(level * 255 / 100)

    fan_result = yield from perform_put_light_state(
        hass_hue, hue_client,
        'fan.living_room_fan', True, brightness)

    fan_result_json = yield from fan_result.json()

    assert fan_result.status == 200
    assert len(fan_result_json) == 2

    living_room_fan = hass_hue.states.get('fan.living_room_fan')
    assert living_room_fan.state == 'on'
    assert living_room_fan.attributes[fan.ATTR_SPEED] == fan.SPEED_MEDIUM


# pylint: disable=invalid-name
@asyncio.coroutine
def test_put_with_form_urlencoded_content_type(hass_hue, hue_client):
    """Test the form with urlencoded content."""
    # Needed for Alexa
    yield from perform_put_test_on_ceiling_lights(
        hass_hue, hue_client, 'application/x-www-form-urlencoded')

    # Make sure we fail gracefully when we can't parse the data
    data = {'key1': 'value1', 'key2': 'value2'}
    result = yield from hue_client.put(
        '/api/username/lights/light.ceiling_lights/state',
        headers={
            'content-type': 'application/x-www-form-urlencoded'
        },
        data=data,
    )

    assert result.status == 400


@asyncio.coroutine
def test_entity_not_found(hue_client):
    """Test for entity which are not found."""
    result = yield from hue_client.get(
        '/api/username/lights/not.existant_entity')

    assert result.status == 404

    result = yield from hue_client.put(
        '/api/username/lights/not.existant_entity/state')

    assert result.status == 404


@asyncio.coroutine
def test_allowed_methods(hue_client):
    """Test the allowed methods."""
    result = yield from hue_client.get(
        '/api/username/lights/light.ceiling_lights/state')

    assert result.status == 405

    result = yield from hue_client.put(
        '/api/username/lights/light.ceiling_lights')

    assert result.status == 405

    result = yield from hue_client.put(
        '/api/username/lights')

    assert result.status == 405


@asyncio.coroutine
def test_proper_put_state_request(hue_client):
    """Test the request to set the state."""
    # Test proper on value parsing
    result = yield from hue_client.put(
            '/api/username/lights/{}/state'.format(
                'light.ceiling_lights'),
            data=json.dumps({HUE_API_STATE_ON: 1234}))

    assert result.status == 400

    # Test proper brightness value parsing
    result = yield from hue_client.put(
        '/api/username/lights/{}/state'.format(
            'light.ceiling_lights'),
        data=json.dumps({
            HUE_API_STATE_ON: True,
            HUE_API_STATE_BRI: 'Hello world!'
        }))

    assert result.status == 400


@asyncio.coroutine
def test_get_empty_groups_state(hue_client):
    """Test the request to get groups endpoint."""
    # Test proper on value parsing
    result = yield from hue_client.get(
            '/api/username/groups')

    assert result.status == 200

    result_json = yield from result.json()

    assert result_json == {}


# pylint: disable=invalid-name
async def perform_put_test_on_ceiling_lights(hass_hue, hue_client,
                                             content_type='application/json'):
    """Test the setting of a light."""
    # Turn the office light off first
    await hass_hue.services.async_call(
        light.DOMAIN, const.SERVICE_TURN_OFF,
        {const.ATTR_ENTITY_ID: 'light.ceiling_lights'},
        blocking=True)

    ceiling_lights = hass_hue.states.get('light.ceiling_lights')
    assert ceiling_lights.state == STATE_OFF

    # Go through the API to turn it on
    office_result = await perform_put_light_state(
        hass_hue, hue_client,
        'light.ceiling_lights', True, 56, content_type)

    assert office_result.status == 200
    assert 'application/json' in office_result.headers['content-type']

    office_result_json = await office_result.json()

    assert len(office_result_json) == 2

    # Check to make sure the state changed
    ceiling_lights = hass_hue.states.get('light.ceiling_lights')
    assert ceiling_lights.state == STATE_ON
    assert ceiling_lights.attributes[light.ATTR_BRIGHTNESS] == 56


@asyncio.coroutine
def perform_get_light_state(client, entity_id, expected_status):
    """Test the getting of a light state."""
    result = yield from client.get('/api/username/lights/{}'.format(entity_id))

    assert result.status == expected_status

    if expected_status == 200:
        assert 'application/json' in result.headers['content-type']

        return (yield from result.json())

    return None


@asyncio.coroutine
def perform_put_light_state(hass_hue, client, entity_id, is_on,
                            brightness=None, content_type='application/json',
                            hue=None, saturation=None):
    """Test the setting of a light state."""
    req_headers = {'Content-Type': content_type}

    data = {HUE_API_STATE_ON: is_on}

    if brightness is not None:
        data[HUE_API_STATE_BRI] = brightness
    if hue is not None:
        data[HUE_API_STATE_HUE] = hue
    if saturation is not None:
        data[HUE_API_STATE_SAT] = saturation

    result = yield from client.put(
        '/api/username/lights/{}/state'.format(entity_id), headers=req_headers,
        data=json.dumps(data).encode())

    # Wait until state change is complete before continuing
    yield from hass_hue.async_block_till_done()

    return result


async def test_external_ip_blocked(hue_client):
    """Test external IP blocked."""
    with patch('homeassistant.components.http.real_ip.ip_address',
               return_value=ip_address('45.45.45.45')):
        result = await hue_client.get('/api/username/lights')

    assert result.status == 400
