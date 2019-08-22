"""Test different accessory types: Fans."""
from collections import namedtuple
from unittest.mock import Mock

import pytest

from homeassistant.components.fan import (
    ATTR_DIRECTION, ATTR_OSCILLATING, ATTR_SPEED, ATTR_SPEED_LIST,
    DIRECTION_FORWARD, DIRECTION_REVERSE, DOMAIN, SPEED_HIGH, SPEED_LOW,
    SPEED_OFF, SUPPORT_DIRECTION, SUPPORT_OSCILLATE, SUPPORT_SET_SPEED)
from homeassistant.components.homekit.const import ATTR_VALUE
from homeassistant.components.homekit.util import HomeKitSpeedMapping
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES, STATE_OFF, STATE_ON,
    STATE_UNKNOWN)

from tests.common import async_mock_service
from tests.components.homekit.common import patch_debounce


@pytest.fixture(scope='module')
def cls():
    """Patch debounce decorator during import of type_fans."""
    patcher = patch_debounce()
    patcher.start()
    _import = __import__('homeassistant.components.homekit.type_fans',
                         fromlist=['Fan'])
    patcher_tuple = namedtuple('Cls', ['fan'])
    yield patcher_tuple(fan=_import.Fan)
    patcher.stop()


async def test_fan_basic(hass, hk_driver, cls, events):
    """Test fan with char state."""
    entity_id = 'fan.demo'

    hass.states.async_set(entity_id, STATE_ON, {ATTR_SUPPORTED_FEATURES: 0})
    await hass.async_block_till_done()
    acc = cls.fan(hass, hk_driver, 'Fan', entity_id, 2, None)

    assert acc.aid == 2
    assert acc.category == 3  # Fan
    assert acc.char_active.value == 0

    # If there are no speed_list values, then HomeKit speed is unsupported
    assert acc.char_speed is None

    await hass.async_add_job(acc.run)
    await hass.async_block_till_done()
    assert acc.char_active.value == 1

    hass.states.async_set(entity_id, STATE_OFF, {ATTR_SUPPORTED_FEATURES: 0})
    await hass.async_block_till_done()
    assert acc.char_active.value == 0

    hass.states.async_set(entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert acc.char_active.value == 0

    hass.states.async_remove(entity_id)
    await hass.async_block_till_done()
    assert acc.char_active.value == 0

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, DOMAIN, 'turn_on')
    call_turn_off = async_mock_service(hass, DOMAIN, 'turn_off')

    await hass.async_add_job(acc.char_active.client_update_value, 1)
    await hass.async_block_till_done()
    assert call_turn_on
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] is None

    hass.states.async_set(entity_id, STATE_ON)
    await hass.async_block_till_done()

    await hass.async_add_job(acc.char_active.client_update_value, 0)
    await hass.async_block_till_done()
    assert call_turn_off
    assert call_turn_off[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] is None


async def test_fan_direction(hass, hk_driver, cls, events):
    """Test fan with direction."""
    entity_id = 'fan.demo'

    hass.states.async_set(entity_id, STATE_ON, {
        ATTR_SUPPORTED_FEATURES: SUPPORT_DIRECTION,
        ATTR_DIRECTION: DIRECTION_FORWARD})
    await hass.async_block_till_done()
    acc = cls.fan(hass, hk_driver, 'Fan', entity_id, 2, None)

    assert acc.char_direction.value == 0

    await hass.async_add_job(acc.run)
    await hass.async_block_till_done()
    assert acc.char_direction.value == 0

    hass.states.async_set(entity_id, STATE_ON,
                          {ATTR_DIRECTION: DIRECTION_REVERSE})
    await hass.async_block_till_done()
    assert acc.char_direction.value == 1

    # Set from HomeKit
    call_set_direction = async_mock_service(hass, DOMAIN, 'set_direction')

    await hass.async_add_job(acc.char_direction.client_update_value, 0)
    await hass.async_block_till_done()
    assert call_set_direction[0]
    assert call_set_direction[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_direction[0].data[ATTR_DIRECTION] == DIRECTION_FORWARD
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] == DIRECTION_FORWARD

    await hass.async_add_job(acc.char_direction.client_update_value, 1)
    await hass.async_block_till_done()
    assert call_set_direction[1]
    assert call_set_direction[1].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_direction[1].data[ATTR_DIRECTION] == DIRECTION_REVERSE
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] == DIRECTION_REVERSE


async def test_fan_oscillate(hass, hk_driver, cls, events):
    """Test fan with oscillate."""
    entity_id = 'fan.demo'

    hass.states.async_set(entity_id, STATE_ON, {
        ATTR_SUPPORTED_FEATURES: SUPPORT_OSCILLATE, ATTR_OSCILLATING: False})
    await hass.async_block_till_done()
    acc = cls.fan(hass, hk_driver, 'Fan', entity_id, 2, None)

    assert acc.char_swing.value == 0

    await hass.async_add_job(acc.run)
    await hass.async_block_till_done()
    assert acc.char_swing.value == 0

    hass.states.async_set(entity_id, STATE_ON, {ATTR_OSCILLATING: True})
    await hass.async_block_till_done()
    assert acc.char_swing.value == 1

    # Set from HomeKit
    call_oscillate = async_mock_service(hass, DOMAIN, 'oscillate')

    await hass.async_add_job(acc.char_swing.client_update_value, 0)
    await hass.async_block_till_done()
    assert call_oscillate[0]
    assert call_oscillate[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_oscillate[0].data[ATTR_OSCILLATING] is False
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] is False

    await hass.async_add_job(acc.char_swing.client_update_value, 1)
    await hass.async_block_till_done()
    assert call_oscillate[1]
    assert call_oscillate[1].data[ATTR_ENTITY_ID] == entity_id
    assert call_oscillate[1].data[ATTR_OSCILLATING] is True
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] is True


async def test_fan_speed(hass, hk_driver, cls, events):
    """Test fan with speed."""
    entity_id = 'fan.demo'
    speed_list = [SPEED_OFF, SPEED_LOW, SPEED_HIGH]

    hass.states.async_set(entity_id, STATE_ON, {
        ATTR_SUPPORTED_FEATURES: SUPPORT_SET_SPEED, ATTR_SPEED: SPEED_OFF,
        ATTR_SPEED_LIST: speed_list})
    await hass.async_block_till_done()
    acc = cls.fan(hass, hk_driver, 'Fan', entity_id, 2, None)
    assert acc.char_speed.value == 0

    await hass.async_add_job(acc.run)
    assert acc.speed_mapping.speed_ranges == \
        HomeKitSpeedMapping(speed_list).speed_ranges

    acc.speed_mapping.speed_to_homekit = Mock(return_value=42)
    acc.speed_mapping.speed_to_states = Mock(return_value='ludicrous')

    hass.states.async_set(entity_id, STATE_ON, {ATTR_SPEED: SPEED_HIGH})
    await hass.async_block_till_done()
    acc.speed_mapping.speed_to_homekit.assert_called_with(SPEED_HIGH)
    assert acc.char_speed.value == 42

    # Set from HomeKit
    call_set_speed = async_mock_service(hass, DOMAIN, 'set_speed')

    await hass.async_add_job(acc.char_speed.client_update_value, 42)
    await hass.async_block_till_done()
    acc.speed_mapping.speed_to_states.assert_called_with(42)
    assert call_set_speed[0]
    assert call_set_speed[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_speed[0].data[ATTR_SPEED] == 'ludicrous'
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] == 'ludicrous'
