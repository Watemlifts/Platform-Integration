"""Support for Homekit device discovery."""
import logging

from homeassistant.helpers.entity import Entity
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

# We need an import from .config_flow, without it .config_flow is never loaded.
from .config_flow import HomekitControllerFlowHandler  # noqa: F401
from .connection import get_accessory_information, HKDevice
from .const import (
    CONTROLLER, ENTITY_MAP, KNOWN_DEVICES
)
from .const import DOMAIN   # noqa: pylint: disable=unused-import
from .storage import EntityMapStorage

_LOGGER = logging.getLogger(__name__)


def escape_characteristic_name(char_name):
    """Escape any dash or dots in a characteristics name."""
    return char_name.replace('-', '_').replace('.', '_')


class HomeKitEntity(Entity):
    """Representation of a Home Assistant HomeKit device."""

    def __init__(self, accessory, devinfo):
        """Initialise a generic HomeKit device."""
        self._available = True
        self._accessory = accessory
        self._aid = devinfo['aid']
        self._iid = devinfo['iid']
        self._features = 0
        self._chars = {}
        self.setup()

    def setup(self):
        """Configure an entity baed on its HomeKit characterstics metadata."""
        # pylint: disable=import-error
        from homekit.model.characteristics import CharacteristicsTypes

        accessories = self._accessory.accessories

        get_uuid = CharacteristicsTypes.get_uuid
        characteristic_types = [
            get_uuid(c) for c in self.get_characteristic_types()
        ]

        self._chars_to_poll = []
        self._chars = {}
        self._char_names = {}

        for accessory in accessories:
            if accessory['aid'] != self._aid:
                continue
            self._accessory_info = get_accessory_information(accessory)
            for service in accessory['services']:
                if service['iid'] != self._iid:
                    continue
                for char in service['characteristics']:
                    try:
                        uuid = CharacteristicsTypes.get_uuid(char['type'])
                    except KeyError:
                        # If a KeyError is raised its a non-standard
                        # characteristic. We must ignore it in this case.
                        continue
                    if uuid not in characteristic_types:
                        continue
                    self._setup_characteristic(char)

    def _setup_characteristic(self, char):
        """Configure an entity based on a HomeKit characteristics metadata."""
        # pylint: disable=import-error
        from homekit.model.characteristics import CharacteristicsTypes

        # Build up a list of (aid, iid) tuples to poll on update()
        self._chars_to_poll.append((self._aid, char['iid']))

        # Build a map of ctype -> iid
        short_name = CharacteristicsTypes.get_short(char['type'])
        self._chars[short_name] = char['iid']
        self._char_names[char['iid']] = short_name

        # Callback to allow entity to configure itself based on this
        # characteristics metadata (valid values, value ranges, features, etc)
        setup_fn_name = escape_characteristic_name(short_name)
        setup_fn = getattr(self, '_setup_{}'.format(setup_fn_name), None)
        if not setup_fn:
            return
        # pylint: disable=not-callable
        setup_fn(char)

    async def async_update(self):
        """Obtain a HomeKit device's state."""
        # pylint: disable=import-error
        from homekit.exceptions import (
            AccessoryDisconnectedError, AccessoryNotFoundError,
            EncryptionError)

        try:
            new_values_dict = await self._accessory.get_characteristics(
                self._chars_to_poll
            )
        except AccessoryNotFoundError:
            # Not only did the connection fail, but also the accessory is not
            # visible on the network.
            self._available = False
            return
        except (AccessoryDisconnectedError, EncryptionError):
            # Temporary connection failure. Device is still available but our
            # connection was dropped.
            return

        self._available = True

        for (_, iid), result in new_values_dict.items():
            if 'value' not in result:
                continue
            # Callback to update the entity with this characteristic value
            char_name = escape_characteristic_name(self._char_names[iid])
            update_fn = getattr(self, '_update_{}'.format(char_name), None)
            if not update_fn:
                continue
            # pylint: disable=not-callable
            update_fn(result['value'])

    @property
    def unique_id(self):
        """Return the ID of this device."""
        serial = self._accessory_info['serial-number']
        return "homekit-{}-{}".format(serial, self._iid)

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._accessory_info.get('name')

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def device_info(self):
        """Return the device info."""
        accessory_serial = self._accessory_info['serial-number']

        device_info = {
            'identifiers': {
                (DOMAIN, 'serial-number', accessory_serial),
            },
            'name': self._accessory_info['name'],
            'manufacturer': self._accessory_info.get('manufacturer', ''),
            'model': self._accessory_info.get('model', ''),
            'sw_version': self._accessory_info.get('firmware.revision', ''),
        }

        # Some devices only have a single accessory - we don't add a
        # via_device otherwise it would be self referential.
        bridge_serial = self._accessory.connection_info['serial-number']
        if accessory_serial != bridge_serial:
            device_info['via_device'] = (
                DOMAIN, 'serial-number', bridge_serial)

        return device_info

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity cares about."""
        raise NotImplementedError


async def async_setup_entry(hass, entry):
    """Set up a HomeKit connection on a config entry."""
    conn = HKDevice(hass, entry, entry.data)
    hass.data[KNOWN_DEVICES][conn.unique_id] = conn

    if not await conn.async_setup():
        del hass.data[KNOWN_DEVICES][conn.unique_id]
        raise ConfigEntryNotReady

    conn_info = conn.connection_info

    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={
            (DOMAIN, 'serial-number', conn_info['serial-number']),
            (DOMAIN, 'accessory-id', conn.unique_id),
        },
        name=conn.name,
        manufacturer=conn_info.get('manufacturer'),
        model=conn_info.get('model'),
        sw_version=conn_info.get('firmware.revision'),
    )

    return True


async def async_setup(hass, config):
    """Set up for Homekit devices."""
    # pylint: disable=import-error
    import homekit

    map_storage = hass.data[ENTITY_MAP] = EntityMapStorage(hass)
    await map_storage.async_initialize()

    hass.data[CONTROLLER] = homekit.Controller()
    hass.data[KNOWN_DEVICES] = {}

    return True


async def async_remove_entry(hass, entry):
    """Cleanup caches before removing config entry."""
    hkid = entry.data['AccessoryPairingID']
    hass.data[ENTITY_MAP].async_delete_map(hkid)
