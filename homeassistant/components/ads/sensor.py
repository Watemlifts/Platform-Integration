"""Support for ADS sensors."""
import logging

import voluptuous as vol

from homeassistant.components import ads
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_UNIT_OF_MEASUREMENT
import homeassistant.helpers.config_validation as cv

from . import CONF_ADS_FACTOR, CONF_ADS_TYPE, CONF_ADS_VAR, \
    AdsEntity, STATE_KEY_STATE

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "ADS sensor"
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADS_VAR): cv.string,
    vol.Optional(CONF_ADS_FACTOR): cv.positive_int,
    vol.Optional(CONF_ADS_TYPE, default=ads.ADSTYPE_INT):
        vol.In([ads.ADSTYPE_INT, ads.ADSTYPE_UINT, ads.ADSTYPE_BYTE,
                ads.ADSTYPE_DINT, ads.ADSTYPE_UDINT]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT, default=''): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up an ADS sensor device."""
    ads_hub = hass.data.get(ads.DATA_ADS)

    ads_var = config.get(CONF_ADS_VAR)
    ads_type = config.get(CONF_ADS_TYPE)
    name = config.get(CONF_NAME)
    unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT)
    factor = config.get(CONF_ADS_FACTOR)

    entity = AdsSensor(
        ads_hub, ads_var, ads_type, name, unit_of_measurement, factor)

    add_entities([entity])


class AdsSensor(AdsEntity):
    """Representation of an ADS sensor entity."""

    def __init__(self, ads_hub, ads_var, ads_type, name, unit_of_measurement,
                 factor):
        """Initialize AdsSensor entity."""
        super().__init__(ads_hub, name, ads_var)
        self._unit_of_measurement = unit_of_measurement
        self._ads_type = ads_type
        self._factor = factor

    async def async_added_to_hass(self):
        """Register device notification."""
        await self.async_initialize_device(
            self._ads_var,
            self._ads_hub.ADS_TYPEMAP[self._ads_type],
            STATE_KEY_STATE,
            self._factor)

    @property
    def state(self):
        """Return the state of the device."""
        return self._state_dict[STATE_KEY_STATE]

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement
