"""Test Automation config panel."""
import json
from unittest.mock import patch

from homeassistant.bootstrap import async_setup_component
from homeassistant.components import config


async def test_get_device_config(hass, hass_client):
    """Test getting device config."""
    with patch.object(config, 'SECTIONS', ['automation']):
        await async_setup_component(hass, 'config', {})

    client = await hass_client()

    def mock_read(path):
        """Mock reading data."""
        return [
            {
                'id': 'sun',
            },
            {
                'id': 'moon',
            }
        ]

    with patch('homeassistant.components.config._read', mock_read):
        resp = await client.get(
            '/api/config/automation/config/moon')

    assert resp.status == 200
    result = await resp.json()

    assert result == {'id': 'moon'}


async def test_update_device_config(hass, hass_client):
    """Test updating device config."""
    with patch.object(config, 'SECTIONS', ['automation']):
        await async_setup_component(hass, 'config', {})

    client = await hass_client()

    orig_data = [
        {
            'id': 'sun',
        },
        {
            'id': 'moon',
        }
    ]

    def mock_read(path):
        """Mock reading data."""
        return orig_data

    written = []

    def mock_write(path, data):
        """Mock writing data."""
        written.append(data)

    with patch('homeassistant.components.config._read', mock_read), \
            patch('homeassistant.components.config._write', mock_write):
        resp = await client.post(
            '/api/config/automation/config/moon', data=json.dumps({
                'trigger': [],
                'action': [],
                'condition': [],
            }))

    assert resp.status == 200
    result = await resp.json()
    assert result == {'result': 'ok'}

    assert list(orig_data[1]) == ['id', 'trigger', 'condition', 'action']
    assert orig_data[1] == {
        'id': 'moon',
        'trigger': [],
        'condition': [],
        'action': [],
    }
    assert written[0] == orig_data


async def test_bad_formatted_automations(hass, hass_client):
    """Test that we handle automations without ID."""
    with patch.object(config, 'SECTIONS', ['automation']):
        await async_setup_component(hass, 'config', {})

    client = await hass_client()

    orig_data = [
        {
            # No ID
            'action': {
                'event': 'hello'
            }
        },
        {
            'id': 'moon',
        }
    ]

    def mock_read(path):
        """Mock reading data."""
        return orig_data

    written = []

    def mock_write(path, data):
        """Mock writing data."""
        written.append(data)

    with patch('homeassistant.components.config._read', mock_read), \
            patch('homeassistant.components.config._write', mock_write):
        resp = await client.post(
            '/api/config/automation/config/moon', data=json.dumps({
                'trigger': [],
                'action': [],
                'condition': [],
            }))

    assert resp.status == 200
    result = await resp.json()
    assert result == {'result': 'ok'}

    # Verify ID added to orig_data
    assert 'id' in orig_data[0]

    assert orig_data[1] == {
        'id': 'moon',
        'trigger': [],
        'condition': [],
        'action': [],
    }


async def test_delete_automation(hass, hass_client):
    """Test deleting an automation."""
    with patch.object(config, 'SECTIONS', ['automation']):
        await async_setup_component(hass, 'config', {})

    client = await hass_client()

    orig_data = [
        {
            'id': 'sun',
        },
        {
            'id': 'moon',
        }
    ]

    def mock_read(path):
        """Mock reading data."""
        return orig_data

    written = []

    def mock_write(path, data):
        """Mock writing data."""
        written.append(data)

    with patch('homeassistant.components.config._read', mock_read), \
            patch('homeassistant.components.config._write', mock_write):
        resp = await client.delete('/api/config/automation/config/sun')

    assert resp.status == 200
    result = await resp.json()
    assert result == {'result': 'ok'}

    assert len(written) == 1
    assert written[0][0]['id'] == 'moon'
