"""Config flow for the Daikin platform."""
import asyncio
import logging

from aiohttp import ClientError
from async_timeout import timeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST

from .const import KEY_IP, KEY_MAC

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register('daikin')
class FlowHandler(config_entries.ConfigFlow):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def _create_entry(self, host, mac):
        """Register new entry."""
        # Check if mac already is registered
        for entry in self._async_current_entries():
            if entry.data[KEY_MAC] == mac:
                return self.async_abort(reason='already_configured')

        return self.async_create_entry(
            title=host,
            data={
                CONF_HOST: host,
                KEY_MAC: mac
            })

    async def _create_device(self, host):
        """Create device."""
        from pydaikin.appliance import Appliance
        try:
            device = Appliance(
                host,
                self.hass.helpers.aiohttp_client.async_get_clientsession(),
            )
            with timeout(10):
                await device.init()
        except asyncio.TimeoutError:
            return self.async_abort(reason='device_timeout')
        except ClientError:
            _LOGGER.exception("ClientError")
            return self.async_abort(reason='device_fail')
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected error creating device")
            return self.async_abort(reason='device_fail')

        mac = device.values.get('mac')
        return await self._create_entry(host, mac)

    async def async_step_user(self, user_input=None):
        """User initiated config flow."""
        if user_input is None:
            return self.async_show_form(
                step_id='user',
                data_schema=vol.Schema({
                    vol.Required(CONF_HOST): str
                })
            )
        return await self._create_device(user_input[CONF_HOST])

    async def async_step_import(self, user_input):
        """Import a config entry."""
        host = user_input.get(CONF_HOST)
        if not host:
            return await self.async_step_user()
        return await self._create_device(host)

    async def async_step_discovery(self, user_input):
        """Initialize step from discovery."""
        _LOGGER.info("Discovered device: %s", user_input)
        return await self._create_entry(user_input[KEY_IP],
                                        user_input[KEY_MAC])
