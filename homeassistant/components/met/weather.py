"""Support for Met.no weather service."""
import logging
from random import randrange

import metno
import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.weather import PLATFORM_SCHEMA, WeatherEntity
from homeassistant.const import (
    CONF_ELEVATION, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME, TEMP_CELSIUS,
    EVENT_CORE_CONFIG_UPDATE)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later
import homeassistant.util.dt as dt_util

from .const import CONF_TRACK_HOME

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Weather forecast from met.no, delivered by the Norwegian " \
              "Meteorological Institute."
DEFAULT_NAME = "Met.no"

URL = 'https://aa015h6buqvih86i1.api.met.no/weatherapi/locationforecast/1.9/'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Inclusive(CONF_LATITUDE, 'coordinates',
                  'Latitude and longitude must exist together'): cv.latitude,
    vol.Inclusive(CONF_LONGITUDE, 'coordinates',
                  'Latitude and longitude must exist together'): cv.longitude,
    vol.Optional(CONF_ELEVATION): int,
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Met.no weather platform."""
    _LOGGER.warning("Loading Met.no via platform config is deprecated")

    # Add defaults.
    config = {
        CONF_ELEVATION: hass.config.elevation,
        **config,
    }

    if config.get(CONF_LATITUDE) is None:
        config[CONF_TRACK_HOME] = True

    async_add_entities([MetWeather(config)])


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add a weather entity from a config_entry."""
    async_add_entities([MetWeather(config_entry.data)])


class MetWeather(WeatherEntity):
    """Implementation of a Met.no weather condition."""

    def __init__(self, config):
        """Initialise the platform with a data instance and site."""
        self._config = config
        self._unsub_track_home = None
        self._unsub_fetch_data = None
        self._weather_data = None
        self._current_weather_data = {}
        self._forecast_data = None

    async def async_added_to_hass(self):
        """Start fetching data."""
        self._init_data()
        await self._fetch_data()
        if self._config.get(CONF_TRACK_HOME):
            self._unsub_track_home = self.hass.bus.async_listen(
                EVENT_CORE_CONFIG_UPDATE, self._core_config_updated)

    @callback
    def _init_data(self):
        """Initialize a data object."""
        conf = self._config

        if self.track_home:
            latitude = self.hass.config.latitude
            longitude = self.hass.config.longitude
            elevation = self.hass.config.elevation
        else:
            latitude = conf[CONF_LATITUDE]
            longitude = conf[CONF_LONGITUDE]
            elevation = conf[CONF_ELEVATION]

        coordinates = {
            'lat': str(latitude),
            'lon': str(longitude),
            'msl': str(elevation),
        }
        self._weather_data = metno.MetWeatherData(
            coordinates, async_get_clientsession(self.hass), URL)

    async def _core_config_updated(self, _event):
        """Handle core config updated."""
        self._init_data()
        if self._unsub_fetch_data:
            self._unsub_fetch_data()
            self._unsub_fetch_data = None
        await self._fetch_data()

    async def will_remove_from_hass(self):
        """Handle entity will be removed from hass."""
        if self._unsub_track_home:
            self._unsub_track_home()
            self._unsub_track_home = None

        if self._unsub_fetch_data:
            self._unsub_fetch_data()
            self._unsub_fetch_data = None

    async def _fetch_data(self, *_):
        """Get the latest data from met.no."""
        if not await self._weather_data.fetching_data():
            # Retry in 15 to 20 minutes.
            minutes = 15 + randrange(6)
            _LOGGER.error("Retrying in %i minutes", minutes)
            self._unsub_fetch_data = async_call_later(
                self.hass, minutes*60, self._fetch_data)
            return

        # Wait between 55-65 minutes. If people update HA on the hour, this
        # will make sure it will spread it out.

        self._unsub_fetch_data = async_call_later(
            self.hass, randrange(55, 65)*60, self._fetch_data)
        self._update()

    def _update(self, *_):
        """Get the latest data from Met.no."""
        self._current_weather_data = self._weather_data.get_current_weather()
        time_zone = dt_util.DEFAULT_TIME_ZONE
        self._forecast_data = self._weather_data.get_forecast(time_zone)
        self.async_write_ha_state()

    @property
    def track_home(self):
        """Return if we are tracking home."""
        return self._config.get(CONF_TRACK_HOME, False)

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def unique_id(self):
        """Return unique ID."""
        if self.track_home:
            return 'home'

        return '{}-{}'.format(
            self._config[CONF_LATITUDE], self._config[CONF_LONGITUDE])

    @property
    def name(self):
        """Return the name of the sensor."""
        name = self._config.get(CONF_NAME)

        if name is not None:
            return name

        if self.track_home:
            return self.hass.config.location_name

        return DEFAULT_NAME

    @property
    def condition(self):
        """Return the current condition."""
        return self._current_weather_data.get('condition')

    @property
    def temperature(self):
        """Return the temperature."""
        return self._current_weather_data.get('temperature')

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def pressure(self):
        """Return the pressure."""
        return self._current_weather_data.get('pressure')

    @property
    def humidity(self):
        """Return the humidity."""
        return self._current_weather_data.get('humidity')

    @property
    def wind_speed(self):
        """Return the wind speed."""
        return self._current_weather_data.get('wind_speed')

    @property
    def wind_bearing(self):
        """Return the wind direction."""
        return self._current_weather_data.get('wind_bearing')

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def forecast(self):
        """Return the forecast array."""
        return self._forecast_data
