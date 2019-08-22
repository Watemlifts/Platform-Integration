"""The tests for the Event automation."""
from unittest.mock import patch, Mock

from homeassistant.core import CoreState
from homeassistant.setup import async_setup_component
import homeassistant.components.automation as automation

from tests.common import async_mock_service, mock_coro


async def test_if_fires_on_hass_start(hass):
    """Test the firing when HASS starts."""
    calls = async_mock_service(hass, 'test', 'automation')
    hass.state = CoreState.not_running
    config = {
        automation.DOMAIN: {
            'alias': 'hello',
            'trigger': {
                'platform': 'homeassistant',
                'event': 'start',
            },
            'action': {
                'service': 'test.automation',
            }
        }
    }

    assert await async_setup_component(hass, automation.DOMAIN, config)
    assert automation.is_on(hass, 'automation.hello')
    assert len(calls) == 0

    await hass.async_start()
    assert automation.is_on(hass, 'automation.hello')
    assert len(calls) == 1

    with patch('homeassistant.config.async_hass_config_yaml',
               Mock(return_value=mock_coro(config))):
        await hass.services.async_call(
            automation.DOMAIN, automation.SERVICE_RELOAD, blocking=True)

    assert automation.is_on(hass, 'automation.hello')
    assert len(calls) == 1


async def test_if_fires_on_hass_shutdown(hass):
    """Test the firing when HASS starts."""
    calls = async_mock_service(hass, 'test', 'automation')
    hass.state = CoreState.not_running

    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'alias': 'hello',
            'trigger': {
                'platform': 'homeassistant',
                'event': 'shutdown',
            },
            'action': {
                'service': 'test.automation',
            }
        }
    })
    assert automation.is_on(hass, 'automation.hello')
    assert len(calls) == 0

    await hass.async_start()
    assert automation.is_on(hass, 'automation.hello')
    assert len(calls) == 0

    with patch.object(hass.loop, 'stop'):
        await hass.async_stop()
    assert len(calls) == 1
