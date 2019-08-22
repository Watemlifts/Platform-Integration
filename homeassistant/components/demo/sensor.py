"""Demo platform that has a couple of fake sensors."""
from homeassistant.const import (
    ATTR_BATTERY_LEVEL, TEMP_CELSIUS, DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE)
from homeassistant.helpers.entity import Entity


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Demo sensors."""
    add_entities([
        DemoSensor('Outside Temperature', 15.6, DEVICE_CLASS_TEMPERATURE,
                   TEMP_CELSIUS, 12),
        DemoSensor('Outside Humidity', 54, DEVICE_CLASS_HUMIDITY, '%', None),
    ])


class DemoSensor(Entity):
    """Representation of a Demo sensor."""

    def __init__(self, name, state, device_class,
                 unit_of_measurement, battery):
        """Initialize the sensor."""
        self._name = name
        self._state = state
        self._device_class = device_class
        self._unit_of_measurement = unit_of_measurement
        self._battery = battery

    @property
    def should_poll(self):
        """No polling needed for a demo sensor."""
        return False

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._battery:
            return {
                ATTR_BATTERY_LEVEL: self._battery,
            }
