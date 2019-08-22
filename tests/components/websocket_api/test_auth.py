"""Test auth of websocket API."""
from unittest.mock import patch

from homeassistant.components.websocket_api.const import (
    URL, SIGNAL_WEBSOCKET_CONNECTED, SIGNAL_WEBSOCKET_DISCONNECTED)
from homeassistant.components.websocket_api.auth import (
    TYPE_AUTH, TYPE_AUTH_INVALID, TYPE_AUTH_OK, TYPE_AUTH_REQUIRED)

from homeassistant.setup import async_setup_component

from tests.common import mock_coro

from . import API_PASSWORD


async def test_auth_via_msg(no_auth_websocket_client, legacy_auth):
    """Test authenticating."""
    await no_auth_websocket_client.send_json({
        'type': TYPE_AUTH,
        'api_password': API_PASSWORD
    })

    msg = await no_auth_websocket_client.receive_json()

    assert msg['type'] == TYPE_AUTH_OK


async def test_auth_events(hass, no_auth_websocket_client, legacy_auth):
    """Test authenticating."""
    connected_evt = []
    hass.helpers.dispatcher.async_dispatcher_connect(
        SIGNAL_WEBSOCKET_CONNECTED,
        lambda: connected_evt.append(1))
    disconnected_evt = []
    hass.helpers.dispatcher.async_dispatcher_connect(
        SIGNAL_WEBSOCKET_DISCONNECTED,
        lambda: disconnected_evt.append(1))

    await test_auth_via_msg(no_auth_websocket_client, legacy_auth)

    assert len(connected_evt) == 1
    assert not disconnected_evt

    await no_auth_websocket_client.close()
    await hass.async_block_till_done()

    assert len(disconnected_evt) == 1


async def test_auth_via_msg_incorrect_pass(no_auth_websocket_client):
    """Test authenticating."""
    with patch('homeassistant.components.websocket_api.auth.'
               'process_wrong_login', return_value=mock_coro()) \
            as mock_process_wrong_login:
        await no_auth_websocket_client.send_json({
            'type': TYPE_AUTH,
            'api_password': API_PASSWORD + 'wrong'
        })

        msg = await no_auth_websocket_client.receive_json()

    assert mock_process_wrong_login.called
    assert msg['type'] == TYPE_AUTH_INVALID
    assert msg['message'] == 'Invalid access token or password'


async def test_auth_events_incorrect_pass(hass, no_auth_websocket_client):
    """Test authenticating."""
    connected_evt = []
    hass.helpers.dispatcher.async_dispatcher_connect(
        SIGNAL_WEBSOCKET_CONNECTED,
        lambda: connected_evt.append(1))
    disconnected_evt = []
    hass.helpers.dispatcher.async_dispatcher_connect(
        SIGNAL_WEBSOCKET_DISCONNECTED,
        lambda: disconnected_evt.append(1))

    await test_auth_via_msg_incorrect_pass(no_auth_websocket_client)

    assert not connected_evt
    assert not disconnected_evt

    await no_auth_websocket_client.close()
    await hass.async_block_till_done()

    assert not connected_evt
    assert not disconnected_evt


async def test_pre_auth_only_auth_allowed(no_auth_websocket_client):
    """Verify that before authentication, only auth messages are allowed."""
    await no_auth_websocket_client.send_json({
        'type': 'call_service',
        'domain': 'domain_test',
        'service': 'test_service',
        'service_data': {
            'hello': 'world'
        }
    })

    msg = await no_auth_websocket_client.receive_json()

    assert msg['type'] == TYPE_AUTH_INVALID
    assert msg['message'].startswith('Auth message incorrectly formatted')


async def test_auth_active_with_token(hass, aiohttp_client, hass_access_token):
    """Test authenticating with a token."""
    assert await async_setup_component(hass, 'websocket_api', {
        'http': {
            'api_password': API_PASSWORD
        }
    })

    client = await aiohttp_client(hass.http.app)

    async with client.ws_connect(URL) as ws:
        auth_msg = await ws.receive_json()
        assert auth_msg['type'] == TYPE_AUTH_REQUIRED

        await ws.send_json({
            'type': TYPE_AUTH,
            'access_token': hass_access_token
        })

        auth_msg = await ws.receive_json()
        assert auth_msg['type'] == TYPE_AUTH_OK


async def test_auth_active_user_inactive(hass, aiohttp_client,
                                         hass_access_token):
    """Test authenticating with a token."""
    refresh_token = await hass.auth.async_validate_access_token(
        hass_access_token)
    refresh_token.user.is_active = False
    assert await async_setup_component(hass, 'websocket_api', {
        'http': {
            'api_password': API_PASSWORD
        }
    })

    client = await aiohttp_client(hass.http.app)

    async with client.ws_connect(URL) as ws:
        auth_msg = await ws.receive_json()
        assert auth_msg['type'] == TYPE_AUTH_REQUIRED

        await ws.send_json({
            'type': TYPE_AUTH,
            'access_token': hass_access_token
        })

        auth_msg = await ws.receive_json()
        assert auth_msg['type'] == TYPE_AUTH_INVALID


async def test_auth_active_with_password_not_allow(hass, aiohttp_client):
    """Test authenticating with a token."""
    assert await async_setup_component(hass, 'websocket_api', {
        'http': {
            'api_password': API_PASSWORD
        }
    })

    client = await aiohttp_client(hass.http.app)

    async with client.ws_connect(URL) as ws:
        auth_msg = await ws.receive_json()
        assert auth_msg['type'] == TYPE_AUTH_REQUIRED

        await ws.send_json({
            'type': TYPE_AUTH,
            'api_password': API_PASSWORD
        })

        auth_msg = await ws.receive_json()
        assert auth_msg['type'] == TYPE_AUTH_INVALID


async def test_auth_legacy_support_with_password(hass, aiohttp_client,
                                                 legacy_auth):
    """Test authenticating with a token."""
    assert await async_setup_component(hass, 'websocket_api', {
        'http': {
            'api_password': API_PASSWORD
        }
    })

    client = await aiohttp_client(hass.http.app)

    async with client.ws_connect(URL) as ws:
        with patch('homeassistant.auth.AuthManager.support_legacy',
                   return_value=True):
            auth_msg = await ws.receive_json()
            assert auth_msg['type'] == TYPE_AUTH_REQUIRED

            await ws.send_json({
                'type': TYPE_AUTH,
                'api_password': API_PASSWORD
            })

            auth_msg = await ws.receive_json()
            assert auth_msg['type'] == TYPE_AUTH_OK


async def test_auth_with_invalid_token(hass, aiohttp_client):
    """Test authenticating with a token."""
    assert await async_setup_component(hass, 'websocket_api', {
        'http': {
            'api_password': API_PASSWORD
        }
    })

    client = await aiohttp_client(hass.http.app)

    async with client.ws_connect(URL) as ws:
        auth_msg = await ws.receive_json()
        assert auth_msg['type'] == TYPE_AUTH_REQUIRED

        await ws.send_json({
            'type': TYPE_AUTH,
            'access_token': 'incorrect'
        })

        auth_msg = await ws.receive_json()
        assert auth_msg['type'] == TYPE_AUTH_INVALID
