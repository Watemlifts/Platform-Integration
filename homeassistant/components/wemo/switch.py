"""Support for WeMo switches."""
import asyncio
import logging
from datetime import datetime, timedelta
import requests

import async_timeout

from homeassistant.components.switch import SwitchDevice
from homeassistant.exceptions import PlatformNotReady
from homeassistant.util import convert
from homeassistant.const import (
    STATE_OFF, STATE_ON, STATE_STANDBY, STATE_UNKNOWN)

from . import SUBSCRIPTION_REGISTRY, DOMAIN as WEMO_DOMAIN

SCAN_INTERVAL = timedelta(seconds=10)

_LOGGER = logging.getLogger(__name__)

ATTR_SENSOR_STATE = 'sensor_state'
ATTR_SWITCH_MODE = 'switch_mode'
ATTR_CURRENT_STATE_DETAIL = 'state_detail'
ATTR_COFFEMAKER_MODE = 'coffeemaker_mode'

MAKER_SWITCH_MOMENTARY = 'momentary'
MAKER_SWITCH_TOGGLE = 'toggle'

WEMO_ON = 1
WEMO_OFF = 0
WEMO_STANDBY = 8


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up discovered WeMo switches."""
    from pywemo import discovery

    if discovery_info is not None:
        location = discovery_info['ssdp_description']
        mac = discovery_info['mac_address']

        try:
            device = discovery.device_from_description(location, mac)
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as err:
            _LOGGER.error("Unable to access %s (%s)", location, err)
            raise PlatformNotReady

        if device:
            add_entities([WemoSwitch(device)])


class WemoSwitch(SwitchDevice):
    """Representation of a WeMo switch."""

    def __init__(self, device):
        """Initialize the WeMo switch."""
        self.wemo = device
        self.insight_params = None
        self.maker_params = None
        self.coffeemaker_mode = None
        self._state = None
        self._mode_string = None
        self._available = True
        self._update_lock = None
        self._model_name = self.wemo.model_name
        self._name = self.wemo.name
        self._serialnumber = self.wemo.serialnumber

    def _subscription_callback(self, _device, _type, _params):
        """Update the state by the Wemo device."""
        _LOGGER.info("Subscription update for %s", self.name)
        updated = self.wemo.subscription_update(_type, _params)
        self.hass.add_job(
            self._async_locked_subscription_callback(not updated))

    async def _async_locked_subscription_callback(self, force_update):
        """Handle an update from a subscription."""
        # If an update is in progress, we don't do anything
        if self._update_lock.locked():
            return

        await self._async_locked_update(force_update)
        self.async_schedule_update_ha_state()

    @property
    def unique_id(self):
        """Return the ID of this WeMo switch."""
        return self._serialnumber

    @property
    def name(self):
        """Return the name of the switch if any."""
        return self._name

    @property
    def device_info(self):
        """Return the device info."""
        return {
            'name': self._name,
            'identifiers': {(WEMO_DOMAIN, self._serialnumber)},
        }

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {}
        if self.maker_params:
            # Is the maker sensor on or off.
            if self.maker_params['hassensor']:
                # Note a state of 1 matches the WeMo app 'not triggered'!
                if self.maker_params['sensorstate']:
                    attr[ATTR_SENSOR_STATE] = STATE_OFF
                else:
                    attr[ATTR_SENSOR_STATE] = STATE_ON

            # Is the maker switch configured as toggle(0) or momentary (1).
            if self.maker_params['switchmode']:
                attr[ATTR_SWITCH_MODE] = MAKER_SWITCH_MOMENTARY
            else:
                attr[ATTR_SWITCH_MODE] = MAKER_SWITCH_TOGGLE

        if self.insight_params or (self.coffeemaker_mode is not None):
            attr[ATTR_CURRENT_STATE_DETAIL] = self.detail_state

        if self.insight_params:
            attr['on_latest_time'] = \
                WemoSwitch.as_uptime(self.insight_params['onfor'])
            attr['on_today_time'] = \
                WemoSwitch.as_uptime(self.insight_params['ontoday'])
            attr['on_total_time'] = \
                WemoSwitch.as_uptime(self.insight_params['ontotal'])
            attr['power_threshold_w'] = \
                convert(
                    self.insight_params['powerthreshold'], float, 0.0
                ) / 1000.0

        if self.coffeemaker_mode is not None:
            attr[ATTR_COFFEMAKER_MODE] = self.coffeemaker_mode

        return attr

    @staticmethod
    def as_uptime(_seconds):
        """Format seconds into uptime string in the format: 00d 00h 00m 00s."""
        uptime = datetime(1, 1, 1) + timedelta(seconds=_seconds)
        return "{:0>2d}d {:0>2d}h {:0>2d}m {:0>2d}s".format(
            uptime.day-1, uptime.hour, uptime.minute, uptime.second)

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        if self.insight_params:
            return convert(
                self.insight_params['currentpower'], float, 0.0
                ) / 1000.0

    @property
    def today_energy_kwh(self):
        """Return the today total energy usage in kWh."""
        if self.insight_params:
            miliwatts = convert(self.insight_params['todaymw'], float, 0.0)
            return round(miliwatts / (1000.0 * 1000.0 * 60), 2)

    @property
    def detail_state(self):
        """Return the state of the device."""
        if self.coffeemaker_mode is not None:
            return self._mode_string
        if self.insight_params:
            standby_state = int(self.insight_params['state'])
            if standby_state == WEMO_ON:
                return STATE_ON
            if standby_state == WEMO_OFF:
                return STATE_OFF
            if standby_state == WEMO_STANDBY:
                return STATE_STANDBY
            return STATE_UNKNOWN

    @property
    def is_on(self):
        """Return true if switch is on. Standby is on."""
        return self._state

    @property
    def available(self):
        """Return true if switch is available."""
        return self._available

    @property
    def icon(self):
        """Return the icon of device based on its type."""
        if self._model_name == 'CoffeeMaker':
            return 'mdi:coffee'
        return None

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self.wemo.on()

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self.wemo.off()

    async def async_added_to_hass(self):
        """Wemo switch added to HASS."""
        # Define inside async context so we know our event loop
        self._update_lock = asyncio.Lock()

        registry = SUBSCRIPTION_REGISTRY
        await self.hass.async_add_job(registry.register, self.wemo)
        registry.on(self.wemo, None, self._subscription_callback)

    async def async_update(self):
        """Update WeMo state.

        Wemo has an aggressive retry logic that sometimes can take over a
        minute to return. If we don't get a state after 5 seconds, assume the
        Wemo switch is unreachable. If update goes through, it will be made
        available again.
        """
        # If an update is in progress, we don't do anything
        if self._update_lock.locked():
            return

        try:
            with async_timeout.timeout(5):
                await asyncio.shield(self._async_locked_update(True))
        except asyncio.TimeoutError:
            _LOGGER.warning('Lost connection to %s', self.name)
            self._available = False

    async def _async_locked_update(self, force_update):
        """Try updating within an async lock."""
        async with self._update_lock:
            await self.hass.async_add_job(self._update, force_update)

    def _update(self, force_update):
        """Update the device state."""
        try:
            self._state = self.wemo.get_state(force_update)

            if self._model_name == 'Insight':
                self.insight_params = self.wemo.insight_params
                self.insight_params['standby_state'] = (
                    self.wemo.get_standby_state)
            elif self._model_name == 'Maker':
                self.maker_params = self.wemo.maker_params
            elif self._model_name == 'CoffeeMaker':
                self.coffeemaker_mode = self.wemo.mode
                self._mode_string = self.wemo.mode_string

            if not self._available:
                _LOGGER.info('Reconnected to %s', self.name)
                self._available = True
        except AttributeError as err:
            _LOGGER.warning("Could not update status for %s (%s)",
                            self.name, err)
            self._available = False
