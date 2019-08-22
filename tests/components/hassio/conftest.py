"""Fixtures for Hass.io."""
import os
from unittest.mock import patch, Mock

import pytest

from homeassistant.core import CoreState
from homeassistant.setup import async_setup_component
from homeassistant.components.hassio.handler import HassIO, HassioAPIError

from tests.common import mock_coro
from . import API_PASSWORD, HASSIO_TOKEN


@pytest.fixture
def hassio_env():
    """Fixture to inject hassio env."""
    with patch.dict(os.environ, {'HASSIO': "127.0.0.1"}), \
            patch('homeassistant.components.hassio.HassIO.is_connected',
                  Mock(return_value=mock_coro(
                    {"result": "ok", "data": {}}))), \
            patch.dict(os.environ, {'HASSIO_TOKEN': "123456"}), \
            patch('homeassistant.components.hassio.HassIO.'
                  'get_homeassistant_info',
                  Mock(side_effect=HassioAPIError())):
        yield


@pytest.fixture
def hassio_stubs(hassio_env, hass, hass_client, aioclient_mock):
    """Create mock hassio http client."""
    with patch(
            'homeassistant.components.hassio.HassIO.update_hass_api',
            return_value=mock_coro({"result": "ok"})
    ), patch(
        'homeassistant.components.hassio.HassIO.update_hass_timezone',
        return_value=mock_coro({"result": "ok"})
    ), patch(
        'homeassistant.components.hassio.HassIO.get_homeassistant_info',
        side_effect=HassioAPIError()
    ):
        hass.state = CoreState.starting
        hass.loop.run_until_complete(async_setup_component(hass, 'hassio', {
            'http': {
                'api_password': API_PASSWORD
            }
        }))


@pytest.fixture
def hassio_client(hassio_stubs, hass, hass_client):
    """Return a Hass.io HTTP client."""
    yield hass.loop.run_until_complete(hass_client())


@pytest.fixture
def hassio_noauth_client(hassio_stubs, hass, aiohttp_client):
    """Return a Hass.io HTTP client without auth."""
    yield hass.loop.run_until_complete(aiohttp_client(hass.http.app))


@pytest.fixture
def hassio_handler(hass, aioclient_mock):
    """Create mock hassio handler."""
    async def get_client_session():
        return hass.helpers.aiohttp_client.async_get_clientsession()

    websession = hass.loop.run_until_complete(get_client_session())

    with patch.dict(os.environ, {'HASSIO_TOKEN': HASSIO_TOKEN}):
        yield HassIO(hass.loop, websession, "127.0.0.1")
