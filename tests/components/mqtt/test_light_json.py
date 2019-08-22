"""The tests for the MQTT JSON light platform.

Configuration with RGB, brightness, color temp, effect, white value and XY:

light:
  platform: mqtt_json
  name: mqtt_json_light_1
  state_topic: "home/rgb1"
  command_topic: "home/rgb1/set"
  brightness: true
  color_temp: true
  effect: true
  rgb: true
  white_value: true
  xy: true

Configuration with RGB, brightness, color temp, effect, white value:

light:
  platform: mqtt_json
  name: mqtt_json_light_1
  state_topic: "home/rgb1"
  command_topic: "home/rgb1/set"
  brightness: true
  color_temp: true
  effect: true
  rgb: true
  white_value: true

Configuration with RGB, brightness, color temp and effect:

light:
  platform: mqtt_json
  name: mqtt_json_light_1
  state_topic: "home/rgb1"
  command_topic: "home/rgb1/set"
  brightness: true
  color_temp: true
  effect: true
  rgb: true

Configuration with RGB, brightness and color temp:

light:
  platform: mqtt_json
  name: mqtt_json_light_1
  state_topic: "home/rgb1"
  command_topic: "home/rgb1/set"
  brightness: true
  rgb: true
  color_temp: true

Configuration with RGB, brightness:

light:
  platform: mqtt_json
  name: mqtt_json_light_1
  state_topic: "home/rgb1"
  command_topic: "home/rgb1/set"
  brightness: true
  rgb: true

Config without RGB:

light:
  platform: mqtt_json
  name: mqtt_json_light_1
  state_topic: "home/rgb1"
  command_topic: "home/rgb1/set"
  brightness: true

Config without RGB and brightness:

light:
  platform: mqtt_json
  name: mqtt_json_light_1
  state_topic: "home/rgb1"
  command_topic: "home/rgb1/set"

Config with brightness and scale:

light:
  platform: mqtt_json
  name: test
  state_topic: "mqtt_json_light_1"
  command_topic: "mqtt_json_light_1/set"
  brightness: true
  brightness_scale: 99
"""
import json
from unittest import mock
from unittest.mock import ANY, patch

from homeassistant.components import light, mqtt
from homeassistant.components.mqtt.discovery import async_start
from homeassistant.const import (
    ATTR_ASSUMED_STATE, ATTR_SUPPORTED_FEATURES, STATE_OFF, STATE_ON,
    STATE_UNAVAILABLE)
import homeassistant.core as ha
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry, async_fire_mqtt_message, async_mock_mqtt_component,
    mock_coro, mock_registry)
from tests.components.light import common


class JsonValidator(object):
    """Helper to compare JSON."""

    def __init__(self, jsondata):
        """Constructor."""
        self.jsondata = jsondata

    def __eq__(self, other):
        """Compare JSON data."""
        return json.loads(self.jsondata) == json.loads(other)


async def test_fail_setup_if_no_command_topic(hass, mqtt_mock):
    """Test if setup fails with no command topic."""
    assert await async_setup_component(hass, light.DOMAIN, {
        light.DOMAIN: {
            'platform': 'mqtt',
            'schema': 'json',
            'name': 'test',
        }
    })
    assert hass.states.get('light.test') is None


async def test_no_color_brightness_color_temp_white_val_if_no_topics(
        hass, mqtt_mock):
    """Test for no RGB, brightness, color temp, effect, white val or XY."""
    assert await async_setup_component(hass, light.DOMAIN, {
        light.DOMAIN: {
            'platform': 'mqtt',
            'schema': 'json',
            'name': 'test',
            'state_topic': 'test_light_rgb',
            'command_topic': 'test_light_rgb/set',
        }
    })

    state = hass.states.get('light.test')
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 40
    assert state.attributes.get('rgb_color') is None
    assert state.attributes.get('brightness') is None
    assert state.attributes.get('color_temp') is None
    assert state.attributes.get('effect') is None
    assert state.attributes.get('white_value') is None
    assert state.attributes.get('xy_color') is None
    assert state.attributes.get('hs_color') is None

    async_fire_mqtt_message(hass, 'test_light_rgb', '{"state":"ON"}')

    state = hass.states.get('light.test')
    assert state.state == STATE_ON
    assert state.attributes.get('rgb_color') is None
    assert state.attributes.get('brightness') is None
    assert state.attributes.get('color_temp') is None
    assert state.attributes.get('effect') is None
    assert state.attributes.get('white_value') is None
    assert state.attributes.get('xy_color') is None
    assert state.attributes.get('hs_color') is None


async def test_controlling_state_via_topic(hass, mqtt_mock):
    """Test the controlling of the state via topic."""
    assert await async_setup_component(hass, light.DOMAIN, {
        light.DOMAIN: {
            'platform': 'mqtt',
            'schema': 'json',
            'name': 'test',
            'state_topic': 'test_light_rgb',
            'command_topic': 'test_light_rgb/set',
            'brightness': True,
            'color_temp': True,
            'effect': True,
            'rgb': True,
            'white_value': True,
            'xy': True,
            'hs': True,
            'qos': '0'
        }
    })

    state = hass.states.get('light.test')
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 191
    assert state.attributes.get('rgb_color') is None
    assert state.attributes.get('brightness') is None
    assert state.attributes.get('color_temp') is None
    assert state.attributes.get('effect') is None
    assert state.attributes.get('white_value') is None
    assert state.attributes.get('xy_color') is None
    assert state.attributes.get('hs_color') is None
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Turn on the light, full white
    async_fire_mqtt_message(hass, 'test_light_rgb',
                            '{"state":"ON",'
                            '"color":{"r":255,"g":255,"b":255},'
                            '"brightness":255,'
                            '"color_temp":155,'
                            '"effect":"colorloop",'
                            '"white_value":150}')

    state = hass.states.get('light.test')
    assert state.state == STATE_ON
    assert state.attributes.get('rgb_color') == (255, 255, 255)
    assert state.attributes.get('brightness') == 255
    assert state.attributes.get('color_temp') == 155
    assert state.attributes.get('effect') == 'colorloop'
    assert state.attributes.get('white_value') == 150
    assert state.attributes.get('xy_color') == (0.323, 0.329)
    assert state.attributes.get('hs_color') == (0.0, 0.0)

    # Turn the light off
    async_fire_mqtt_message(hass, 'test_light_rgb', '{"state":"OFF"}')

    state = hass.states.get('light.test')
    assert state.state == STATE_OFF

    async_fire_mqtt_message(hass, 'test_light_rgb',
                            '{"state":"ON", "brightness":100}')

    light_state = hass.states.get('light.test')

    assert light_state.attributes['brightness'] == 100

    async_fire_mqtt_message(hass, 'test_light_rgb',
                            '{"state":"ON", '
                            '"color":{"r":125,"g":125,"b":125}}')

    light_state = hass.states.get('light.test')
    assert light_state.attributes.get('rgb_color') == (255, 255, 255)

    async_fire_mqtt_message(hass, 'test_light_rgb',
                            '{"state":"ON", "color":{"x":0.135,"y":0.135}}')

    light_state = hass.states.get('light.test')
    assert light_state.attributes.get('xy_color') == (0.141, 0.14)

    async_fire_mqtt_message(hass, 'test_light_rgb',
                            '{"state":"ON", "color":{"h":180,"s":50}}')

    light_state = hass.states.get('light.test')
    assert light_state.attributes.get('hs_color') == (180.0, 50.0)

    async_fire_mqtt_message(hass, 'test_light_rgb',
                            '{"state":"ON", "color_temp":155}')

    light_state = hass.states.get('light.test')
    assert light_state.attributes.get('color_temp') == 155

    async_fire_mqtt_message(hass, 'test_light_rgb',
                            '{"state":"ON", "effect":"colorloop"}')

    light_state = hass.states.get('light.test')
    assert light_state.attributes.get('effect') == 'colorloop'

    async_fire_mqtt_message(hass, 'test_light_rgb',
                            '{"state":"ON", "white_value":155}')

    light_state = hass.states.get('light.test')
    assert light_state.attributes.get('white_value') == 155


async def test_sending_mqtt_commands_and_optimistic(hass, mqtt_mock):
    """Test the sending of command in optimistic mode."""
    fake_state = ha.State('light.test', 'on', {'brightness': 95,
                                               'hs_color': [100, 100],
                                               'effect': 'random',
                                               'color_temp': 100,
                                               'white_value': 50})

    with patch('homeassistant.helpers.restore_state.RestoreEntity'
               '.async_get_last_state',
               return_value=mock_coro(fake_state)):
        assert await async_setup_component(hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt',
                'schema': 'json',
                'name': 'test',
                'command_topic': 'test_light_rgb/set',
                'brightness': True,
                'color_temp': True,
                'effect': True,
                'hs': True,
                'rgb': True,
                'xy': True,
                'white_value': True,
                'qos': 2
            }
        })

    state = hass.states.get('light.test')
    assert state.state == STATE_ON
    assert state.attributes.get('brightness') == 95
    assert state.attributes.get('hs_color') == (100, 100)
    assert state.attributes.get('effect') == 'random'
    assert state.attributes.get('color_temp') == 100
    assert state.attributes.get('white_value') == 50
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 191
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_on(hass, 'light.test')

    mqtt_mock.async_publish.assert_called_once_with(
        'test_light_rgb/set', '{"state": "ON"}', 2, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get('light.test')
    assert state.state == STATE_ON

    await common.async_turn_off(hass, 'light.test')

    mqtt_mock.async_publish.assert_called_once_with(
        'test_light_rgb/set', '{"state": "OFF"}', 2, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get('light.test')
    assert state.state == STATE_OFF

    mqtt_mock.reset_mock()
    await common.async_turn_on(hass, 'light.test',
                               brightness=50, xy_color=[0.123, 0.123])
    await common.async_turn_on(hass, 'light.test',
                               brightness=50, hs_color=[359, 78])
    await common.async_turn_on(hass, 'light.test', rgb_color=[255, 128, 0],
                               white_value=80)

    mqtt_mock.async_publish.assert_has_calls([
        mock.call(
            'test_light_rgb/set',
            JsonValidator(
                '{"state": "ON", "color": {"r": 0, "g": 123, "b": 255,'
                ' "x": 0.14, "y": 0.131, "h": 210.824, "s": 100.0},'
                ' "brightness": 50}'),
            2, False),
        mock.call(
            'test_light_rgb/set',
            JsonValidator(
                '{"state": "ON", "color": {"r": 255, "g": 56, "b": 59,'
                ' "x": 0.654, "y": 0.301, "h": 359.0, "s": 78.0},'
                ' "brightness": 50}'),
            2, False),
        mock.call(
            'test_light_rgb/set',
            JsonValidator(
                '{"state": "ON", "color": {"r": 255, "g": 128, "b": 0,'
                ' "x": 0.611, "y": 0.375, "h": 30.118, "s": 100.0},'
                ' "white_value": 80}'),
            2, False),
    ], any_order=True)

    state = hass.states.get('light.test')
    assert state.state == STATE_ON
    assert state.attributes['rgb_color'] == (255, 128, 0)
    assert state.attributes['brightness'] == 50
    assert state.attributes['hs_color'] == (30.118, 100)
    assert state.attributes['white_value'] == 80
    assert state.attributes['xy_color'] == (0.611, 0.375)


async def test_sending_hs_color(hass, mqtt_mock):
    """Test light.turn_on with hs color sends hs color parameters."""
    assert await async_setup_component(hass, light.DOMAIN, {
        light.DOMAIN: {
            'platform': 'mqtt',
            'schema': 'json',
            'name': 'test',
            'command_topic': 'test_light_rgb/set',
            'brightness': True,
            'hs': True,
        }
    })

    state = hass.states.get('light.test')
    assert state.state == STATE_OFF

    mqtt_mock.reset_mock()
    await common.async_turn_on(hass, 'light.test',
                               brightness=50, xy_color=[0.123, 0.123])
    await common.async_turn_on(hass, 'light.test',
                               brightness=50, hs_color=[359, 78])
    await common.async_turn_on(hass, 'light.test', rgb_color=[255, 128, 0],
                               white_value=80)

    mqtt_mock.async_publish.assert_has_calls([
        mock.call(
            'test_light_rgb/set',
            JsonValidator(
                '{"state": "ON", "color": {"h": 210.824, "s": 100.0},'
                ' "brightness": 50}'),
            0, False),
        mock.call(
            'test_light_rgb/set',
            JsonValidator(
                '{"state": "ON", "color": {"h": 359.0, "s": 78.0},'
                ' "brightness": 50}'),
            0, False),
        mock.call(
            'test_light_rgb/set',
            JsonValidator(
                '{"state": "ON", "color": {"h": 30.118, "s": 100.0},'
                ' "white_value": 80}'),
            0, False),
    ], any_order=True)


async def test_sending_rgb_color_no_brightness(hass, mqtt_mock):
    """Test light.turn_on with hs color sends rgb color parameters."""
    assert await async_setup_component(hass, light.DOMAIN, {
        light.DOMAIN: {
            'platform': 'mqtt',
            'schema': 'json',
            'name': 'test',
            'command_topic': 'test_light_rgb/set',
            'rgb': True,
        }
    })

    state = hass.states.get('light.test')
    assert state.state == STATE_OFF

    await common.async_turn_on(hass, 'light.test',
                               brightness=50, xy_color=[0.123, 0.123])
    await common.async_turn_on(hass, 'light.test',
                               brightness=50, hs_color=[359, 78])
    await common.async_turn_on(hass, 'light.test', rgb_color=[255, 128, 0],
                               brightness=255)

    mqtt_mock.async_publish.assert_has_calls([
        mock.call(
            'test_light_rgb/set',
            JsonValidator(
                '{"state": "ON", "color": {"r": 0, "g": 24, "b": 50}}'),
            0, False),
        mock.call(
            'test_light_rgb/set',
            JsonValidator(
                '{"state": "ON", "color": {"r": 50, "g": 11, "b": 11}}'),
            0, False),
        mock.call(
            'test_light_rgb/set',
            JsonValidator(
                '{"state": "ON", "color": {"r": 255, "g": 128, "b": 0}}'),
            0, False),
    ], any_order=True)


async def test_sending_rgb_color_with_brightness(hass, mqtt_mock):
    """Test light.turn_on with hs color sends rgb color parameters."""
    assert await async_setup_component(hass, light.DOMAIN, {
        light.DOMAIN: {
            'platform': 'mqtt',
            'schema': 'json',
            'name': 'test',
            'command_topic': 'test_light_rgb/set',
            'brightness': True,
            'rgb': True,
        }
    })

    state = hass.states.get('light.test')
    assert state.state == STATE_OFF

    await common.async_turn_on(hass, 'light.test',
                               brightness=50, xy_color=[0.123, 0.123])
    await common.async_turn_on(hass, 'light.test',
                               brightness=50, hs_color=[359, 78])
    await common.async_turn_on(hass, 'light.test', rgb_color=[255, 128, 0],
                               white_value=80)

    mqtt_mock.async_publish.assert_has_calls([
        mock.call(
            'test_light_rgb/set',
            JsonValidator(
                '{"state": "ON", "color": {"r": 0, "g": 123, "b": 255},'
                ' "brightness": 50}'),
            0, False),
        mock.call(
            'test_light_rgb/set',
            JsonValidator(
                '{"state": "ON", "color": {"r": 255, "g": 56, "b": 59},'
                ' "brightness": 50}'),
            0, False),
        mock.call(
            'test_light_rgb/set',
            JsonValidator(
                '{"state": "ON", "color": {"r": 255, "g": 128, "b": 0},'
                ' "white_value": 80}'),
            0, False),
    ], any_order=True)


async def test_sending_xy_color(hass, mqtt_mock):
    """Test light.turn_on with hs color sends xy color parameters."""
    assert await async_setup_component(hass, light.DOMAIN, {
        light.DOMAIN: {
            'platform': 'mqtt',
            'schema': 'json',
            'name': 'test',
            'command_topic': 'test_light_rgb/set',
            'brightness': True,
            'xy': True,
        }
    })

    state = hass.states.get('light.test')
    assert state.state == STATE_OFF

    await common.async_turn_on(hass, 'light.test',
                               brightness=50, xy_color=[0.123, 0.123])
    await common.async_turn_on(hass, 'light.test',
                               brightness=50, hs_color=[359, 78])
    await common.async_turn_on(hass, 'light.test', rgb_color=[255, 128, 0],
                               white_value=80)

    mqtt_mock.async_publish.assert_has_calls([
        mock.call(
            'test_light_rgb/set',
            JsonValidator(
                '{"state": "ON", "color": {"x": 0.14, "y": 0.131},'
                ' "brightness": 50}'),
            0, False),
        mock.call(
            'test_light_rgb/set',
            JsonValidator(
                '{"state": "ON", "color": {"x": 0.654, "y": 0.301},'
                ' "brightness": 50}'),
            0, False),
        mock.call(
            'test_light_rgb/set',
            JsonValidator(
                '{"state": "ON", "color": {"x": 0.611, "y": 0.375},'
                ' "white_value": 80}'),
            0, False),
    ], any_order=True)


async def test_flash_short_and_long(hass, mqtt_mock):
    """Test for flash length being sent when included."""
    assert await async_setup_component(hass, light.DOMAIN, {
        light.DOMAIN: {
            'platform': 'mqtt',
            'schema': 'json',
            'name': 'test',
            'command_topic': 'test_light_rgb/set',
            'flash_time_short': 5,
            'flash_time_long': 15,
            'qos': 0
        }
    })

    state = hass.states.get('light.test')
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 40

    await common.async_turn_on(hass, 'light.test', flash='short')

    mqtt_mock.async_publish.assert_called_once_with(
        'test_light_rgb/set', JsonValidator(
                '{"state": "ON", "flash": 5}'), 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get('light.test')
    assert state.state == STATE_ON

    await common.async_turn_on(hass, 'light.test', flash='long')

    mqtt_mock.async_publish.assert_called_once_with(
        'test_light_rgb/set', JsonValidator(
                '{"state": "ON", "flash": 15}'), 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get('light.test')
    assert state.state == STATE_ON


async def test_transition(hass, mqtt_mock):
    """Test for transition time being sent when included."""
    assert await async_setup_component(hass, light.DOMAIN, {
        light.DOMAIN: {
            'platform': 'mqtt',
            'schema': 'json',
            'name': 'test',
            'command_topic': 'test_light_rgb/set',
            'qos': 0
        }
    })

    state = hass.states.get('light.test')
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 40

    await common.async_turn_on(hass, 'light.test', transition=15)

    mqtt_mock.async_publish.assert_called_once_with(
        'test_light_rgb/set', JsonValidator(
                '{"state": "ON", "transition": 15}'), 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get('light.test')
    assert state.state == STATE_ON

    await common.async_turn_off(hass, 'light.test', transition=30)

    mqtt_mock.async_publish.assert_called_once_with(
        'test_light_rgb/set', JsonValidator(
                '{"state": "OFF", "transition": 30}'), 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get('light.test')
    assert state.state == STATE_OFF


async def test_brightness_scale(hass, mqtt_mock):
    """Test for brightness scaling."""
    assert await async_setup_component(hass, light.DOMAIN, {
        light.DOMAIN: {
            'platform': 'mqtt',
            'schema': 'json',
            'name': 'test',
            'state_topic': 'test_light_bright_scale',
            'command_topic': 'test_light_bright_scale/set',
            'brightness': True,
            'brightness_scale': 99
        }
    })

    state = hass.states.get('light.test')
    assert state.state == STATE_OFF
    assert state.attributes.get('brightness') is None
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Turn on the light
    async_fire_mqtt_message(hass, 'test_light_bright_scale', '{"state":"ON"}')

    state = hass.states.get('light.test')
    assert state.state == STATE_ON
    assert state.attributes.get('brightness') == 255

    # Turn on the light with brightness
    async_fire_mqtt_message(hass, 'test_light_bright_scale',
                            '{"state":"ON", "brightness": 99}')

    state = hass.states.get('light.test')
    assert state.state == STATE_ON
    assert state.attributes.get('brightness') == 255


async def test_invalid_color_brightness_and_white_values(hass, mqtt_mock):
    """Test that invalid color/brightness/white values are ignored."""
    assert await async_setup_component(hass, light.DOMAIN, {
        light.DOMAIN: {
            'platform': 'mqtt',
            'schema': 'json',
            'name': 'test',
            'state_topic': 'test_light_rgb',
            'command_topic': 'test_light_rgb/set',
            'brightness': True,
            'rgb': True,
            'white_value': True,
            'qos': '0'
        }
    })

    state = hass.states.get('light.test')
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 185
    assert state.attributes.get('rgb_color') is None
    assert state.attributes.get('brightness') is None
    assert state.attributes.get('white_value') is None
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Turn on the light
    async_fire_mqtt_message(hass, 'test_light_rgb',
                            '{"state":"ON",'
                            '"color":{"r":255,"g":255,"b":255},'
                            '"brightness": 255,'
                            '"white_value": 255}')

    state = hass.states.get('light.test')
    assert state.state == STATE_ON
    assert state.attributes.get('rgb_color') == (255, 255, 255)
    assert state.attributes.get('brightness') == 255
    assert state.attributes.get('white_value') == 255

    # Bad color values
    async_fire_mqtt_message(hass, 'test_light_rgb',
                            '{"state":"ON",'
                            '"color":{"r":"bad","g":"val","b":"test"}}')

    # Color should not have changed
    state = hass.states.get('light.test')
    assert state.state == STATE_ON
    assert state.attributes.get('rgb_color') == (255, 255, 255)

    # Bad brightness values
    async_fire_mqtt_message(hass, 'test_light_rgb',
                            '{"state":"ON",'
                            '"brightness": "badValue"}')

    # Brightness should not have changed
    state = hass.states.get('light.test')
    assert state.state == STATE_ON
    assert state.attributes.get('brightness') == 255

    # Bad white value
    async_fire_mqtt_message(hass, 'test_light_rgb',
                            '{"state":"ON",'
                            '"white_value": "badValue"}')

    # White value should not have changed
    state = hass.states.get('light.test')
    assert state.state == STATE_ON
    assert state.attributes.get('white_value') == 255


async def test_default_availability_payload(hass, mqtt_mock):
    """Test availability by default payload with defined topic."""
    assert await async_setup_component(hass, light.DOMAIN, {
        light.DOMAIN: {
            'platform': 'mqtt',
            'schema': 'json',
            'name': 'test',
            'state_topic': 'test_light_rgb',
            'command_topic': 'test_light_rgb/set',
            'availability_topic': 'availability-topic'
        }
    })

    state = hass.states.get('light.test')
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, 'availability-topic', 'online')

    state = hass.states.get('light.test')
    assert state.state != STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, 'availability-topic', 'offline')

    state = hass.states.get('light.test')
    assert state.state == STATE_UNAVAILABLE


async def test_custom_availability_payload(hass, mqtt_mock):
    """Test availability by custom payload with defined topic."""
    assert await async_setup_component(hass, light.DOMAIN, {
        light.DOMAIN: {
            'platform': 'mqtt',
            'schema': 'json',
            'name': 'test',
            'state_topic': 'test_light_rgb',
            'command_topic': 'test_light_rgb/set',
            'availability_topic': 'availability-topic',
            'payload_available': 'good',
            'payload_not_available': 'nogood'
        }
    })

    state = hass.states.get('light.test')
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, 'availability-topic', 'good')

    state = hass.states.get('light.test')
    assert state.state != STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, 'availability-topic', 'nogood')

    state = hass.states.get('light.test')
    assert state.state == STATE_UNAVAILABLE


async def test_setting_attribute_via_mqtt_json_message(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    assert await async_setup_component(hass, light.DOMAIN, {
        light.DOMAIN: {
            'platform': 'mqtt',
            'schema': 'json',
            'name': 'test',
            'command_topic': 'test-topic',
            'json_attributes_topic': 'attr-topic'
        }
    })

    async_fire_mqtt_message(hass, 'attr-topic', '{ "val": "100" }')
    state = hass.states.get('light.test')

    assert state.attributes.get('val') == '100'


async def test_update_with_json_attrs_not_dict(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    assert await async_setup_component(hass, light.DOMAIN, {
        light.DOMAIN: {
            'platform': 'mqtt',
            'schema': 'json',
            'name': 'test',
            'command_topic': 'test-topic',
            'json_attributes_topic': 'attr-topic'
        }
    })

    async_fire_mqtt_message(hass, 'attr-topic', '[ "list", "of", "things"]')
    state = hass.states.get('light.test')

    assert state.attributes.get('val') is None
    assert 'JSON result was not a dictionary' in caplog.text


async def test_update_with_json_attrs_bad_JSON(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    assert await async_setup_component(hass, light.DOMAIN, {
        light.DOMAIN: {
            'platform': 'mqtt',
            'schema': 'json',
            'name': 'test',
            'command_topic': 'test-topic',
            'json_attributes_topic': 'attr-topic'
        }
    })

    async_fire_mqtt_message(hass, 'attr-topic', 'This is not JSON')

    state = hass.states.get('light.test')
    assert state.attributes.get('val') is None
    assert 'Erroneous JSON: This is not JSON' in caplog.text


async def test_discovery_update_attr(hass, mqtt_mock, caplog):
    """Test update of discovered MQTTAttributes."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, 'homeassistant', {}, entry)
    data1 = (
        '{ "name": "Beer",'
        '  "schema": "json",'
        '  "command_topic": "test_topic",'
        '  "json_attributes_topic": "attr-topic1" }'
    )
    data2 = (
        '{ "name": "Beer",'
        '  "schema": "json",'
        '  "command_topic": "test_topic",'
        '  "json_attributes_topic": "attr-topic2" }'
    )
    async_fire_mqtt_message(hass, 'homeassistant/light/bla/config',
                            data1)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, 'attr-topic1', '{ "val": "100" }')
    state = hass.states.get('light.beer')
    assert state.attributes.get('val') == '100'

    # Change json_attributes_topic
    async_fire_mqtt_message(hass, 'homeassistant/light/bla/config',
                            data2)
    await hass.async_block_till_done()

    # Verify we are no longer subscribing to the old topic
    async_fire_mqtt_message(hass, 'attr-topic1', '{ "val": "50" }')
    state = hass.states.get('light.beer')
    assert state.attributes.get('val') == '100'

    # Verify we are subscribing to the new topic
    async_fire_mqtt_message(hass, 'attr-topic2', '{ "val": "75" }')
    state = hass.states.get('light.beer')
    assert state.attributes.get('val') == '75'


async def test_unique_id(hass):
    """Test unique id option only creates one light per unique_id."""
    await async_mock_mqtt_component(hass)
    assert await async_setup_component(hass, light.DOMAIN, {
        light.DOMAIN: [{
            'platform': 'mqtt',
            'name': 'Test 1',
            'schema': 'json',
            'state_topic': 'test-topic',
            'command_topic': 'test_topic',
            'unique_id': 'TOTALLY_UNIQUE'
        }, {
            'platform': 'mqtt',
            'name': 'Test 2',
            'schema': 'json',
            'state_topic': 'test-topic',
            'command_topic': 'test_topic',
            'unique_id': 'TOTALLY_UNIQUE'
        }]
    })
    async_fire_mqtt_message(hass, 'test-topic', 'payload')
    assert len(hass.states.async_entity_ids(light.DOMAIN)) == 1


async def test_discovery_removal(hass, mqtt_mock, caplog):
    """Test removal of discovered mqtt_json lights."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, 'homeassistant', {'mqtt': {}}, entry)
    data = (
        '{ "name": "Beer",'
        '  "schema": "json",'
        '  "command_topic": "test_topic" }'
    )
    async_fire_mqtt_message(hass, 'homeassistant/light/bla/config',
                            data)
    await hass.async_block_till_done()
    state = hass.states.get('light.beer')
    assert state is not None
    assert state.name == 'Beer'
    async_fire_mqtt_message(hass, 'homeassistant/light/bla/config',
                            '')
    await hass.async_block_till_done()
    state = hass.states.get('light.beer')
    assert state is None


async def test_discovery_deprecated(hass, mqtt_mock, caplog):
    """Test discovery of mqtt_json light with deprecated platform option."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, 'homeassistant', {'mqtt': {}}, entry)
    data = (
        '{ "name": "Beer",'
        '  "platform": "mqtt_json",'
        '  "command_topic": "test_topic"}'
    )
    async_fire_mqtt_message(hass, 'homeassistant/light/bla/config',
                            data)
    await hass.async_block_till_done()
    state = hass.states.get('light.beer')
    assert state is not None
    assert state.name == 'Beer'


async def test_discovery_update_light(hass, mqtt_mock, caplog):
    """Test update of discovered light."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, 'homeassistant', {}, entry)

    data1 = (
        '{ "name": "Beer",'
        '  "schema": "json",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )
    data2 = (
        '{ "name": "Milk",'
        '  "schema": "json",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )

    async_fire_mqtt_message(hass, 'homeassistant/light/bla/config',
                            data1)
    await hass.async_block_till_done()

    state = hass.states.get('light.beer')
    assert state is not None
    assert state.name == 'Beer'

    async_fire_mqtt_message(hass, 'homeassistant/light/bla/config',
                            data2)
    await hass.async_block_till_done()

    state = hass.states.get('light.beer')
    assert state is not None
    assert state.name == 'Milk'
    state = hass.states.get('light.milk')
    assert state is None


async def test_discovery_broken(hass, mqtt_mock, caplog):
    """Test handling of bad discovery message."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, 'homeassistant', {}, entry)

    data1 = (
        '{ "name": "Beer" }'
    )
    data2 = (
        '{ "name": "Milk",'
        '  "schema": "json",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )

    async_fire_mqtt_message(hass, 'homeassistant/light/bla/config',
                            data1)
    await hass.async_block_till_done()

    state = hass.states.get('light.beer')
    assert state is None

    async_fire_mqtt_message(hass, 'homeassistant/light/bla/config',
                            data2)
    await hass.async_block_till_done()

    state = hass.states.get('light.milk')
    assert state is not None
    assert state.name == 'Milk'
    state = hass.states.get('light.beer')
    assert state is None


async def test_entity_device_info_with_identifier(hass, mqtt_mock):
    """Test MQTT light device registry integration."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    entry.add_to_hass(hass)
    await async_start(hass, 'homeassistant', {}, entry)
    registry = await hass.helpers.device_registry.async_get_registry()

    data = json.dumps({
        'platform': 'mqtt',
        'name': 'Test 1',
        'schema': 'json',
        'state_topic': 'test-topic',
        'command_topic': 'test-topic',
        'device': {
            'identifiers': ['helloworld'],
            'connections': [
                ["mac", "02:5b:26:a8:dc:12"],
            ],
            'manufacturer': 'Whatever',
            'name': 'Beer',
            'model': 'Glass',
            'sw_version': '0.1-beta',
        },
        'unique_id': 'veryunique'
    })
    async_fire_mqtt_message(hass, 'homeassistant/light/bla/config',
                            data)
    await hass.async_block_till_done()

    device = registry.async_get_device({('mqtt', 'helloworld')}, set())
    assert device is not None
    assert device.identifiers == {('mqtt', 'helloworld')}
    assert device.connections == {('mac', "02:5b:26:a8:dc:12")}
    assert device.manufacturer == 'Whatever'
    assert device.name == 'Beer'
    assert device.model == 'Glass'
    assert device.sw_version == '0.1-beta'


async def test_entity_device_info_update(hass, mqtt_mock):
    """Test device registry update."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    entry.add_to_hass(hass)
    await async_start(hass, 'homeassistant', {}, entry)
    registry = await hass.helpers.device_registry.async_get_registry()

    config = {
        'platform': 'mqtt',
        'name': 'Test 1',
        'schema': 'json',
        'state_topic': 'test-topic',
        'command_topic': 'test-command-topic',
        'device': {
            'identifiers': ['helloworld'],
            'connections': [
                ["mac", "02:5b:26:a8:dc:12"],
            ],
            'manufacturer': 'Whatever',
            'name': 'Beer',
            'model': 'Glass',
            'sw_version': '0.1-beta',
        },
        'unique_id': 'veryunique'
    }

    data = json.dumps(config)
    async_fire_mqtt_message(hass, 'homeassistant/light/bla/config',
                            data)
    await hass.async_block_till_done()

    device = registry.async_get_device({('mqtt', 'helloworld')}, set())
    assert device is not None
    assert device.name == 'Beer'

    config['device']['name'] = 'Milk'
    data = json.dumps(config)
    async_fire_mqtt_message(hass, 'homeassistant/light/bla/config',
                            data)
    await hass.async_block_till_done()

    device = registry.async_get_device({('mqtt', 'helloworld')}, set())
    assert device is not None
    assert device.name == 'Milk'


async def test_entity_id_update(hass, mqtt_mock):
    """Test MQTT subscriptions are managed when entity_id is updated."""
    registry = mock_registry(hass, {})
    mock_mqtt = await async_mock_mqtt_component(hass)
    assert await async_setup_component(hass, light.DOMAIN, {
        light.DOMAIN: [{
            'platform': 'mqtt',
            'name': 'beer',
            'schema': 'json',
            'state_topic': 'test-topic',
            'command_topic': 'command-topic',
            'availability_topic': 'avty-topic',
            'unique_id': 'TOTALLY_UNIQUE'
        }]
    })

    state = hass.states.get('light.beer')
    assert state is not None
    assert mock_mqtt.async_subscribe.call_count == 2
    mock_mqtt.async_subscribe.assert_any_call('test-topic', ANY, 0, 'utf-8')
    mock_mqtt.async_subscribe.assert_any_call('avty-topic', ANY, 0, 'utf-8')
    mock_mqtt.async_subscribe.reset_mock()

    registry.async_update_entity('light.beer', new_entity_id='light.milk')
    await hass.async_block_till_done()

    state = hass.states.get('light.beer')
    assert state is None

    state = hass.states.get('light.milk')
    assert state is not None
    assert mock_mqtt.async_subscribe.call_count == 2
    mock_mqtt.async_subscribe.assert_any_call('test-topic', ANY, 0, 'utf-8')
    mock_mqtt.async_subscribe.assert_any_call('avty-topic', ANY, 0, 'utf-8')
