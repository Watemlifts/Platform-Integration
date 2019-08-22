"""Device tracker platform that adds support for OwnTracks over MQTT."""
import logging

from homeassistant.core import callback
from homeassistant.const import (
    ATTR_GPS_ACCURACY,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_BATTERY_LEVEL,
)
from homeassistant.components.device_tracker.const import (
    ENTITY_ID_FORMAT, ATTR_SOURCE_TYPE, SOURCE_TYPE_GPS)
from homeassistant.components.device_tracker.config_entry import (
    DeviceTrackerEntity
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers import device_registry
from . import DOMAIN as OT_DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up OwnTracks based off an entry."""
    @callback
    def _receive_data(dev_id, **data):
        """Receive set location."""
        entity = hass.data[OT_DOMAIN]['devices'].get(dev_id)

        if entity is not None:
            entity.update_data(data)
            return

        entity = hass.data[OT_DOMAIN]['devices'][dev_id] = OwnTracksEntity(
            dev_id, data
        )
        async_add_entities([entity])

    hass.data[OT_DOMAIN]['context'].set_async_see(_receive_data)

    # Restore previously loaded devices
    dev_reg = await device_registry.async_get_registry(hass)
    dev_ids = {
        identifier[1]
        for device in dev_reg.devices.values()
        for identifier in device.identifiers
        if identifier[0] == OT_DOMAIN
    }

    if not dev_ids:
        return True

    entities = []
    for dev_id in dev_ids:
        entity = hass.data[OT_DOMAIN]['devices'][dev_id] = OwnTracksEntity(
            dev_id
        )
        entities.append(entity)

    async_add_entities(entities)

    return True


class OwnTracksEntity(DeviceTrackerEntity, RestoreEntity):
    """Represent a tracked device."""

    def __init__(self, dev_id, data=None):
        """Set up OwnTracks entity."""
        self._dev_id = dev_id
        self._data = data or {}
        self.entity_id = ENTITY_ID_FORMAT.format(dev_id)

    @property
    def unique_id(self):
        """Return the unique ID."""
        return self._dev_id

    @property
    def battery_level(self):
        """Return the battery level of the device."""
        return self._data.get('battery')

    @property
    def device_state_attributes(self):
        """Return device specific attributes."""
        return self._data.get('attributes')

    @property
    def location_accuracy(self):
        """Return the gps accuracy of the device."""
        return self._data.get('gps_accuracy')

    @property
    def latitude(self):
        """Return latitude value of the device."""
        # Check with "get" instead of "in" because value can be None
        if self._data.get('gps'):
            return self._data['gps'][0]

        return None

    @property
    def longitude(self):
        """Return longitude value of the device."""
        # Check with "get" instead of "in" because value can be None
        if self._data.get('gps'):
            return self._data['gps'][1]

        return None

    @property
    def location_name(self):
        """Return a location name for the current location of the device."""
        return self._data.get('location_name')

    @property
    def name(self):
        """Return the name of the device."""
        return self._data.get('host_name')

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def source_type(self):
        """Return the source type, eg gps or router, of the device."""
        return self._data.get('source_type', SOURCE_TYPE_GPS)

    @property
    def device_info(self):
        """Return the device info."""
        return {
            'name': self.name,
            'identifiers': {(OT_DOMAIN, self._dev_id)},
        }

    async def async_added_to_hass(self):
        """Call when entity about to be added to Home Assistant."""
        await super().async_added_to_hass()

        # Don't restore if we got set up with data.
        if self._data:
            return

        state = await self.async_get_last_state()

        if state is None:
            return

        attr = state.attributes
        self._data = {
            'host_name': state.name,
            'gps': (attr.get(ATTR_LATITUDE), attr.get(ATTR_LONGITUDE)),
            'gps_accuracy': attr.get(ATTR_GPS_ACCURACY),
            'battery': attr.get(ATTR_BATTERY_LEVEL),
            'source_type': attr.get(ATTR_SOURCE_TYPE),
        }

    @callback
    def update_data(self, data):
        """Mark the device as seen."""
        self._data = data
        self.async_write_ha_state()
