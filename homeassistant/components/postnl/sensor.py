"""Sensor for PostNL packages."""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_NAME, CONF_PASSWORD, CONF_USERNAME)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = 'Information provided by PostNL'

DEFAULT_NAME = 'postnl'

ICON = 'mdi:package-variant-closed'

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=30)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the PostNL sensor platform."""
    from postnl_api import PostNL_API, UnauthorizedException

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    name = config.get(CONF_NAME)

    try:
        api = PostNL_API(username, password)

    except UnauthorizedException:
        _LOGGER.exception("Can't connect to the PostNL webservice")
        return

    add_entities([PostNLSensor(api, name)], True)


class PostNLSensor(Entity):
    """Representation of a PostNL sensor."""

    def __init__(self, api, name):
        """Initialize the PostNL sensor."""
        self._name = name
        self._attributes = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }
        self._state = None
        self._api = api

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return 'packages'

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return ICON

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update device state."""
        shipments = self._api.get_relevant_shipments()
        self._attributes['shipments'] = shipments
        self._state = len(shipments)
