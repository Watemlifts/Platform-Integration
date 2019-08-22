"""Support for Homematic thermostats."""
import logging

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    STATE_AUTO, STATE_MANUAL, SUPPORT_OPERATION_MODE,
    SUPPORT_TARGET_TEMPERATURE)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS

from . import ATTR_DISCOVER_DEVICES, HM_ATTRIBUTE_SUPPORT, HMDevice

_LOGGER = logging.getLogger(__name__)

STATE_BOOST = 'boost'
STATE_COMFORT = 'comfort'
STATE_LOWERING = 'lowering'

HM_STATE_MAP = {
    'AUTO_MODE': STATE_AUTO,
    'MANU_MODE': STATE_MANUAL,
    'BOOST_MODE': STATE_BOOST,
    'COMFORT_MODE': STATE_COMFORT,
    'LOWERING_MODE': STATE_LOWERING
}

HM_TEMP_MAP = [
    'ACTUAL_TEMPERATURE',
    'TEMPERATURE',
]

HM_HUMI_MAP = [
    'ACTUAL_HUMIDITY',
    'HUMIDITY',
]

HM_CONTROL_MODE = 'CONTROL_MODE'
HMIP_CONTROL_MODE = 'SET_POINT_MODE'

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Homematic thermostat platform."""
    if discovery_info is None:
        return

    devices = []
    for conf in discovery_info[ATTR_DISCOVER_DEVICES]:
        new_device = HMThermostat(conf)
        devices.append(new_device)

    add_entities(devices)


class HMThermostat(HMDevice, ClimateDevice):
    """Representation of a Homematic thermostat."""

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def temperature_unit(self):
        """Return the unit of measurement that is used."""
        return TEMP_CELSIUS

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        if HM_CONTROL_MODE not in self._data:
            return None

        # boost mode is active
        if self._data.get('BOOST_MODE', False):
            return STATE_BOOST

        # HmIP uses the set_point_mode to say if its
        # auto or manual
        if HMIP_CONTROL_MODE in self._data:
            code = self._data[HMIP_CONTROL_MODE]
        # Other devices use the control_mode
        else:
            code = self._data['CONTROL_MODE']

        # get the name of the mode
        name = HM_ATTRIBUTE_SUPPORT[HM_CONTROL_MODE][1][code]
        return name.lower()

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        # HMIP use set_point_mode for operation
        if HMIP_CONTROL_MODE in self._data:
            return [STATE_MANUAL, STATE_AUTO, STATE_BOOST]

        # HM
        op_list = []
        for mode in self._hmdevice.ACTIONNODE:
            if mode in HM_STATE_MAP:
                op_list.append(HM_STATE_MAP.get(mode))
        return op_list

    @property
    def current_humidity(self):
        """Return the current humidity."""
        for node in HM_HUMI_MAP:
            if node in self._data:
                return self._data[node]

    @property
    def current_temperature(self):
        """Return the current temperature."""
        for node in HM_TEMP_MAP:
            if node in self._data:
                return self._data[node]

    @property
    def target_temperature(self):
        """Return the target temperature."""
        return self._data.get(self._state)

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return None

        self._hmdevice.writeNodeData(self._state, float(temperature))

    def set_operation_mode(self, operation_mode):
        """Set new target operation mode."""
        for mode, state in HM_STATE_MAP.items():
            if state == operation_mode:
                code = getattr(self._hmdevice, mode, 0)
                self._hmdevice.MODE = code
                return

    @property
    def min_temp(self):
        """Return the minimum temperature - 4.5 means off."""
        return 4.5

    @property
    def max_temp(self):
        """Return the maximum temperature - 30.5 means on."""
        return 30.5

    def _init_data_struct(self):
        """Generate a data dict (self._data) from the Homematic metadata."""
        self._state = next(iter(self._hmdevice.WRITENODE.keys()))
        self._data[self._state] = None

        if HM_CONTROL_MODE in self._hmdevice.ATTRIBUTENODE or \
                HMIP_CONTROL_MODE in self._hmdevice.ATTRIBUTENODE:
            self._data[HM_CONTROL_MODE] = None

        for node in self._hmdevice.SENSORNODE.keys():
            self._data[node] = None
