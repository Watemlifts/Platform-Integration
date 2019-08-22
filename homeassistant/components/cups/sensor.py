"""Details about printers which are connected to CUPS."""
import importlib
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

ATTR_DEVICE_URI = 'device_uri'
ATTR_PRINTER_INFO = 'printer_info'
ATTR_PRINTER_IS_SHARED = 'printer_is_shared'
ATTR_PRINTER_LOCATION = 'printer_location'
ATTR_PRINTER_MODEL = 'printer_model'
ATTR_PRINTER_STATE_MESSAGE = 'printer_state_message'
ATTR_PRINTER_STATE_REASON = 'printer_state_reason'
ATTR_PRINTER_TYPE = 'printer_type'
ATTR_PRINTER_URI_SUPPORTED = 'printer_uri_supported'

CONF_PRINTERS = 'printers'
CONF_IS_CUPS_SERVER = 'is_cups_server'

DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 631
DEFAULT_IS_CUPS_SERVER = True

ICON = 'mdi:printer'

SCAN_INTERVAL = timedelta(minutes=1)

PRINTER_STATES = {
    3: 'idle',
    4: 'printing',
    5: 'stopped',
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PRINTERS): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_IS_CUPS_SERVER,
                 default=DEFAULT_IS_CUPS_SERVER): cv.boolean,
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the CUPS sensor."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    printers = config.get(CONF_PRINTERS)
    is_cups = config.get(CONF_IS_CUPS_SERVER)

    if is_cups:
        data = CupsData(host, port, None)
        data.update()
        if data.available is False:
            _LOGGER.error("Unable to connect to CUPS server: %s:%s",
                          host, port)
            raise PlatformNotReady()

        dev = []
        for printer in printers:
            if printer not in data.printers:
                _LOGGER.error("Printer is not present: %s", printer)
                continue
            dev.append(CupsSensor(data, printer))

        add_entities(dev, True)
        return

    data = CupsData(host, port, printers)
    data.update()
    if data.available is False:
        _LOGGER.error("Unable to connect to IPP printer: %s:%s",
                      host, port)
        raise PlatformNotReady()

    dev = []
    for printer in printers:
        dev.append(IPPSensor(data, printer))

    add_entities(dev, True)


class CupsSensor(Entity):
    """Representation of a CUPS sensor."""

    def __init__(self, data, printer):
        """Initialize the CUPS sensor."""
        self.data = data
        self._name = printer
        self._printer = None
        self._available = False

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._printer is None:
            return None

        key = self._printer['printer-state']
        return PRINTER_STATES.get(key, key)

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        if self._printer is None:
            return None

        return {
            ATTR_DEVICE_URI: self._printer['device-uri'],
            ATTR_PRINTER_INFO: self._printer['printer-info'],
            ATTR_PRINTER_IS_SHARED: self._printer['printer-is-shared'],
            ATTR_PRINTER_LOCATION: self._printer['printer-location'],
            ATTR_PRINTER_MODEL: self._printer['printer-make-and-model'],
            ATTR_PRINTER_STATE_MESSAGE:
                self._printer['printer-state-message'],
            ATTR_PRINTER_STATE_REASON:
                self._printer['printer-state-reasons'],
            ATTR_PRINTER_TYPE: self._printer['printer-type'],
            ATTR_PRINTER_URI_SUPPORTED:
                self._printer['printer-uri-supported'],
        }

    def update(self):
        """Get the latest data and updates the states."""
        self.data.update()
        self._printer = self.data.printers.get(self._name)
        self._available = self.data.available


class IPPSensor(Entity):
    """Implementation of the IPPSensor.

    This sensor represents the status of the printer.
    """

    def __init__(self, data, name):
        """Initialize the sensor."""
        self.data = data
        self._name = name
        self._attributes = None
        self._available = False

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._attributes['printer-make-and-model']

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return ICON

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._attributes is None:
            return None

        key = self._attributes['printer-state']
        return PRINTER_STATES.get(key, key)

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        if self._attributes is None:
            return None

        state_attributes = {}

        if 'printer-info' in self._attributes:
            state_attributes[ATTR_PRINTER_INFO] = \
                self._attributes['printer-info']

        if 'printer-location' in self._attributes:
            state_attributes[ATTR_PRINTER_LOCATION] = \
                self._attributes['printer-location']

        if 'printer-state-message' in self._attributes:
            state_attributes[ATTR_PRINTER_STATE_MESSAGE] = \
                self._attributes['printer-state-message']

        if 'printer-state-reasons' in self._attributes:
            state_attributes[ATTR_PRINTER_STATE_REASON] = \
                self._attributes['printer-state-reasons']

        if 'printer-uri-supported' in self._attributes:
            state_attributes[ATTR_PRINTER_URI_SUPPORTED] = \
                self._attributes['printer-uri-supported']

        return state_attributes

    def update(self):
        """Fetch new state data for the sensor."""
        self.data.update()
        self._attributes = self.data.attributes.get(self._name)
        self._available = self.data.available


# pylint: disable=no-name-in-module
class CupsData:
    """Get the latest data from CUPS and update the state."""

    def __init__(self, host, port, ipp_printers):
        """Initialize the data object."""
        self._host = host
        self._port = port
        self._ipp_printers = ipp_printers
        self.is_cups = (ipp_printers is None)
        self.printers = None
        self.attributes = {}
        self.available = False

    def update(self):
        """Get the latest data from CUPS."""
        cups = importlib.import_module('cups')

        try:
            conn = cups.Connection(host=self._host, port=self._port)
            if self.is_cups:
                self.printers = conn.getPrinters()
            else:
                for ipp_printer in self._ipp_printers:
                    self.attributes[ipp_printer] = conn.getPrinterAttributes(
                        uri="ipp://{}:{}/{}"
                        .format(self._host, self._port, ipp_printer))

            self.available = True
        except RuntimeError:
            self.available = False
