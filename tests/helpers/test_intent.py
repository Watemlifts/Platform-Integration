"""Tests for the intent helpers."""

import voluptuous as vol

import pytest

from homeassistant.core import State
from homeassistant.helpers import (intent, config_validation as cv)


class MockIntentHandler(intent.IntentHandler):
    """Provide a mock intent handler."""

    def __init__(self, slot_schema):
        """Initialize the mock handler."""
        self.slot_schema = slot_schema


def test_async_match_state():
    """Test async_match_state helper."""
    state1 = State('light.kitchen', 'on')
    state2 = State('switch.kitchen', 'on')

    state = intent.async_match_state(None, 'kitch', [state1, state2])
    assert state is state1


def test_async_validate_slots():
    """Test async_validate_slots of IntentHandler."""
    handler1 = MockIntentHandler({
        vol.Required('name'): cv.string,
        })

    with pytest.raises(vol.error.MultipleInvalid):
        handler1.async_validate_slots({})
    with pytest.raises(vol.error.MultipleInvalid):
        handler1.async_validate_slots({'name': 1})
    with pytest.raises(vol.error.MultipleInvalid):
        handler1.async_validate_slots({'name': 'kitchen'})
    handler1.async_validate_slots({'name': {'value': 'kitchen'}})
    handler1.async_validate_slots({
        'name': {'value': 'kitchen'},
        'probability': {'value': '0.5'}
        })
