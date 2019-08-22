"""
Regression tests for Ecobee 3.

https://github.com/home-assistant/home-assistant/issues/15336
"""

from unittest import mock

from homekit import AccessoryDisconnectedError
import pytest

from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.components.climate.const import (
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_TARGET_HUMIDITY,
    SUPPORT_TARGET_HUMIDITY_HIGH, SUPPORT_TARGET_HUMIDITY_LOW,
    SUPPORT_OPERATION_MODE)


from tests.components.homekit_controller.common import (
    FakePairing, device_config_changed, setup_accessories_from_file,
    setup_test_accessories, Helper
)


async def test_ecobee3_setup(hass):
    """Test that a Ecbobee 3 can be correctly setup in HA."""
    accessories = await setup_accessories_from_file(hass, 'ecobee3.json')
    pairing = await setup_test_accessories(hass, accessories)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    climate = entity_registry.async_get('climate.homew')
    assert climate.unique_id == 'homekit-123456789012-16'

    climate_helper = Helper(hass, 'climate.homew', pairing, accessories[0])
    climate_state = await climate_helper.poll_and_get_state()
    assert climate_state.attributes['friendly_name'] == 'HomeW'
    assert climate_state.attributes['supported_features'] == (
        SUPPORT_TARGET_TEMPERATURE | SUPPORT_TARGET_HUMIDITY |
        SUPPORT_TARGET_HUMIDITY_HIGH | SUPPORT_TARGET_HUMIDITY_LOW |
        SUPPORT_OPERATION_MODE
    )

    assert climate_state.attributes['operation_list'] == [
        'off',
        'heat',
        'cool',
        'auto',
    ]

    assert climate_state.attributes['min_temp'] == 7.2
    assert climate_state.attributes['max_temp'] == 33.3
    assert climate_state.attributes['min_humidity'] == 20
    assert climate_state.attributes['max_humidity'] == 50

    occ1 = entity_registry.async_get('binary_sensor.kitchen')
    assert occ1.unique_id == 'homekit-AB1C-56'

    occ1_helper = Helper(
        hass, 'binary_sensor.kitchen', pairing, accessories[0])
    occ1_state = await occ1_helper.poll_and_get_state()
    assert occ1_state.attributes['friendly_name'] == 'Kitchen'

    occ2 = entity_registry.async_get('binary_sensor.porch')
    assert occ2.unique_id == 'homekit-AB2C-56'

    occ3 = entity_registry.async_get('binary_sensor.basement')
    assert occ3.unique_id == 'homekit-AB3C-56'

    device_registry = await hass.helpers.device_registry.async_get_registry()

    climate_device = device_registry.async_get(climate.device_id)
    assert climate_device.manufacturer == 'ecobee Inc.'
    assert climate_device.name == 'HomeW'
    assert climate_device.model == 'ecobee3'
    assert climate_device.sw_version == '4.2.394'
    assert climate_device.via_device_id is None

    # Check that an attached sensor has its own device entity that
    # is linked to the bridge
    sensor_device = device_registry.async_get(occ1.device_id)
    assert sensor_device.manufacturer == 'ecobee Inc.'
    assert sensor_device.name == 'Kitchen'
    assert sensor_device.model == 'REMOTE SENSOR'
    assert sensor_device.sw_version == '1.0.0'
    assert sensor_device.via_device_id == climate_device.id


async def test_ecobee3_setup_from_cache(hass, hass_storage):
    """Test that Ecbobee can be correctly setup from its cached entity map."""
    accessories = await setup_accessories_from_file(hass, 'ecobee3.json')

    hass_storage['homekit_controller-entity-map'] = {
        'version': 1,
        'data': {
            'pairings': {
                '00:00:00:00:00:00': {
                    'config_num': 1,
                    'accessories': [
                        a.to_accessory_and_service_list() for a in accessories
                    ],
                }
            }
        }
    }

    await setup_test_accessories(hass, accessories)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    climate = entity_registry.async_get('climate.homew')
    assert climate.unique_id == 'homekit-123456789012-16'

    occ1 = entity_registry.async_get('binary_sensor.kitchen')
    assert occ1.unique_id == 'homekit-AB1C-56'

    occ2 = entity_registry.async_get('binary_sensor.porch')
    assert occ2.unique_id == 'homekit-AB2C-56'

    occ3 = entity_registry.async_get('binary_sensor.basement')
    assert occ3.unique_id == 'homekit-AB3C-56'


async def test_ecobee3_setup_connection_failure(hass):
    """Test that Ecbobee can be correctly setup from its cached entity map."""
    accessories = await setup_accessories_from_file(hass, 'ecobee3.json')

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    # Test that the connection fails during initial setup.
    # No entities should be created.
    list_accessories = 'list_accessories_and_characteristics'
    with mock.patch.object(FakePairing, list_accessories) as laac:
        laac.side_effect = AccessoryDisconnectedError('Connection failed')

        # If there is no cached entity map and the accessory connection is
        # failing then we have to fail the config entry setup.
        with pytest.raises(ConfigEntryNotReady):
            await setup_test_accessories(hass, accessories)

    climate = entity_registry.async_get('climate.homew')
    assert climate is None

    # When accessory raises ConfigEntryNoteReady HA will retry - lets make
    # sure there is no cruft causing conflicts left behind by now doing
    # a successful setup.
    await setup_test_accessories(hass, accessories)

    climate = entity_registry.async_get('climate.homew')
    assert climate.unique_id == 'homekit-123456789012-16'

    occ1 = entity_registry.async_get('binary_sensor.kitchen')
    assert occ1.unique_id == 'homekit-AB1C-56'

    occ2 = entity_registry.async_get('binary_sensor.porch')
    assert occ2.unique_id == 'homekit-AB2C-56'

    occ3 = entity_registry.async_get('binary_sensor.basement')
    assert occ3.unique_id == 'homekit-AB3C-56'


async def test_ecobee3_add_sensors_at_runtime(hass):
    """Test that new sensors are automatically added."""
    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    # Set up a base Ecobee 3 with no additional sensors.
    # There shouldn't be any entities but climate visible.
    accessories = await setup_accessories_from_file(
        hass, 'ecobee3_no_sensors.json')
    await setup_test_accessories(hass, accessories)

    climate = entity_registry.async_get('climate.homew')
    assert climate.unique_id == 'homekit-123456789012-16'

    occ1 = entity_registry.async_get('binary_sensor.kitchen')
    assert occ1 is None

    occ2 = entity_registry.async_get('binary_sensor.porch')
    assert occ2 is None

    occ3 = entity_registry.async_get('binary_sensor.basement')
    assert occ3 is None

    # Now added 3 new sensors at runtime - sensors should appear and climate
    # shouldn't be duplicated.
    accessories = await setup_accessories_from_file(hass, 'ecobee3.json')
    await device_config_changed(hass, accessories)

    occ1 = entity_registry.async_get('binary_sensor.kitchen')
    assert occ1.unique_id == 'homekit-AB1C-56'

    occ2 = entity_registry.async_get('binary_sensor.porch')
    assert occ2.unique_id == 'homekit-AB2C-56'

    occ3 = entity_registry.async_get('binary_sensor.basement')
    assert occ3.unique_id == 'homekit-AB3C-56'
