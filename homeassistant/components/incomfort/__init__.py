"""Support for an Intergas boiler via an InComfort/Intouch Lan2RF gateway."""
import logging

from aiohttp import ClientResponseError
import voluptuous as vol
from incomfortclient import Gateway as InComfortGateway

from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.discovery import async_load_platform

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'incomfort'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Inclusive(CONF_USERNAME, 'credentials'): cv.string,
        vol.Inclusive(CONF_PASSWORD, 'credentials'): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, hass_config):
    """Create an Intergas InComfort/Intouch system."""
    incomfort_data = hass.data[DOMAIN] = {}

    credentials = dict(hass_config[DOMAIN])
    hostname = credentials.pop(CONF_HOST)

    client = incomfort_data['client'] = InComfortGateway(
        hostname, **credentials, session=async_get_clientsession(hass)
    )

    try:
        heater = incomfort_data['heater'] = list(await client.heaters)[0]
    except ClientResponseError as err:
        _LOGGER.warning(
            "Setup failed, check your configuration, message is: %s", err)
        return False

    await heater.update()

    for platform in ['water_heater', 'binary_sensor', 'sensor', 'climate']:
        hass.async_create_task(async_load_platform(
            hass, platform, DOMAIN, {}, hass_config))

    return True
