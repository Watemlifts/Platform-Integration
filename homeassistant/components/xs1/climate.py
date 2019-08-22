"""Support for XS1 climate devices."""
from functools import partial
import logging

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import SUPPORT_TARGET_TEMPERATURE
from homeassistant.const import ATTR_TEMPERATURE

from . import ACTUATORS, DOMAIN as COMPONENT_DOMAIN, SENSORS, XS1DeviceEntity

_LOGGER = logging.getLogger(__name__)

MIN_TEMP = 8
MAX_TEMP = 25


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the XS1 thermostat platform."""
    from xs1_api_client.api_constants import ActuatorType

    actuators = hass.data[COMPONENT_DOMAIN][ACTUATORS]
    sensors = hass.data[COMPONENT_DOMAIN][SENSORS]

    thermostat_entities = []
    for actuator in actuators:
        if actuator.type() == ActuatorType.TEMPERATURE:
            # Search for a matching sensor (by name)
            actuator_name = actuator.name()

            matching_sensor = None
            for sensor in sensors:
                if actuator_name in sensor.name():
                    matching_sensor = sensor
                    break

            thermostat_entities.append(
                XS1ThermostatEntity(actuator, matching_sensor))

    async_add_entities(thermostat_entities)


class XS1ThermostatEntity(XS1DeviceEntity, ClimateDevice):
    """Representation of a XS1 thermostat."""

    def __init__(self, device, sensor):
        """Initialize the actuator."""
        super().__init__(device)
        self.sensor = sensor

    @property
    def name(self):
        """Return the name of the device if any."""
        return self.device.name()

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_TARGET_TEMPERATURE

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if self.sensor is None:
            return None

        return self.sensor.value()

    @property
    def temperature_unit(self):
        """Return the unit of measurement used by the platform."""
        return self.device.unit()

    @property
    def target_temperature(self):
        """Return the current target temperature."""
        return self.device.new_value()

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return MIN_TEMP

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return MAX_TEMP

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)

        self.device.set_value(temp)

        if self.sensor is not None:
            self.schedule_update_ha_state()

    async def async_update(self):
        """Also update the sensor when available."""
        await super().async_update()
        if self.sensor is not None:
            await self.hass.async_add_executor_job(
                partial(self.sensor.update))
