"""Support for LCN climate control."""
import pypck

from homeassistant.components.climate import ClimateDevice, const
from homeassistant.const import (
    ATTR_TEMPERATURE, CONF_ADDRESS, CONF_UNIT_OF_MEASUREMENT)

from . import LcnDevice
from .const import (
    CONF_CONNECTIONS, CONF_LOCKABLE, CONF_MAX_TEMP, CONF_MIN_TEMP,
    CONF_SETPOINT, CONF_SOURCE, DATA_LCN)
from .helpers import get_connection


async def async_setup_platform(hass, hass_config, async_add_entities,
                               discovery_info=None):
    """Set up the LCN climate platform."""
    if discovery_info is None:
        return

    devices = []
    for config in discovery_info:
        address, connection_id = config[CONF_ADDRESS]
        addr = pypck.lcn_addr.LcnAddr(*address)
        connections = hass.data[DATA_LCN][CONF_CONNECTIONS]
        connection = get_connection(connections, connection_id)
        address_connection = connection.get_address_conn(addr)

        devices.append(LcnClimate(config, address_connection))

    async_add_entities(devices)


class LcnClimate(LcnDevice, ClimateDevice):
    """Representation of a LCN climate device."""

    def __init__(self, config, address_connection):
        """Initialize of a LCN climate device."""
        super().__init__(config, address_connection)

        self.variable = pypck.lcn_defs.Var[config[CONF_SOURCE]]
        self.setpoint = pypck.lcn_defs.Var[config[CONF_SETPOINT]]
        self.unit = pypck.lcn_defs.VarUnit.parse(
            config[CONF_UNIT_OF_MEASUREMENT])

        self.regulator_id = \
            pypck.lcn_defs.Var.to_set_point_id(self.setpoint)
        self.is_lockable = config[CONF_LOCKABLE]
        self._max_temp = config[CONF_MAX_TEMP]
        self._min_temp = config[CONF_MIN_TEMP]

        self._current_temperature = None
        self._target_temperature = None
        self._is_on = None

        self.support = const.SUPPORT_TARGET_TEMPERATURE
        if self.is_lockable:
            self.support |= const.SUPPORT_ON_OFF

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        await self.address_connection.activate_status_request_handler(
            self.variable)
        await self.address_connection.activate_status_request_handler(
            self.setpoint)

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self.support

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self.unit.value

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def is_on(self):
        """Return true if the device is on."""
        return self._is_on

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self._max_temp

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self._min_temp

    async def async_turn_on(self):
        """Turn on."""
        self._is_on = True
        self.address_connection.lock_regulator(self.regulator_id, False)
        await self.async_update_ha_state()

    async def async_turn_off(self):
        """Turn off."""
        self._is_on = False
        self.address_connection.lock_regulator(self.regulator_id, True)
        self._target_temperature = None
        await self.async_update_ha_state()

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        self._target_temperature = temperature
        self.address_connection.var_abs(
            self.setpoint, self._target_temperature, self.unit)
        await self.async_update_ha_state()

    def input_received(self, input_obj):
        """Set temperature value when LCN input object is received."""
        if not isinstance(input_obj, pypck.inputs.ModStatusVar):
            return

        if input_obj.get_var() == self.variable:
            self._current_temperature = \
                input_obj.get_value().to_var_unit(self.unit)
        elif input_obj.get_var() == self.setpoint:
            self._is_on = not input_obj.get_value().is_locked_regulator()
            if self.is_on:
                self._target_temperature = \
                    input_obj.get_value().to_var_unit(self.unit)

        self.async_schedule_update_ha_state()
