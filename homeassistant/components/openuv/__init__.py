"""Support for UV data from openuv.io."""
import logging

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_API_KEY, CONF_BINARY_SENSORS, CONF_ELEVATION,
    CONF_LATITUDE, CONF_LONGITUDE, CONF_MONITORED_CONDITIONS, CONF_SENSORS)
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.service import verify_domain_control

from .config_flow import configured_instances
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_OPENUV_CLIENT = 'data_client'
DATA_OPENUV_LISTENER = 'data_listener'
DATA_PROTECTION_WINDOW = 'protection_window'
DATA_UV = 'uv'

DEFAULT_ATTRIBUTION = 'Data provided by OpenUV'

NOTIFICATION_ID = 'openuv_notification'
NOTIFICATION_TITLE = 'OpenUV Component Setup'

TOPIC_UPDATE = '{0}_data_update'.format(DOMAIN)

TYPE_CURRENT_OZONE_LEVEL = 'current_ozone_level'
TYPE_CURRENT_UV_INDEX = 'current_uv_index'
TYPE_CURRENT_UV_LEVEL = 'current_uv_level'
TYPE_MAX_UV_INDEX = 'max_uv_index'
TYPE_PROTECTION_WINDOW = 'uv_protection_window'
TYPE_SAFE_EXPOSURE_TIME_1 = 'safe_exposure_time_type_1'
TYPE_SAFE_EXPOSURE_TIME_2 = 'safe_exposure_time_type_2'
TYPE_SAFE_EXPOSURE_TIME_3 = 'safe_exposure_time_type_3'
TYPE_SAFE_EXPOSURE_TIME_4 = 'safe_exposure_time_type_4'
TYPE_SAFE_EXPOSURE_TIME_5 = 'safe_exposure_time_type_5'
TYPE_SAFE_EXPOSURE_TIME_6 = 'safe_exposure_time_type_6'

BINARY_SENSORS = {
    TYPE_PROTECTION_WINDOW: ('Protection Window', 'mdi:sunglasses')
}

BINARY_SENSOR_SCHEMA = vol.Schema({
    vol.Optional(CONF_MONITORED_CONDITIONS, default=list(BINARY_SENSORS)):
        vol.All(cv.ensure_list, [vol.In(BINARY_SENSORS)])
})

SENSORS = {
    TYPE_CURRENT_OZONE_LEVEL: (
        'Current Ozone Level', 'mdi:vector-triangle', 'du'),
    TYPE_CURRENT_UV_INDEX: ('Current UV Index', 'mdi:weather-sunny', 'index'),
    TYPE_CURRENT_UV_LEVEL: ('Current UV Level', 'mdi:weather-sunny', None),
    TYPE_MAX_UV_INDEX: ('Max UV Index', 'mdi:weather-sunny', 'index'),
    TYPE_SAFE_EXPOSURE_TIME_1: (
        'Skin Type 1 Safe Exposure Time', 'mdi:timer', 'minutes'),
    TYPE_SAFE_EXPOSURE_TIME_2: (
        'Skin Type 2 Safe Exposure Time', 'mdi:timer', 'minutes'),
    TYPE_SAFE_EXPOSURE_TIME_3: (
        'Skin Type 3 Safe Exposure Time', 'mdi:timer', 'minutes'),
    TYPE_SAFE_EXPOSURE_TIME_4: (
        'Skin Type 4 Safe Exposure Time', 'mdi:timer', 'minutes'),
    TYPE_SAFE_EXPOSURE_TIME_5: (
        'Skin Type 5 Safe Exposure Time', 'mdi:timer', 'minutes'),
    TYPE_SAFE_EXPOSURE_TIME_6: (
        'Skin Type 6 Safe Exposure Time', 'mdi:timer', 'minutes'),
}

SENSOR_SCHEMA = vol.Schema({
    vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SENSORS)):
        vol.All(cv.ensure_list, [vol.In(SENSORS)])
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_ELEVATION): float,
        vol.Optional(CONF_LATITUDE): cv.latitude,
        vol.Optional(CONF_LONGITUDE): cv.longitude,
        vol.Optional(CONF_BINARY_SENSORS, default={}):
            BINARY_SENSOR_SCHEMA,
        vol.Optional(CONF_SENSORS, default={}): SENSOR_SCHEMA,
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the OpenUV component."""
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_OPENUV_CLIENT] = {}
    hass.data[DOMAIN][DATA_OPENUV_LISTENER] = {}

    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    identifier = '{0}, {1}'.format(
        conf.get(CONF_LATITUDE, hass.config.latitude),
        conf.get(CONF_LONGITUDE, hass.config.longitude))
    if identifier in configured_instances(hass):
        return True

    data = {
        CONF_API_KEY: conf[CONF_API_KEY],
        CONF_BINARY_SENSORS: conf[CONF_BINARY_SENSORS],
        CONF_SENSORS: conf[CONF_SENSORS],
    }

    if CONF_LATITUDE in conf:
        data[CONF_LATITUDE] = conf[CONF_LATITUDE]
    if CONF_LONGITUDE in conf:
        data[CONF_LONGITUDE] = conf[CONF_LONGITUDE]
    if CONF_ELEVATION in conf:
        data[CONF_ELEVATION] = conf[CONF_ELEVATION]

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={'source': SOURCE_IMPORT}, data=data))

    return True


async def async_setup_entry(hass, config_entry):
    """Set up OpenUV as config entry."""
    from pyopenuv import Client
    from pyopenuv.errors import OpenUvError

    _verify_domain_control = verify_domain_control(hass, DOMAIN)

    try:
        websession = aiohttp_client.async_get_clientsession(hass)
        openuv = OpenUV(
            Client(
                config_entry.data[CONF_API_KEY],
                config_entry.data.get(CONF_LATITUDE, hass.config.latitude),
                config_entry.data.get(CONF_LONGITUDE, hass.config.longitude),
                websession,
                altitude=config_entry.data.get(
                    CONF_ELEVATION, hass.config.elevation)),
            config_entry.data.get(CONF_BINARY_SENSORS, {}).get(
                CONF_MONITORED_CONDITIONS, list(BINARY_SENSORS)),
            config_entry.data.get(CONF_SENSORS, {}).get(
                CONF_MONITORED_CONDITIONS, list(SENSORS)))
        await openuv.async_update()
        hass.data[DOMAIN][DATA_OPENUV_CLIENT][config_entry.entry_id] = openuv
    except OpenUvError as err:
        _LOGGER.error('Config entry failed: %s', err)
        raise ConfigEntryNotReady

    for component in ('binary_sensor', 'sensor'):
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(
                config_entry, component))

    @_verify_domain_control
    async def update_data(service):
        """Refresh OpenUV data."""
        _LOGGER.debug('Refreshing OpenUV data')

        try:
            await openuv.async_update()
        except OpenUvError as err:
            _LOGGER.error('Error during data update: %s', err)
            return

        async_dispatcher_send(hass, TOPIC_UPDATE)

    hass.services.async_register(DOMAIN, 'update_data', update_data)

    return True


async def async_unload_entry(hass, config_entry):
    """Unload an OpenUV config entry."""
    hass.data[DOMAIN][DATA_OPENUV_CLIENT].pop(config_entry.entry_id)

    for component in ('binary_sensor', 'sensor'):
        await hass.config_entries.async_forward_entry_unload(
            config_entry, component)

    return True


class OpenUV:
    """Define a generic OpenUV object."""

    def __init__(self, client, binary_sensor_conditions, sensor_conditions):
        """Initialize."""
        self.binary_sensor_conditions = binary_sensor_conditions
        self.client = client
        self.data = {}
        self.sensor_conditions = sensor_conditions

    async def async_update(self):
        """Update sensor/binary sensor data."""
        if TYPE_PROTECTION_WINDOW in self.binary_sensor_conditions:
            resp = await self.client.uv_protection_window()
            data = resp['result']

            if data.get('from_time') and data.get('to_time'):
                self.data[DATA_PROTECTION_WINDOW] = data
            else:
                _LOGGER.debug(
                    'No valid protection window data for this location')
                self.data[DATA_PROTECTION_WINDOW] = {}

        if any(c in self.sensor_conditions for c in SENSORS):
            data = await self.client.uv_index()
            self.data[DATA_UV] = data


class OpenUvEntity(Entity):
    """Define a generic OpenUV entity."""

    def __init__(self, openuv):
        """Initialize."""
        self._attrs = {ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION}
        self._name = None
        self.openuv = openuv

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attrs

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name
