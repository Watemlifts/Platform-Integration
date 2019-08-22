"""Test Group config panel."""
import asyncio
import json
from unittest.mock import patch, MagicMock

from homeassistant.bootstrap import async_setup_component
from homeassistant.components import config


VIEW_NAME = 'api:config:group:config'


@asyncio.coroutine
def test_get_device_config(hass, hass_client):
    """Test getting device config."""
    with patch.object(config, 'SECTIONS', ['group']):
        yield from async_setup_component(hass, 'config', {})

    client = yield from hass_client()

    def mock_read(path):
        """Mock reading data."""
        return {
            'hello.beer': {
                'free': 'beer',
            },
            'other.entity': {
                'do': 'something',
            },
        }

    with patch('homeassistant.components.config._read', mock_read):
        resp = yield from client.get(
            '/api/config/group/config/hello.beer')

    assert resp.status == 200
    result = yield from resp.json()

    assert result == {'free': 'beer'}


@asyncio.coroutine
def test_update_device_config(hass, hass_client):
    """Test updating device config."""
    with patch.object(config, 'SECTIONS', ['group']):
        yield from async_setup_component(hass, 'config', {})

    client = yield from hass_client()

    orig_data = {
        'hello.beer': {
            'ignored': True,
        },
        'other.entity': {
            'polling_intensity': 2,
        },
    }

    def mock_read(path):
        """Mock reading data."""
        return orig_data

    written = []

    def mock_write(path, data):
        """Mock writing data."""
        written.append(data)

    mock_call = MagicMock()

    with patch('homeassistant.components.config._read', mock_read), \
            patch('homeassistant.components.config._write', mock_write), \
            patch.object(hass.services, 'async_call', mock_call):
        resp = yield from client.post(
            '/api/config/group/config/hello_beer', data=json.dumps({
                'name': 'Beer',
                'entities': ['light.top', 'light.bottom'],
            }))

    assert resp.status == 200
    result = yield from resp.json()
    assert result == {'result': 'ok'}

    orig_data['hello_beer']['name'] = 'Beer'
    orig_data['hello_beer']['entities'] = ['light.top', 'light.bottom']

    assert written[0] == orig_data
    mock_call.assert_called_once_with('group', 'reload')


@asyncio.coroutine
def test_update_device_config_invalid_key(hass, hass_client):
    """Test updating device config."""
    with patch.object(config, 'SECTIONS', ['group']):
        yield from async_setup_component(hass, 'config', {})

    client = yield from hass_client()

    resp = yield from client.post(
        '/api/config/group/config/not a slug', data=json.dumps({
            'name': 'YO',
        }))

    assert resp.status == 400


@asyncio.coroutine
def test_update_device_config_invalid_data(hass, hass_client):
    """Test updating device config."""
    with patch.object(config, 'SECTIONS', ['group']):
        yield from async_setup_component(hass, 'config', {})

    client = yield from hass_client()

    resp = yield from client.post(
        '/api/config/group/config/hello_beer', data=json.dumps({
            'invalid_option': 2
        }))

    assert resp.status == 400


@asyncio.coroutine
def test_update_device_config_invalid_json(hass, hass_client):
    """Test updating device config."""
    with patch.object(config, 'SECTIONS', ['group']):
        yield from async_setup_component(hass, 'config', {})

    client = yield from hass_client()

    resp = yield from client.post(
        '/api/config/group/config/hello_beer', data='not json')

    assert resp.status == 400
