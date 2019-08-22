"""Support for deCONZ switches."""
from homeassistant.components.switch import SwitchDevice
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import NEW_LIGHT, POWER_PLUGS, SIRENS
from .deconz_device import DeconzDevice
from .gateway import get_gateway_from_config_entry


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Old way of setting up deCONZ platforms."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up switches for deCONZ component.

    Switches are based same device class as lights in deCONZ.
    """
    gateway = get_gateway_from_config_entry(hass, config_entry)

    @callback
    def async_add_switch(lights):
        """Add switch from deCONZ."""
        entities = []

        for light in lights:

            if light.type in POWER_PLUGS:
                entities.append(DeconzPowerPlug(light, gateway))

            elif light.type in SIRENS:
                entities.append(DeconzSiren(light, gateway))

        async_add_entities(entities, True)

    gateway.listeners.append(async_dispatcher_connect(
        hass, gateway.async_event_new_device(NEW_LIGHT), async_add_switch))

    async_add_switch(gateway.api.lights.values())


class DeconzPowerPlug(DeconzDevice, SwitchDevice):
    """Representation of a deCONZ power plug."""

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._device.state

    async def async_turn_on(self, **kwargs):
        """Turn on switch."""
        data = {'on': True}
        await self._device.async_set_state(data)

    async def async_turn_off(self, **kwargs):
        """Turn off switch."""
        data = {'on': False}
        await self._device.async_set_state(data)


class DeconzSiren(DeconzDevice, SwitchDevice):
    """Representation of a deCONZ siren."""

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._device.alert == 'lselect'

    async def async_turn_on(self, **kwargs):
        """Turn on switch."""
        data = {'alert': 'lselect'}
        await self._device.async_set_state(data)

    async def async_turn_off(self, **kwargs):
        """Turn off switch."""
        data = {'alert': 'none'}
        await self._device.async_set_state(data)
