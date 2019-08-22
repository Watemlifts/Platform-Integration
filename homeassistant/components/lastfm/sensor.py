"""Sensor for Last.fm account status."""
import logging
import re

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_API_KEY, ATTR_ATTRIBUTION
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

ATTR_LAST_PLAYED = 'last_played'
ATTR_PLAY_COUNT = 'play_count'
ATTR_TOP_PLAYED = 'top_played'
ATTRIBUTION = "Data provided by Last.fm"

CONF_USERS = 'users'

ICON = 'mdi:lastfm'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_USERS, default=[]): vol.All(cv.ensure_list, [cv.string]),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Last.fm sensor platform."""
    import pylast as lastfm
    from pylast import WSError

    api_key = config[CONF_API_KEY]
    users = config.get(CONF_USERS)

    lastfm_api = lastfm.LastFMNetwork(api_key=api_key)

    entities = []
    for username in users:
        try:
            lastfm_api.get_user(username).get_image()
            entities.append(LastfmSensor(username, lastfm_api))
        except WSError as error:
            _LOGGER.error(error)
            return

    add_entities(entities, True)


class LastfmSensor(Entity):
    """A class for the Last.fm account."""

    def __init__(self, user, lastfm):
        """Initialize the sensor."""
        self._user = lastfm.get_user(user)
        self._name = user
        self._lastfm = lastfm
        self._state = "Not Scrobbling"
        self._playcount = None
        self._lastplayed = None
        self._topplayed = None
        self._cover = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def entity_id(self):
        """Return the entity ID."""
        return 'sensor.lastfm_{}'.format(self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Update device state."""
        self._cover = self._user.get_image()
        self._playcount = self._user.get_playcount()
        last = self._user.get_recent_tracks(limit=2)[0]
        self._lastplayed = "{} - {}".format(
            last.track.artist, last.track.title)
        top = self._user.get_top_tracks(limit=1)[0]
        toptitle = re.search("', '(.+?)',", str(top))
        topartist = re.search("'(.+?)',", str(top))
        self._topplayed = "{} - {}".format(
            topartist.group(1), toptitle.group(1))
        if self._user.get_now_playing() is None:
            self._state = "Not Scrobbling"
            return
        now = self._user.get_now_playing()
        self._state = "{} - {}".format(now.artist, now.title)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_LAST_PLAYED: self._lastplayed,
            ATTR_PLAY_COUNT: self._playcount,
            ATTR_TOP_PLAYED: self._topplayed,
        }

    @property
    def entity_picture(self):
        """Avatar of the user."""
        return self._cover

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return ICON
