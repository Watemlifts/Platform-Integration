"""Support for monitoring a Sense energy sensor device."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.core import callback

from . import SENSE_DATA, SENSE_DEVICE_UPDATE

_LOGGER = logging.getLogger(__name__)

BIN_SENSOR_CLASS = 'power'
MDI_ICONS = {
    'ac': 'air-conditioner',
    'aquarium': 'fish',
    'car': 'car-electric',
    'computer': 'desktop-classic',
    'cup': 'coffee',
    'dehumidifier': 'water-off',
    'dishes': 'dishwasher',
    'drill': 'toolbox',
    'fan': 'fan',
    'freezer': 'fridge-top',
    'fridge': 'fridge-bottom',
    'game': 'gamepad-variant',
    'garage': 'garage',
    'grill': 'stove',
    'heat': 'fire',
    'heater': 'radiatior',
    'humidifier': 'water',
    'kettle': 'kettle',
    'leafblower': 'leaf',
    'lightbulb': 'lightbulb',
    'media_console': 'set-top-box',
    'modem': 'router-wireless',
    'outlet': 'power-socket-us',
    'papershredder': 'shredder',
    'printer': 'printer',
    'pump': 'water-pump',
    'settings': 'settings',
    'skillet': 'pot',
    'smartcamera': 'webcam',
    'socket': 'power-plug',
    'sound': 'speaker',
    'stove': 'stove',
    'trash': 'trash-can',
    'tv': 'television',
    'vacuum': 'robot-vacuum',
    'washer': 'washing-machine',
}


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Sense binary sensor."""
    if discovery_info is None:
        return
    data = hass.data[SENSE_DATA]

    sense_devices = await data.get_discovered_device_data()
    devices = [SenseDevice(data, device) for device in sense_devices
               if device['tags']['DeviceListAllowed'] == 'true']
    async_add_entities(devices)


def sense_to_mdi(sense_icon):
    """Convert sense icon to mdi icon."""
    return 'mdi:{}'.format(MDI_ICONS.get(sense_icon, 'power-plug'))


class SenseDevice(BinarySensorDevice):
    """Implementation of a Sense energy device binary sensor."""

    def __init__(self, data, device):
        """Initialize the Sense binary sensor."""
        self._name = device['name']
        self._id = device['id']
        self._icon = sense_to_mdi(device['icon'])
        self._data = data
        self._undo_dispatch_subscription = None

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._name in self._data.active_devices

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the id of the binary sensor."""
        return self._id

    @property
    def icon(self):
        """Return the icon of the binary sensor."""
        return self._icon

    @property
    def device_class(self):
        """Return the device class of the binary sensor."""
        return BIN_SENSOR_CLASS

    @property
    def should_poll(self):
        """Return the deviceshould not poll for updates."""
        return False

    async def async_added_to_hass(self):
        """Register callbacks."""
        @callback
        def update():
            """Update the state."""
            self.async_schedule_update_ha_state(True)

        self._undo_dispatch_subscription = async_dispatcher_connect(
            self.hass, SENSE_DEVICE_UPDATE, update)

    async def async_will_remove_from_hass(self):
        """Undo subscription."""
        if self._undo_dispatch_subscription:
            self._undo_dispatch_subscription()
