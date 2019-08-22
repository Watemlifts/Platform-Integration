"""Support for interface with an Harman/Kardon or JBL AVR."""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.media_player import (
    MediaPlayerDevice, PLATFORM_SCHEMA)
from homeassistant.components.media_player.const import (
    SUPPORT_TURN_OFF, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_STEP,
    SUPPORT_TURN_ON, SUPPORT_SELECT_SOURCE)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PORT, STATE_OFF, STATE_ON)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Harman Kardon AVR'
DEFAULT_PORT = 10025

SUPPORT_HARMAN_KARDON_AVR = SUPPORT_VOLUME_STEP | SUPPORT_VOLUME_MUTE | \
                            SUPPORT_TURN_OFF | SUPPORT_TURN_ON | \
                            SUPPORT_SELECT_SOURCE

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})


def setup_platform(hass, config, add_entities, discover_info=None):
    """Set up the AVR platform."""
    import hkavr

    name = config[CONF_NAME]
    host = config[CONF_HOST]
    port = config[CONF_PORT]

    avr = hkavr.HkAVR(host, port, name)
    avr_device = HkAvrDevice(avr)

    add_entities([avr_device], True)


class HkAvrDevice(MediaPlayerDevice):
    """Representation of a Harman Kardon AVR / JBL AVR TV."""

    def __init__(self, avr):
        """Initialize a new HarmanKardonAVR."""
        self._avr = avr

        self._name = avr.name
        self._host = avr.host
        self._port = avr.port

        self._source_list = avr.sources

        self._state = None
        self._muted = avr.muted
        self._current_source = avr.current_source

    def update(self):
        """Update the state of this media_player."""
        if self._avr.is_on():
            self._state = STATE_ON
        elif self._avr.is_off():
            self._state = STATE_OFF
        else:
            self._state = None

        self._muted = self._avr.muted
        self._current_source = self._avr.current_source

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def is_volume_muted(self):
        """Muted status not available."""
        return self._muted

    @property
    def source(self):
        """Return the current input source."""
        return self._current_source

    @property
    def source_list(self):
        """Available sources."""
        return self._source_list

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_HARMAN_KARDON_AVR

    def turn_on(self):
        """Turn the AVR on."""
        self._avr.power_on()

    def turn_off(self):
        """Turn off the AVR."""
        self._avr.power_off()

    def select_source(self, source):
        """Select input source."""
        return self._avr.select_source(source)

    def volume_up(self):
        """Volume up the AVR."""
        return self._avr.volume_up()

    def volume_down(self):
        """Volume down AVR."""
        return self._avr.volume_down()

    def mute_volume(self, mute):
        """Send mute command."""
        return self._avr.mute(mute)
