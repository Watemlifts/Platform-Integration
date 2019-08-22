"""The tests for the mqtt climate component."""
import copy
import json
import pytest
import unittest
from unittest.mock import ANY

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.components.climate import (
    DEFAULT_MAX_TEMP, DEFAULT_MIN_TEMP)
from homeassistant.components.climate.const import (
    DOMAIN as CLIMATE_DOMAIN,
    SUPPORT_AUX_HEAT, SUPPORT_AWAY_MODE,
    SUPPORT_FAN_MODE, SUPPORT_HOLD_MODE, SUPPORT_OPERATION_MODE,
    SUPPORT_SWING_MODE, SUPPORT_TARGET_TEMPERATURE, STATE_AUTO,
    STATE_COOL, STATE_HEAT, STATE_DRY, STATE_FAN_ONLY,
    SUPPORT_TARGET_TEMPERATURE_LOW, SUPPORT_TARGET_TEMPERATURE_HIGH)
from homeassistant.components.mqtt.discovery import async_start
from homeassistant.const import STATE_OFF, STATE_UNAVAILABLE

from tests.common import (
    MockConfigEntry, async_fire_mqtt_message, async_mock_mqtt_component,
    async_setup_component, mock_registry)
from tests.components.climate import common

ENTITY_CLIMATE = 'climate.test'

DEFAULT_CONFIG = {
    'climate': {
        'platform': 'mqtt',
        'name': 'test',
        'mode_command_topic': 'mode-topic',
        'temperature_command_topic': 'temperature-topic',
        'temperature_low_command_topic': 'temperature-low-topic',
        'temperature_high_command_topic': 'temperature-high-topic',
        'fan_mode_command_topic': 'fan-mode-topic',
        'swing_mode_command_topic': 'swing-mode-topic',
        'away_mode_command_topic': 'away-mode-topic',
        'hold_command_topic': 'hold-topic',
        'aux_command_topic': 'aux-topic'
    }}


async def test_setup_params(hass, mqtt_mock):
    """Test the initial parameters."""
    assert await async_setup_component(hass, CLIMATE_DOMAIN, DEFAULT_CONFIG)

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('temperature') == 21
    assert state.attributes.get('fan_mode') == 'low'
    assert state.attributes.get('swing_mode') == 'off'
    assert state.attributes.get('operation_mode') == 'off'
    assert state.attributes.get('min_temp') == DEFAULT_MIN_TEMP
    assert state.attributes.get('max_temp') == DEFAULT_MAX_TEMP


async def test_supported_features(hass, mqtt_mock):
    """Test the supported_features."""
    assert await async_setup_component(hass, CLIMATE_DOMAIN, DEFAULT_CONFIG)

    state = hass.states.get(ENTITY_CLIMATE)
    support = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE |
               SUPPORT_SWING_MODE | SUPPORT_FAN_MODE | SUPPORT_AWAY_MODE |
               SUPPORT_HOLD_MODE | SUPPORT_AUX_HEAT |
               SUPPORT_TARGET_TEMPERATURE_LOW |
               SUPPORT_TARGET_TEMPERATURE_HIGH)

    assert state.attributes.get("supported_features") == support


async def test_get_operation_modes(hass, mqtt_mock):
    """Test that the operation list returns the correct modes."""
    assert await async_setup_component(hass, CLIMATE_DOMAIN, DEFAULT_CONFIG)

    state = hass.states.get(ENTITY_CLIMATE)
    modes = state.attributes.get('operation_list')
    assert [
        STATE_AUTO, STATE_OFF, STATE_COOL,
        STATE_HEAT, STATE_DRY, STATE_FAN_ONLY
    ] == modes


async def test_set_operation_bad_attr_and_state(hass, mqtt_mock, caplog):
    """Test setting operation mode without required attribute.

    Also check the state.
    """
    assert await async_setup_component(hass, CLIMATE_DOMAIN, DEFAULT_CONFIG)

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('operation_mode') == 'off'
    assert state.state == 'off'
    with pytest.raises(vol.Invalid) as excinfo:
        await common.async_set_operation_mode(hass, None, ENTITY_CLIMATE)
    assert ("string value is None for dictionary value @ "
            "data['operation_mode']")\
        in str(excinfo.value)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('operation_mode') == 'off'
    assert state.state == 'off'


async def test_set_operation(hass, mqtt_mock):
    """Test setting of new operation mode."""
    assert await async_setup_component(hass, CLIMATE_DOMAIN, DEFAULT_CONFIG)

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('operation_mode') == 'off'
    assert state.state == 'off'
    await common.async_set_operation_mode(hass, 'cool', ENTITY_CLIMATE)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('operation_mode') == 'cool'
    assert state.state == 'cool'
    mqtt_mock.async_publish.assert_called_once_with(
        'mode-topic', 'cool', 0, False)


async def test_set_operation_pessimistic(hass, mqtt_mock):
    """Test setting operation mode in pessimistic mode."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config['climate']['mode_state_topic'] = 'mode-state'
    assert await async_setup_component(hass, CLIMATE_DOMAIN, config)

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('operation_mode') is None
    assert state.state == 'unknown'

    await common.async_set_operation_mode(hass, 'cool', ENTITY_CLIMATE)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('operation_mode') is None
    assert state.state == 'unknown'

    async_fire_mqtt_message(hass, 'mode-state', 'cool')
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('operation_mode') == 'cool'
    assert state.state == 'cool'

    async_fire_mqtt_message(hass, 'mode-state', 'bogus mode')
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('operation_mode') == 'cool'
    assert state.state == 'cool'


async def test_set_operation_with_power_command(hass, mqtt_mock):
    """Test setting of new operation mode with power command enabled."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config['climate']['power_command_topic'] = 'power-command'
    assert await async_setup_component(hass, CLIMATE_DOMAIN, config)

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('operation_mode') == 'off'
    assert state.state == 'off'
    await common.async_set_operation_mode(hass, 'on', ENTITY_CLIMATE)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('operation_mode') == 'on'
    assert state.state == 'on'
    mqtt_mock.async_publish.assert_has_calls([
        unittest.mock.call('power-command', 'ON', 0, False),
        unittest.mock.call('mode-topic', 'on', 0, False)
    ])
    mqtt_mock.async_publish.reset_mock()

    await common.async_set_operation_mode(hass, 'off', ENTITY_CLIMATE)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('operation_mode') == 'off'
    assert state.state == 'off'
    mqtt_mock.async_publish.assert_has_calls([
        unittest.mock.call('power-command', 'OFF', 0, False),
        unittest.mock.call('mode-topic', 'off', 0, False)
    ])
    mqtt_mock.async_publish.reset_mock()


async def test_set_fan_mode_bad_attr(hass, mqtt_mock, caplog):
    """Test setting fan mode without required attribute."""
    assert await async_setup_component(hass, CLIMATE_DOMAIN, DEFAULT_CONFIG)

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('fan_mode') == 'low'
    with pytest.raises(vol.Invalid) as excinfo:
        await common.async_set_fan_mode(hass, None, ENTITY_CLIMATE)
    assert "string value is None for dictionary value @ data['fan_mode']"\
        in str(excinfo.value)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('fan_mode') == 'low'


async def test_set_fan_mode_pessimistic(hass, mqtt_mock):
    """Test setting of new fan mode in pessimistic mode."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config['climate']['fan_mode_state_topic'] = 'fan-state'
    assert await async_setup_component(hass, CLIMATE_DOMAIN, config)

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('fan_mode') is None

    await common.async_set_fan_mode(hass, 'high', ENTITY_CLIMATE)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('fan_mode') is None

    async_fire_mqtt_message(hass, 'fan-state', 'high')
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('fan_mode') == 'high'

    async_fire_mqtt_message(hass, 'fan-state', 'bogus mode')
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('fan_mode') == 'high'


async def test_set_fan_mode(hass, mqtt_mock):
    """Test setting of new fan mode."""
    assert await async_setup_component(hass, CLIMATE_DOMAIN, DEFAULT_CONFIG)

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('fan_mode') == 'low'
    await common.async_set_fan_mode(hass, 'high', ENTITY_CLIMATE)
    mqtt_mock.async_publish.assert_called_once_with(
        'fan-mode-topic', 'high', 0, False)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('fan_mode') == 'high'


async def test_set_swing_mode_bad_attr(hass, mqtt_mock, caplog):
    """Test setting swing mode without required attribute."""
    assert await async_setup_component(hass, CLIMATE_DOMAIN, DEFAULT_CONFIG)

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('swing_mode') == 'off'
    with pytest.raises(vol.Invalid) as excinfo:
        await common.async_set_swing_mode(hass, None, ENTITY_CLIMATE)
    assert "string value is None for dictionary value @ data['swing_mode']"\
        in str(excinfo.value)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('swing_mode') == 'off'


async def test_set_swing_pessimistic(hass, mqtt_mock):
    """Test setting swing mode in pessimistic mode."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config['climate']['swing_mode_state_topic'] = 'swing-state'
    assert await async_setup_component(hass, CLIMATE_DOMAIN, config)

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('swing_mode') is None

    await common.async_set_swing_mode(hass, 'on', ENTITY_CLIMATE)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('swing_mode') is None

    async_fire_mqtt_message(hass, 'swing-state', 'on')
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('swing_mode') == 'on'

    async_fire_mqtt_message(hass, 'swing-state', 'bogus state')
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('swing_mode') == 'on'


async def test_set_swing(hass, mqtt_mock):
    """Test setting of new swing mode."""
    assert await async_setup_component(hass, CLIMATE_DOMAIN, DEFAULT_CONFIG)

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('swing_mode') == 'off'
    await common.async_set_swing_mode(hass, 'on', ENTITY_CLIMATE)
    mqtt_mock.async_publish.assert_called_once_with(
        'swing-mode-topic', 'on', 0, False)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('swing_mode') == 'on'


async def test_set_target_temperature(hass, mqtt_mock):
    """Test setting the target temperature."""
    assert await async_setup_component(hass, CLIMATE_DOMAIN, DEFAULT_CONFIG)

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('temperature') == 21
    await common.async_set_operation_mode(hass, 'heat', ENTITY_CLIMATE)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('operation_mode') == 'heat'
    mqtt_mock.async_publish.assert_called_once_with(
        'mode-topic', 'heat', 0, False)
    mqtt_mock.async_publish.reset_mock()
    await common.async_set_temperature(hass, temperature=47,
                                       entity_id=ENTITY_CLIMATE)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('temperature') == 47
    mqtt_mock.async_publish.assert_called_once_with(
        'temperature-topic', 47, 0, False)

    # also test directly supplying the operation mode to set_temperature
    mqtt_mock.async_publish.reset_mock()
    await common.async_set_temperature(hass, temperature=21,
                                       operation_mode='cool',
                                       entity_id=ENTITY_CLIMATE)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('operation_mode') == 'cool'
    assert state.attributes.get('temperature') == 21
    mqtt_mock.async_publish.assert_has_calls([
        unittest.mock.call('mode-topic', 'cool', 0, False),
        unittest.mock.call('temperature-topic', 21, 0, False)
    ])
    mqtt_mock.async_publish.reset_mock()


async def test_set_target_temperature_pessimistic(hass, mqtt_mock):
    """Test setting the target temperature."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config['climate']['temperature_state_topic'] = 'temperature-state'
    assert await async_setup_component(hass, CLIMATE_DOMAIN, config)

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('temperature') is None
    await common.async_set_operation_mode(hass, 'heat', ENTITY_CLIMATE)
    await common.async_set_temperature(hass, temperature=47,
                                       entity_id=ENTITY_CLIMATE)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('temperature') is None

    async_fire_mqtt_message(hass, 'temperature-state', '1701')
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('temperature') == 1701

    async_fire_mqtt_message(hass, 'temperature-state', 'not a number')
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('temperature') == 1701


async def test_set_target_temperature_low_high(hass, mqtt_mock):
    """Test setting the low/high target temperature."""
    assert await async_setup_component(hass, CLIMATE_DOMAIN, DEFAULT_CONFIG)

    await common.async_set_temperature(hass, target_temp_low=20,
                                       target_temp_high=23,
                                       entity_id=ENTITY_CLIMATE)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('target_temp_low') == 20
    assert state.attributes.get('target_temp_high') == 23
    mqtt_mock.async_publish.assert_any_call(
        'temperature-low-topic', 20, 0, False)
    mqtt_mock.async_publish.assert_any_call(
        'temperature-high-topic', 23, 0, False)


async def test_set_target_temperature_low_highpessimistic(hass, mqtt_mock):
    """Test setting the low/high target temperature."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config['climate']['temperature_low_state_topic'] = \
        'temperature-low-state'
    config['climate']['temperature_high_state_topic'] = \
        'temperature-high-state'
    assert await async_setup_component(hass, CLIMATE_DOMAIN, config)

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('target_temp_low') is None
    assert state.attributes.get('target_temp_high') is None
    await common.async_set_temperature(hass, target_temp_low=20,
                                       target_temp_high=23,
                                       entity_id=ENTITY_CLIMATE)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('target_temp_low') is None
    assert state.attributes.get('target_temp_high') is None

    async_fire_mqtt_message(hass, 'temperature-low-state', '1701')
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('target_temp_low') == 1701
    assert state.attributes.get('target_temp_high') is None

    async_fire_mqtt_message(hass, 'temperature-high-state', '1703')
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('target_temp_low') == 1701
    assert state.attributes.get('target_temp_high') == 1703

    async_fire_mqtt_message(hass, 'temperature-low-state', 'not a number')
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('target_temp_low') == 1701

    async_fire_mqtt_message(hass, 'temperature-high-state', 'not a number')
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('target_temp_high') == 1703


async def test_receive_mqtt_temperature(hass, mqtt_mock):
    """Test getting the current temperature via MQTT."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config['climate']['current_temperature_topic'] = 'current_temperature'
    assert await async_setup_component(hass, CLIMATE_DOMAIN, config)

    async_fire_mqtt_message(hass, 'current_temperature', '47')
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('current_temperature') == 47


async def test_set_away_mode_pessimistic(hass, mqtt_mock):
    """Test setting of the away mode."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config['climate']['away_mode_state_topic'] = 'away-state'
    assert await async_setup_component(hass, CLIMATE_DOMAIN, config)

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('away_mode') == 'off'

    await common.async_set_away_mode(hass, True, ENTITY_CLIMATE)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('away_mode') == 'off'

    async_fire_mqtt_message(hass, 'away-state', 'ON')
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('away_mode') == 'on'

    async_fire_mqtt_message(hass, 'away-state', 'OFF')
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('away_mode') == 'off'

    async_fire_mqtt_message(hass, 'away-state', 'nonsense')
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('away_mode') == 'off'


async def test_set_away_mode(hass, mqtt_mock):
    """Test setting of the away mode."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config['climate']['payload_on'] = 'AN'
    config['climate']['payload_off'] = 'AUS'

    assert await async_setup_component(hass, CLIMATE_DOMAIN, config)

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('away_mode') == 'off'
    await common.async_set_away_mode(hass, True, ENTITY_CLIMATE)
    mqtt_mock.async_publish.assert_called_once_with(
        'away-mode-topic', 'AN', 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('away_mode') == 'on'

    await common.async_set_away_mode(hass, False, ENTITY_CLIMATE)
    mqtt_mock.async_publish.assert_called_once_with(
        'away-mode-topic', 'AUS', 0, False)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('away_mode') == 'off'


async def test_set_hold_pessimistic(hass, mqtt_mock):
    """Test setting the hold mode in pessimistic mode."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config['climate']['hold_state_topic'] = 'hold-state'
    assert await async_setup_component(hass, CLIMATE_DOMAIN, config)

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('hold_mode') is None

    await common.async_set_hold_mode(hass, 'on', ENTITY_CLIMATE)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('hold_mode') is None

    async_fire_mqtt_message(hass, 'hold-state', 'on')
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('hold_mode') == 'on'

    async_fire_mqtt_message(hass, 'hold-state', 'off')
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('hold_mode') == 'off'


async def test_set_hold(hass, mqtt_mock):
    """Test setting the hold mode."""
    assert await async_setup_component(hass, CLIMATE_DOMAIN, DEFAULT_CONFIG)

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('hold_mode') is None
    await common.async_set_hold_mode(hass, 'on', ENTITY_CLIMATE)
    mqtt_mock.async_publish.assert_called_once_with(
        'hold-topic', 'on', 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('hold_mode') == 'on'

    await common.async_set_hold_mode(hass, 'off', ENTITY_CLIMATE)
    mqtt_mock.async_publish.assert_called_once_with(
        'hold-topic', 'off', 0, False)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('hold_mode') == 'off'


async def test_set_aux_pessimistic(hass, mqtt_mock):
    """Test setting of the aux heating in pessimistic mode."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config['climate']['aux_state_topic'] = 'aux-state'
    assert await async_setup_component(hass, CLIMATE_DOMAIN, config)

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('aux_heat') == 'off'

    await common.async_set_aux_heat(hass, True, ENTITY_CLIMATE)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('aux_heat') == 'off'

    async_fire_mqtt_message(hass, 'aux-state', 'ON')
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('aux_heat') == 'on'

    async_fire_mqtt_message(hass, 'aux-state', 'OFF')
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('aux_heat') == 'off'

    async_fire_mqtt_message(hass, 'aux-state', 'nonsense')
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('aux_heat') == 'off'


async def test_set_aux(hass, mqtt_mock):
    """Test setting of the aux heating."""
    assert await async_setup_component(hass, CLIMATE_DOMAIN, DEFAULT_CONFIG)

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('aux_heat') == 'off'
    await common.async_set_aux_heat(hass, True, ENTITY_CLIMATE)
    mqtt_mock.async_publish.assert_called_once_with(
        'aux-topic', 'ON', 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('aux_heat') == 'on'

    await common.async_set_aux_heat(hass, False, ENTITY_CLIMATE)
    mqtt_mock.async_publish.assert_called_once_with(
        'aux-topic', 'OFF', 0, False)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('aux_heat') == 'off'


async def test_custom_availability_payload(hass, mqtt_mock):
    """Test availability by custom payload with defined topic."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config['climate']['availability_topic'] = 'availability-topic'
    config['climate']['payload_available'] = 'good'
    config['climate']['payload_not_available'] = 'nogood'

    assert await async_setup_component(hass, CLIMATE_DOMAIN, config)

    state = hass.states.get('climate.test')
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, 'availability-topic', 'good')

    state = hass.states.get('climate.test')
    assert state.state != STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, 'availability-topic', 'nogood')

    state = hass.states.get('climate.test')
    assert state.state == STATE_UNAVAILABLE


async def test_set_with_templates(hass, mqtt_mock, caplog):
    """Test setting of new fan mode in pessimistic mode."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    # By default, just unquote the JSON-strings
    config['climate']['value_template'] = '{{ value_json }}'
    # Something more complicated for hold mode
    config['climate']['hold_state_template'] = \
        '{{ value_json.attribute }}'
    # Rendering to a bool for aux heat
    config['climate']['aux_state_template'] = \
        "{{ value == 'switchmeon' }}"

    config['climate']['mode_state_topic'] = 'mode-state'
    config['climate']['fan_mode_state_topic'] = 'fan-state'
    config['climate']['swing_mode_state_topic'] = 'swing-state'
    config['climate']['temperature_state_topic'] = 'temperature-state'
    config['climate']['away_mode_state_topic'] = 'away-state'
    config['climate']['hold_state_topic'] = 'hold-state'
    config['climate']['aux_state_topic'] = 'aux-state'
    config['climate']['current_temperature_topic'] = 'current-temperature'

    assert await async_setup_component(hass, CLIMATE_DOMAIN, config)

    # Operation Mode
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('operation_mode') is None
    async_fire_mqtt_message(hass, 'mode-state', '"cool"')
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('operation_mode') == 'cool'

    # Fan Mode
    assert state.attributes.get('fan_mode') is None
    async_fire_mqtt_message(hass, 'fan-state', '"high"')
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('fan_mode') == 'high'

    # Swing Mode
    assert state.attributes.get('swing_mode') is None
    async_fire_mqtt_message(hass, 'swing-state', '"on"')
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('swing_mode') == 'on'

    # Temperature - with valid value
    assert state.attributes.get('temperature') is None
    async_fire_mqtt_message(hass, 'temperature-state', '"1031"')
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('temperature') == 1031

    # Temperature - with invalid value
    async_fire_mqtt_message(hass, 'temperature-state', '"-INVALID-"')
    state = hass.states.get(ENTITY_CLIMATE)
    # make sure, the invalid value gets logged...
    assert "Could not parse temperature from -INVALID-" in caplog.text
    # ... but the actual value stays unchanged.
    assert state.attributes.get('temperature') == 1031

    # Away Mode
    assert state.attributes.get('away_mode') == 'off'
    async_fire_mqtt_message(hass, 'away-state', '"ON"')
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('away_mode') == 'on'

    # Away Mode with JSON values
    async_fire_mqtt_message(hass, 'away-state', 'false')
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('away_mode') == 'off'

    async_fire_mqtt_message(hass, 'away-state', 'true')
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('away_mode') == 'on'

    # Hold Mode
    assert state.attributes.get('hold_mode') is None
    async_fire_mqtt_message(hass, 'hold-state', """
        { "attribute": "somemode" }
    """)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('hold_mode') == 'somemode'

    # Aux mode
    assert state.attributes.get('aux_heat') == 'off'
    async_fire_mqtt_message(hass, 'aux-state', 'switchmeon')
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('aux_heat') == 'on'

    # anything other than 'switchmeon' should turn Aux mode off
    async_fire_mqtt_message(hass, 'aux-state', 'somerandomstring')
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('aux_heat') == 'off'

    # Current temperature
    async_fire_mqtt_message(hass, 'current-temperature', '"74656"')
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get('current_temperature') == 74656


async def test_min_temp_custom(hass, mqtt_mock):
    """Test a custom min temp."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config['climate']['min_temp'] = 26

    assert await async_setup_component(hass, CLIMATE_DOMAIN, config)

    state = hass.states.get(ENTITY_CLIMATE)
    min_temp = state.attributes.get('min_temp')

    assert isinstance(min_temp, float)
    assert state.attributes.get('min_temp') == 26


async def test_max_temp_custom(hass, mqtt_mock):
    """Test a custom max temp."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config['climate']['max_temp'] = 60

    assert await async_setup_component(hass, CLIMATE_DOMAIN, config)

    state = hass.states.get(ENTITY_CLIMATE)
    max_temp = state.attributes.get('max_temp')

    assert isinstance(max_temp, float)
    assert max_temp == 60


async def test_temp_step_custom(hass, mqtt_mock):
    """Test a custom temp step."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config['climate']['temp_step'] = 0.01

    assert await async_setup_component(hass, CLIMATE_DOMAIN, config)

    state = hass.states.get(ENTITY_CLIMATE)
    temp_step = state.attributes.get('target_temp_step')

    assert isinstance(temp_step, float)
    assert temp_step == 0.01


async def test_setting_attribute_via_mqtt_json_message(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    assert await async_setup_component(hass, CLIMATE_DOMAIN, {
        CLIMATE_DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'power_state_topic': 'test-topic',
            'power_command_topic': 'test_topic',
            'json_attributes_topic': 'attr-topic'
        }
    })

    async_fire_mqtt_message(hass, 'attr-topic', '{ "val": "100" }')
    state = hass.states.get('climate.test')

    assert state.attributes.get('val') == '100'


async def test_update_with_json_attrs_not_dict(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    assert await async_setup_component(hass, CLIMATE_DOMAIN, {
        CLIMATE_DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'power_state_topic': 'test-topic',
            'power_command_topic': 'test_topic',
            'json_attributes_topic': 'attr-topic'
        }
    })

    async_fire_mqtt_message(hass, 'attr-topic', '[ "list", "of", "things"]')
    state = hass.states.get('climate.test')

    assert state.attributes.get('val') is None
    assert 'JSON result was not a dictionary' in caplog.text


async def test_update_with_json_attrs_bad_JSON(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    assert await async_setup_component(hass, CLIMATE_DOMAIN, {
        CLIMATE_DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'power_state_topic': 'test-topic',
            'power_command_topic': 'test_topic',
            'json_attributes_topic': 'attr-topic'
        }
    })

    async_fire_mqtt_message(hass, 'attr-topic', 'This is not JSON')

    state = hass.states.get('climate.test')
    assert state.attributes.get('val') is None
    assert 'Erroneous JSON: This is not JSON' in caplog.text


async def test_discovery_update_attr(hass, mqtt_mock, caplog):
    """Test update of discovered MQTTAttributes."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, 'homeassistant', {}, entry)
    data1 = (
        '{ "name": "Beer",'
        '  "power_state_topic": "test-topic",'
        '  "power_command_topic": "test_topic",'
        '  "json_attributes_topic": "attr-topic1" }'
    )
    data2 = (
        '{ "name": "Beer",'
        '  "power_state_topic": "test-topic",'
        '  "power_command_topic": "test_topic",'
        '  "json_attributes_topic": "attr-topic2" }'
    )
    async_fire_mqtt_message(hass, 'homeassistant/climate/bla/config',
                            data1)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, 'attr-topic1', '{ "val": "100" }')
    state = hass.states.get('climate.beer')
    assert state.attributes.get('val') == '100'

    # Change json_attributes_topic
    async_fire_mqtt_message(hass, 'homeassistant/climate/bla/config',
                            data2)
    await hass.async_block_till_done()

    # Verify we are no longer subscribing to the old topic
    async_fire_mqtt_message(hass, 'attr-topic1', '{ "val": "50" }')
    state = hass.states.get('climate.beer')
    assert state.attributes.get('val') == '100'

    # Verify we are subscribing to the new topic
    async_fire_mqtt_message(hass, 'attr-topic2', '{ "val": "75" }')
    state = hass.states.get('climate.beer')
    assert state.attributes.get('val') == '75'


async def test_unique_id(hass):
    """Test unique id option only creates one climate per unique_id."""
    await async_mock_mqtt_component(hass)
    assert await async_setup_component(hass, CLIMATE_DOMAIN, {
        CLIMATE_DOMAIN: [{
            'platform': 'mqtt',
            'name': 'Test 1',
            'power_state_topic': 'test-topic',
            'power_command_topic': 'test_topic',
            'unique_id': 'TOTALLY_UNIQUE'
        }, {
            'platform': 'mqtt',
            'name': 'Test 2',
            'power_state_topic': 'test-topic',
            'power_command_topic': 'test_topic',
            'unique_id': 'TOTALLY_UNIQUE'
        }]
    })
    async_fire_mqtt_message(hass, 'test-topic', 'payload')
    assert len(hass.states.async_entity_ids(CLIMATE_DOMAIN)) == 1


async def test_discovery_removal_climate(hass, mqtt_mock, caplog):
    """Test removal of discovered climate."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, 'homeassistant', {}, entry)
    data = (
        '{ "name": "Beer" }'
    )
    async_fire_mqtt_message(hass, 'homeassistant/climate/bla/config',
                            data)
    await hass.async_block_till_done()
    state = hass.states.get('climate.beer')
    assert state is not None
    assert state.name == 'Beer'
    async_fire_mqtt_message(hass, 'homeassistant/climate/bla/config',
                            '')
    await hass.async_block_till_done()
    state = hass.states.get('climate.beer')
    assert state is None


async def test_discovery_update_climate(hass, mqtt_mock, caplog):
    """Test update of discovered climate."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, 'homeassistant', {}, entry)
    data1 = (
        '{ "name": "Beer" }'
    )
    data2 = (
        '{ "name": "Milk" }'
    )
    async_fire_mqtt_message(hass, 'homeassistant/climate/bla/config',
                            data1)
    await hass.async_block_till_done()

    state = hass.states.get('climate.beer')
    assert state is not None
    assert state.name == 'Beer'

    async_fire_mqtt_message(hass, 'homeassistant/climate/bla/config',
                            data2)
    await hass.async_block_till_done()

    state = hass.states.get('climate.beer')
    assert state is not None
    assert state.name == 'Milk'

    state = hass.states.get('climate.milk')
    assert state is None


async def test_discovery_broken(hass, mqtt_mock, caplog):
    """Test handling of bad discovery message."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, 'homeassistant', {}, entry)

    data1 = (
        '{ "name": "Beer",'
        '  "power_command_topic": "test_topic#" }'
    )
    data2 = (
        '{ "name": "Milk", '
        '  "power_command_topic": "test_topic" }'
    )

    async_fire_mqtt_message(hass, 'homeassistant/climate/bla/config',
                            data1)
    await hass.async_block_till_done()

    state = hass.states.get('climate.beer')
    assert state is None

    async_fire_mqtt_message(hass, 'homeassistant/climate/bla/config',
                            data2)
    await hass.async_block_till_done()

    state = hass.states.get('climate.milk')
    assert state is not None
    assert state.name == 'Milk'
    state = hass.states.get('climate.beer')
    assert state is None


async def test_entity_device_info_with_identifier(hass, mqtt_mock):
    """Test MQTT climate device registry integration."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    entry.add_to_hass(hass)
    await async_start(hass, 'homeassistant', {}, entry)
    registry = await hass.helpers.device_registry.async_get_registry()

    data = json.dumps({
        'platform': 'mqtt',
        'name': 'Test 1',
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
    async_fire_mqtt_message(hass, 'homeassistant/climate/bla/config',
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
        'power_state_topic': 'test-topic',
        'power_command_topic': 'test-command-topic',
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
    async_fire_mqtt_message(hass, 'homeassistant/climate/bla/config',
                            data)
    await hass.async_block_till_done()

    device = registry.async_get_device({('mqtt', 'helloworld')}, set())
    assert device is not None
    assert device.name == 'Beer'

    config['device']['name'] = 'Milk'
    data = json.dumps(config)
    async_fire_mqtt_message(hass, 'homeassistant/climate/bla/config',
                            data)
    await hass.async_block_till_done()

    device = registry.async_get_device({('mqtt', 'helloworld')}, set())
    assert device is not None
    assert device.name == 'Milk'


async def test_entity_id_update(hass, mqtt_mock):
    """Test MQTT subscriptions are managed when entity_id is updated."""
    registry = mock_registry(hass, {})
    mock_mqtt = await async_mock_mqtt_component(hass)
    assert await async_setup_component(hass, CLIMATE_DOMAIN, {
        CLIMATE_DOMAIN: [{
            'platform': 'mqtt',
            'name': 'beer',
            'mode_state_topic': 'test-topic',
            'availability_topic': 'avty-topic',
            'unique_id': 'TOTALLY_UNIQUE'
        }]
    })

    state = hass.states.get('climate.beer')
    assert state is not None
    assert mock_mqtt.async_subscribe.call_count == 2
    mock_mqtt.async_subscribe.assert_any_call('test-topic', ANY, 0, 'utf-8')
    mock_mqtt.async_subscribe.assert_any_call('avty-topic', ANY, 0, 'utf-8')
    mock_mqtt.async_subscribe.reset_mock()

    registry.async_update_entity('climate.beer', new_entity_id='climate.milk')
    await hass.async_block_till_done()

    state = hass.states.get('climate.beer')
    assert state is None

    state = hass.states.get('climate.milk')
    assert state is not None
    assert mock_mqtt.async_subscribe.call_count == 2
    mock_mqtt.async_subscribe.assert_any_call('test-topic', ANY, 0, 'utf-8')
    mock_mqtt.async_subscribe.assert_any_call('avty-topic', ANY, 0, 'utf-8')
