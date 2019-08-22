"""This platform allows several lights to be grouped into one light."""
from collections import Counter
import itertools
import logging
from typing import Any, Callable, Iterator, List, Optional, Tuple

import voluptuous as vol

from homeassistant.components import light
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES, CONF_ENTITIES, CONF_NAME,
    STATE_ON, STATE_UNAVAILABLE)
from homeassistant.core import State, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_EFFECT, ATTR_EFFECT_LIST,
    ATTR_FLASH, ATTR_HS_COLOR, ATTR_MAX_MIREDS, ATTR_MIN_MIREDS,
    ATTR_TRANSITION, ATTR_WHITE_VALUE, PLATFORM_SCHEMA, SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR, SUPPORT_COLOR_TEMP, SUPPORT_EFFECT, SUPPORT_FLASH,
    SUPPORT_TRANSITION, SUPPORT_WHITE_VALUE)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Light Group'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_ENTITIES): cv.entities_domain(light.DOMAIN)
})

SUPPORT_GROUP_LIGHT = (SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP | SUPPORT_EFFECT
                       | SUPPORT_FLASH | SUPPORT_COLOR | SUPPORT_TRANSITION
                       | SUPPORT_WHITE_VALUE)


async def async_setup_platform(hass: HomeAssistantType, config: ConfigType,
                               async_add_entities,
                               discovery_info=None) -> None:
    """Initialize light.group platform."""
    async_add_entities([LightGroup(config.get(CONF_NAME),
                                   config[CONF_ENTITIES])])


class LightGroup(light.Light):
    """Representation of a light group."""

    def __init__(self, name: str, entity_ids: List[str]) -> None:
        """Initialize a light group."""
        self._name = name  # type: str
        self._entity_ids = entity_ids  # type: List[str]
        self._is_on = False  # type: bool
        self._available = False  # type: bool
        self._brightness = None  # type: Optional[int]
        self._hs_color = None  # type: Optional[Tuple[float, float]]
        self._color_temp = None  # type: Optional[int]
        self._min_mireds = 154  # type: Optional[int]
        self._max_mireds = 500  # type: Optional[int]
        self._white_value = None  # type: Optional[int]
        self._effect_list = None  # type: Optional[List[str]]
        self._effect = None  # type: Optional[str]
        self._supported_features = 0  # type: int
        self._async_unsub_state_changed = None

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        @callback
        def async_state_changed_listener(entity_id: str, old_state: State,
                                         new_state: State):
            """Handle child updates."""
            self.async_schedule_update_ha_state(True)

        self._async_unsub_state_changed = async_track_state_change(
            self.hass, self._entity_ids, async_state_changed_listener)
        await self.async_update()

    async def async_will_remove_from_hass(self):
        """Handle removal from HASS."""
        if self._async_unsub_state_changed is not None:
            self._async_unsub_state_changed()
            self._async_unsub_state_changed = None

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def is_on(self) -> bool:
        """Return the on/off state of the light group."""
        return self._is_on

    @property
    def available(self) -> bool:
        """Return whether the light group is available."""
        return self._available

    @property
    def brightness(self) -> Optional[int]:
        """Return the brightness of this light group between 0..255."""
        return self._brightness

    @property
    def hs_color(self) -> Optional[Tuple[float, float]]:
        """Return the HS color value [float, float]."""
        return self._hs_color

    @property
    def color_temp(self) -> Optional[int]:
        """Return the CT color value in mireds."""
        return self._color_temp

    @property
    def min_mireds(self) -> Optional[int]:
        """Return the coldest color_temp that this light group supports."""
        return self._min_mireds

    @property
    def max_mireds(self) -> Optional[int]:
        """Return the warmest color_temp that this light group supports."""
        return self._max_mireds

    @property
    def white_value(self) -> Optional[int]:
        """Return the white value of this light group between 0..255."""
        return self._white_value

    @property
    def effect_list(self) -> Optional[List[str]]:
        """Return the list of supported effects."""
        return self._effect_list

    @property
    def effect(self) -> Optional[str]:
        """Return the current effect."""
        return self._effect

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return self._supported_features

    @property
    def should_poll(self) -> bool:
        """No polling needed for a light group."""
        return False

    async def async_turn_on(self, **kwargs):
        """Forward the turn_on command to all lights in the light group."""
        data = {ATTR_ENTITY_ID: self._entity_ids}

        if ATTR_BRIGHTNESS in kwargs:
            data[ATTR_BRIGHTNESS] = kwargs[ATTR_BRIGHTNESS]

        if ATTR_HS_COLOR in kwargs:
            data[ATTR_HS_COLOR] = kwargs[ATTR_HS_COLOR]

        if ATTR_COLOR_TEMP in kwargs:
            data[ATTR_COLOR_TEMP] = kwargs[ATTR_COLOR_TEMP]

        if ATTR_WHITE_VALUE in kwargs:
            data[ATTR_WHITE_VALUE] = kwargs[ATTR_WHITE_VALUE]

        if ATTR_EFFECT in kwargs:
            data[ATTR_EFFECT] = kwargs[ATTR_EFFECT]

        if ATTR_TRANSITION in kwargs:
            data[ATTR_TRANSITION] = kwargs[ATTR_TRANSITION]

        if ATTR_FLASH in kwargs:
            data[ATTR_FLASH] = kwargs[ATTR_FLASH]

        await self.hass.services.async_call(
            light.DOMAIN, light.SERVICE_TURN_ON, data, blocking=True)

    async def async_turn_off(self, **kwargs):
        """Forward the turn_off command to all lights in the light group."""
        data = {ATTR_ENTITY_ID: self._entity_ids}

        if ATTR_TRANSITION in kwargs:
            data[ATTR_TRANSITION] = kwargs[ATTR_TRANSITION]

        await self.hass.services.async_call(
            light.DOMAIN, light.SERVICE_TURN_OFF, data, blocking=True)

    async def async_update(self):
        """Query all members and determine the light group state."""
        all_states = [self.hass.states.get(x) for x in self._entity_ids]
        states = list(filter(None, all_states))
        on_states = [state for state in states if state.state == STATE_ON]

        self._is_on = len(on_states) > 0
        self._available = any(state.state != STATE_UNAVAILABLE
                              for state in states)

        self._brightness = _reduce_attribute(on_states, ATTR_BRIGHTNESS)

        self._hs_color = _reduce_attribute(
            on_states, ATTR_HS_COLOR, reduce=_mean_tuple)

        self._white_value = _reduce_attribute(on_states, ATTR_WHITE_VALUE)

        self._color_temp = _reduce_attribute(on_states, ATTR_COLOR_TEMP)
        self._min_mireds = _reduce_attribute(
            states, ATTR_MIN_MIREDS, default=154, reduce=min)
        self._max_mireds = _reduce_attribute(
            states, ATTR_MAX_MIREDS, default=500, reduce=max)

        self._effect_list = None
        all_effect_lists = list(
            _find_state_attributes(states, ATTR_EFFECT_LIST))
        if all_effect_lists:
            # Merge all effects from all effect_lists with a union merge.
            self._effect_list = list(set().union(*all_effect_lists))

        self._effect = None
        all_effects = list(_find_state_attributes(on_states, ATTR_EFFECT))
        if all_effects:
            # Report the most common effect.
            effects_count = Counter(itertools.chain(all_effects))
            self._effect = effects_count.most_common(1)[0][0]

        self._supported_features = 0
        for support in _find_state_attributes(states, ATTR_SUPPORTED_FEATURES):
            # Merge supported features by emulating support for every feature
            # we find.
            self._supported_features |= support
        # Bitwise-and the supported features with the GroupedLight's features
        # so that we don't break in the future when a new feature is added.
        self._supported_features &= SUPPORT_GROUP_LIGHT


def _find_state_attributes(states: List[State],
                           key: str) -> Iterator[Any]:
    """Find attributes with matching key from states."""
    for state in states:
        value = state.attributes.get(key)
        if value is not None:
            yield value


def _mean_int(*args):
    """Return the mean of the supplied values."""
    return int(sum(args) / len(args))


def _mean_tuple(*args):
    """Return the mean values along the columns of the supplied values."""
    return tuple(sum(l) / len(l) for l in zip(*args))


def _reduce_attribute(states: List[State],
                      key: str,
                      default: Optional[Any] = None,
                      reduce: Callable[..., Any] = _mean_int) -> Any:
    """Find the first attribute matching key from states.

    If none are found, return default.
    """
    attrs = list(_find_state_attributes(states, key))

    if not attrs:
        return default

    if len(attrs) == 1:
        return attrs[0]

    return reduce(*attrs)
