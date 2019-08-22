"""Support for the Netatmo Weather Service."""
import logging
import threading
from datetime import timedelta
from time import time

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_MODE, CONF_MONITORED_CONDITIONS,
    TEMP_CELSIUS, DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_BATTERY)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import call_later
from homeassistant.util import Throttle
from .const import DATA_NETATMO_AUTH

_LOGGER = logging.getLogger(__name__)

CONF_MODULES = 'modules'
CONF_STATION = 'station'
CONF_AREAS = 'areas'
CONF_LAT_NE = 'lat_ne'
CONF_LON_NE = 'lon_ne'
CONF_LAT_SW = 'lat_sw'
CONF_LON_SW = 'lon_sw'

DEFAULT_MODE = 'avg'
MODE_TYPES = {'max', 'avg'}

DEFAULT_NAME_PUBLIC = 'Netatmo Public Data'

# This is the Netatmo data upload interval in seconds
NETATMO_UPDATE_INTERVAL = 600

# NetAtmo Public Data is uploaded to server every 10 minutes
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=600)

SUPPORTED_PUBLIC_SENSOR_TYPES = [
    'temperature', 'pressure', 'humidity', 'rain', 'windstrength',
    'guststrength'
]

SENSOR_TYPES = {
    'temperature': ['Temperature', TEMP_CELSIUS, 'mdi:thermometer',
                    DEVICE_CLASS_TEMPERATURE],
    'co2': ['CO2', 'ppm', 'mdi:cloud', None],
    'pressure': ['Pressure', 'mbar', 'mdi:gauge', None],
    'noise': ['Noise', 'dB', 'mdi:volume-high', None],
    'humidity': ['Humidity', '%', 'mdi:water-percent', DEVICE_CLASS_HUMIDITY],
    'rain': ['Rain', 'mm', 'mdi:weather-rainy', None],
    'sum_rain_1': ['sum_rain_1', 'mm', 'mdi:weather-rainy', None],
    'sum_rain_24': ['sum_rain_24', 'mm', 'mdi:weather-rainy', None],
    'battery_vp': ['Battery', '', 'mdi:battery', None],
    'battery_lvl': ['Battery_lvl', '', 'mdi:battery', None],
    'battery_percent': ['battery_percent', '%', None, DEVICE_CLASS_BATTERY],
    'min_temp': ['Min Temp.', TEMP_CELSIUS, 'mdi:thermometer', None],
    'max_temp': ['Max Temp.', TEMP_CELSIUS, 'mdi:thermometer', None],
    'windangle': ['Angle', '', 'mdi:compass', None],
    'windangle_value': ['Angle Value', 'º', 'mdi:compass', None],
    'windstrength': ['Wind Strength', 'km/h', 'mdi:weather-windy', None],
    'gustangle': ['Gust Angle', '', 'mdi:compass', None],
    'gustangle_value': ['Gust Angle Value', 'º', 'mdi:compass', None],
    'guststrength': ['Gust Strength', 'km/h', 'mdi:weather-windy', None],
    'rf_status': ['Radio', '', 'mdi:signal', None],
    'rf_status_lvl': ['Radio_lvl', '', 'mdi:signal', None],
    'wifi_status': ['Wifi', '', 'mdi:wifi', None],
    'wifi_status_lvl': ['Wifi_lvl', 'dBm', 'mdi:wifi', None],
    'health_idx': ['Health', '', 'mdi:cloud', None],
}

MODULE_SCHEMA = vol.Schema({
    vol.Required(cv.string): vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_STATION): cv.string,
    vol.Optional(CONF_MODULES): MODULE_SCHEMA,
    vol.Optional(CONF_AREAS): vol.All(cv.ensure_list, [
        {
            vol.Required(CONF_LAT_NE): cv.latitude,
            vol.Required(CONF_LAT_SW): cv.latitude,
            vol.Required(CONF_LON_NE): cv.longitude,
            vol.Required(CONF_LON_SW): cv.longitude,
            vol.Required(CONF_MONITORED_CONDITIONS): [vol.In(
                SUPPORTED_PUBLIC_SENSOR_TYPES)],
            vol.Optional(CONF_MODE, default=DEFAULT_MODE): vol.In(MODE_TYPES),
            vol.Optional(CONF_NAME, default=DEFAULT_NAME_PUBLIC): cv.string
        }
    ]),
})

MODULE_TYPE_OUTDOOR = 'NAModule1'
MODULE_TYPE_WIND = 'NAModule2'
MODULE_TYPE_RAIN = 'NAModule3'
MODULE_TYPE_INDOOR = 'NAModule4'


NETATMO_DEVICE_TYPES = {
    'WeatherStationData': 'weather station',
    'HomeCoachData': 'home coach'
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the available Netatmo weather sensors."""
    dev = []
    auth = hass.data[DATA_NETATMO_AUTH]

    if config.get(CONF_AREAS) is not None:
        for area in config[CONF_AREAS]:
            data = NetatmoPublicData(
                auth,
                lat_ne=area[CONF_LAT_NE],
                lon_ne=area[CONF_LON_NE],
                lat_sw=area[CONF_LAT_SW],
                lon_sw=area[CONF_LON_SW]
            )
            for sensor_type in area[CONF_MONITORED_CONDITIONS]:
                dev.append(NetatmoPublicSensor(
                    area[CONF_NAME],
                    data,
                    sensor_type,
                    area[CONF_MODE]
                ))
    else:
        def _retry(_data):
            try:
                _dev = find_devices(_data)
            except requests.exceptions.Timeout:
                return call_later(hass, NETATMO_UPDATE_INTERVAL,
                                  lambda _: _retry(_data))
            if _dev:
                add_entities(_dev, True)

        import pyatmo
        for data_class in [pyatmo.WeatherStationData, pyatmo.HomeCoachData]:
            try:
                data = NetatmoData(auth, data_class, config.get(CONF_STATION))
            except pyatmo.NoDevice:
                _LOGGER.warning(
                    "No %s devices found",
                    NETATMO_DEVICE_TYPES[data_class.__name__]
                )
                continue
            # Test if manually configured
            if CONF_MODULES in config:
                module_items = config[CONF_MODULES].items()
                module_names = data.get_module_names()
                for module_name, monitored_conditions in module_items:
                    if module_name not in module_names:
                        continue
                    for condition in monitored_conditions:
                        dev.append(NetatmoSensor(
                            data, module_name, condition.lower(),
                            config.get(CONF_STATION)))
                continue

            # otherwise add all modules and conditions
            try:
                dev.extend(find_devices(data))
            except requests.exceptions.Timeout:
                call_later(hass, NETATMO_UPDATE_INTERVAL,
                           lambda _: _retry(data))

    if dev:
        add_entities(dev, True)


def find_devices(data):
    """Find all devices."""
    dev = []
    module_names = data.get_module_names()
    for module_name in module_names:
        for condition in data.station_data.monitoredConditions(module_name):
            dev.append(NetatmoSensor(
                data, module_name, condition.lower(), data.station))
    return dev


class NetatmoSensor(Entity):
    """Implementation of a Netatmo sensor."""

    def __init__(self, netatmo_data, module_name, sensor_type, station):
        """Initialize the sensor."""
        self._name = 'Netatmo {} {}'.format(module_name,
                                            SENSOR_TYPES[sensor_type][0])
        self.netatmo_data = netatmo_data
        self.module_name = module_name
        self.type = sensor_type
        self.station_name = station
        self._state = None
        self._device_class = SENSOR_TYPES[self.type][3]
        self._icon = SENSOR_TYPES[self.type][2]
        self._unit_of_measurement = SENSOR_TYPES[self.type][1]
        module = self.netatmo_data.station_data.moduleByName(
            station=self.station_name, module=module_name
        )
        self._module_type = module['type']
        self._unique_id = '{}-{}'.format(module['_id'], self.type)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def unique_id(self):
        """Return the unique ID for this sensor."""
        return self._unique_id

    def update(self):
        """Get the latest data from Netatmo API and updates the states."""
        self.netatmo_data.update()
        if self.netatmo_data.data is None:
            if self._state is None:
                return
            _LOGGER.warning("No data found for %s", self.module_name)
            self._state = None
            return

        data = self.netatmo_data.data.get(self.module_name)

        if data is None:
            _LOGGER.warning("No data found for %s", self.module_name)
            self._state = None
            return

        try:
            if self.type == 'temperature':
                self._state = round(data['Temperature'], 1)
            elif self.type == 'humidity':
                self._state = data['Humidity']
            elif self.type == 'rain':
                self._state = data['Rain']
            elif self.type == 'sum_rain_1':
                self._state = data['sum_rain_1']
            elif self.type == 'sum_rain_24':
                self._state = data['sum_rain_24']
            elif self.type == 'noise':
                self._state = data['Noise']
            elif self.type == 'co2':
                self._state = data['CO2']
            elif self.type == 'pressure':
                self._state = round(data['Pressure'], 1)
            elif self.type == 'battery_percent':
                self._state = data['battery_percent']
            elif self.type == 'battery_lvl':
                self._state = data['battery_vp']
            elif (self.type == 'battery_vp' and
                  self._module_type == MODULE_TYPE_WIND):
                if data['battery_vp'] >= 5590:
                    self._state = "Full"
                elif data['battery_vp'] >= 5180:
                    self._state = "High"
                elif data['battery_vp'] >= 4770:
                    self._state = "Medium"
                elif data['battery_vp'] >= 4360:
                    self._state = "Low"
                elif data['battery_vp'] < 4360:
                    self._state = "Very Low"
            elif (self.type == 'battery_vp' and
                  self._module_type == MODULE_TYPE_RAIN):
                if data['battery_vp'] >= 5500:
                    self._state = "Full"
                elif data['battery_vp'] >= 5000:
                    self._state = "High"
                elif data['battery_vp'] >= 4500:
                    self._state = "Medium"
                elif data['battery_vp'] >= 4000:
                    self._state = "Low"
                elif data['battery_vp'] < 4000:
                    self._state = "Very Low"
            elif (self.type == 'battery_vp' and
                  self._module_type == MODULE_TYPE_INDOOR):
                if data['battery_vp'] >= 5640:
                    self._state = "Full"
                elif data['battery_vp'] >= 5280:
                    self._state = "High"
                elif data['battery_vp'] >= 4920:
                    self._state = "Medium"
                elif data['battery_vp'] >= 4560:
                    self._state = "Low"
                elif data['battery_vp'] < 4560:
                    self._state = "Very Low"
            elif (self.type == 'battery_vp' and
                  self._module_type == MODULE_TYPE_OUTDOOR):
                if data['battery_vp'] >= 5500:
                    self._state = "Full"
                elif data['battery_vp'] >= 5000:
                    self._state = "High"
                elif data['battery_vp'] >= 4500:
                    self._state = "Medium"
                elif data['battery_vp'] >= 4000:
                    self._state = "Low"
                elif data['battery_vp'] < 4000:
                    self._state = "Very Low"
            elif self.type == 'min_temp':
                self._state = data['min_temp']
            elif self.type == 'max_temp':
                self._state = data['max_temp']
            elif self.type == 'windangle_value':
                self._state = data['WindAngle']
            elif self.type == 'windangle':
                if data['WindAngle'] >= 330:
                    self._state = "N (%d\xb0)" % data['WindAngle']
                elif data['WindAngle'] >= 300:
                    self._state = "NW (%d\xb0)" % data['WindAngle']
                elif data['WindAngle'] >= 240:
                    self._state = "W (%d\xb0)" % data['WindAngle']
                elif data['WindAngle'] >= 210:
                    self._state = "SW (%d\xb0)" % data['WindAngle']
                elif data['WindAngle'] >= 150:
                    self._state = "S (%d\xb0)" % data['WindAngle']
                elif data['WindAngle'] >= 120:
                    self._state = "SE (%d\xb0)" % data['WindAngle']
                elif data['WindAngle'] >= 60:
                    self._state = "E (%d\xb0)" % data['WindAngle']
                elif data['WindAngle'] >= 30:
                    self._state = "NE (%d\xb0)" % data['WindAngle']
                elif data['WindAngle'] >= 0:
                    self._state = "N (%d\xb0)" % data['WindAngle']
            elif self.type == 'windstrength':
                self._state = data['WindStrength']
            elif self.type == 'gustangle_value':
                self._state = data['GustAngle']
            elif self.type == 'gustangle':
                if data['GustAngle'] >= 330:
                    self._state = "N (%d\xb0)" % data['GustAngle']
                elif data['GustAngle'] >= 300:
                    self._state = "NW (%d\xb0)" % data['GustAngle']
                elif data['GustAngle'] >= 240:
                    self._state = "W (%d\xb0)" % data['GustAngle']
                elif data['GustAngle'] >= 210:
                    self._state = "SW (%d\xb0)" % data['GustAngle']
                elif data['GustAngle'] >= 150:
                    self._state = "S (%d\xb0)" % data['GustAngle']
                elif data['GustAngle'] >= 120:
                    self._state = "SE (%d\xb0)" % data['GustAngle']
                elif data['GustAngle'] >= 60:
                    self._state = "E (%d\xb0)" % data['GustAngle']
                elif data['GustAngle'] >= 30:
                    self._state = "NE (%d\xb0)" % data['GustAngle']
                elif data['GustAngle'] >= 0:
                    self._state = "N (%d\xb0)" % data['GustAngle']
            elif self.type == 'guststrength':
                self._state = data['GustStrength']
            elif self.type == 'rf_status_lvl':
                self._state = data['rf_status']
            elif self.type == 'rf_status':
                if data['rf_status'] >= 90:
                    self._state = "Low"
                elif data['rf_status'] >= 76:
                    self._state = "Medium"
                elif data['rf_status'] >= 60:
                    self._state = "High"
                elif data['rf_status'] <= 59:
                    self._state = "Full"
            elif self.type == 'wifi_status_lvl':
                self._state = data['wifi_status']
            elif self.type == 'wifi_status':
                if data['wifi_status'] >= 86:
                    self._state = "Low"
                elif data['wifi_status'] >= 71:
                    self._state = "Medium"
                elif data['wifi_status'] >= 56:
                    self._state = "High"
                elif data['wifi_status'] <= 55:
                    self._state = "Full"
            elif self.type == 'health_idx':
                if data['health_idx'] == 0:
                    self._state = "Healthy"
                elif data['health_idx'] == 1:
                    self._state = "Fine"
                elif data['health_idx'] == 2:
                    self._state = "Fair"
                elif data['health_idx'] == 3:
                    self._state = "Poor"
                elif data['health_idx'] == 4:
                    self._state = "Unhealthy"
        except KeyError:
            _LOGGER.error("No %s data found for %s", self.type,
                          self.module_name)
            self._state = None
            return


class NetatmoPublicSensor(Entity):
    """Represent a single sensor in a Netatmo."""

    def __init__(self, area_name, data, sensor_type, mode):
        """Initialize the sensor."""
        self.netatmo_data = data
        self.type = sensor_type
        self._mode = mode
        self._name = '{} {}'.format(area_name,
                                    SENSOR_TYPES[self.type][0])
        self._area_name = area_name
        self._state = None
        self._device_class = SENSOR_TYPES[self.type][3]
        self._icon = SENSOR_TYPES[self.type][2]
        self._unit_of_measurement = SENSOR_TYPES[self.type][1]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return self._icon

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return self._unit_of_measurement

    def update(self):
        """Get the latest data from Netatmo API and updates the states."""
        self.netatmo_data.update()

        if self.netatmo_data.data is None:
            _LOGGER.warning("No data found for %s", self._name)
            self._state = None
            return

        data = None

        if self.type == 'temperature':
            data = self.netatmo_data.data.getLatestTemperatures()
        elif self.type == 'pressure':
            data = self.netatmo_data.data.getLatestPressures()
        elif self.type == 'humidity':
            data = self.netatmo_data.data.getLatestHumidities()
        elif self.type == 'rain':
            data = self.netatmo_data.data.getLatestRain()
        elif self.type == 'windstrength':
            data = self.netatmo_data.data.getLatestWindStrengths()
        elif self.type == 'guststrength':
            data = self.netatmo_data.data.getLatestGustStrengths()

        if not data:
            _LOGGER.warning("No station provides %s data in the area %s",
                            self.type, self._area_name)
            self._state = None
            return

        if self._mode == 'avg':
            self._state = round(sum(data.values()) / len(data), 1)
        elif self._mode == 'max':
            self._state = max(data.values())


class NetatmoPublicData:
    """Get the latest data from Netatmo."""

    def __init__(self, auth, lat_ne, lon_ne, lat_sw, lon_sw):
        """Initialize the data object."""
        self.auth = auth
        self.data = None
        self.lat_ne = lat_ne
        self.lon_ne = lon_ne
        self.lat_sw = lat_sw
        self.lon_sw = lon_sw

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Request an update from the Netatmo API."""
        import pyatmo
        data = pyatmo.PublicData(self.auth,
                                 LAT_NE=self.lat_ne,
                                 LON_NE=self.lon_ne,
                                 LAT_SW=self.lat_sw,
                                 LON_SW=self.lon_sw,
                                 filtering=True)

        if data.CountStationInArea() == 0:
            _LOGGER.warning('No Stations available in this area.')
            return

        self.data = data


class NetatmoData:
    """Get the latest data from Netatmo."""

    def __init__(self, auth, data_class, station):
        """Initialize the data object."""
        self.auth = auth
        self.data_class = data_class
        self.data = {}
        self.station_data = self.data_class(self.auth)
        self.station = station
        self._next_update = time()
        self._update_in_progress = threading.Lock()

    def get_module_names(self):
        """Return all module available on the API as a list."""
        if self.station is not None:
            return self.station_data.modulesNamesList(station=self.station)
        return self.station_data.modulesNamesList()

    def update(self):
        """Call the Netatmo API to update the data.

        This method is not throttled by the builtin Throttle decorator
        but with a custom logic, which takes into account the time
        of the last update from the cloud.
        """
        if time() < self._next_update or \
                not self._update_in_progress.acquire(False):
            return
        try:
            from pyatmo import NoDevice
            try:
                self.station_data = self.data_class(self.auth)
                _LOGGER.debug("%s detected!", str(self.data_class.__name__))
            except NoDevice:
                _LOGGER.warning("No Weather or HomeCoach devices found for %s",
                                str(self.station)
                                )
                return
            except requests.exceptions.Timeout:
                _LOGGER.warning("Timed out when connecting to Netatmo server.")
                return

            if self.station is not None:
                data = self.station_data.lastData(
                    station=self.station, exclude=3600)
            else:
                data = self.station_data.lastData(exclude=3600)
            if not data:
                self._next_update = time() + NETATMO_UPDATE_INTERVAL
                return
            self.data = data

            newinterval = 0
            try:
                for module in self.data:
                    if 'When' in self.data[module]:
                        newinterval = self.data[module]['When']
                        break
            except TypeError:
                _LOGGER.debug("No %s modules found", self.data_class.__name__)

            if newinterval:
                # Try and estimate when fresh data will be available
                newinterval += NETATMO_UPDATE_INTERVAL - time()
                if newinterval > NETATMO_UPDATE_INTERVAL - 30:
                    newinterval = NETATMO_UPDATE_INTERVAL
                else:
                    if newinterval < NETATMO_UPDATE_INTERVAL / 2:
                        # Never hammer the Netatmo API more than
                        # twice per update interval
                        newinterval = NETATMO_UPDATE_INTERVAL / 2
                    _LOGGER.info(
                        "Netatmo refresh interval reset to %d seconds",
                        newinterval)
            else:
                # Last update time not found, fall back to default value
                newinterval = NETATMO_UPDATE_INTERVAL

            self._next_update = time() + newinterval
        finally:
            self._update_in_progress.release()
