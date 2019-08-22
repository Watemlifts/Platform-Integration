"""Support for Epson projector."""
import logging

import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerDevice, MEDIA_PLAYER_SCHEMA, PLATFORM_SCHEMA)
from homeassistant.components.media_player.const import (
    DOMAIN, SUPPORT_NEXT_TRACK,
    SUPPORT_PREVIOUS_TRACK, SUPPORT_SELECT_SOURCE, SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_STEP)
from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_HOST, CONF_NAME, CONF_PORT, CONF_SSL, STATE_OFF,
    STATE_ON)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

ATTR_CMODE = 'cmode'

DATA_EPSON = 'epson'
DEFAULT_NAME = 'EPSON Projector'

SERVICE_SELECT_CMODE = 'epson_select_cmode'
SUPPORT_CMODE = 33001

SUPPORT_EPSON = SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE |\
            SUPPORT_CMODE | SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_STEP | \
            SUPPORT_NEXT_TRACK | SUPPORT_PREVIOUS_TRACK


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=80): cv.port,
    vol.Optional(CONF_SSL, default=False): cv.boolean,
})


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the Epson media player platform."""
    from epson_projector.const import (CMODE_LIST_SET)

    if DATA_EPSON not in hass.data:
        hass.data[DATA_EPSON] = []

    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    ssl = config.get(CONF_SSL)

    epson = EpsonProjector(async_get_clientsession(
        hass, verify_ssl=False), name, host, port, ssl)

    hass.data[DATA_EPSON].append(epson)
    async_add_entities([epson], update_before_add=True)

    async def async_service_handler(service):
        """Handle for services."""
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        if entity_ids:
            devices = [device for device in hass.data[DATA_EPSON]
                       if device.entity_id in entity_ids]
        else:
            devices = hass.data[DATA_EPSON]
        for device in devices:
            if service.service == SERVICE_SELECT_CMODE:
                cmode = service.data.get(ATTR_CMODE)
                await device.select_cmode(cmode)
            device.async_schedule_update_ha_state(True)

    epson_schema = MEDIA_PLAYER_SCHEMA.extend({
        vol.Required(ATTR_CMODE): vol.All(cv.string, vol.Any(*CMODE_LIST_SET))
    })
    hass.services.async_register(
        DOMAIN, SERVICE_SELECT_CMODE, async_service_handler,
        schema=epson_schema)


class EpsonProjector(MediaPlayerDevice):
    """Representation of Epson Projector Device."""

    def __init__(self, websession, name, host, port, encryption):
        """Initialize entity to control Epson projector."""
        import epson_projector as epson
        from epson_projector.const import DEFAULT_SOURCES

        self._name = name
        self._projector = epson.Projector(
            host, websession=websession, port=port)
        self._cmode = None
        self._source_list = list(DEFAULT_SOURCES.values())
        self._source = None
        self._volume = None
        self._state = None

    async def async_update(self):
        """Update state of device."""
        from epson_projector.const import (
            EPSON_CODES, POWER, CMODE, CMODE_LIST, SOURCE, VOLUME, BUSY,
            SOURCE_LIST)
        is_turned_on = await self._projector.get_property(POWER)
        _LOGGER.debug("Project turn on/off status: %s", is_turned_on)
        if is_turned_on and is_turned_on == EPSON_CODES[POWER]:
            self._state = STATE_ON
            cmode = await self._projector.get_property(CMODE)
            self._cmode = CMODE_LIST.get(cmode, self._cmode)
            source = await self._projector.get_property(SOURCE)
            self._source = SOURCE_LIST.get(source, self._source)
            volume = await self._projector.get_property(VOLUME)
            if volume:
                self._volume = volume
        elif is_turned_on == BUSY:
            self._state = STATE_ON
        else:
            self._state = STATE_OFF

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_EPSON

    async def async_turn_on(self):
        """Turn on epson."""
        from epson_projector.const import TURN_ON
        if self._state == STATE_OFF:
            await self._projector.send_command(TURN_ON)

    async def async_turn_off(self):
        """Turn off epson."""
        from epson_projector.const import TURN_OFF
        if self._state == STATE_ON:
            await self._projector.send_command(TURN_OFF)

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_list

    @property
    def source(self):
        """Get current input sources."""
        return self._source

    @property
    def volume_level(self):
        """Return the volume level of the media player (0..1)."""
        return self._volume

    async def select_cmode(self, cmode):
        """Set color mode in Epson."""
        from epson_projector.const import (CMODE_LIST_SET)
        await self._projector.send_command(CMODE_LIST_SET[cmode])

    async def async_select_source(self, source):
        """Select input source."""
        from epson_projector.const import INV_SOURCES
        selected_source = INV_SOURCES[source]
        await self._projector.send_command(selected_source)

    async def async_mute_volume(self, mute):
        """Mute (true) or unmute (false) sound."""
        from epson_projector.const import MUTE
        await self._projector.send_command(MUTE)

    async def async_volume_up(self):
        """Increase volume."""
        from epson_projector.const import VOL_UP
        await self._projector.send_command(VOL_UP)

    async def async_volume_down(self):
        """Decrease volume."""
        from epson_projector.const import VOL_DOWN
        await self._projector.send_command(VOL_DOWN)

    async def async_media_play(self):
        """Play media via Epson."""
        from epson_projector.const import PLAY
        await self._projector.send_command(PLAY)

    async def async_media_pause(self):
        """Pause media via Epson."""
        from epson_projector.const import PAUSE
        await self._projector.send_command(PAUSE)

    async def async_media_next_track(self):
        """Skip to next."""
        from epson_projector.const import FAST
        await self._projector.send_command(FAST)

    async def async_media_previous_track(self):
        """Skip to previous."""
        from epson_projector.const import BACK
        await self._projector.send_command(BACK)

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        attributes = {}
        if self._cmode is not None:
            attributes[ATTR_CMODE] = self._cmode
        return attributes
