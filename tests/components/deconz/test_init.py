"""Test deCONZ component setup process."""
from unittest.mock import Mock, patch

import asyncio
import pytest
import voluptuous as vol

from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.setup import async_setup_component
from homeassistant.components import deconz

from tests.common import mock_coro, MockConfigEntry

ENTRY1_HOST = '1.2.3.4'
ENTRY1_PORT = 80
ENTRY1_API_KEY = '1234567890ABCDEF'
ENTRY1_BRIDGEID = '12345ABC'

ENTRY2_HOST = '2.3.4.5'
ENTRY2_PORT = 80
ENTRY2_API_KEY = '1234567890ABCDEF'
ENTRY2_BRIDGEID = '23456DEF'


async def setup_entry(hass, entry):
    """Test that setup entry works."""
    with patch.object(deconz.DeconzGateway, 'async_setup',
                      return_value=mock_coro(True)), \
            patch.object(deconz.DeconzGateway, 'async_update_device_registry',
                         return_value=mock_coro(True)):
        assert await deconz.async_setup_entry(hass, entry) is True


async def test_config_with_host_passed_to_config_entry(hass):
    """Test that configured options for a host are loaded via config entry."""
    with patch.object(hass.config_entries, 'flow') as mock_config_flow:
        assert await async_setup_component(hass, deconz.DOMAIN, {
            deconz.DOMAIN: {
                deconz.CONF_HOST: ENTRY1_HOST,
                deconz.CONF_PORT: ENTRY1_PORT
            }
        }) is True
    # Import flow started
    assert len(mock_config_flow.mock_calls) == 1


async def test_config_without_host_not_passed_to_config_entry(hass):
    """Test that a configuration without a host does not initiate an import."""
    MockConfigEntry(domain=deconz.DOMAIN, data={}).add_to_hass(hass)
    with patch.object(hass.config_entries, 'flow') as mock_config_flow:
        assert await async_setup_component(hass, deconz.DOMAIN, {
            deconz.DOMAIN: {}
        }) is True
    # No flow started
    assert len(mock_config_flow.mock_calls) == 0


async def test_config_import_entry_fails_when_entries_exist(hass):
    """Test that an already registered host does not initiate an import."""
    MockConfigEntry(domain=deconz.DOMAIN, data={}).add_to_hass(hass)
    with patch.object(hass.config_entries, 'flow') as mock_config_flow:
        assert await async_setup_component(hass, deconz.DOMAIN, {
            deconz.DOMAIN: {
                deconz.CONF_HOST: ENTRY1_HOST,
                deconz.CONF_PORT: ENTRY1_PORT
            }
        }) is True
    # No flow started
    assert len(mock_config_flow.mock_calls) == 0


async def test_config_discovery(hass):
    """Test that a discovered bridge does not initiate an import."""
    with patch.object(hass, 'config_entries') as mock_config_entries:
        assert await async_setup_component(hass, deconz.DOMAIN, {}) is True
    # No flow started
    assert len(mock_config_entries.flow.mock_calls) == 0


async def test_setup_entry_fails(hass):
    """Test setup entry fails if deCONZ is not available."""
    entry = Mock()
    entry.data = {
        deconz.CONF_HOST: ENTRY1_HOST,
        deconz.CONF_PORT: ENTRY1_PORT,
        deconz.CONF_API_KEY: ENTRY1_API_KEY
    }
    with patch('pydeconz.DeconzSession.async_load_parameters',
               side_effect=Exception):
        await deconz.async_setup_entry(hass, entry)


async def test_setup_entry_no_available_bridge(hass):
    """Test setup entry fails if deCONZ is not available."""
    entry = Mock()
    entry.data = {
        deconz.CONF_HOST: ENTRY1_HOST,
        deconz.CONF_PORT: ENTRY1_PORT,
        deconz.CONF_API_KEY: ENTRY1_API_KEY
    }
    with patch('pydeconz.DeconzSession.async_load_parameters',
               side_effect=asyncio.TimeoutError),\
            pytest.raises(ConfigEntryNotReady):
        await deconz.async_setup_entry(hass, entry)


async def test_setup_entry_successful(hass):
    """Test setup entry is successful."""
    entry = MockConfigEntry(domain=deconz.DOMAIN, data={
        deconz.CONF_HOST: ENTRY1_HOST,
        deconz.CONF_PORT: ENTRY1_PORT,
        deconz.CONF_API_KEY: ENTRY1_API_KEY,
        deconz.CONF_BRIDGEID: ENTRY1_BRIDGEID
    })
    entry.add_to_hass(hass)

    await setup_entry(hass, entry)

    assert ENTRY1_BRIDGEID in hass.data[deconz.DOMAIN]
    assert hass.data[deconz.DOMAIN][ENTRY1_BRIDGEID].master


async def test_setup_entry_multiple_gateways(hass):
    """Test setup entry is successful with multiple gateways."""
    entry = MockConfigEntry(domain=deconz.DOMAIN, data={
        deconz.CONF_HOST: ENTRY1_HOST,
        deconz.CONF_PORT: ENTRY1_PORT,
        deconz.CONF_API_KEY: ENTRY1_API_KEY,
        deconz.CONF_BRIDGEID: ENTRY1_BRIDGEID
    })
    entry.add_to_hass(hass)

    entry2 = MockConfigEntry(domain=deconz.DOMAIN, data={
        deconz.CONF_HOST: ENTRY2_HOST,
        deconz.CONF_PORT: ENTRY2_PORT,
        deconz.CONF_API_KEY: ENTRY2_API_KEY,
        deconz.CONF_BRIDGEID: ENTRY2_BRIDGEID
    })
    entry2.add_to_hass(hass)

    await setup_entry(hass, entry)
    await setup_entry(hass, entry2)

    assert ENTRY1_BRIDGEID in hass.data[deconz.DOMAIN]
    assert hass.data[deconz.DOMAIN][ENTRY1_BRIDGEID].master
    assert ENTRY2_BRIDGEID in hass.data[deconz.DOMAIN]
    assert not hass.data[deconz.DOMAIN][ENTRY2_BRIDGEID].master


async def test_unload_entry(hass):
    """Test being able to unload an entry."""
    entry = MockConfigEntry(domain=deconz.DOMAIN, data={
        deconz.CONF_HOST: ENTRY1_HOST,
        deconz.CONF_PORT: ENTRY1_PORT,
        deconz.CONF_API_KEY: ENTRY1_API_KEY,
        deconz.CONF_BRIDGEID: ENTRY1_BRIDGEID
    })
    entry.add_to_hass(hass)

    await setup_entry(hass, entry)

    with patch.object(deconz.DeconzGateway, 'async_reset',
                      return_value=mock_coro(True)):
        assert await deconz.async_unload_entry(hass, entry)

    assert not hass.data[deconz.DOMAIN]


async def test_unload_entry_multiple_gateways(hass):
    """Test being able to unload an entry and master gateway gets moved."""
    entry = MockConfigEntry(domain=deconz.DOMAIN, data={
        deconz.CONF_HOST: ENTRY1_HOST,
        deconz.CONF_PORT: ENTRY1_PORT,
        deconz.CONF_API_KEY: ENTRY1_API_KEY,
        deconz.CONF_BRIDGEID: ENTRY1_BRIDGEID
    })
    entry.add_to_hass(hass)

    entry2 = MockConfigEntry(domain=deconz.DOMAIN, data={
        deconz.CONF_HOST: ENTRY2_HOST,
        deconz.CONF_PORT: ENTRY2_PORT,
        deconz.CONF_API_KEY: ENTRY2_API_KEY,
        deconz.CONF_BRIDGEID: ENTRY2_BRIDGEID
    })
    entry2.add_to_hass(hass)

    await setup_entry(hass, entry)
    await setup_entry(hass, entry2)

    with patch.object(deconz.DeconzGateway, 'async_reset',
                      return_value=mock_coro(True)):
        assert await deconz.async_unload_entry(hass, entry)

    assert ENTRY2_BRIDGEID in hass.data[deconz.DOMAIN]
    assert hass.data[deconz.DOMAIN][ENTRY2_BRIDGEID].master


async def test_service_configure(hass):
    """Test that service invokes pydeconz with the correct path and data."""
    entry = MockConfigEntry(domain=deconz.DOMAIN, data={
        deconz.CONF_HOST: ENTRY1_HOST,
        deconz.CONF_PORT: ENTRY1_PORT,
        deconz.CONF_API_KEY: ENTRY1_API_KEY,
        deconz.CONF_BRIDGEID: ENTRY1_BRIDGEID
    })
    entry.add_to_hass(hass)

    await setup_entry(hass, entry)

    hass.data[deconz.DOMAIN][ENTRY1_BRIDGEID].deconz_ids = {
        'light.test': '/light/1'
    }
    data = {'on': True, 'attr1': 10, 'attr2': 20}

    # only field
    with patch('pydeconz.DeconzSession.async_put_state',
               return_value=mock_coro(True)):
        await hass.services.async_call('deconz', 'configure', service_data={
            'field': '/light/42', 'data': data
        })
        await hass.async_block_till_done()

    # only entity
    with patch('pydeconz.DeconzSession.async_put_state',
               return_value=mock_coro(True)):
        await hass.services.async_call('deconz', 'configure', service_data={
            'entity': 'light.test', 'data': data
        })
        await hass.async_block_till_done()

    # entity + field
    with patch('pydeconz.DeconzSession.async_put_state',
               return_value=mock_coro(True)):
        await hass.services.async_call('deconz', 'configure', service_data={
            'entity': 'light.test', 'field': '/state', 'data': data})
        await hass.async_block_till_done()

    # non-existing entity (or not from deCONZ)
    with patch('pydeconz.DeconzSession.async_put_state',
               return_value=mock_coro(True)):
        await hass.services.async_call('deconz', 'configure', service_data={
            'entity': 'light.nonexisting', 'field': '/state', 'data': data})
        await hass.async_block_till_done()

    # field does not start with /
    with pytest.raises(vol.Invalid):
        with patch('pydeconz.DeconzSession.async_put_state',
                   return_value=mock_coro(True)):
            await hass.services.async_call(
                'deconz', 'configure', service_data={
                    'entity': 'light.test', 'field': 'state', 'data': data})
            await hass.async_block_till_done()


async def test_service_refresh_devices(hass):
    """Test that service can refresh devices."""
    entry = MockConfigEntry(domain=deconz.DOMAIN, data={
        deconz.CONF_HOST: ENTRY1_HOST,
        deconz.CONF_PORT: ENTRY1_PORT,
        deconz.CONF_API_KEY: ENTRY1_API_KEY,
        deconz.CONF_BRIDGEID: ENTRY1_BRIDGEID
    })
    entry.add_to_hass(hass)

    await setup_entry(hass, entry)

    with patch('pydeconz.DeconzSession.async_load_parameters',
               return_value=mock_coro(True)):
        await hass.services.async_call(
            'deconz', 'device_refresh', service_data={})
        await hass.async_block_till_done()

    with patch('pydeconz.DeconzSession.async_load_parameters',
               return_value=mock_coro(False)):
        await hass.services.async_call(
            'deconz', 'device_refresh', service_data={})
        await hass.async_block_till_done()
