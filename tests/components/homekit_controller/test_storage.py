"""Basic checks for entity map storage."""
from tests.common import flush_store
from tests.components.homekit_controller.common import (
    FakeService, setup_test_component, setup_platform)

from homeassistant import config_entries
from homeassistant.components.homekit_controller import async_remove_entry
from homeassistant.components.homekit_controller.const import ENTITY_MAP


async def test_load_from_storage(hass, hass_storage):
    """Test that entity map can be correctly loaded from cache."""
    hkid = '00:00:00:00:00:00'

    hass_storage['homekit_controller-entity-map'] = {
        'version': 1,
        'data': {
            'pairings': {
                hkid: {
                    'c#': 1,
                    'accessories': [],
                }
            }
        }
    }

    await setup_platform(hass)
    assert hkid in hass.data[ENTITY_MAP].storage_data


async def test_storage_is_removed(hass, hass_storage):
    """Test entity map storage removal is idempotent."""
    await setup_platform(hass)

    entity_map = hass.data[ENTITY_MAP]
    hkid = '00:00:00:00:00:01'

    entity_map.async_create_or_update_map(
        hkid,
        1,
        [],
    )
    assert hkid in entity_map.storage_data
    await flush_store(entity_map.store)
    assert hkid in hass_storage[ENTITY_MAP]['data']['pairings']

    entity_map.async_delete_map(hkid)
    assert hkid not in hass.data[ENTITY_MAP].storage_data
    await flush_store(entity_map.store)

    assert hass_storage[ENTITY_MAP]['data']['pairings'] == {}


async def test_storage_is_removed_idempotent(hass):
    """Test entity map storage removal is idempotent."""
    await setup_platform(hass)

    entity_map = hass.data[ENTITY_MAP]
    hkid = '00:00:00:00:00:01'

    assert hkid not in entity_map.storage_data

    entity_map.async_delete_map(hkid)

    assert hkid not in entity_map.storage_data


def create_lightbulb_service():
    """Define lightbulb characteristics."""
    service = FakeService('public.hap.service.lightbulb')
    on_char = service.add_characteristic('on')
    on_char.value = 0
    return service


async def test_storage_is_updated_on_add(hass, hass_storage, utcnow):
    """Test entity map storage is cleaned up on adding an accessory."""
    bulb = create_lightbulb_service()
    await setup_test_component(hass, [bulb])

    entity_map = hass.data[ENTITY_MAP]
    hkid = '00:00:00:00:00:00'

    # Is in memory store updated?
    assert hkid in entity_map.storage_data

    # Is saved out to store?
    await flush_store(entity_map.store)
    assert hkid in hass_storage[ENTITY_MAP]['data']['pairings']


async def test_storage_is_removed_on_config_entry_removal(hass, utcnow):
    """Test entity map storage is cleaned up on config entry removal."""
    bulb = create_lightbulb_service()
    await setup_test_component(hass, [bulb])

    hkid = '00:00:00:00:00:00'

    pairing_data = {
        'AccessoryPairingID': hkid,
    }

    entry = config_entries.ConfigEntry(
        1, 'homekit_controller', 'TestData', pairing_data,
        'test', config_entries.CONN_CLASS_LOCAL_PUSH
    )

    assert hkid in hass.data[ENTITY_MAP].storage_data

    await async_remove_entry(hass, entry)

    assert hkid not in hass.data[ENTITY_MAP].storage_data
