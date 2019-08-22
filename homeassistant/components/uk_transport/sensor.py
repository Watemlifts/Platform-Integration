"""Support for UK public transport data provided by transportapi.com.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.uk_transport/
"""
import logging
import re
from datetime import datetime, timedelta

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_MODE
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

ATTR_ATCOCODE = 'atcocode'
ATTR_LOCALITY = 'locality'
ATTR_STOP_NAME = 'stop_name'
ATTR_REQUEST_TIME = 'request_time'
ATTR_NEXT_BUSES = 'next_buses'
ATTR_STATION_CODE = 'station_code'
ATTR_CALLING_AT = 'calling_at'
ATTR_NEXT_TRAINS = 'next_trains'

CONF_API_APP_KEY = 'app_key'
CONF_API_APP_ID = 'app_id'
CONF_QUERIES = 'queries'
CONF_ORIGIN = 'origin'
CONF_DESTINATION = 'destination'

_QUERY_SCHEME = vol.Schema({
    vol.Required(CONF_MODE):
        vol.All(cv.ensure_list, [vol.In(list(['bus', 'train']))]),
    vol.Required(CONF_ORIGIN): cv.string,
    vol.Required(CONF_DESTINATION): cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_APP_ID): cv.string,
    vol.Required(CONF_API_APP_KEY): cv.string,
    vol.Required(CONF_QUERIES): [_QUERY_SCHEME],
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Get the uk_transport sensor."""
    sensors = []
    number_sensors = len(config.get(CONF_QUERIES))
    interval = timedelta(seconds=87*number_sensors)

    for query in config.get(CONF_QUERIES):
        if 'bus' in query.get(CONF_MODE):
            stop_atcocode = query.get(CONF_ORIGIN)
            bus_direction = query.get(CONF_DESTINATION)
            sensors.append(
                UkTransportLiveBusTimeSensor(
                    config.get(CONF_API_APP_ID),
                    config.get(CONF_API_APP_KEY),
                    stop_atcocode,
                    bus_direction,
                    interval))

        elif 'train' in query.get(CONF_MODE):
            station_code = query.get(CONF_ORIGIN)
            calling_at = query.get(CONF_DESTINATION)
            sensors.append(
                UkTransportLiveTrainTimeSensor(
                    config.get(CONF_API_APP_ID),
                    config.get(CONF_API_APP_KEY),
                    station_code,
                    calling_at,
                    interval))

    add_entities(sensors, True)


class UkTransportSensor(Entity):
    """
    Sensor that reads the UK transport web API.

    transportapi.com provides comprehensive transport data for UK train, tube
    and bus travel across the UK via simple JSON API. Subclasses of this
    base class can be used to access specific types of information.
    """

    TRANSPORT_API_URL_BASE = "https://transportapi.com/v3/uk/"
    ICON = 'mdi:train'

    def __init__(self, name, api_app_id, api_app_key, url):
        """Initialize the sensor."""
        self._data = {}
        self._api_app_id = api_app_id
        self._api_app_key = api_app_key
        self._url = self.TRANSPORT_API_URL_BASE + url
        self._name = name
        self._state = None

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
        """Return the unit this state is expressed in."""
        return "min"

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self.ICON

    def _do_api_request(self, params):
        """Perform an API request."""
        request_params = dict({
            'app_id': self._api_app_id,
            'app_key': self._api_app_key,
        }, **params)

        response = requests.get(self._url, params=request_params)
        if response.status_code != 200:
            _LOGGER.warning('Invalid response from API')
        elif 'error' in response.json():
            if 'exceeded' in response.json()['error']:
                self._state = 'Usage limits exceeded'
            if 'invalid' in response.json()['error']:
                self._state = 'Credentials invalid'
        else:
            self._data = response.json()


class UkTransportLiveBusTimeSensor(UkTransportSensor):
    """Live bus time sensor from UK transportapi.com."""

    ICON = 'mdi:bus'

    def __init__(self, api_app_id, api_app_key,
                 stop_atcocode, bus_direction, interval):
        """Construct a live bus time sensor."""
        self._stop_atcocode = stop_atcocode
        self._bus_direction = bus_direction
        self._next_buses = []
        self._destination_re = re.compile(
            '{}'.format(bus_direction), re.IGNORECASE
        )

        sensor_name = 'Next bus to {}'.format(bus_direction)
        stop_url = 'bus/stop/{}/live.json'.format(stop_atcocode)

        UkTransportSensor.__init__(
            self, sensor_name, api_app_id, api_app_key, stop_url
        )
        self.update = Throttle(interval)(self._update)

    def _update(self):
        """Get the latest live departure data for the specified stop."""
        params = {'group': 'route', 'nextbuses': 'no'}

        self._do_api_request(params)

        if self._data != {}:
            self._next_buses = []

            for (route, departures) in self._data['departures'].items():
                for departure in departures:
                    if self._destination_re.search(departure['direction']):
                        self._next_buses.append({
                            'route': route,
                            'direction': departure['direction'],
                            'scheduled': departure['aimed_departure_time'],
                            'estimated': departure['best_departure_estimate']
                        })

            if self._next_buses:
                self._state = min(
                    _delta_mins(bus['scheduled'])
                    for bus in self._next_buses)
            else:
                self._state = None

    @property
    def device_state_attributes(self):
        """Return other details about the sensor state."""
        attrs = {}
        if self._data is not None:
            for key in [
                    ATTR_ATCOCODE, ATTR_LOCALITY, ATTR_STOP_NAME,
                    ATTR_REQUEST_TIME
            ]:
                attrs[key] = self._data.get(key)
            attrs[ATTR_NEXT_BUSES] = self._next_buses
            return attrs


class UkTransportLiveTrainTimeSensor(UkTransportSensor):
    """Live train time sensor from UK transportapi.com."""

    ICON = 'mdi:train'

    def __init__(self, api_app_id, api_app_key,
                 station_code, calling_at, interval):
        """Construct a live bus time sensor."""
        self._station_code = station_code
        self._calling_at = calling_at
        self._next_trains = []

        sensor_name = 'Next train to {}'.format(calling_at)
        query_url = 'train/station/{}/live.json'.format(station_code)

        UkTransportSensor.__init__(
            self, sensor_name, api_app_id, api_app_key, query_url
        )
        self.update = Throttle(interval)(self._update)

    def _update(self):
        """Get the latest live departure data for the specified stop."""
        params = {'darwin': 'false',
                  'calling_at': self._calling_at,
                  'train_status': 'passenger'}

        self._do_api_request(params)
        self._next_trains = []

        if self._data != {}:
            if self._data['departures']['all'] == []:
                self._state = 'No departures'
            else:
                for departure in self._data['departures']['all']:
                    self._next_trains.append({
                        'origin_name': departure['origin_name'],
                        'destination_name': departure['destination_name'],
                        'status': departure['status'],
                        'scheduled': departure['aimed_departure_time'],
                        'estimated': departure['expected_departure_time'],
                        'platform': departure['platform'],
                        'operator_name': departure['operator_name']
                        })

                if self._next_trains:
                    self._state = min(
                        _delta_mins(train['scheduled'])
                        for train in self._next_trains)
                else:
                    self._state = None

    @property
    def device_state_attributes(self):
        """Return other details about the sensor state."""
        attrs = {}
        if self._data is not None:
            attrs[ATTR_STATION_CODE] = self._station_code
            attrs[ATTR_CALLING_AT] = self._calling_at
            if self._next_trains:
                attrs[ATTR_NEXT_TRAINS] = self._next_trains
            return attrs


def _delta_mins(hhmm_time_str):
    """Calculate time delta in minutes to a time in hh:mm format."""
    now = datetime.now()
    hhmm_time = datetime.strptime(hhmm_time_str, '%H:%M')

    hhmm_datetime = datetime(
        now.year, now.month, now.day,
        hour=hhmm_time.hour, minute=hhmm_time.minute
    )
    if hhmm_datetime < now:
        hhmm_datetime += timedelta(days=1)

    delta_mins = (hhmm_datetime - now).seconds // 60
    return delta_mins
