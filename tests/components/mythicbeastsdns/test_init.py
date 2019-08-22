"""Test the Mythic Beasts DNS component."""
import logging
import asynctest

from homeassistant.setup import async_setup_component
from homeassistant.components import mythicbeastsdns

_LOGGER = logging.getLogger(__name__)


async def mbddns_update_mock(domain, password, host, ttl=60, session=None):
    """Mock out mythic beasts updater."""
    if password == 'incorrect':
        _LOGGER.error("Updating Mythic Beasts failed: Not authenticated")
        return False
    if host[0] == '$':
        _LOGGER.error("Updating Mythic Beasts failed: Invalid Character")
        return False
    return True


@asynctest.mock.patch('mbddns.update', new=mbddns_update_mock)
async def test_update(hass):
    """Run with correct values and check true is returned."""
    result = await async_setup_component(
        hass,
        mythicbeastsdns.DOMAIN,
        {
            mythicbeastsdns.DOMAIN: {
                'domain': 'example.org',
                'password': 'correct',
                'host': 'hass'
            }
        }
    )
    assert result


@asynctest.mock.patch('mbddns.update', new=mbddns_update_mock)
async def test_update_fails_if_wrong_token(hass):
    """Run with incorrect token and check false is returned."""
    result = await async_setup_component(
        hass,
        mythicbeastsdns.DOMAIN,
        {
            mythicbeastsdns.DOMAIN: {
                'domain': 'example.org',
                'password': 'incorrect',
                'host': 'hass'
            }
        }
    )
    assert not result


@asynctest.mock.patch('mbddns.update', new=mbddns_update_mock)
async def test_update_fails_if_invalid_host(hass):
    """Run with invalid characters in host and check false is returned."""
    result = await async_setup_component(
        hass,
        mythicbeastsdns.DOMAIN,
        {
            mythicbeastsdns.DOMAIN: {
                'domain': 'example.org',
                'password': 'correct',
                'host': '$hass'
            }
        }
    )
    assert not result
