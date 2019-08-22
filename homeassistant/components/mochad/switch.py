"""Support for X10 switch over Mochad."""
import logging

import voluptuous as vol

from homeassistant.components import mochad
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import (CONF_NAME, CONF_DEVICES,
                                 CONF_PLATFORM, CONF_ADDRESS)
from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): mochad.DOMAIN,
    CONF_DEVICES: [{
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_ADDRESS): cv.x10_address,
        vol.Optional(mochad.CONF_COMM_TYPE): cv.string,
    }]
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up X10 switches over a mochad controller."""
    devs = config.get(CONF_DEVICES)
    add_entities([MochadSwitch(
        hass, mochad.CONTROLLER.ctrl, dev) for dev in devs])
    return True


class MochadSwitch(SwitchDevice):
    """Representation of a X10 switch over Mochad."""

    def __init__(self, hass, ctrl, dev):
        """Initialize a Mochad Switch Device."""
        from pymochad import device

        self._controller = ctrl
        self._address = dev[CONF_ADDRESS]
        self._name = dev.get(CONF_NAME, 'x10_switch_dev_%s' % self._address)
        self._comm_type = dev.get(mochad.CONF_COMM_TYPE, 'pl')
        self.switch = device.Device(
            ctrl, self._address, comm_type=self._comm_type)
        # Init with false to avoid locking HA for long on CM19A (goes from rf
        # to pl via TM751, but not other way around)
        if self._comm_type == 'pl':
            self._state = self._get_device_status()
        else:
            self._state = False

    @property
    def name(self):
        """Get the name of the switch."""
        return self._name

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        from pymochad.exceptions import MochadException
        _LOGGER.debug("Reconnect %s:%s", self._controller.server,
                      self._controller.port)
        with mochad.REQ_LOCK:
            try:
                # Recycle socket on new command to recover mochad connection
                self._controller.reconnect()
                self.switch.send_cmd('on')
                # No read data on CM19A which is rf only
                if self._comm_type == 'pl':
                    self._controller.read_data()
                self._state = True
            except (MochadException, OSError) as exc:
                _LOGGER.error("Error with mochad communication: %s", exc)

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        from pymochad.exceptions import MochadException
        _LOGGER.debug("Reconnect %s:%s", self._controller.server,
                      self._controller.port)
        with mochad.REQ_LOCK:
            try:
                # Recycle socket on new command to recover mochad connection
                self._controller.reconnect()
                self.switch.send_cmd('off')
                # No read data on CM19A which is rf only
                if self._comm_type == 'pl':
                    self._controller.read_data()
                self._state = False
            except (MochadException, OSError) as exc:
                _LOGGER.error("Error with mochad communication: %s", exc)

    def _get_device_status(self):
        """Get the status of the switch from mochad."""
        with mochad.REQ_LOCK:
            status = self.switch.get_status().rstrip()
        return status == 'on'

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state
