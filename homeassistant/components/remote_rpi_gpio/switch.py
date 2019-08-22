"""Allows to configure a switch using RPi GPIO."""
import logging

import voluptuous as vol

from homeassistant.components.switch import SwitchDevice, PLATFORM_SCHEMA
from homeassistant.const import DEVICE_DEFAULT_NAME, CONF_HOST

import homeassistant.helpers.config_validation as cv

from . import CONF_INVERT_LOGIC, DEFAULT_INVERT_LOGIC
from .. import remote_rpi_gpio

_LOGGER = logging.getLogger(__name__)

CONF_PORTS = 'ports'

_SENSORS_SCHEMA = vol.Schema({
    cv.positive_int: cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PORTS): _SENSORS_SCHEMA,
    vol.Optional(CONF_INVERT_LOGIC,
                 default=DEFAULT_INVERT_LOGIC): cv.boolean
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Remote Raspberry PI GPIO devices."""
    address = config[CONF_HOST]
    invert_logic = config[CONF_INVERT_LOGIC]
    ports = config[CONF_PORTS]

    devices = []
    for port, name in ports.items():
        try:
            led = remote_rpi_gpio.setup_output(
                address, port, invert_logic)
        except (ValueError, IndexError, KeyError, IOError):
            return
        new_switch = RemoteRPiGPIOSwitch(name, led, invert_logic)
        devices.append(new_switch)

    add_entities(devices)


class RemoteRPiGPIOSwitch(SwitchDevice):
    """Representation of a Remtoe Raspberry Pi GPIO."""

    def __init__(self, name, led, invert_logic):
        """Initialize the pin."""
        self._name = name or DEVICE_DEFAULT_NAME
        self._state = False
        self._invert_logic = invert_logic
        self._switch = led

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def assumed_state(self):
        """If unable to access real state of the entity."""
        return True

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the device on."""
        remote_rpi_gpio.write_output(self._switch,
                                     0 if self._invert_logic else 1)
        self._state = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        remote_rpi_gpio.write_output(self._switch,
                                     1 if self._invert_logic else 0)
        self._state = False
        self.schedule_update_ha_state()
