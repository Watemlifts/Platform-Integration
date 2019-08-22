"""Support for VELUX KLF 200 devices."""
import logging

import voluptuous as vol

from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (CONF_HOST, CONF_PASSWORD)

DOMAIN = "velux"
DATA_VELUX = "data_velux"
SUPPORTED_DOMAINS = ['cover', 'scene']
_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the velux component."""
    from pyvlx import PyVLXException
    try:
        hass.data[DATA_VELUX] = VeluxModule(hass, config)
        await hass.data[DATA_VELUX].async_start()

    except PyVLXException as ex:
        _LOGGER.exception("Can't connect to velux interface: %s", ex)
        return False

    for component in SUPPORTED_DOMAINS:
        hass.async_create_task(
            discovery.async_load_platform(hass, component, DOMAIN, {}, config))
    return True


class VeluxModule:
    """Abstraction for velux component."""

    def __init__(self, hass, config):
        """Initialize for velux component."""
        from pyvlx import PyVLX
        host = config[DOMAIN].get(CONF_HOST)
        password = config[DOMAIN].get(CONF_PASSWORD)
        self.pyvlx = PyVLX(
            host=host,
            password=password)

    async def async_start(self):
        """Start velux component."""
        await self.pyvlx.load_scenes()
        await self.pyvlx.load_nodes()
