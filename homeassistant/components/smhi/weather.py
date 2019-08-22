"""Support for the Swedish weather institute weather service."""
import asyncio
from datetime import timedelta
import logging
from typing import Dict, List

import aiohttp
import async_timeout

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION, ATTR_FORECAST_PRECIPITATION, ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW, ATTR_FORECAST_TIME, WeatherEntity)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME, TEMP_CELSIUS)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.util import Throttle, slugify

from .const import ATTR_SMHI_CLOUDINESS, ENTITY_ID_SENSOR_FORMAT

_LOGGER = logging.getLogger(__name__)

# Used to map condition from API results
CONDITION_CLASSES = {
    'cloudy': [5, 6],
    'fog': [7],
    'hail': [],
    'lightning': [21],
    'lightning-rainy': [11],
    'partlycloudy': [3, 4],
    'pouring': [10, 20],
    'rainy': [8, 9, 18, 19],
    'snowy': [15, 16, 17, 25, 26, 27],
    'snowy-rainy': [12, 13, 14, 22, 23, 24],
    'sunny': [1, 2],
    'windy': [],
    'windy-variant': [],
    'exceptional': [],
}

# 5 minutes between retrying connect to API again
RETRY_TIMEOUT = 5*60

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=31)


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Old way of setting up components.

    Can only be called when a user accidentally mentions smhi in the
    config. In that case it will be ignored.
    """
    pass


async def async_setup_entry(
        hass: HomeAssistant, config_entry: ConfigEntry,
        config_entries) -> bool:
    """Add a weather entity from map location."""
    location = config_entry.data
    name = slugify(location[CONF_NAME])

    session = aiohttp_client.async_get_clientsession(hass)

    entity = SmhiWeather(
        location[CONF_NAME], location[CONF_LATITUDE], location[CONF_LONGITUDE],
        session=session)
    entity.entity_id = ENTITY_ID_SENSOR_FORMAT.format(name)

    config_entries([entity], True)
    return True


class SmhiWeather(WeatherEntity):
    """Representation of a weather entity."""

    def __init__(self, name: str, latitude: str,
                 longitude: str,
                 session: aiohttp.ClientSession = None) -> None:
        """Initialize the SMHI weather entity."""
        from smhi import Smhi

        self._name = name
        self._latitude = latitude
        self._longitude = longitude
        self._forecasts = None
        self._fail_count = 0
        self._smhi_api = Smhi(self._longitude, self._latitude, session=session)

    @property
    def unique_id(self) -> str:
        """Return a unique id."""
        return '{}, {}'.format(self._latitude, self._longitude)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self) -> None:
        """Refresh the forecast data from SMHI weather API."""
        from smhi.smhi_lib import SmhiForecastException

        def fail():
            """Postpone updates."""
            self._fail_count += 1
            if self._fail_count < 3:
                self.hass.helpers.event.async_call_later(
                    RETRY_TIMEOUT, self.retry_update())

        try:
            with async_timeout.timeout(10):
                self._forecasts = await self.get_weather_forecast()
                self._fail_count = 0

        except (asyncio.TimeoutError, SmhiForecastException):
            _LOGGER.error(
                "Failed to connect to SMHI API, retry in 5 minutes")
            fail()

    async def retry_update(self):
        """Retry refresh weather forecast."""
        self.async_update()

    async def get_weather_forecast(self) -> []:
        """Return the current forecasts from SMHI API."""
        return await self._smhi_api.async_get_forecast()

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def temperature(self) -> int:
        """Return the temperature."""
        if self._forecasts is not None:
            return self._forecasts[0].temperature
        return None

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def humidity(self) -> int:
        """Return the humidity."""
        if self._forecasts is not None:
            return self._forecasts[0].humidity
        return None

    @property
    def wind_speed(self) -> float:
        """Return the wind speed."""
        if self._forecasts is not None:
            # Convert from m/s to km/h
            return round(self._forecasts[0].wind_speed * 18 / 5)
        return None

    @property
    def wind_bearing(self) -> int:
        """Return the wind bearing."""
        if self._forecasts is not None:
            return self._forecasts[0].wind_direction
        return None

    @property
    def visibility(self) -> float:
        """Return the visibility."""
        if self._forecasts is not None:
            return self._forecasts[0].horizontal_visibility
        return None

    @property
    def pressure(self) -> int:
        """Return the pressure."""
        if self._forecasts is not None:
            return self._forecasts[0].pressure
        return None

    @property
    def cloudiness(self) -> int:
        """Return the cloudiness."""
        if self._forecasts is not None:
            return self._forecasts[0].cloudiness
        return None

    @property
    def condition(self) -> str:
        """Return the weather condition."""
        if self._forecasts is None:
            return None
        return next((
            k for k, v in CONDITION_CLASSES.items()
            if self._forecasts[0].symbol in v), None)

    @property
    def attribution(self) -> str:
        """Return the attribution."""
        return 'Swedish weather institute (SMHI)'

    @property
    def forecast(self) -> List:
        """Return the forecast."""
        if self._forecasts is None or len(self._forecasts) < 2:
            return None

        data = []

        for forecast in self._forecasts[1:]:
            condition = next((
                k for k, v in CONDITION_CLASSES.items()
                if forecast.symbol in v), None)

            data.append({
                ATTR_FORECAST_TIME: forecast.valid_time.isoformat(),
                ATTR_FORECAST_TEMP: forecast.temperature_max,
                ATTR_FORECAST_TEMP_LOW: forecast.temperature_min,
                ATTR_FORECAST_PRECIPITATION:
                    round(forecast.total_precipitation, 1),
                ATTR_FORECAST_CONDITION: condition,
            })

        return data

    @property
    def device_state_attributes(self) -> Dict:
        """Return SMHI specific attributes."""
        if self.cloudiness:
            return {ATTR_SMHI_CLOUDINESS: self.cloudiness}
