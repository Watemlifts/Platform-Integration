"""Support for XS1 switches."""
import logging

from homeassistant.helpers.entity import ToggleEntity

from . import ACTUATORS, DOMAIN as COMPONENT_DOMAIN, XS1DeviceEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the XS1 switch platform."""
    from xs1_api_client.api_constants import ActuatorType

    actuators = hass.data[COMPONENT_DOMAIN][ACTUATORS]

    switch_entities = []
    for actuator in actuators:
        if (actuator.type() == ActuatorType.SWITCH) or \
                (actuator.type() == ActuatorType.DIMMER):
            switch_entities.append(XS1SwitchEntity(actuator))

    async_add_entities(switch_entities)


class XS1SwitchEntity(XS1DeviceEntity, ToggleEntity):
    """Representation of a XS1 switch actuator."""

    @property
    def name(self):
        """Return the name of the device if any."""
        return self.device.name()

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.device.value() == 100

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self.device.turn_on()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self.device.turn_off()
