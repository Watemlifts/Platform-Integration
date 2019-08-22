"""Support for Zigbee sensors."""
from binascii import hexlify
import logging

import voluptuous as vol

from homeassistant.components import zigbee
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity import Entity

from . import PLATFORM_SCHEMA

_LOGGER = logging.getLogger(__name__)

CONF_TYPE = 'type'
CONF_MAX_VOLTS = 'max_volts'

DEFAULT_VOLTS = 1.2
TYPES = ['analog', 'temperature']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_TYPE): vol.In(TYPES),
    vol.Optional(CONF_MAX_VOLTS, default=DEFAULT_VOLTS): vol.Coerce(float),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the ZigBee platform.

    Uses the 'type' config value to work out which type of ZigBee sensor we're
    dealing with and instantiates the relevant classes to handle it.
    """
    typ = config.get(CONF_TYPE)

    try:
        sensor_class, config_class = TYPE_CLASSES[typ]
    except KeyError:
        _LOGGER.exception("Unknown ZigBee sensor type: %s", typ)
        return

    add_entities([sensor_class(hass, config_class(config))], True)


class ZigBeeTemperatureSensor(Entity):
    """Representation of XBee Pro temperature sensor."""

    def __init__(self, hass, config):
        """Initialize the sensor."""
        self._config = config
        self._temp = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._config.name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._temp

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement the value is expressed in."""
        return TEMP_CELSIUS

    def update(self):
        """Get the latest data."""
        try:
            self._temp = zigbee.DEVICE.get_temperature(self._config.address)
        except zigbee.ZIGBEE_TX_FAILURE:
            _LOGGER.warning(
                "Transmission failure when attempting to get sample from "
                "ZigBee device at address: %s", hexlify(self._config.address))
        except zigbee.ZIGBEE_EXCEPTION as exc:
            _LOGGER.exception(
                "Unable to get sample from ZigBee device: %s", exc)


# This must be below the classes to which it refers.
TYPE_CLASSES = {
    "temperature": (ZigBeeTemperatureSensor, zigbee.ZigBeeConfig),
    "analog": (zigbee.ZigBeeAnalogIn, zigbee.ZigBeeAnalogInConfig)
}
