"""Support gathering system information of hosts which are running netdata."""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_HOST, CONF_ICON, CONF_NAME, CONF_PORT, CONF_RESOURCES)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)

CONF_DATA_GROUP = 'data_group'
CONF_ELEMENT = 'element'
CONF_INVERT = 'invert'

DEFAULT_HOST = 'localhost'
DEFAULT_NAME = 'Netdata'
DEFAULT_PORT = 19999

DEFAULT_ICON = 'mdi:desktop-classic'

RESOURCE_SCHEMA = vol.Any({
    vol.Required(CONF_DATA_GROUP): cv.string,
    vol.Required(CONF_ELEMENT): cv.string,
    vol.Optional(CONF_ICON, default=DEFAULT_ICON): cv.icon,
    vol.Optional(CONF_INVERT, default=False): cv.boolean,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Required(CONF_RESOURCES): vol.Schema({cv.string: RESOURCE_SCHEMA}),
})


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the Netdata sensor."""
    from netdata import Netdata

    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    resources = config.get(CONF_RESOURCES)

    session = async_get_clientsession(hass)
    netdata = NetdataData(Netdata(host, hass.loop, session, port=port))
    await netdata.async_update()

    if netdata.api.metrics is None:
        raise PlatformNotReady

    dev = []
    for entry, data in resources.items():
        icon = data[CONF_ICON]
        sensor = data[CONF_DATA_GROUP]
        element = data[CONF_ELEMENT]
        invert = data[CONF_INVERT]
        sensor_name = entry
        try:
            resource_data = netdata.api.metrics[sensor]
            unit = '%' if resource_data['units'] == 'percentage' else \
                resource_data['units']
        except KeyError:
            _LOGGER.error("Sensor is not available: %s", sensor)
            continue

        dev.append(NetdataSensor(
            netdata, name, sensor, sensor_name, element, icon, unit, invert))

    async_add_entities(dev, True)


class NetdataSensor(Entity):
    """Implementation of a Netdata sensor."""

    def __init__(
            self, netdata, name, sensor, sensor_name, element, icon, unit,
            invert):
        """Initialize the Netdata sensor."""
        self.netdata = netdata
        self._state = None
        self._sensor = sensor
        self._element = element
        self._sensor_name = self._sensor if sensor_name is None else \
            sensor_name
        self._name = name
        self._icon = icon
        self._unit_of_measurement = unit
        self._invert = invert

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self._name, self._sensor_name)

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._icon

    @property
    def state(self):
        """Return the state of the resources."""
        return self._state

    @property
    def available(self):
        """Could the resource be accessed during the last update call."""
        return self.netdata.available

    async def async_update(self):
        """Get the latest data from Netdata REST API."""
        await self.netdata.async_update()
        resource_data = self.netdata.api.metrics.get(self._sensor)
        self._state = round(
            resource_data['dimensions'][self._element]['value'], 2) \
            * (-1 if self._invert else 1)


class NetdataData:
    """The class for handling the data retrieval."""

    def __init__(self, api):
        """Initialize the data object."""
        self.api = api
        self.available = True

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Get the latest data from the Netdata REST API."""
        from netdata.exceptions import NetdataError

        try:
            await self.api.get_allmetrics()
            self.available = True
        except NetdataError:
            _LOGGER.error("Unable to retrieve data from Netdata")
            self.available = False
