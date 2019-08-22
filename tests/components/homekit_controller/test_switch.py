"""Basic checks for HomeKitSwitch."""
from tests.components.homekit_controller.common import (
    setup_test_component)


async def test_switch_change_outlet_state(hass, utcnow):
    """Test that we can turn a HomeKit outlet on and off again."""
    from homekit.model.services import OutletService

    helper = await setup_test_component(hass, [OutletService()])

    await hass.services.async_call('switch', 'turn_on', {
        'entity_id': 'switch.testdevice',
    }, blocking=True)
    assert helper.characteristics[('outlet', 'on')].value == 1

    await hass.services.async_call('switch', 'turn_off', {
        'entity_id': 'switch.testdevice',
    }, blocking=True)
    assert helper.characteristics[('outlet', 'on')].value == 0


async def test_switch_read_outlet_state(hass, utcnow):
    """Test that we can read the state of a HomeKit outlet accessory."""
    from homekit.model.services import OutletService

    helper = await setup_test_component(hass, [OutletService()])

    # Initial state is that the switch is off and the outlet isn't in use
    switch_1 = await helper.poll_and_get_state()
    assert switch_1.state == 'off'
    assert switch_1.attributes['outlet_in_use'] is False

    # Simulate that someone switched on the device in the real world not via HA
    helper.characteristics[('outlet', 'on')].set_value(True)
    switch_1 = await helper.poll_and_get_state()
    assert switch_1.state == 'on'
    assert switch_1.attributes['outlet_in_use'] is False

    # Simulate that device switched off in the real world not via HA
    helper.characteristics[('outlet', 'on')].set_value(False)
    switch_1 = await helper.poll_and_get_state()
    assert switch_1.state == 'off'

    # Simulate that someone plugged something into the device
    helper.characteristics[('outlet', 'outlet-in-use')].value = True
    switch_1 = await helper.poll_and_get_state()
    assert switch_1.state == 'off'
    assert switch_1.attributes['outlet_in_use'] is True
