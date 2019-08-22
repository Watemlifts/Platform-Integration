"""Module that groups code required to handle state restore for component."""
import asyncio
from typing import Iterable, Optional

from homeassistant.const import (
    SERVICE_MEDIA_PAUSE, SERVICE_MEDIA_PLAY, SERVICE_MEDIA_SEEK,
    SERVICE_MEDIA_STOP, SERVICE_TURN_OFF, SERVICE_TURN_ON, SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET, STATE_IDLE, STATE_OFF, STATE_ON, STATE_PAUSED,
    STATE_PLAYING)
from homeassistant.core import Context, State
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.loader import bind_hass

from .const import (
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    ATTR_MEDIA_SEEK_POSITION,
    ATTR_INPUT_SOURCE,
    ATTR_SOUND_MODE,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_ENQUEUE,
    SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOURCE,
    SERVICE_SELECT_SOUND_MODE,
    DOMAIN,
)


async def _async_reproduce_states(hass: HomeAssistantType,
                                  state: State,
                                  context: Optional[Context] = None) -> None:
    """Reproduce component states."""
    async def call_service(service: str, keys: Iterable):
        """Call service with set of attributes given."""
        data = {}
        data['entity_id'] = state.entity_id
        for key in keys:
            if key in state.attributes:
                data[key] = state.attributes[key]

        await hass.services.async_call(
            DOMAIN, service, data,
            blocking=True, context=context)

    if state.state == STATE_ON:
        await call_service(SERVICE_TURN_ON, [])
    elif state.state == STATE_OFF:
        await call_service(SERVICE_TURN_OFF, [])
    elif state.state == STATE_PLAYING:
        await call_service(SERVICE_MEDIA_PLAY, [])
    elif state.state == STATE_IDLE:
        await call_service(SERVICE_MEDIA_STOP, [])
    elif state.state == STATE_PAUSED:
        await call_service(SERVICE_MEDIA_PAUSE, [])

    if ATTR_MEDIA_VOLUME_LEVEL in state.attributes:
        await call_service(SERVICE_VOLUME_SET, [ATTR_MEDIA_VOLUME_LEVEL])

    if ATTR_MEDIA_VOLUME_MUTED in state.attributes:
        await call_service(SERVICE_VOLUME_MUTE, [ATTR_MEDIA_VOLUME_MUTED])

    if ATTR_MEDIA_SEEK_POSITION in state.attributes:
        await call_service(SERVICE_MEDIA_SEEK, [ATTR_MEDIA_SEEK_POSITION])

    if ATTR_INPUT_SOURCE in state.attributes:
        await call_service(SERVICE_SELECT_SOURCE, [ATTR_INPUT_SOURCE])

    if ATTR_SOUND_MODE in state.attributes:
        await call_service(SERVICE_SELECT_SOUND_MODE, [ATTR_SOUND_MODE])

    if (ATTR_MEDIA_CONTENT_TYPE in state.attributes) and \
       (ATTR_MEDIA_CONTENT_ID in state.attributes):
        await call_service(SERVICE_PLAY_MEDIA,
                           [ATTR_MEDIA_CONTENT_TYPE,
                            ATTR_MEDIA_CONTENT_ID,
                            ATTR_MEDIA_ENQUEUE])


@bind_hass
async def async_reproduce_states(hass: HomeAssistantType,
                                 states: Iterable[State],
                                 context: Optional[Context] = None) -> None:
    """Reproduce component states."""
    await asyncio.gather(*[
        _async_reproduce_states(hass, state, context)
        for state in states])
