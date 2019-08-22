"""Support for ADS covers."""
import logging

import voluptuous as vol

from homeassistant.components.cover import (
    PLATFORM_SCHEMA, SUPPORT_OPEN, SUPPORT_CLOSE, SUPPORT_STOP,
    SUPPORT_SET_POSITION, ATTR_POSITION, DEVICE_CLASSES_SCHEMA,
    CoverDevice)
from homeassistant.const import (
    CONF_NAME, CONF_DEVICE_CLASS)
import homeassistant.helpers.config_validation as cv

from . import CONF_ADS_VAR, CONF_ADS_VAR_POSITION, DATA_ADS, \
    AdsEntity, STATE_KEY_STATE, STATE_KEY_POSITION

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'ADS Cover'

CONF_ADS_VAR_SET_POS = 'adsvar_set_position'
CONF_ADS_VAR_OPEN = 'adsvar_open'
CONF_ADS_VAR_CLOSE = 'adsvar_close'
CONF_ADS_VAR_STOP = 'adsvar_stop'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_ADS_VAR): cv.string,
    vol.Optional(CONF_ADS_VAR_POSITION): cv.string,
    vol.Optional(CONF_ADS_VAR_SET_POS): cv.string,
    vol.Optional(CONF_ADS_VAR_CLOSE): cv.string,
    vol.Optional(CONF_ADS_VAR_OPEN): cv.string,
    vol.Optional(CONF_ADS_VAR_STOP): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the cover platform for ADS."""
    ads_hub = hass.data[DATA_ADS]

    ads_var_is_closed = config.get(CONF_ADS_VAR)
    ads_var_position = config.get(CONF_ADS_VAR_POSITION)
    ads_var_pos_set = config.get(CONF_ADS_VAR_SET_POS)
    ads_var_open = config.get(CONF_ADS_VAR_OPEN)
    ads_var_close = config.get(CONF_ADS_VAR_CLOSE)
    ads_var_stop = config.get(CONF_ADS_VAR_STOP)
    name = config[CONF_NAME]
    device_class = config.get(CONF_DEVICE_CLASS)

    add_entities([AdsCover(ads_hub,
                           ads_var_is_closed,
                           ads_var_position,
                           ads_var_pos_set,
                           ads_var_open,
                           ads_var_close,
                           ads_var_stop,
                           name,
                           device_class)])


class AdsCover(AdsEntity, CoverDevice):
    """Representation of ADS cover."""

    def __init__(self, ads_hub,
                 ads_var_is_closed, ads_var_position,
                 ads_var_pos_set, ads_var_open,
                 ads_var_close, ads_var_stop, name, device_class):
        """Initialize AdsCover entity."""
        super().__init__(ads_hub, name, ads_var_is_closed)
        if self._ads_var is None:
            if ads_var_position is not None:
                self._unique_id = ads_var_position
            elif ads_var_pos_set is not None:
                self._unique_id = ads_var_pos_set
            elif ads_var_open is not None:
                self._unique_id = ads_var_open

        self._state_dict[STATE_KEY_POSITION] = None
        self._ads_var_position = ads_var_position
        self._ads_var_pos_set = ads_var_pos_set
        self._ads_var_open = ads_var_open
        self._ads_var_close = ads_var_close
        self._ads_var_stop = ads_var_stop
        self._device_class = device_class

    async def async_added_to_hass(self):
        """Register device notification."""
        if self._ads_var is not None:
            await self.async_initialize_device(self._ads_var,
                                               self._ads_hub.PLCTYPE_BOOL)

        if self._ads_var_position is not None:
            await self.async_initialize_device(self._ads_var_position,
                                               self._ads_hub.PLCTYPE_BYTE,
                                               STATE_KEY_POSITION)

    @property
    def device_class(self):
        """Return the class of this cover."""
        return self._device_class

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        if self._ads_var is not None:
            return self._state_dict[STATE_KEY_STATE]
        if self._ads_var_position is not None:
            return self._state_dict[STATE_KEY_POSITION] == 0
        return None

    @property
    def current_cover_position(self):
        """Return current position of cover."""
        return self._state_dict[STATE_KEY_POSITION]

    @property
    def supported_features(self):
        """Flag supported features."""
        supported_features = SUPPORT_OPEN | SUPPORT_CLOSE

        if self._ads_var_stop is not None:
            supported_features |= SUPPORT_STOP

        if self._ads_var_pos_set is not None:
            supported_features |= SUPPORT_SET_POSITION

        return supported_features

    def stop_cover(self, **kwargs):
        """Fire the stop action."""
        if self._ads_var_stop:
            self._ads_hub.write_by_name(self._ads_var_stop, True,
                                        self._ads_hub.PLCTYPE_BOOL)

    def set_cover_position(self, **kwargs):
        """Set cover position."""
        position = kwargs[ATTR_POSITION]
        if self._ads_var_pos_set is not None:
            self._ads_hub.write_by_name(self._ads_var_pos_set, position,
                                        self._ads_hub.PLCTYPE_BYTE)

    def open_cover(self, **kwargs):
        """Move the cover up."""
        if self._ads_var_open is not None:
            self._ads_hub.write_by_name(self._ads_var_open, True,
                                        self._ads_hub.PLCTYPE_BOOL)
        elif self._ads_var_pos_set is not None:
            self.set_cover_position(position=100)

    def close_cover(self, **kwargs):
        """Move the cover down."""
        if self._ads_var_close is not None:
            self._ads_hub.write_by_name(self._ads_var_close, True,
                                        self._ads_hub.PLCTYPE_BOOL)
        elif self._ads_var_pos_set is not None:
            self.set_cover_position(position=0)

    @property
    def available(self):
        """Return False if state has not been updated yet."""
        if self._ads_var is not None or self._ads_var_position is not None:
            return self._state_dict[STATE_KEY_STATE] is not None or \
                   self._state_dict[STATE_KEY_POSITION] is not None
        return True
