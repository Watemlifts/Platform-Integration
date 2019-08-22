"""Support for VOC."""
import logging

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES, BinarySensorDevice)

from . import DATA_KEY, VolvoEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the Volvo sensors."""
    if discovery_info is None:
        return
    async_add_entities([VolvoSensor(hass.data[DATA_KEY], *discovery_info)])


class VolvoSensor(VolvoEntity, BinarySensorDevice):
    """Representation of a Volvo sensor."""

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        return self.instrument.is_on

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        if self.instrument.device_class in DEVICE_CLASSES:
            return self.instrument.device_class
        return None
