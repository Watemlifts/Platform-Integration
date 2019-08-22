"""Support for OpenUV sensors."""
import logging

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util.dt import as_local, parse_datetime

from . import (
    DATA_OPENUV_CLIENT, DATA_UV, DOMAIN, SENSORS, TOPIC_UPDATE,
    TYPE_CURRENT_OZONE_LEVEL, TYPE_CURRENT_UV_INDEX, TYPE_CURRENT_UV_LEVEL,
    TYPE_MAX_UV_INDEX, TYPE_SAFE_EXPOSURE_TIME_1, TYPE_SAFE_EXPOSURE_TIME_2,
    TYPE_SAFE_EXPOSURE_TIME_3, TYPE_SAFE_EXPOSURE_TIME_4,
    TYPE_SAFE_EXPOSURE_TIME_5, TYPE_SAFE_EXPOSURE_TIME_6, OpenUvEntity)

_LOGGER = logging.getLogger(__name__)

ATTR_MAX_UV_TIME = 'time'

EXPOSURE_TYPE_MAP = {
    TYPE_SAFE_EXPOSURE_TIME_1: 'st1',
    TYPE_SAFE_EXPOSURE_TIME_2: 'st2',
    TYPE_SAFE_EXPOSURE_TIME_3: 'st3',
    TYPE_SAFE_EXPOSURE_TIME_4: 'st4',
    TYPE_SAFE_EXPOSURE_TIME_5: 'st5',
    TYPE_SAFE_EXPOSURE_TIME_6: 'st6'
}

UV_LEVEL_EXTREME = 'Extreme'
UV_LEVEL_VHIGH = 'Very High'
UV_LEVEL_HIGH = 'High'
UV_LEVEL_MODERATE = 'Moderate'
UV_LEVEL_LOW = 'Low'


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up an OpenUV sensor based on existing config."""
    pass


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up a Nest sensor based on a config entry."""
    openuv = hass.data[DOMAIN][DATA_OPENUV_CLIENT][entry.entry_id]

    sensors = []
    for sensor_type in openuv.sensor_conditions:
        name, icon, unit = SENSORS[sensor_type]
        sensors.append(
            OpenUvSensor(
                openuv, sensor_type, name, icon, unit, entry.entry_id))

    async_add_entities(sensors, True)


class OpenUvSensor(OpenUvEntity):
    """Define a binary sensor for OpenUV."""

    def __init__(self, openuv, sensor_type, name, icon, unit, entry_id):
        """Initialize the sensor."""
        super().__init__(openuv)

        self._async_unsub_dispatcher_connect = None
        self._entry_id = entry_id
        self._icon = icon
        self._latitude = openuv.client.latitude
        self._longitude = openuv.client.longitude
        self._name = name
        self._sensor_type = sensor_type
        self._state = None
        self._unit = unit

    @property
    def icon(self):
        """Return the icon."""
        return self._icon

    @property
    def should_poll(self):
        """Disable polling."""
        return False

    @property
    def state(self):
        """Return the status of the sensor."""
        return self._state

    @property
    def unique_id(self) -> str:
        """Return a unique, HASS-friendly identifier for this entity."""
        return '{0}_{1}_{2}'.format(
            self._latitude, self._longitude, self._sensor_type)

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit

    async def async_added_to_hass(self):
        """Register callbacks."""
        @callback
        def update():
            """Update the state."""
            self.async_schedule_update_ha_state(True)

        self._async_unsub_dispatcher_connect = async_dispatcher_connect(
            self.hass, TOPIC_UPDATE, update)

    async def async_will_remove_from_hass(self):
        """Disconnect dispatcher listener when removed."""
        if self._async_unsub_dispatcher_connect:
            self._async_unsub_dispatcher_connect()

    async def async_update(self):
        """Update the state."""
        data = self.openuv.data[DATA_UV]['result']
        if self._sensor_type == TYPE_CURRENT_OZONE_LEVEL:
            self._state = data['ozone']
        elif self._sensor_type == TYPE_CURRENT_UV_INDEX:
            self._state = data['uv']
        elif self._sensor_type == TYPE_CURRENT_UV_LEVEL:
            if data['uv'] >= 11:
                self._state = UV_LEVEL_EXTREME
            elif data['uv'] >= 8:
                self._state = UV_LEVEL_VHIGH
            elif data['uv'] >= 6:
                self._state = UV_LEVEL_HIGH
            elif data['uv'] >= 3:
                self._state = UV_LEVEL_MODERATE
            else:
                self._state = UV_LEVEL_LOW
        elif self._sensor_type == TYPE_MAX_UV_INDEX:
            self._state = data['uv_max']
            self._attrs.update({
                ATTR_MAX_UV_TIME: as_local(parse_datetime(data['uv_max_time']))
            })
        elif self._sensor_type in (TYPE_SAFE_EXPOSURE_TIME_1,
                                   TYPE_SAFE_EXPOSURE_TIME_2,
                                   TYPE_SAFE_EXPOSURE_TIME_3,
                                   TYPE_SAFE_EXPOSURE_TIME_4,
                                   TYPE_SAFE_EXPOSURE_TIME_5,
                                   TYPE_SAFE_EXPOSURE_TIME_6):
            self._state = data['safe_exposure_time'][EXPOSURE_TYPE_MAP[
                self._sensor_type]]
