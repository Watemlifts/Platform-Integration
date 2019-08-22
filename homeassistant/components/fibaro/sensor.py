"""Support for Fibaro sensors."""
import logging

from homeassistant.components.sensor import ENTITY_ID_FORMAT
from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_ILLUMINANCE, DEVICE_CLASS_TEMPERATURE,
    TEMP_CELSIUS, TEMP_FAHRENHEIT)
from homeassistant.helpers.entity import Entity

from . import FIBARO_DEVICES, FibaroDevice

SENSOR_TYPES = {
    'com.fibaro.temperatureSensor':
        ['Temperature', None, None, DEVICE_CLASS_TEMPERATURE],
    'com.fibaro.smokeSensor':
        ['Smoke', 'ppm', 'mdi:fire', None],
    'CO2':
        ['CO2', 'ppm', 'mdi:cloud', None],
    'com.fibaro.humiditySensor':
        ['Humidity', '%', None, DEVICE_CLASS_HUMIDITY],
    'com.fibaro.lightSensor':
        ['Light', 'lx', None, DEVICE_CLASS_ILLUMINANCE]
}

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Fibaro controller devices."""
    if discovery_info is None:
        return

    add_entities(
        [FibaroSensor(device)
         for device in hass.data[FIBARO_DEVICES]['sensor']], True)


class FibaroSensor(FibaroDevice, Entity):
    """Representation of a Fibaro Sensor."""

    def __init__(self, fibaro_device):
        """Initialize the sensor."""
        self.current_value = None
        self.last_changed_time = None
        super().__init__(fibaro_device)
        self.entity_id = ENTITY_ID_FORMAT.format(self.ha_id)
        if fibaro_device.type in SENSOR_TYPES:
            self._unit = SENSOR_TYPES[fibaro_device.type][1]
            self._icon = SENSOR_TYPES[fibaro_device.type][2]
            self._device_class = SENSOR_TYPES[fibaro_device.type][3]
        else:
            self._unit = None
            self._icon = None
            self._device_class = None
        try:
            if not self._unit:
                if self.fibaro_device.properties.unit == 'lux':
                    self._unit = 'lx'
                elif self.fibaro_device.properties.unit == 'C':
                    self._unit = TEMP_CELSIUS
                elif self.fibaro_device.properties.unit == 'F':
                    self._unit = TEMP_FAHRENHEIT
                else:
                    self._unit = self.fibaro_device.properties.unit
        except (KeyError, ValueError):
            pass

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.current_value

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._device_class

    def update(self):
        """Update the state."""
        try:
            self.current_value = float(self.fibaro_device.properties.value)
        except (KeyError, ValueError):
            pass
