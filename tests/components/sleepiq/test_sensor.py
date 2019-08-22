"""The tests for SleepIQ sensor platform."""
import unittest
from unittest.mock import MagicMock

import requests_mock

from homeassistant.setup import setup_component
import homeassistant.components.sleepiq.sensor as sleepiq

from tests.components.sleepiq.test_init import mock_responses
from tests.common import get_test_home_assistant


class TestSleepIQSensorSetup(unittest.TestCase):
    """Tests the SleepIQ Sensor platform."""

    DEVICES = []

    def add_entities(self, devices):
        """Mock add devices."""
        for device in devices:
            self.DEVICES.append(device)

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.username = 'foo'
        self.password = 'bar'
        self.config = {
            'username': self.username,
            'password': self.password,
        }

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    @requests_mock.Mocker()
    def test_setup(self, mock):
        """Test for successfully setting up the SleepIQ platform."""
        mock_responses(mock)

        assert setup_component(self.hass, 'sleepiq', {
            'sleepiq': {
                'username': '',
                'password': '',
            }
        })

        sleepiq.setup_platform(self.hass,
                               self.config,
                               self.add_entities,
                               MagicMock())
        assert 2 == len(self.DEVICES)

        left_side = self.DEVICES[1]
        assert 'SleepNumber ILE Test1 SleepNumber' == left_side.name
        assert 40 == left_side.state

        right_side = self.DEVICES[0]
        assert 'SleepNumber ILE Test2 SleepNumber' == right_side.name
        assert 80 == right_side.state
