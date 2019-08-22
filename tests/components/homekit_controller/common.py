"""Code to support homekit_controller tests."""
import json
import os
from datetime import timedelta
from unittest import mock

from homekit.model.services import AbstractService, ServicesTypes
from homekit.model.characteristics import (
    AbstractCharacteristic, CharacteristicPermissions, CharacteristicsTypes)
from homekit.model import Accessory, get_id
from homekit.exceptions import AccessoryNotFoundError

from homeassistant import config_entries
from homeassistant.components.homekit_controller.const import (
    CONTROLLER, DOMAIN, HOMEKIT_ACCESSORY_DISPATCH)
from homeassistant.components.homekit_controller import (
    async_setup_entry, config_flow)
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util
from tests.common import async_fire_time_changed, load_fixture


class FakePairing:
    """
    A test fake that pretends to be a paired HomeKit accessory.

    This only contains methods and values that exist on the upstream Pairing
    class.
    """

    def __init__(self, accessories):
        """Create a fake pairing from an accessory model."""
        self.accessories = accessories
        self.pairing_data = {}
        self.available = True

    def list_accessories_and_characteristics(self):
        """Fake implementation of list_accessories_and_characteristics."""
        accessories = [
            a.to_accessory_and_service_list() for a in self.accessories
        ]
        # replicate what happens upstream right now
        self.pairing_data['accessories'] = accessories
        return accessories

    def get_characteristics(self, characteristics):
        """Fake implementation of get_characteristics."""
        if not self.available:
            raise AccessoryNotFoundError('Accessory not found')

        results = {}
        for aid, cid in characteristics:
            for accessory in self.accessories:
                if aid != accessory.aid:
                    continue
                for service in accessory.services:
                    for char in service.characteristics:
                        if char.iid != cid:
                            continue
                        results[(aid, cid)] = {
                            'value': char.get_value()
                        }
        return results

    def put_characteristics(self, characteristics):
        """Fake implementation of put_characteristics."""
        for aid, cid, new_val in characteristics:
            for accessory in self.accessories:
                if aid != accessory.aid:
                    continue
                for service in accessory.services:
                    for char in service.characteristics:
                        if char.iid != cid:
                            continue
                        char.set_value(new_val)


class FakeController:
    """
    A test fake that pretends to be a paired HomeKit accessory.

    This only contains methods and values that exist on the upstream Controller
    class.
    """

    def __init__(self):
        """Create a Fake controller with no pairings."""
        self.pairings = {}

    def add(self, accessories):
        """Create and register a fake pairing for a simulated accessory."""
        pairing = FakePairing(accessories)
        self.pairings['00:00:00:00:00:00'] = pairing
        return pairing


class Helper:
    """Helper methods for interacting with HomeKit fakes."""

    def __init__(self, hass, entity_id, pairing, accessory):
        """Create a helper for a given accessory/entity."""
        self.hass = hass
        self.entity_id = entity_id
        self.pairing = pairing
        self.accessory = accessory

        self.characteristics = {}
        for service in self.accessory.services:
            service_name = ServicesTypes.get_short(service.type)
            for char in service.characteristics:
                char_name = CharacteristicsTypes.get_short(char.type)
                self.characteristics[(service_name, char_name)] = char

    async def poll_and_get_state(self):
        """Trigger a time based poll and return the current entity state."""
        next_update = dt_util.utcnow() + timedelta(seconds=60)
        async_fire_time_changed(self.hass, next_update)
        await self.hass.async_block_till_done()

        state = self.hass.states.get(self.entity_id)
        assert state is not None
        return state


class FakeCharacteristic(AbstractCharacteristic):
    """
    A model of a generic HomeKit characteristic.

    Base is abstract and can't be instanced directly so this subclass is
    needed even though it doesn't add any methods.
    """

    def to_accessory_and_service_list(self):
        """Serialize the characteristic."""
        # Upstream doesn't correctly serialize valid_values
        # This fix will be upstreamed and this function removed when it
        # is fixed.
        record = super().to_accessory_and_service_list()
        if self.valid_values:
            record['valid-values'] = self.valid_values
        return record


class FakeService(AbstractService):
    """A model of a generic HomeKit service."""

    def __init__(self, service_name):
        """Create a fake service by its short form HAP spec name."""
        char_type = ServicesTypes.get_uuid(service_name)
        super().__init__(char_type, get_id())

    def add_characteristic(self, name):
        """Add a characteristic to this service by name."""
        full_name = 'public.hap.characteristic.' + name
        char = FakeCharacteristic(get_id(), full_name, None)
        char.perms = [
            CharacteristicPermissions.paired_read,
            CharacteristicPermissions.paired_write
        ]
        self.characteristics.append(char)
        return char


async def setup_accessories_from_file(hass, path):
    """Load an collection of accessory defs from JSON data."""
    accessories_fixture = await hass.async_add_executor_job(
        load_fixture,
        os.path.join('homekit_controller', path),
    )
    accessories_json = json.loads(accessories_fixture)

    accessories = []

    for accessory_data in accessories_json:
        accessory = Accessory('Name', 'Mfr', 'Model', '0001', '0.1')
        accessory.services = []
        accessory.aid = accessory_data['aid']
        for service_data in accessory_data['services']:
            service = FakeService('public.hap.service.accessory-information')
            service.type = service_data['type']
            service.iid = service_data['iid']

            for char_data in service_data['characteristics']:
                char = FakeCharacteristic(1, '23', None)
                char.type = char_data['type']
                char.iid = char_data['iid']
                char.perms = char_data['perms']
                char.format = char_data['format']
                if 'description' in char_data:
                    char.description = char_data['description']
                if 'value' in char_data:
                    char.value = char_data['value']
                if 'minValue' in char_data:
                    char.minValue = char_data['minValue']
                if 'maxValue' in char_data:
                    char.maxValue = char_data['maxValue']
                if 'valid-values' in char_data:
                    char.valid_values = char_data['valid-values']
                service.characteristics.append(char)

            accessory.services.append(service)

        accessories.append(accessory)

    return accessories


async def setup_platform(hass):
    """Load the platform but with a fake Controller API."""
    config = {
        'discovery': {
        }
    }

    with mock.patch('homekit.Controller') as controller:
        fake_controller = controller.return_value = FakeController()
        await async_setup_component(hass, DOMAIN, config)

    return fake_controller


async def setup_test_accessories(hass, accessories):
    """Load a fake homekit device based on captured JSON profile."""
    fake_controller = await setup_platform(hass)
    pairing = fake_controller.add(accessories)

    discovery_info = {
        'name': 'TestDevice',
        'host': '127.0.0.1',
        'port': 8080,
        'properties': {
            'md': 'TestDevice',
            'id': '00:00:00:00:00:00',
            'c#': 1,
        }
    }

    pairing.pairing_data.update({
        'AccessoryPairingID': discovery_info['properties']['id'],
    })

    config_entry = config_entries.ConfigEntry(
        1, 'homekit_controller', 'TestData', pairing.pairing_data,
        'test', config_entries.CONN_CLASS_LOCAL_PUSH
    )

    pairing_cls_loc = 'homekit.controller.ip_implementation.IpPairing'
    with mock.patch(pairing_cls_loc) as pairing_cls:
        pairing_cls.return_value = pairing
        await async_setup_entry(hass, config_entry)
        await hass.async_block_till_done()

    return pairing


async def device_config_changed(hass, accessories):
    """Discover new devices added to HomeAssistant at runtime."""
    # Update the accessories our FakePairing knows about
    controller = hass.data[CONTROLLER]
    pairing = controller.pairings['00:00:00:00:00:00']
    pairing.accessories = accessories

    discovery_info = {
        'name': 'TestDevice',
        'host': '127.0.0.1',
        'port': 8080,
        'properties': {
            'md': 'TestDevice',
            'id': '00:00:00:00:00:00',
            'c#': '2',
            'sf': '0',
        }
    }

    # Config Flow will abort and notify us if the discovery event is of
    # interest - in this case c# has incremented
    flow = config_flow.HomekitControllerFlowHandler()
    flow.hass = hass
    flow.context = {}
    result = await flow.async_step_zeroconf(discovery_info)
    assert result['type'] == 'abort'
    assert result['reason'] == 'already_configured'

    # Wait for services to reconfigure
    await hass.async_block_till_done()
    await hass.async_block_till_done()


async def setup_test_component(hass, services, capitalize=False, suffix=None):
    """Load a fake homekit accessory based on a homekit accessory model.

    If capitalize is True, property names will be in upper case.

    If suffix is set, entityId will include the suffix
    """
    domain = None
    for service in services:
        service_name = ServicesTypes.get_short(service.type)
        if service_name in HOMEKIT_ACCESSORY_DISPATCH:
            domain = HOMEKIT_ACCESSORY_DISPATCH[service_name]
            break

    assert domain, 'Cannot map test homekit services to homeassistant domain'

    accessory = Accessory('TestDevice', 'example.com', 'Test', '0001', '0.1')
    accessory.services.extend(services)

    pairing = await setup_test_accessories(hass, [accessory])
    entity = 'testdevice' if suffix is None else 'testdevice_{}'.format(suffix)
    return Helper(hass, '.'.join((domain, entity)), pairing, accessory)
