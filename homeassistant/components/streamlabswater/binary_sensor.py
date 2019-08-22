"""Support for Streamlabs Water Monitor Away Mode."""

from datetime import timedelta

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.streamlabswater import (
    DOMAIN as STREAMLABSWATER_DOMAIN)
from homeassistant.util import Throttle

DEPENDS = ['streamlabswater']

MIN_TIME_BETWEEN_LOCATION_UPDATES = timedelta(seconds=60)

ATTR_LOCATION_ID = "location_id"
NAME_AWAY_MODE = "Water Away Mode"


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the StreamLabsWater mode sensor."""
    client = hass.data[STREAMLABSWATER_DOMAIN]['client']
    location_id = hass.data[STREAMLABSWATER_DOMAIN]['location_id']
    location_name = hass.data[STREAMLABSWATER_DOMAIN]['location_name']

    streamlabs_location_data = StreamlabsLocationData(location_id, client)
    streamlabs_location_data.update()

    add_devices([
        StreamlabsAwayMode(location_name, streamlabs_location_data)
    ])


class StreamlabsLocationData:
    """Track and query location data."""

    def __init__(self, location_id, client):
        """Initialize the location data."""
        self._location_id = location_id
        self._client = client
        self._is_away = None

    @Throttle(MIN_TIME_BETWEEN_LOCATION_UPDATES)
    def update(self):
        """Query and store location data."""
        location = self._client.get_location(self._location_id)
        self._is_away = location['homeAway'] == 'away'

    def is_away(self):
        """Return whether away more is enabled."""
        return self._is_away


class StreamlabsAwayMode(BinarySensorDevice):
    """Monitor the away mode state."""

    def __init__(self, location_name, streamlabs_location_data):
        """Initialize the away mode device."""
        self._location_name = location_name
        self._streamlabs_location_data = streamlabs_location_data
        self._is_away = None

    @property
    def name(self):
        """Return the name for away mode."""
        return "{} {}".format(self._location_name, NAME_AWAY_MODE)

    @property
    def is_on(self):
        """Return if away mode is on."""
        return self._streamlabs_location_data.is_away()

    def update(self):
        """Retrieve the latest location data and away mode state."""
        self._streamlabs_location_data.update()
