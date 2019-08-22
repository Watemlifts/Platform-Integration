"""Support for Blink Alarm Control Panel."""
import logging

from homeassistant.components.alarm_control_panel import AlarmControlPanel
from homeassistant.const import (
    ATTR_ATTRIBUTION, STATE_ALARM_ARMED_AWAY, STATE_ALARM_DISARMED)

from . import BLINK_DATA, DEFAULT_ATTRIBUTION

_LOGGER = logging.getLogger(__name__)

ICON = 'mdi:security'


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Arlo Alarm Control Panels."""
    if discovery_info is None:
        return
    data = hass.data[BLINK_DATA]

    sync_modules = []
    for sync_name, sync_module in data.sync.items():
        sync_modules.append(BlinkSyncModule(data, sync_name, sync_module))
    add_entities(sync_modules, True)


class BlinkSyncModule(AlarmControlPanel):
    """Representation of a Blink Alarm Control Panel."""

    def __init__(self, data, name, sync):
        """Initialize the alarm control panel."""
        self.data = data
        self.sync = sync
        self._name = name
        self._state = None

    @property
    def unique_id(self):
        """Return the unique id for the sync module."""
        return self.sync.serial

    @property
    def icon(self):
        """Return icon."""
        return ICON

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def name(self):
        """Return the name of the panel."""
        return "{} {}".format(BLINK_DATA, self._name)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attr = self.sync.attributes
        attr['network_info'] = self.data.networks
        attr['associated_cameras'] = list(self.sync.cameras.keys())
        attr[ATTR_ATTRIBUTION] = DEFAULT_ATTRIBUTION
        return attr

    def update(self):
        """Update the state of the device."""
        _LOGGER.debug("Updating Blink Alarm Control Panel %s", self._name)
        self.data.refresh()
        mode = self.sync.arm
        if mode:
            self._state = STATE_ALARM_ARMED_AWAY
        else:
            self._state = STATE_ALARM_DISARMED

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        self.sync.arm = False
        self.sync.refresh()

    def alarm_arm_away(self, code=None):
        """Send arm command."""
        self.sync.arm = True
        self.sync.refresh()
