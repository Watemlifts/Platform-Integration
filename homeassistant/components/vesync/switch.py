"""Support for Etekcity VeSync switches."""
import logging
import voluptuous as vol
from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD)
import homeassistant.helpers.config_validation as cv


_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the VeSync switch platform."""
    from pyvesync_v2.vesync import VeSync

    switches = []

    manager = VeSync(config.get(CONF_USERNAME), config.get(CONF_PASSWORD))

    if not manager.login():
        _LOGGER.error("Unable to login to VeSync")
        return

    manager.update()

    if manager.devices is not None and manager.devices:
        if len(manager.devices) == 1:
            count_string = 'switch'
        else:
            count_string = 'switches'

        _LOGGER.info("Discovered %d VeSync %s",
                     len(manager.devices), count_string)

        for switch in manager.devices:
            switches.append(VeSyncSwitchHA(switch))
            _LOGGER.info("Added a VeSync switch named '%s'",
                         switch.device_name)
    else:
        _LOGGER.info("No VeSync devices found")

    add_entities(switches)


class VeSyncSwitchHA(SwitchDevice):
    """Representation of a VeSync switch."""

    def __init__(self, plug):
        """Initialize the VeSync switch device."""
        self.smartplug = plug
        self._current_power_w = None
        self._today_energy_kwh = None

    @property
    def unique_id(self):
        """Return the ID of this switch."""
        return self.smartplug.cid

    @property
    def name(self):
        """Return the name of the switch."""
        return self.smartplug.device_name

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        return self._current_power_w

    @property
    def today_energy_kwh(self):
        """Return the today total energy usage in kWh."""
        return self._today_energy_kwh

    @property
    def available(self) -> bool:
        """Return True if switch is available."""
        return self.smartplug.connection_status == "online"

    @property
    def is_on(self):
        """Return True if switch is on."""
        return self.smartplug.device_status == "on"

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self.smartplug.turn_on()

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self.smartplug.turn_off()

    def update(self):
        """Handle data changes for node values."""
        self.smartplug.update()
        if self.smartplug.devtype == 'outlet':
            self._current_power_w = self.smartplug.get_power()
            self._today_energy_kwh = self.smartplug.get_kwh_today()
