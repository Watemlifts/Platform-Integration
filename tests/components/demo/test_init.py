"""The tests for the Demo component."""
import json
import os

import pytest

from homeassistant.setup import async_setup_component
from homeassistant.components import demo
from homeassistant.components.device_tracker.legacy import YAML_DEVICES
from homeassistant.helpers.json import JSONEncoder


@pytest.fixture(autouse=True)
def mock_history(hass):
    """Mock history component loaded."""
    hass.config.components.add('history')


@pytest.fixture(autouse=True)
def demo_cleanup(hass):
    """Clean up device tracker demo file."""
    yield
    try:
        os.remove(hass.config.path(YAML_DEVICES))
    except FileNotFoundError:
        pass


async def test_setting_up_demo(hass):
    """Test if we can set up the demo and dump it to JSON."""
    assert await async_setup_component(hass, demo.DOMAIN, {
        'demo': {}
    })
    await hass.async_start()

    # This is done to make sure entity components don't accidentally store
    # non-JSON-serializable data in the state machine.
    try:
        json.dumps(hass.states.async_all(), cls=JSONEncoder)
    except Exception:
        pytest.fail('Unable to convert all demo entities to JSON. '
                    'Wrong data in state machine!')
