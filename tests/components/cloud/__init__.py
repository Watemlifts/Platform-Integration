"""Tests for the cloud component."""
from unittest.mock import patch

from homeassistant.setup import async_setup_component
from homeassistant.components import cloud
from homeassistant.components.cloud import const

from tests.common import mock_coro


async def mock_cloud(hass, config=None):
    """Mock cloud."""
    assert await async_setup_component(
        hass, cloud.DOMAIN, {
            'cloud': config or {}
        })
    cloud_inst = hass.data['cloud']
    with patch('hass_nabucasa.Cloud.run_executor', return_value=mock_coro()):
        await cloud_inst.start()


def mock_cloud_prefs(hass, prefs={}):
    """Fixture for cloud component."""
    prefs_to_set = {
        const.PREF_ENABLE_ALEXA: True,
        const.PREF_ENABLE_GOOGLE: True,
        const.PREF_GOOGLE_SECURE_DEVICES_PIN: None,
    }
    prefs_to_set.update(prefs)
    hass.data[cloud.DOMAIN].client._prefs._prefs = prefs_to_set
    return prefs_to_set
