"""Support for Nest thermostats."""
import logging

import voluptuous as vol

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateDevice
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW, STATE_AUTO, STATE_COOL,
    STATE_ECO, STATE_HEAT, SUPPORT_AWAY_MODE, SUPPORT_FAN_MODE,
    SUPPORT_OPERATION_MODE, SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_HIGH, SUPPORT_TARGET_TEMPERATURE_LOW)
from homeassistant.const import (
    ATTR_TEMPERATURE, CONF_SCAN_INTERVAL, STATE_OFF, STATE_ON, TEMP_CELSIUS,
    TEMP_FAHRENHEIT)
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DATA_NEST, DOMAIN as NEST_DOMAIN, SIGNAL_NEST_UPDATE

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_SCAN_INTERVAL):
        vol.All(vol.Coerce(int), vol.Range(min=1)),
})

NEST_MODE_HEAT_COOL = 'heat-cool'


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Nest thermostat.

    No longer in use.
    """


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Nest climate device based on a config entry."""
    temp_unit = hass.config.units.temperature_unit

    thermostats = await hass.async_add_job(hass.data[DATA_NEST].thermostats)

    all_devices = [NestThermostat(structure, device, temp_unit)
                   for structure, device in thermostats]

    async_add_entities(all_devices, True)


class NestThermostat(ClimateDevice):
    """Representation of a Nest thermostat."""

    def __init__(self, structure, device, temp_unit):
        """Initialize the thermostat."""
        self._unit = temp_unit
        self.structure = structure
        self.device = device
        self._fan_list = [STATE_ON, STATE_AUTO]

        # Set the default supported features
        self._support_flags = (SUPPORT_TARGET_TEMPERATURE |
                               SUPPORT_OPERATION_MODE | SUPPORT_AWAY_MODE)

        # Not all nest devices support cooling and heating remove unused
        self._operation_list = [STATE_OFF]

        # Add supported nest thermostat features
        if self.device.can_heat:
            self._operation_list.append(STATE_HEAT)

        if self.device.can_cool:
            self._operation_list.append(STATE_COOL)

        if self.device.can_heat and self.device.can_cool:
            self._operation_list.append(STATE_AUTO)
            self._support_flags = (self._support_flags |
                                   SUPPORT_TARGET_TEMPERATURE_HIGH |
                                   SUPPORT_TARGET_TEMPERATURE_LOW)

        self._operation_list.append(STATE_ECO)

        # feature of device
        self._has_fan = self.device.has_fan
        if self._has_fan:
            self._support_flags = (self._support_flags | SUPPORT_FAN_MODE)

        # data attributes
        self._away = None
        self._location = None
        self._name = None
        self._humidity = None
        self._target_temperature = None
        self._temperature = None
        self._temperature_scale = None
        self._mode = None
        self._fan = None
        self._eco_temperature = None
        self._is_locked = None
        self._locked_temperature = None
        self._min_temperature = None
        self._max_temperature = None

    @property
    def should_poll(self):
        """Do not need poll thanks using Nest streaming API."""
        return False

    async def async_added_to_hass(self):
        """Register update signal handler."""
        async def async_update_state():
            """Update device state."""
            await self.async_update_ha_state(True)

        async_dispatcher_connect(self.hass, SIGNAL_NEST_UPDATE,
                                 async_update_state)

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags

    @property
    def unique_id(self):
        """Return unique ID for this device."""
        return self.device.serial

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            'identifiers': {
                (NEST_DOMAIN, self.device.device_id),
            },
            'name': self.device.name_long,
            'manufacturer': 'Nest Labs',
            'model': "Thermostat",
            'sw_version': self.device.software_version,
        }

    @property
    def name(self):
        """Return the name of the nest, if any."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._temperature_scale

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._temperature

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        if self._mode in [STATE_HEAT, STATE_COOL, STATE_OFF, STATE_ECO]:
            return self._mode
        if self._mode == NEST_MODE_HEAT_COOL:
            return STATE_AUTO
        return None

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self._mode not in (NEST_MODE_HEAT_COOL, STATE_ECO):
            return self._target_temperature
        return None

    @property
    def target_temperature_low(self):
        """Return the lower bound temperature we try to reach."""
        if self._mode == STATE_ECO:
            return self._eco_temperature[0]
        if self._mode == NEST_MODE_HEAT_COOL:
            return self._target_temperature[0]
        return None

    @property
    def target_temperature_high(self):
        """Return the upper bound temperature we try to reach."""
        if self._mode == STATE_ECO:
            return self._eco_temperature[1]
        if self._mode == NEST_MODE_HEAT_COOL:
            return self._target_temperature[1]
        return None

    @property
    def is_away_mode_on(self):
        """Return if away mode is on."""
        return self._away

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        import nest
        temp = None
        target_temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        target_temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        if self._mode == NEST_MODE_HEAT_COOL:
            if target_temp_low is not None and target_temp_high is not None:
                temp = (target_temp_low, target_temp_high)
                _LOGGER.debug("Nest set_temperature-output-value=%s", temp)
        else:
            temp = kwargs.get(ATTR_TEMPERATURE)
            _LOGGER.debug("Nest set_temperature-output-value=%s", temp)
        try:
            if temp is not None:
                self.device.target = temp
        except nest.nest.APIError as api_error:
            _LOGGER.error("An error occurred while setting temperature: %s",
                          api_error)
            # restore target temperature
            self.schedule_update_ha_state(True)

    def set_operation_mode(self, operation_mode):
        """Set operation mode."""
        if operation_mode in [STATE_HEAT, STATE_COOL, STATE_OFF, STATE_ECO]:
            device_mode = operation_mode
        elif operation_mode == STATE_AUTO:
            device_mode = NEST_MODE_HEAT_COOL
        else:
            device_mode = STATE_OFF
            _LOGGER.error(
                "An error occurred while setting device mode. "
                "Invalid operation mode: %s", operation_mode)
        self.device.mode = device_mode

    @property
    def operation_list(self):
        """List of available operation modes."""
        return self._operation_list

    def turn_away_mode_on(self):
        """Turn away on."""
        self.structure.away = True

    def turn_away_mode_off(self):
        """Turn away off."""
        self.structure.away = False

    @property
    def current_fan_mode(self):
        """Return whether the fan is on."""
        if self._has_fan:
            # Return whether the fan is on
            return STATE_ON if self._fan else STATE_AUTO
        # No Fan available so disable slider
        return None

    @property
    def fan_list(self):
        """List of available fan modes."""
        if self._has_fan:
            return self._fan_list
        return None

    def set_fan_mode(self, fan_mode):
        """Turn fan on/off."""
        if self._has_fan:
            self.device.fan = fan_mode.lower()

    @property
    def min_temp(self):
        """Identify min_temp in Nest API or defaults if not available."""
        return self._min_temperature

    @property
    def max_temp(self):
        """Identify max_temp in Nest API or defaults if not available."""
        return self._max_temperature

    def update(self):
        """Cache value from Python-nest."""
        self._location = self.device.where
        self._name = self.device.name
        self._humidity = self.device.humidity
        self._temperature = self.device.temperature
        self._mode = self.device.mode
        self._target_temperature = self.device.target
        self._fan = self.device.fan
        self._away = self.structure.away == 'away'
        self._eco_temperature = self.device.eco_temperature
        self._locked_temperature = self.device.locked_temperature
        self._min_temperature = self.device.min_temperature
        self._max_temperature = self.device.max_temperature
        self._is_locked = self.device.is_locked
        if self.device.temperature_scale == 'C':
            self._temperature_scale = TEMP_CELSIUS
        else:
            self._temperature_scale = TEMP_FAHRENHEIT
