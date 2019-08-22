"""Tests for mobile_app component."""
# pylint: disable=redefined-outer-name,unused-import
import pytest

from tests.common import mock_device_registry

from homeassistant.setup import async_setup_component

from homeassistant.components.mobile_app.const import DOMAIN

from .const import REGISTER, REGISTER_CLEARTEXT


@pytest.fixture
def registry(hass):
    """Return a configured device registry."""
    return mock_device_registry(hass)


@pytest.fixture
async def create_registrations(authed_api_client):
    """Return two new registrations."""
    enc_reg = await authed_api_client.post(
        '/api/mobile_app/registrations', json=REGISTER
    )

    assert enc_reg.status == 201
    enc_reg_json = await enc_reg.json()

    clear_reg = await authed_api_client.post(
        '/api/mobile_app/registrations', json=REGISTER_CLEARTEXT
    )

    assert clear_reg.status == 201
    clear_reg_json = await clear_reg.json()

    return (enc_reg_json, clear_reg_json)


@pytest.fixture
async def webhook_client(hass, aiohttp_client):
    """mobile_app mock client."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()
    return await aiohttp_client(hass.http.app)


@pytest.fixture
async def authed_api_client(hass, hass_client):
    """Provide an authenticated client for mobile_app to use."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()
    return await hass_client()


@pytest.fixture(autouse=True)
async def setup_ws(hass):
    """Configure the websocket_api component."""
    assert await async_setup_component(hass, 'websocket_api', {})
    await hass.async_block_till_done()
