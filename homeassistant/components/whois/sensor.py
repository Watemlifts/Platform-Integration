"""Get WHOIS information for a given host."""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

CONF_DOMAIN = 'domain'

DEFAULT_NAME = 'Whois'

ATTR_EXPIRES = 'expires'
ATTR_NAME_SERVERS = 'name_servers'
ATTR_REGISTRAR = 'registrar'
ATTR_UPDATED = 'updated'

SCAN_INTERVAL = timedelta(hours=24)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DOMAIN): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the WHOIS sensor."""
    import whois

    domain = config.get(CONF_DOMAIN)
    name = config.get(CONF_NAME)

    try:
        if 'expiration_date' in whois.whois(domain):
            add_entities([WhoisSensor(name, domain)], True)
        else:
            _LOGGER.error(
                "WHOIS lookup for %s didn't contain expiration_date",
                domain)
            return
    except whois.BaseException as ex:
        _LOGGER.error(
            "Exception %s occurred during WHOIS lookup for %s", ex, domain)
        return


class WhoisSensor(Entity):
    """Implementation of a WHOIS sensor."""

    def __init__(self, name, domain):
        """Initialize the sensor."""
        import whois

        self.whois = whois.whois

        self._name = name
        self._domain = domain

        self._state = None
        self._attributes = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon to represent this sensor."""
        return 'mdi:calendar-clock'

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement to present the value in."""
        return 'days'

    @property
    def state(self):
        """Return the expiration days for hostname."""
        return self._state

    @property
    def device_state_attributes(self):
        """Get the more info attributes."""
        return self._attributes

    def _empty_state_and_attributes(self):
        """Empty the state and attributes on an error."""
        self._state = None
        self._attributes = None

    def update(self):
        """Get the current WHOIS data for the domain."""
        import whois

        try:
            response = self.whois(self._domain)
        except whois.BaseException as ex:
            _LOGGER.error("Exception %s occurred during WHOIS lookup", ex)
            self._empty_state_and_attributes()
            return

        if response:
            if 'expiration_date' not in response:
                _LOGGER.error(
                    "Failed to find expiration_date in whois lookup response. "
                    "Did find: %s", ', '.join(response.keys()))
                self._empty_state_and_attributes()
                return

            if not response['expiration_date']:
                _LOGGER.error("Whois response contains empty expiration_date")
                self._empty_state_and_attributes()
                return

            attrs = {}

            expiration_date = response['expiration_date']
            attrs[ATTR_EXPIRES] = expiration_date.isoformat()

            if 'nameservers' in response:
                attrs[ATTR_NAME_SERVERS] = ' '.join(response['nameservers'])

            if 'updated_date' in response:
                update_date = response['updated_date']
                if isinstance(update_date, list):
                    attrs[ATTR_UPDATED] = update_date[0].isoformat()
                else:
                    attrs[ATTR_UPDATED] = update_date.isoformat()

            if 'registrar' in response:
                attrs[ATTR_REGISTRAR] = response['registrar']

            time_delta = (expiration_date - expiration_date.now())

            self._attributes = attrs
            self._state = time_delta.days
