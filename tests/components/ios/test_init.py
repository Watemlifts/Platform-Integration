"""Tests for the iOS init file."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.setup import async_setup_component
from homeassistant.components import ios

from tests.common import mock_component, mock_coro


@pytest.fixture(autouse=True)
def mock_load_json():
    """Mock load_json."""
    with patch('homeassistant.components.ios.load_json', return_value={}):
        yield


@pytest.fixture(autouse=True)
def mock_dependencies(hass):
    """Mock dependencies loaded."""
    mock_component(hass, 'zeroconf')
    mock_component(hass, 'device_tracker')


async def test_creating_entry_sets_up_sensor(hass):
    """Test setting up iOS loads the sensor component."""
    with patch('homeassistant.components.ios.sensor.async_setup_entry',
               return_value=mock_coro(True)) as mock_setup:
        result = await hass.config_entries.flow.async_init(
            ios.DOMAIN, context={'source': config_entries.SOURCE_USER})

        # Confirmation form
        assert result['type'] == data_entry_flow.RESULT_TYPE_FORM

        result = await hass.config_entries.flow.async_configure(
            result['flow_id'], {})
        assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 1


async def test_configuring_ios_creates_entry(hass):
    """Test that specifying config will create an entry."""
    with patch('homeassistant.components.ios.async_setup_entry',
               return_value=mock_coro(True)) as mock_setup:
        await async_setup_component(hass, ios.DOMAIN, {
            'ios': {
                'push': {}
            }
        })
        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 1


async def test_not_configuring_ios_not_creates_entry(hass):
    """Test that no config will not create an entry."""
    with patch('homeassistant.components.ios.async_setup_entry',
               return_value=mock_coro(True)) as mock_setup:
        await async_setup_component(hass, ios.DOMAIN, {})
        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 0
