"""Support for Fibaro switches."""
import logging

from homeassistant.components.switch import ENTITY_ID_FORMAT, SwitchDevice
from homeassistant.util import convert

from . import FIBARO_DEVICES, FibaroDevice

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Fibaro switches."""
    if discovery_info is None:
        return

    add_entities(
        [FibaroSwitch(device) for
         device in hass.data[FIBARO_DEVICES]['switch']], True)


class FibaroSwitch(FibaroDevice, SwitchDevice):
    """Representation of a Fibaro Switch."""

    def __init__(self, fibaro_device):
        """Initialize the Fibaro device."""
        self._state = False
        super().__init__(fibaro_device)
        self.entity_id = ENTITY_ID_FORMAT.format(self.ha_id)

    def turn_on(self, **kwargs):
        """Turn device on."""
        self.call_turn_on()
        self._state = True

    def turn_off(self, **kwargs):
        """Turn device off."""
        self.call_turn_off()
        self._state = False

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        if 'power' in self.fibaro_device.interfaces:
            return convert(self.fibaro_device.properties.power, float, 0.0)
        return None

    @property
    def today_energy_kwh(self):
        """Return the today total energy usage in kWh."""
        if 'energy' in self.fibaro_device.interfaces:
            return convert(self.fibaro_device.properties.energy, float, 0.0)
        return None

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def update(self):
        """Update device state."""
        self._state = self.current_binary_state
