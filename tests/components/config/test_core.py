"""Test hassbian config."""
from unittest.mock import patch

import pytest

from homeassistant.bootstrap import async_setup_component
from homeassistant.components import config
from homeassistant.components.websocket_api.const import TYPE_RESULT
from homeassistant.const import CONF_UNIT_SYSTEM, CONF_UNIT_SYSTEM_IMPERIAL
from homeassistant.util import dt as dt_util, location
from tests.common import mock_coro

ORIG_TIME_ZONE = dt_util.DEFAULT_TIME_ZONE


@pytest.fixture
async def client(hass, hass_ws_client):
    """Fixture that can interact with the config manager API."""
    with patch.object(config, 'SECTIONS', ['core']):
        assert await async_setup_component(hass, 'config', {})
    return await hass_ws_client(hass)


async def test_validate_config_ok(hass, hass_client):
    """Test checking config."""
    with patch.object(config, 'SECTIONS', ['core']):
        await async_setup_component(hass, 'config', {})

    client = await hass_client()

    with patch(
        'homeassistant.components.config.core.async_check_ha_config_file',
            return_value=mock_coro()):
        resp = await client.post('/api/config/core/check_config')

    assert resp.status == 200
    result = await resp.json()
    assert result['result'] == 'valid'
    assert result['errors'] is None

    with patch(
        'homeassistant.components.config.core.async_check_ha_config_file',
            return_value=mock_coro('beer')):
        resp = await client.post('/api/config/core/check_config')

    assert resp.status == 200
    result = await resp.json()
    assert result['result'] == 'invalid'
    assert result['errors'] == 'beer'


async def test_websocket_core_update(hass, client):
    """Test core config update websocket command."""
    assert hass.config.latitude != 60
    assert hass.config.longitude != 50
    assert hass.config.elevation != 25
    assert hass.config.location_name != 'Huis'
    assert hass.config.units.name != CONF_UNIT_SYSTEM_IMPERIAL
    assert hass.config.time_zone.zone != 'America/New_York'

    await client.send_json({
        'id': 5,
        'type': 'config/core/update',
        'latitude': 60,
        'longitude': 50,
        'elevation': 25,
        'location_name': 'Huis',
        CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_IMPERIAL,
        'time_zone': 'America/New_York',
    })

    msg = await client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success']
    assert hass.config.latitude == 60
    assert hass.config.longitude == 50
    assert hass.config.elevation == 25
    assert hass.config.location_name == 'Huis'
    assert hass.config.units.name == CONF_UNIT_SYSTEM_IMPERIAL
    assert hass.config.time_zone.zone == 'America/New_York'

    dt_util.set_default_time_zone(ORIG_TIME_ZONE)


async def test_websocket_core_update_not_admin(
        hass, hass_ws_client, hass_admin_user):
    """Test core config fails for non admin."""
    hass_admin_user.groups = []
    with patch.object(config, 'SECTIONS', ['core']):
        await async_setup_component(hass, 'config', {})

    client = await hass_ws_client(hass)
    await client.send_json({
        'id': 6,
        'type': 'config/core/update',
        'latitude': 23,
    })

    msg = await client.receive_json()

    assert msg['id'] == 6
    assert msg['type'] == TYPE_RESULT
    assert not msg['success']
    assert msg['error']['code'] == 'unauthorized'


async def test_websocket_bad_core_update(hass, client):
    """Test core config update fails with bad parameters."""
    await client.send_json({
        'id': 7,
        'type': 'config/core/update',
        'latituude': 23,
    })

    msg = await client.receive_json()

    assert msg['id'] == 7
    assert msg['type'] == TYPE_RESULT
    assert not msg['success']
    assert msg['error']['code'] == 'invalid_format'


async def test_detect_config(hass, client):
    """Test detect config."""
    with patch('homeassistant.util.location.async_detect_location_info',
               return_value=mock_coro(None)):
        await client.send_json({
            'id': 1,
            'type': 'config/core/detect',
        })

        msg = await client.receive_json()

    assert msg['success'] is True
    assert msg['result'] == {}


async def test_detect_config_fail(hass, client):
    """Test detect config."""
    with patch('homeassistant.util.location.async_detect_location_info',
               return_value=mock_coro(location.LocationInfo(
                   ip=None,
                   country_code=None,
                   country_name=None,
                   region_code=None,
                   region_name=None,
                   city=None,
                   zip_code=None,
                   latitude=None,
                   longitude=None,
                   use_metric=True,
                   time_zone='Europe/Amsterdam',
               ))):
        await client.send_json({
            'id': 1,
            'type': 'config/core/detect',
        })

        msg = await client.receive_json()

    assert msg['success'] is True
    assert msg['result'] == {
        'unit_system': 'metric',
        'time_zone': 'Europe/Amsterdam',
    }
