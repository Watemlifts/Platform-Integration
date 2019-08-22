"""The test for the fido sensor platform."""
import asyncio
import logging
import sys
from unittest.mock import MagicMock

from homeassistant.bootstrap import async_setup_component
from homeassistant.components.fido import sensor as fido
from tests.common import assert_setup_component


CONTRACT = "123456789"


class FidoClientMock():
    """Fake Fido client."""

    def __init__(self, username, password, timeout=None, httpsession=None):
        """Fake Fido client init."""
        pass

    def get_phone_numbers(self):
        """Return Phone numbers."""
        return ["1112223344"]

    def get_data(self):
        """Return fake fido data."""
        return {"balance": 160.12,
                "1112223344": {"data_remaining": 100.33}}

    @asyncio.coroutine
    def fetch_data(self):
        """Return fake fetching data."""
        pass


class FidoClientMockError(FidoClientMock):
    """Fake Fido client error."""

    @asyncio.coroutine
    def fetch_data(self):
        """Return fake fetching data."""
        raise PyFidoErrorMock("Fake Error")


class PyFidoErrorMock(Exception):
    """Fake PyFido Error."""


class PyFidoClientFakeModule():
    """Fake pyfido.client module."""

    PyFidoError = PyFidoErrorMock


class PyFidoFakeModule():
    """Fake pyfido module."""

    FidoClient = FidoClientMockError


def fake_async_add_entities(component, update_before_add=False):
    """Fake async_add_entities function."""
    pass


@asyncio.coroutine
def test_fido_sensor(loop, hass):
    """Test the Fido number sensor."""
    sys.modules['pyfido'] = MagicMock()
    sys.modules['pyfido.client'] = MagicMock()
    sys.modules['pyfido.client.PyFidoError'] = \
        PyFidoErrorMock
    import pyfido.client
    pyfido.FidoClient = FidoClientMock
    pyfido.client.PyFidoError = PyFidoErrorMock
    config = {
        'sensor': {
            'platform': 'fido',
            'name': 'fido',
            'username': 'myusername',
            'password': 'password',
            'monitored_variables': [
                'balance',
                'data_remaining',
            ],
        }
    }
    with assert_setup_component(1):
        yield from async_setup_component(hass, 'sensor', config)
    state = hass.states.get('sensor.fido_1112223344_balance')
    assert state.state == "160.12"
    assert state.attributes.get('number') == "1112223344"
    state = hass.states.get('sensor.fido_1112223344_data_remaining')
    assert state.state == "100.33"


@asyncio.coroutine
def test_error(hass, caplog):
    """Test the Fido sensor errors."""
    caplog.set_level(logging.ERROR)
    sys.modules['pyfido'] = PyFidoFakeModule()
    sys.modules['pyfido.client'] = PyFidoClientFakeModule()

    config = {}
    fake_async_add_entities = MagicMock()
    yield from fido.async_setup_platform(hass, config,
                                         fake_async_add_entities)
    assert fake_async_add_entities.called is False
