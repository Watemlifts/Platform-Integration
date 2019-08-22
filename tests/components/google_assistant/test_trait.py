"""Tests for the Google Assistant traits."""
from unittest.mock import patch, Mock

import pytest

from homeassistant.components import (
    binary_sensor,
    camera,
    cover,
    fan,
    input_boolean,
    light,
    lock,
    media_player,
    scene,
    script,
    sensor,
    switch,
    vacuum,
    group,
)
from homeassistant.components.climate import const as climate
from homeassistant.components.google_assistant import (
    trait, helpers, const, error)
from homeassistant.const import (
    STATE_ON, STATE_OFF, ATTR_ENTITY_ID, SERVICE_TURN_ON, SERVICE_TURN_OFF,
    TEMP_CELSIUS, TEMP_FAHRENHEIT, ATTR_SUPPORTED_FEATURES, ATTR_TEMPERATURE,
    ATTR_DEVICE_CLASS, ATTR_ASSUMED_STATE, STATE_UNKNOWN)
from homeassistant.core import State, DOMAIN as HA_DOMAIN, EVENT_CALL_SERVICE
from homeassistant.util import color
from tests.common import async_mock_service, mock_coro
from . import BASIC_CONFIG, MockConfig


REQ_ID = 'ff36a3cc-ec34-11e6-b1a0-64510650abcf'

BASIC_DATA = helpers.RequestData(
    BASIC_CONFIG,
    'test-agent',
    REQ_ID,
)

PIN_CONFIG = MockConfig(
    secure_devices_pin='1234'
)

PIN_DATA = helpers.RequestData(
    PIN_CONFIG,
    'test-agent',
    REQ_ID,
)


async def test_brightness_light(hass):
    """Test brightness trait support for light domain."""
    assert helpers.get_google_type(light.DOMAIN, None) is not None
    assert trait.BrightnessTrait.supported(light.DOMAIN,
                                           light.SUPPORT_BRIGHTNESS, None)

    trt = trait.BrightnessTrait(hass, State('light.bla', light.STATE_ON, {
        light.ATTR_BRIGHTNESS: 243
    }), BASIC_CONFIG)

    assert trt.sync_attributes() == {}

    assert trt.query_attributes() == {
        'brightness': 95
    }

    events = []
    hass.bus.async_listen(EVENT_CALL_SERVICE, events.append)

    calls = async_mock_service(hass, light.DOMAIN, light.SERVICE_TURN_ON)
    await trt.execute(
        trait.COMMAND_BRIGHTNESS_ABSOLUTE, BASIC_DATA,
        {'brightness': 50}, {})
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: 'light.bla',
        light.ATTR_BRIGHTNESS_PCT: 50
    }

    assert len(events) == 1
    assert events[0].data == {
        'domain': 'light',
        'service': 'turn_on',
        'service_data': {'brightness_pct': 50, 'entity_id': 'light.bla'}
    }


async def test_camera_stream(hass):
    """Test camera stream trait support for camera domain."""
    hass.config.api = Mock(base_url='http://1.1.1.1:8123')
    assert helpers.get_google_type(camera.DOMAIN, None) is not None
    assert trait.CameraStreamTrait.supported(camera.DOMAIN,
                                             camera.SUPPORT_STREAM, None)

    trt = trait.CameraStreamTrait(
        hass, State('camera.bla', camera.STATE_IDLE, {}), BASIC_CONFIG
    )

    assert trt.sync_attributes() == {
        'cameraStreamSupportedProtocols': [
            "hls",
        ],
        'cameraStreamNeedAuthToken': False,
        'cameraStreamNeedDrmEncryption': False,
    }

    assert trt.query_attributes() == {}

    with patch('homeassistant.components.camera.async_request_stream',
               return_value=mock_coro('/api/streams/bla')):
        await trt.execute(trait.COMMAND_GET_CAMERA_STREAM, BASIC_DATA, {}, {})

    assert trt.query_attributes() == {
        'cameraStreamAccessUrl': 'http://1.1.1.1:8123/api/streams/bla'
    }


async def test_onoff_group(hass):
    """Test OnOff trait support for group domain."""
    assert helpers.get_google_type(group.DOMAIN, None) is not None
    assert trait.OnOffTrait.supported(group.DOMAIN, 0, None)

    trt_on = trait.OnOffTrait(hass, State('group.bla', STATE_ON), BASIC_CONFIG)

    assert trt_on.sync_attributes() == {}

    assert trt_on.query_attributes() == {
        'on': True
    }

    trt_off = trait.OnOffTrait(hass, State('group.bla', STATE_OFF),
                               BASIC_CONFIG)

    assert trt_off.query_attributes() == {
        'on': False
    }

    on_calls = async_mock_service(hass, HA_DOMAIN, SERVICE_TURN_ON)
    await trt_on.execute(
        trait.COMMAND_ONOFF, BASIC_DATA,
        {'on': True}, {})
    assert len(on_calls) == 1
    assert on_calls[0].data == {
        ATTR_ENTITY_ID: 'group.bla',
    }

    off_calls = async_mock_service(hass, HA_DOMAIN, SERVICE_TURN_OFF)
    await trt_on.execute(
        trait.COMMAND_ONOFF, BASIC_DATA,
        {'on': False}, {})
    assert len(off_calls) == 1
    assert off_calls[0].data == {
        ATTR_ENTITY_ID: 'group.bla',
    }


async def test_onoff_input_boolean(hass):
    """Test OnOff trait support for input_boolean domain."""
    assert helpers.get_google_type(input_boolean.DOMAIN, None) is not None
    assert trait.OnOffTrait.supported(input_boolean.DOMAIN, 0, None)

    trt_on = trait.OnOffTrait(hass, State('input_boolean.bla', STATE_ON),
                              BASIC_CONFIG)

    assert trt_on.sync_attributes() == {}

    assert trt_on.query_attributes() == {
        'on': True
    }

    trt_off = trait.OnOffTrait(hass, State('input_boolean.bla', STATE_OFF),
                               BASIC_CONFIG)

    assert trt_off.query_attributes() == {
        'on': False
    }

    on_calls = async_mock_service(hass, input_boolean.DOMAIN, SERVICE_TURN_ON)
    await trt_on.execute(
        trait.COMMAND_ONOFF, BASIC_DATA,
        {'on': True}, {})
    assert len(on_calls) == 1
    assert on_calls[0].data == {
        ATTR_ENTITY_ID: 'input_boolean.bla',
    }

    off_calls = async_mock_service(hass, input_boolean.DOMAIN,
                                   SERVICE_TURN_OFF)
    await trt_on.execute(
        trait.COMMAND_ONOFF, BASIC_DATA,
        {'on': False}, {})
    assert len(off_calls) == 1
    assert off_calls[0].data == {
        ATTR_ENTITY_ID: 'input_boolean.bla',
    }


async def test_onoff_switch(hass):
    """Test OnOff trait support for switch domain."""
    assert helpers.get_google_type(switch.DOMAIN, None) is not None
    assert trait.OnOffTrait.supported(switch.DOMAIN, 0, None)

    trt_on = trait.OnOffTrait(hass, State('switch.bla', STATE_ON),
                              BASIC_CONFIG)

    assert trt_on.sync_attributes() == {}

    assert trt_on.query_attributes() == {
        'on': True
    }

    trt_off = trait.OnOffTrait(hass, State('switch.bla', STATE_OFF),
                               BASIC_CONFIG)

    assert trt_off.query_attributes() == {
        'on': False
    }

    on_calls = async_mock_service(hass, switch.DOMAIN, SERVICE_TURN_ON)
    await trt_on.execute(
        trait.COMMAND_ONOFF, BASIC_DATA,
        {'on': True}, {})
    assert len(on_calls) == 1
    assert on_calls[0].data == {
        ATTR_ENTITY_ID: 'switch.bla',
    }

    off_calls = async_mock_service(hass, switch.DOMAIN, SERVICE_TURN_OFF)
    await trt_on.execute(
        trait.COMMAND_ONOFF, BASIC_DATA,
        {'on': False}, {})
    assert len(off_calls) == 1
    assert off_calls[0].data == {
        ATTR_ENTITY_ID: 'switch.bla',
    }


async def test_onoff_fan(hass):
    """Test OnOff trait support for fan domain."""
    assert helpers.get_google_type(fan.DOMAIN, None) is not None
    assert trait.OnOffTrait.supported(fan.DOMAIN, 0, None)

    trt_on = trait.OnOffTrait(hass, State('fan.bla', STATE_ON), BASIC_CONFIG)

    assert trt_on.sync_attributes() == {}

    assert trt_on.query_attributes() == {
        'on': True
    }

    trt_off = trait.OnOffTrait(hass, State('fan.bla', STATE_OFF), BASIC_CONFIG)
    assert trt_off.query_attributes() == {
        'on': False
    }

    on_calls = async_mock_service(hass, fan.DOMAIN, SERVICE_TURN_ON)
    await trt_on.execute(
        trait.COMMAND_ONOFF, BASIC_DATA,
        {'on': True}, {})
    assert len(on_calls) == 1
    assert on_calls[0].data == {
        ATTR_ENTITY_ID: 'fan.bla',
    }

    off_calls = async_mock_service(hass, fan.DOMAIN, SERVICE_TURN_OFF)
    await trt_on.execute(
        trait.COMMAND_ONOFF, BASIC_DATA,
        {'on': False}, {})
    assert len(off_calls) == 1
    assert off_calls[0].data == {
        ATTR_ENTITY_ID: 'fan.bla',
    }


async def test_onoff_light(hass):
    """Test OnOff trait support for light domain."""
    assert helpers.get_google_type(light.DOMAIN, None) is not None
    assert trait.OnOffTrait.supported(light.DOMAIN, 0, None)

    trt_on = trait.OnOffTrait(hass, State('light.bla', STATE_ON), BASIC_CONFIG)

    assert trt_on.sync_attributes() == {}

    assert trt_on.query_attributes() == {
        'on': True
    }

    trt_off = trait.OnOffTrait(hass, State('light.bla', STATE_OFF),
                               BASIC_CONFIG)

    assert trt_off.query_attributes() == {
        'on': False
    }

    on_calls = async_mock_service(hass, light.DOMAIN, SERVICE_TURN_ON)
    await trt_on.execute(
        trait.COMMAND_ONOFF, BASIC_DATA,
        {'on': True}, {})
    assert len(on_calls) == 1
    assert on_calls[0].data == {
        ATTR_ENTITY_ID: 'light.bla',
    }

    off_calls = async_mock_service(hass, light.DOMAIN, SERVICE_TURN_OFF)
    await trt_on.execute(
        trait.COMMAND_ONOFF, BASIC_DATA,
        {'on': False}, {})
    assert len(off_calls) == 1
    assert off_calls[0].data == {
        ATTR_ENTITY_ID: 'light.bla',
    }


async def test_onoff_media_player(hass):
    """Test OnOff trait support for media_player domain."""
    assert helpers.get_google_type(media_player.DOMAIN, None) is not None
    assert trait.OnOffTrait.supported(media_player.DOMAIN, 0, None)

    trt_on = trait.OnOffTrait(hass, State('media_player.bla', STATE_ON),
                              BASIC_CONFIG)

    assert trt_on.sync_attributes() == {}

    assert trt_on.query_attributes() == {
        'on': True
    }

    trt_off = trait.OnOffTrait(hass, State('media_player.bla', STATE_OFF),
                               BASIC_CONFIG)

    assert trt_off.query_attributes() == {
        'on': False
    }

    on_calls = async_mock_service(hass, media_player.DOMAIN, SERVICE_TURN_ON)
    await trt_on.execute(
        trait.COMMAND_ONOFF, BASIC_DATA,
        {'on': True}, {})
    assert len(on_calls) == 1
    assert on_calls[0].data == {
        ATTR_ENTITY_ID: 'media_player.bla',
    }

    off_calls = async_mock_service(hass, media_player.DOMAIN,
                                   SERVICE_TURN_OFF)

    await trt_on.execute(
        trait.COMMAND_ONOFF, BASIC_DATA,
        {'on': False}, {})
    assert len(off_calls) == 1
    assert off_calls[0].data == {
        ATTR_ENTITY_ID: 'media_player.bla',
    }


async def test_onoff_climate(hass):
    """Test OnOff trait not supported for climate domain."""
    assert helpers.get_google_type(climate.DOMAIN, None) is not None
    assert not trait.OnOffTrait.supported(
        climate.DOMAIN, climate.SUPPORT_ON_OFF, None)


async def test_dock_vacuum(hass):
    """Test dock trait support for vacuum domain."""
    assert helpers.get_google_type(vacuum.DOMAIN, None) is not None
    assert trait.DockTrait.supported(vacuum.DOMAIN, 0, None)

    trt = trait.DockTrait(hass, State('vacuum.bla', vacuum.STATE_IDLE),
                          BASIC_CONFIG)

    assert trt.sync_attributes() == {}

    assert trt.query_attributes() == {
        'isDocked': False
    }

    calls = async_mock_service(hass, vacuum.DOMAIN,
                               vacuum.SERVICE_RETURN_TO_BASE)
    await trt.execute(
        trait.COMMAND_DOCK, BASIC_DATA, {}, {})
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: 'vacuum.bla',
    }


async def test_startstop_vacuum(hass):
    """Test startStop trait support for vacuum domain."""
    assert helpers.get_google_type(vacuum.DOMAIN, None) is not None
    assert trait.StartStopTrait.supported(vacuum.DOMAIN, 0, None)

    trt = trait.StartStopTrait(hass, State('vacuum.bla', vacuum.STATE_PAUSED, {
        ATTR_SUPPORTED_FEATURES: vacuum.SUPPORT_PAUSE,
    }), BASIC_CONFIG)

    assert trt.sync_attributes() == {'pausable': True}

    assert trt.query_attributes() == {
        'isRunning': False,
        'isPaused': True
    }

    start_calls = async_mock_service(hass, vacuum.DOMAIN,
                                     vacuum.SERVICE_START)
    await trt.execute(trait.COMMAND_STARTSTOP, BASIC_DATA, {'start': True}, {})
    assert len(start_calls) == 1
    assert start_calls[0].data == {
        ATTR_ENTITY_ID: 'vacuum.bla',
    }

    stop_calls = async_mock_service(hass, vacuum.DOMAIN,
                                    vacuum.SERVICE_STOP)
    await trt.execute(
        trait.COMMAND_STARTSTOP, BASIC_DATA, {'start': False}, {})
    assert len(stop_calls) == 1
    assert stop_calls[0].data == {
        ATTR_ENTITY_ID: 'vacuum.bla',
    }

    pause_calls = async_mock_service(hass, vacuum.DOMAIN,
                                     vacuum.SERVICE_PAUSE)
    await trt.execute(
        trait.COMMAND_PAUSEUNPAUSE, BASIC_DATA, {'pause': True}, {})
    assert len(pause_calls) == 1
    assert pause_calls[0].data == {
        ATTR_ENTITY_ID: 'vacuum.bla',
    }

    unpause_calls = async_mock_service(hass, vacuum.DOMAIN,
                                       vacuum.SERVICE_START)
    await trt.execute(
        trait.COMMAND_PAUSEUNPAUSE, BASIC_DATA, {'pause': False}, {})
    assert len(unpause_calls) == 1
    assert unpause_calls[0].data == {
        ATTR_ENTITY_ID: 'vacuum.bla',
    }


async def test_color_setting_color_light(hass):
    """Test ColorSpectrum trait support for light domain."""
    assert helpers.get_google_type(light.DOMAIN, None) is not None
    assert not trait.ColorSettingTrait.supported(light.DOMAIN, 0, None)
    assert trait.ColorSettingTrait.supported(light.DOMAIN,
                                             light.SUPPORT_COLOR, None)

    trt = trait.ColorSettingTrait(hass, State('light.bla', STATE_ON, {
        light.ATTR_HS_COLOR: (20, 94),
        light.ATTR_BRIGHTNESS: 200,
        ATTR_SUPPORTED_FEATURES: light.SUPPORT_COLOR,
    }), BASIC_CONFIG)

    assert trt.sync_attributes() == {
        'colorModel': 'hsv'
    }

    assert trt.query_attributes() == {
        'color': {
            'spectrumHsv': {
                'hue': 20,
                'saturation': 0.94,
                'value': 200 / 255,
            }
        }
    }

    assert trt.can_execute(trait.COMMAND_COLOR_ABSOLUTE, {
        'color': {
            'spectrumRGB': 16715792
        }
    })

    calls = async_mock_service(hass, light.DOMAIN, SERVICE_TURN_ON)
    await trt.execute(trait.COMMAND_COLOR_ABSOLUTE, BASIC_DATA, {
        'color': {
            'spectrumRGB': 1052927
        }
    }, {})
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: 'light.bla',
        light.ATTR_HS_COLOR: (240, 93.725),
    }

    await trt.execute(trait.COMMAND_COLOR_ABSOLUTE, BASIC_DATA, {
        'color': {
            'spectrumHSV': {
                'hue': 100,
                'saturation': .50,
                'value': .20,
            }
        }
    }, {})
    assert len(calls) == 2
    assert calls[1].data == {
        ATTR_ENTITY_ID: 'light.bla',
        light.ATTR_HS_COLOR: [100, 50],
        light.ATTR_BRIGHTNESS: .2 * 255,
    }


async def test_color_setting_temperature_light(hass):
    """Test ColorTemperature trait support for light domain."""
    assert helpers.get_google_type(light.DOMAIN, None) is not None
    assert not trait.ColorSettingTrait.supported(light.DOMAIN, 0, None)
    assert trait.ColorSettingTrait.supported(light.DOMAIN,
                                             light.SUPPORT_COLOR_TEMP, None)

    trt = trait.ColorSettingTrait(hass, State('light.bla', STATE_ON, {
        light.ATTR_MIN_MIREDS: 200,
        light.ATTR_COLOR_TEMP: 300,
        light.ATTR_MAX_MIREDS: 500,
        ATTR_SUPPORTED_FEATURES: light.SUPPORT_COLOR_TEMP,
    }), BASIC_CONFIG)

    assert trt.sync_attributes() == {
        'colorTemperatureRange': {
            'temperatureMinK': 2000,
            'temperatureMaxK': 5000,
        }
    }

    assert trt.query_attributes() == {
        'color': {
            'temperatureK': 3333
        }
    }

    assert trt.can_execute(trait.COMMAND_COLOR_ABSOLUTE, {
        'color': {
            'temperature': 400
        }
    })
    calls = async_mock_service(hass, light.DOMAIN, SERVICE_TURN_ON)

    with pytest.raises(helpers.SmartHomeError) as err:
        await trt.execute(trait.COMMAND_COLOR_ABSOLUTE, BASIC_DATA, {
            'color': {
                'temperature': 5555
            }
        }, {})
    assert err.value.code == const.ERR_VALUE_OUT_OF_RANGE

    await trt.execute(trait.COMMAND_COLOR_ABSOLUTE, BASIC_DATA, {
        'color': {
            'temperature': 2857
        }
    }, {})
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: 'light.bla',
        light.ATTR_COLOR_TEMP: color.color_temperature_kelvin_to_mired(2857)
    }


async def test_color_light_temperature_light_bad_temp(hass):
    """Test ColorTemperature trait support for light domain."""
    assert helpers.get_google_type(light.DOMAIN, None) is not None
    assert not trait.ColorSettingTrait.supported(light.DOMAIN, 0, None)
    assert trait.ColorSettingTrait.supported(light.DOMAIN,
                                             light.SUPPORT_COLOR_TEMP, None)

    trt = trait.ColorSettingTrait(hass, State('light.bla', STATE_ON, {
        light.ATTR_MIN_MIREDS: 200,
        light.ATTR_COLOR_TEMP: 0,
        light.ATTR_MAX_MIREDS: 500,
    }), BASIC_CONFIG)

    assert trt.query_attributes() == {
    }


async def test_scene_scene(hass):
    """Test Scene trait support for scene domain."""
    assert helpers.get_google_type(scene.DOMAIN, None) is not None
    assert trait.SceneTrait.supported(scene.DOMAIN, 0, None)

    trt = trait.SceneTrait(hass, State('scene.bla', scene.STATE), BASIC_CONFIG)
    assert trt.sync_attributes() == {}
    assert trt.query_attributes() == {}
    assert trt.can_execute(trait.COMMAND_ACTIVATE_SCENE, {})

    calls = async_mock_service(hass, scene.DOMAIN, SERVICE_TURN_ON)
    await trt.execute(trait.COMMAND_ACTIVATE_SCENE, BASIC_DATA, {}, {})
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: 'scene.bla',
    }


async def test_scene_script(hass):
    """Test Scene trait support for script domain."""
    assert helpers.get_google_type(script.DOMAIN, None) is not None
    assert trait.SceneTrait.supported(script.DOMAIN, 0, None)

    trt = trait.SceneTrait(hass, State('script.bla', STATE_OFF), BASIC_CONFIG)
    assert trt.sync_attributes() == {}
    assert trt.query_attributes() == {}
    assert trt.can_execute(trait.COMMAND_ACTIVATE_SCENE, {})

    calls = async_mock_service(hass, script.DOMAIN, SERVICE_TURN_ON)
    await trt.execute(trait.COMMAND_ACTIVATE_SCENE, BASIC_DATA, {}, {})

    # We don't wait till script execution is done.
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: 'script.bla',
    }


async def test_temperature_setting_climate_onoff(hass):
    """Test TemperatureSetting trait support for climate domain - range."""
    assert helpers.get_google_type(climate.DOMAIN, None) is not None
    assert not trait.TemperatureSettingTrait.supported(climate.DOMAIN, 0, None)
    assert trait.TemperatureSettingTrait.supported(
        climate.DOMAIN, climate.SUPPORT_OPERATION_MODE, None)

    hass.config.units.temperature_unit = TEMP_FAHRENHEIT

    trt = trait.TemperatureSettingTrait(hass, State(
        'climate.bla', climate.STATE_AUTO, {
            ATTR_SUPPORTED_FEATURES: (
                climate.SUPPORT_OPERATION_MODE | climate.SUPPORT_ON_OFF |
                climate.SUPPORT_TARGET_TEMPERATURE_HIGH |
                climate.SUPPORT_TARGET_TEMPERATURE_LOW),
            climate.ATTR_OPERATION_MODE: climate.STATE_COOL,
            climate.ATTR_OPERATION_LIST: [
                climate.STATE_COOL,
                climate.STATE_HEAT,
                climate.STATE_AUTO,
            ],
            climate.ATTR_MIN_TEMP: None,
            climate.ATTR_MAX_TEMP: None,
        }), BASIC_CONFIG)
    assert trt.sync_attributes() == {
        'availableThermostatModes': 'off,on,cool,heat,heatcool',
        'thermostatTemperatureUnit': 'F',
    }
    assert trt.can_execute(trait.COMMAND_THERMOSTAT_SET_MODE, {})

    calls = async_mock_service(
        hass, climate.DOMAIN, SERVICE_TURN_ON)
    await trt.execute(trait.COMMAND_THERMOSTAT_SET_MODE, BASIC_DATA, {
        'thermostatMode': 'on',
    }, {})
    assert len(calls) == 1

    calls = async_mock_service(
        hass, climate.DOMAIN, SERVICE_TURN_OFF)
    await trt.execute(trait.COMMAND_THERMOSTAT_SET_MODE, BASIC_DATA, {
        'thermostatMode': 'off',
    }, {})
    assert len(calls) == 1


async def test_temperature_setting_climate_range(hass):
    """Test TemperatureSetting trait support for climate domain - range."""
    assert helpers.get_google_type(climate.DOMAIN, None) is not None
    assert not trait.TemperatureSettingTrait.supported(climate.DOMAIN, 0, None)
    assert trait.TemperatureSettingTrait.supported(
        climate.DOMAIN, climate.SUPPORT_OPERATION_MODE, None)

    hass.config.units.temperature_unit = TEMP_FAHRENHEIT

    trt = trait.TemperatureSettingTrait(hass, State(
        'climate.bla', climate.STATE_AUTO, {
            climate.ATTR_CURRENT_TEMPERATURE: 70,
            climate.ATTR_CURRENT_HUMIDITY: 25,
            ATTR_SUPPORTED_FEATURES:
                climate.SUPPORT_OPERATION_MODE |
                climate.SUPPORT_TARGET_TEMPERATURE_HIGH |
                climate.SUPPORT_TARGET_TEMPERATURE_LOW,
            climate.ATTR_OPERATION_MODE: climate.STATE_AUTO,
            climate.ATTR_OPERATION_LIST: [
                STATE_OFF,
                climate.STATE_COOL,
                climate.STATE_HEAT,
                climate.STATE_AUTO,
            ],
            climate.ATTR_TARGET_TEMP_HIGH: 75,
            climate.ATTR_TARGET_TEMP_LOW: 65,
            climate.ATTR_MIN_TEMP: 50,
            climate.ATTR_MAX_TEMP: 80
        }), BASIC_CONFIG)
    assert trt.sync_attributes() == {
        'availableThermostatModes': 'off,cool,heat,heatcool',
        'thermostatTemperatureUnit': 'F',
    }
    assert trt.query_attributes() == {
        'thermostatMode': 'heatcool',
        'thermostatTemperatureAmbient': 21.1,
        'thermostatHumidityAmbient': 25,
        'thermostatTemperatureSetpointLow': 18.3,
        'thermostatTemperatureSetpointHigh': 23.9,
    }
    assert trt.can_execute(trait.COMMAND_THERMOSTAT_TEMPERATURE_SET_RANGE, {})
    assert trt.can_execute(trait.COMMAND_THERMOSTAT_SET_MODE, {})

    calls = async_mock_service(
        hass, climate.DOMAIN, climate.SERVICE_SET_TEMPERATURE)
    await trt.execute(
        trait.COMMAND_THERMOSTAT_TEMPERATURE_SET_RANGE, BASIC_DATA, {
            'thermostatTemperatureSetpointHigh': 25,
            'thermostatTemperatureSetpointLow': 20,
        }, {})
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: 'climate.bla',
        climate.ATTR_TARGET_TEMP_HIGH: 77,
        climate.ATTR_TARGET_TEMP_LOW: 68,
    }

    calls = async_mock_service(
        hass, climate.DOMAIN, climate.SERVICE_SET_OPERATION_MODE)
    await trt.execute(trait.COMMAND_THERMOSTAT_SET_MODE, BASIC_DATA, {
        'thermostatMode': 'heatcool',
    }, {})
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: 'climate.bla',
        climate.ATTR_OPERATION_MODE: climate.STATE_AUTO,
    }

    with pytest.raises(helpers.SmartHomeError) as err:
        await trt.execute(
            trait.COMMAND_THERMOSTAT_TEMPERATURE_SETPOINT, BASIC_DATA,
            {'thermostatTemperatureSetpoint': -100}, {})
    assert err.value.code == const.ERR_VALUE_OUT_OF_RANGE
    hass.config.units.temperature_unit = TEMP_CELSIUS


async def test_temperature_setting_climate_setpoint(hass):
    """Test TemperatureSetting trait support for climate domain - setpoint."""
    assert helpers.get_google_type(climate.DOMAIN, None) is not None
    assert not trait.TemperatureSettingTrait.supported(climate.DOMAIN, 0, None)
    assert trait.TemperatureSettingTrait.supported(
        climate.DOMAIN, climate.SUPPORT_OPERATION_MODE, None)

    hass.config.units.temperature_unit = TEMP_CELSIUS

    trt = trait.TemperatureSettingTrait(hass, State(
        'climate.bla', climate.STATE_AUTO, {
            ATTR_SUPPORTED_FEATURES: (
                climate.SUPPORT_OPERATION_MODE | climate.SUPPORT_ON_OFF),
            climate.ATTR_OPERATION_MODE: climate.STATE_COOL,
            climate.ATTR_OPERATION_LIST: [
                STATE_OFF,
                climate.STATE_COOL,
            ],
            climate.ATTR_MIN_TEMP: 10,
            climate.ATTR_MAX_TEMP: 30,
            ATTR_TEMPERATURE: 18,
            climate.ATTR_CURRENT_TEMPERATURE: 20
        }), BASIC_CONFIG)
    assert trt.sync_attributes() == {
        'availableThermostatModes': 'off,on,cool',
        'thermostatTemperatureUnit': 'C',
    }
    assert trt.query_attributes() == {
        'thermostatMode': 'cool',
        'thermostatTemperatureAmbient': 20,
        'thermostatTemperatureSetpoint': 18,
    }
    assert trt.can_execute(trait.COMMAND_THERMOSTAT_TEMPERATURE_SETPOINT, {})
    assert trt.can_execute(trait.COMMAND_THERMOSTAT_SET_MODE, {})

    calls = async_mock_service(
        hass, climate.DOMAIN, climate.SERVICE_SET_TEMPERATURE)

    with pytest.raises(helpers.SmartHomeError):
        await trt.execute(
            trait.COMMAND_THERMOSTAT_TEMPERATURE_SETPOINT, BASIC_DATA,
            {'thermostatTemperatureSetpoint': -100}, {})

    await trt.execute(
        trait.COMMAND_THERMOSTAT_TEMPERATURE_SETPOINT, BASIC_DATA,
        {'thermostatTemperatureSetpoint': 19}, {})
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: 'climate.bla',
        ATTR_TEMPERATURE: 19
    }


async def test_temperature_setting_climate_setpoint_auto(hass):
    """
    Test TemperatureSetting trait support for climate domain.

    Setpoint in auto mode.
    """
    hass.config.units.temperature_unit = TEMP_CELSIUS

    trt = trait.TemperatureSettingTrait(hass, State(
        'climate.bla', climate.STATE_AUTO, {
            ATTR_SUPPORTED_FEATURES: (
                climate.SUPPORT_OPERATION_MODE | climate.SUPPORT_ON_OFF),
            climate.ATTR_OPERATION_MODE: climate.STATE_AUTO,
            climate.ATTR_OPERATION_LIST: [
                STATE_OFF,
                climate.STATE_AUTO,
            ],
            climate.ATTR_MIN_TEMP: 10,
            climate.ATTR_MAX_TEMP: 30,
            ATTR_TEMPERATURE: 18,
            climate.ATTR_CURRENT_TEMPERATURE: 20
        }), BASIC_CONFIG)
    assert trt.sync_attributes() == {
        'availableThermostatModes': 'off,on,heatcool',
        'thermostatTemperatureUnit': 'C',
    }
    assert trt.query_attributes() == {
        'thermostatMode': 'heatcool',
        'thermostatTemperatureAmbient': 20,
        'thermostatTemperatureSetpointHigh': 18,
        'thermostatTemperatureSetpointLow': 18,
    }
    assert trt.can_execute(trait.COMMAND_THERMOSTAT_TEMPERATURE_SETPOINT, {})
    assert trt.can_execute(trait.COMMAND_THERMOSTAT_SET_MODE, {})

    calls = async_mock_service(
        hass, climate.DOMAIN, climate.SERVICE_SET_TEMPERATURE)

    await trt.execute(
        trait.COMMAND_THERMOSTAT_TEMPERATURE_SETPOINT, BASIC_DATA,
        {'thermostatTemperatureSetpoint': 19}, {})
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: 'climate.bla',
        ATTR_TEMPERATURE: 19
    }


async def test_lock_unlock_lock(hass):
    """Test LockUnlock trait locking support for lock domain."""
    assert helpers.get_google_type(lock.DOMAIN, None) is not None
    assert trait.LockUnlockTrait.supported(lock.DOMAIN, lock.SUPPORT_OPEN,
                                           None)
    assert trait.LockUnlockTrait.might_2fa(lock.DOMAIN, lock.SUPPORT_OPEN,
                                           None)

    trt = trait.LockUnlockTrait(hass,
                                State('lock.front_door', lock.STATE_LOCKED),
                                PIN_CONFIG)

    assert trt.sync_attributes() == {}

    assert trt.query_attributes() == {
        'isLocked': True
    }

    assert trt.can_execute(trait.COMMAND_LOCKUNLOCK, {'lock': True})

    calls = async_mock_service(hass, lock.DOMAIN, lock.SERVICE_LOCK)

    await trt.execute(trait.COMMAND_LOCKUNLOCK, PIN_DATA, {'lock': True}, {})

    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: 'lock.front_door'
    }


async def test_lock_unlock_unlock(hass):
    """Test LockUnlock trait unlocking support for lock domain."""
    assert helpers.get_google_type(lock.DOMAIN, None) is not None
    assert trait.LockUnlockTrait.supported(lock.DOMAIN, lock.SUPPORT_OPEN,
                                           None)

    trt = trait.LockUnlockTrait(hass,
                                State('lock.front_door', lock.STATE_LOCKED),
                                PIN_CONFIG)

    assert trt.sync_attributes() == {}

    assert trt.query_attributes() == {
        'isLocked': True
    }

    assert trt.can_execute(trait.COMMAND_LOCKUNLOCK, {'lock': False})

    calls = async_mock_service(hass, lock.DOMAIN, lock.SERVICE_UNLOCK)

    # No challenge data
    with pytest.raises(error.ChallengeNeeded) as err:
        await trt.execute(
            trait.COMMAND_LOCKUNLOCK, PIN_DATA, {'lock': False}, {})
    assert len(calls) == 0
    assert err.value.code == const.ERR_CHALLENGE_NEEDED
    assert err.value.challenge_type == const.CHALLENGE_PIN_NEEDED

    # invalid pin
    with pytest.raises(error.ChallengeNeeded) as err:
        await trt.execute(
            trait.COMMAND_LOCKUNLOCK, PIN_DATA, {'lock': False},
            {'pin': 9999})
    assert len(calls) == 0
    assert err.value.code == const.ERR_CHALLENGE_NEEDED
    assert err.value.challenge_type == const.CHALLENGE_FAILED_PIN_NEEDED

    await trt.execute(
        trait.COMMAND_LOCKUNLOCK, PIN_DATA, {'lock': False}, {'pin': '1234'})

    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: 'lock.front_door'
    }

    # Test without pin
    trt = trait.LockUnlockTrait(hass,
                                State('lock.front_door', lock.STATE_LOCKED),
                                BASIC_CONFIG)

    with pytest.raises(error.SmartHomeError) as err:
        await trt.execute(
            trait.COMMAND_LOCKUNLOCK, BASIC_DATA, {'lock': False}, {})
    assert len(calls) == 1
    assert err.value.code == const.ERR_CHALLENGE_NOT_SETUP

    # Test with 2FA override
    with patch('homeassistant.components.google_assistant.helpers'
               '.AbstractConfig.should_2fa', return_value=False):
        await trt.execute(
            trait.COMMAND_LOCKUNLOCK, BASIC_DATA, {'lock': False}, {})
    assert len(calls) == 2


async def test_fan_speed(hass):
    """Test FanSpeed trait speed control support for fan domain."""
    assert helpers.get_google_type(fan.DOMAIN, None) is not None
    assert trait.FanSpeedTrait.supported(fan.DOMAIN, fan.SUPPORT_SET_SPEED,
                                         None)

    trt = trait.FanSpeedTrait(
        hass, State(
            'fan.living_room_fan', fan.SPEED_HIGH, attributes={
                'speed_list': [
                    fan.SPEED_OFF, fan.SPEED_LOW, fan.SPEED_MEDIUM,
                    fan.SPEED_HIGH
                ],
                'speed': 'low'
            }), BASIC_CONFIG)

    assert trt.sync_attributes() == {
        'availableFanSpeeds': {
            'ordered': True,
            'speeds': [
                {
                    'speed_name': 'off',
                    'speed_values': [
                        {
                            'speed_synonym': ['stop', 'off'],
                            'lang': 'en'
                        }
                    ]
                },
                {
                    'speed_name': 'low',
                    'speed_values': [
                        {
                            'speed_synonym': [
                                'slow', 'low', 'slowest', 'lowest'],
                            'lang': 'en'
                        }
                    ]
                },
                {
                    'speed_name': 'medium',
                    'speed_values': [
                        {
                            'speed_synonym': ['medium', 'mid', 'middle'],
                            'lang': 'en'
                        }
                    ]
                },
                {
                    'speed_name': 'high',
                    'speed_values': [
                        {
                            'speed_synonym': [
                                'high', 'max', 'fast', 'highest', 'fastest',
                                'maximum'],
                            'lang': 'en'
                        }
                    ]
                }
            ]
        },
        'reversible': False
    }

    assert trt.query_attributes() == {
        'currentFanSpeedSetting': 'low',
        'on': True,
        'online': True
    }

    assert trt.can_execute(
        trait.COMMAND_FANSPEED, params={'fanSpeed': 'medium'})

    calls = async_mock_service(hass, fan.DOMAIN, fan.SERVICE_SET_SPEED)
    await trt.execute(
        trait.COMMAND_FANSPEED, BASIC_DATA, {'fanSpeed': 'medium'}, {})

    assert len(calls) == 1
    assert calls[0].data == {
        'entity_id': 'fan.living_room_fan',
        'speed': 'medium'
    }


async def test_modes(hass):
    """Test Mode trait."""
    assert helpers.get_google_type(media_player.DOMAIN, None) is not None
    assert trait.ModesTrait.supported(
        media_player.DOMAIN, media_player.SUPPORT_SELECT_SOURCE, None)

    trt = trait.ModesTrait(
        hass, State(
            'media_player.living_room', media_player.STATE_PLAYING,
            attributes={
                media_player.ATTR_INPUT_SOURCE_LIST: [
                    'media', 'game', 'chromecast', 'plex'
                ],
                media_player.ATTR_INPUT_SOURCE: 'game'
            }),
        BASIC_CONFIG)

    attribs = trt.sync_attributes()
    assert attribs == {
        'availableModes': [
            {
                'name': 'input source',
                'name_values': [
                    {
                        'name_synonym': ['input source'],
                        'lang': 'en'
                    }
                ],
                'settings': [
                    {
                        'setting_name': 'media',
                        'setting_values': [
                            {
                                'setting_synonym': ['media', 'media mode'],
                                'lang': 'en'
                            }
                        ]
                    },
                    {
                        'setting_name': 'game',
                        'setting_values': [
                            {
                                'setting_synonym': ['game', 'game mode'],
                                'lang': 'en'
                            }
                        ]
                    },
                    {
                        'setting_name': 'chromecast',
                        'setting_values': [
                            {
                                'setting_synonym': ['chromecast'],
                                'lang': 'en'
                            }
                        ]
                    }
                ],
                'ordered': False
            }
        ]
    }

    assert trt.query_attributes() == {
        'currentModeSettings': {'source': 'game'},
        'on': True,
        'online': True
    }

    assert trt.can_execute(
        trait.COMMAND_MODES, params={
            'updateModeSettings': {
                trt.HA_TO_GOOGLE.get(media_player.ATTR_INPUT_SOURCE): 'media'
            }})

    calls = async_mock_service(
        hass, media_player.DOMAIN, media_player.SERVICE_SELECT_SOURCE)
    await trt.execute(
        trait.COMMAND_MODES, BASIC_DATA, {
            'updateModeSettings': {
                trt.HA_TO_GOOGLE.get(media_player.ATTR_INPUT_SOURCE): 'media'
            }}, {})

    assert len(calls) == 1
    assert calls[0].data == {
        'entity_id': 'media_player.living_room',
        'source': 'media'
    }


async def test_openclose_cover(hass):
    """Test OpenClose trait support for cover domain."""
    assert helpers.get_google_type(cover.DOMAIN, None) is not None
    assert trait.OpenCloseTrait.supported(cover.DOMAIN,
                                          cover.SUPPORT_SET_POSITION, None)

    trt = trait.OpenCloseTrait(hass, State('cover.bla', cover.STATE_OPEN, {
        cover.ATTR_CURRENT_POSITION: 75,
        ATTR_SUPPORTED_FEATURES: cover.SUPPORT_SET_POSITION,
    }), BASIC_CONFIG)

    assert trt.sync_attributes() == {}
    assert trt.query_attributes() == {
        'openPercent': 75
    }

    calls = async_mock_service(
        hass, cover.DOMAIN, cover.SERVICE_SET_COVER_POSITION)
    await trt.execute(
        trait.COMMAND_OPENCLOSE, BASIC_DATA,
        {'openPercent': 50}, {})
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: 'cover.bla',
        cover.ATTR_POSITION: 50
    }


async def test_openclose_cover_unknown_state(hass):
    """Test OpenClose trait support for cover domain with unknown state."""
    assert helpers.get_google_type(cover.DOMAIN, None) is not None
    assert trait.OpenCloseTrait.supported(cover.DOMAIN,
                                          cover.SUPPORT_SET_POSITION, None)

    # No state
    trt = trait.OpenCloseTrait(hass, State('cover.bla', STATE_UNKNOWN, {
    }), BASIC_CONFIG)

    assert trt.sync_attributes() == {}

    with pytest.raises(helpers.SmartHomeError):
        trt.query_attributes()

    calls = async_mock_service(
        hass, cover.DOMAIN, cover.SERVICE_OPEN_COVER)
    await trt.execute(
        trait.COMMAND_OPENCLOSE, BASIC_DATA,
        {'openPercent': 100}, {})
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: 'cover.bla',
    }

    assert trt.query_attributes() == {'openPercent': 100}


async def test_openclose_cover_assumed_state(hass):
    """Test OpenClose trait support for cover domain."""
    assert helpers.get_google_type(cover.DOMAIN, None) is not None
    assert trait.OpenCloseTrait.supported(cover.DOMAIN,
                                          cover.SUPPORT_SET_POSITION, None)

    trt = trait.OpenCloseTrait(hass, State('cover.bla', cover.STATE_OPEN, {
        ATTR_ASSUMED_STATE: True,
        ATTR_SUPPORTED_FEATURES: cover.SUPPORT_SET_POSITION,
    }), BASIC_CONFIG)

    assert trt.sync_attributes() == {}

    with pytest.raises(helpers.SmartHomeError):
        trt.query_attributes()

    calls = async_mock_service(
        hass, cover.DOMAIN, cover.SERVICE_SET_COVER_POSITION)
    await trt.execute(
        trait.COMMAND_OPENCLOSE, BASIC_DATA,
        {'openPercent': 40}, {})
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: 'cover.bla',
        cover.ATTR_POSITION: 40
    }

    assert trt.query_attributes() == {'openPercent': 40}


async def test_openclose_cover_no_position(hass):
    """Test OpenClose trait support for cover domain."""
    assert helpers.get_google_type(cover.DOMAIN, None) is not None
    assert trait.OpenCloseTrait.supported(cover.DOMAIN,
                                          cover.SUPPORT_SET_POSITION, None)

    trt = trait.OpenCloseTrait(hass, State('cover.bla', cover.STATE_OPEN, {
    }), BASIC_CONFIG)

    assert trt.sync_attributes() == {}
    assert trt.query_attributes() == {
        'openPercent': 100
    }

    calls = async_mock_service(
        hass, cover.DOMAIN, cover.SERVICE_CLOSE_COVER)
    await trt.execute(
        trait.COMMAND_OPENCLOSE, BASIC_DATA,
        {'openPercent': 0}, {})
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: 'cover.bla',
    }


@pytest.mark.parametrize('device_class', (
    cover.DEVICE_CLASS_DOOR,
    cover.DEVICE_CLASS_GARAGE,
))
async def test_openclose_cover_secure(hass, device_class):
    """Test OpenClose trait support for cover domain."""
    assert helpers.get_google_type(cover.DOMAIN, device_class) is not None
    assert trait.OpenCloseTrait.supported(
        cover.DOMAIN, cover.SUPPORT_SET_POSITION, device_class)
    assert trait.OpenCloseTrait.might_2fa(
        cover.DOMAIN, cover.SUPPORT_SET_POSITION, device_class)

    trt = trait.OpenCloseTrait(hass, State('cover.bla', cover.STATE_OPEN, {
        ATTR_DEVICE_CLASS: device_class,
        ATTR_SUPPORTED_FEATURES: cover.SUPPORT_SET_POSITION,
        cover.ATTR_CURRENT_POSITION: 75
    }), PIN_CONFIG)

    assert trt.sync_attributes() == {}
    assert trt.query_attributes() == {
        'openPercent': 75
    }

    calls = async_mock_service(
        hass, cover.DOMAIN, cover.SERVICE_SET_COVER_POSITION)

    # No challenge data
    with pytest.raises(error.ChallengeNeeded) as err:
        await trt.execute(
            trait.COMMAND_OPENCLOSE, PIN_DATA,
            {'openPercent': 50}, {})
    assert len(calls) == 0
    assert err.value.code == const.ERR_CHALLENGE_NEEDED
    assert err.value.challenge_type == const.CHALLENGE_PIN_NEEDED

    # invalid pin
    with pytest.raises(error.ChallengeNeeded) as err:
        await trt.execute(
            trait.COMMAND_OPENCLOSE, PIN_DATA,
            {'openPercent': 50}, {'pin': '9999'})
    assert len(calls) == 0
    assert err.value.code == const.ERR_CHALLENGE_NEEDED
    assert err.value.challenge_type == const.CHALLENGE_FAILED_PIN_NEEDED

    await trt.execute(
        trait.COMMAND_OPENCLOSE, PIN_DATA,
        {'openPercent': 50}, {'pin': '1234'})
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: 'cover.bla',
        cover.ATTR_POSITION: 50
    }

    # no challenge on close
    calls = async_mock_service(
        hass, cover.DOMAIN, cover.SERVICE_CLOSE_COVER)
    await trt.execute(
        trait.COMMAND_OPENCLOSE, PIN_DATA,
        {'openPercent': 0}, {})
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: 'cover.bla'
    }


@pytest.mark.parametrize('device_class', (
    binary_sensor.DEVICE_CLASS_DOOR,
    binary_sensor.DEVICE_CLASS_GARAGE_DOOR,
    binary_sensor.DEVICE_CLASS_LOCK,
    binary_sensor.DEVICE_CLASS_OPENING,
    binary_sensor.DEVICE_CLASS_WINDOW,
))
async def test_openclose_binary_sensor(hass, device_class):
    """Test OpenClose trait support for binary_sensor domain."""
    assert helpers.get_google_type(
        binary_sensor.DOMAIN, device_class) is not None
    assert trait.OpenCloseTrait.supported(binary_sensor.DOMAIN,
                                          0, device_class)

    trt = trait.OpenCloseTrait(hass, State('binary_sensor.test', STATE_ON, {
        ATTR_DEVICE_CLASS: device_class,
    }), BASIC_CONFIG)

    assert trt.sync_attributes() == {
        'queryOnlyOpenClose': True,
    }

    assert trt.query_attributes() == {
        'openPercent': 100
    }

    trt = trait.OpenCloseTrait(hass, State('binary_sensor.test', STATE_OFF, {
        ATTR_DEVICE_CLASS: device_class,
    }), BASIC_CONFIG)

    assert trt.sync_attributes() == {
        'queryOnlyOpenClose': True,
    }

    assert trt.query_attributes() == {
        'openPercent': 0
    }


async def test_volume_media_player(hass):
    """Test volume trait support for media player domain."""
    assert helpers.get_google_type(media_player.DOMAIN, None) is not None
    assert trait.VolumeTrait.supported(media_player.DOMAIN,
                                       media_player.SUPPORT_VOLUME_SET |
                                       media_player.SUPPORT_VOLUME_MUTE,
                                       None)

    trt = trait.VolumeTrait(hass, State(
        'media_player.bla', media_player.STATE_PLAYING, {
            media_player.ATTR_MEDIA_VOLUME_LEVEL: .3,
            media_player.ATTR_MEDIA_VOLUME_MUTED: False,
        }), BASIC_CONFIG)

    assert trt.sync_attributes() == {}

    assert trt.query_attributes() == {
        'currentVolume': 30,
        'isMuted': False
    }

    calls = async_mock_service(
        hass, media_player.DOMAIN, media_player.SERVICE_VOLUME_SET)
    await trt.execute(
        trait.COMMAND_SET_VOLUME, BASIC_DATA,
        {'volumeLevel': 60}, {})
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: 'media_player.bla',
        media_player.ATTR_MEDIA_VOLUME_LEVEL: .6
    }


async def test_volume_media_player_relative(hass):
    """Test volume trait support for media player domain."""
    trt = trait.VolumeTrait(hass, State(
        'media_player.bla', media_player.STATE_PLAYING, {
            media_player.ATTR_MEDIA_VOLUME_LEVEL: .3,
            media_player.ATTR_MEDIA_VOLUME_MUTED: False,
        }), BASIC_CONFIG)

    assert trt.sync_attributes() == {}

    assert trt.query_attributes() == {
        'currentVolume': 30,
        'isMuted': False
    }

    calls = async_mock_service(
        hass, media_player.DOMAIN, media_player.SERVICE_VOLUME_SET)

    await trt.execute(
        trait.COMMAND_VOLUME_RELATIVE, BASIC_DATA,
        {'volumeRelativeLevel': 20,
         'relativeSteps': 2}, {})
    assert len(calls) == 1
    assert calls[0].data == {
        ATTR_ENTITY_ID: 'media_player.bla',
        media_player.ATTR_MEDIA_VOLUME_LEVEL: .5
    }


async def test_temperature_setting_sensor(hass):
    """Test TemperatureSetting trait support for temperature sensor."""
    assert helpers.get_google_type(sensor.DOMAIN,
                                   sensor.DEVICE_CLASS_TEMPERATURE) is not None
    assert not trait.TemperatureSettingTrait.supported(
        sensor.DOMAIN,
        0,
        sensor.DEVICE_CLASS_HUMIDITY
    )
    assert trait.TemperatureSettingTrait.supported(
        sensor.DOMAIN,
        0,
        sensor.DEVICE_CLASS_TEMPERATURE
    )

    hass.config.units.temperature_unit = TEMP_FAHRENHEIT

    trt = trait.TemperatureSettingTrait(hass, State('sensor.test', "70", {
        ATTR_DEVICE_CLASS: sensor.DEVICE_CLASS_TEMPERATURE,
    }), BASIC_CONFIG)

    assert trt.sync_attributes() == {
        'queryOnlyTemperatureSetting': True,
        'thermostatTemperatureUnit': 'F',
    }

    assert trt.query_attributes() == {
        'thermostatTemperatureAmbient': 21.1
    }
    hass.config.units.temperature_unit = TEMP_CELSIUS
