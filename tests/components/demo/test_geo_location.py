"""The tests for the demo platform."""
import unittest
from unittest.mock import patch

from homeassistant.components import geo_location
from homeassistant.components.demo.geo_location import \
    NUMBER_OF_DEMO_DEVICES, DEFAULT_UNIT_OF_MEASUREMENT, \
    DEFAULT_UPDATE_INTERVAL
from homeassistant.setup import setup_component
from tests.common import get_test_home_assistant, assert_setup_component, \
    fire_time_changed
import homeassistant.util.dt as dt_util

CONFIG = {
    geo_location.DOMAIN: [
        {
            'platform': 'demo'
        }
    ]
}


class TestDemoPlatform(unittest.TestCase):
    """Test the demo platform."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_platform(self):
        """Test setup of demo platform via configuration."""
        utcnow = dt_util.utcnow()
        # Patching 'utcnow' to gain more control over the timed update.
        with patch('homeassistant.util.dt.utcnow', return_value=utcnow):
            with assert_setup_component(1, geo_location.DOMAIN):
                assert setup_component(self.hass, geo_location.DOMAIN, CONFIG)
            self.hass.block_till_done()

            # In this test, one zone and geolocation entities have been
            # generated.
            all_states = [self.hass.states.get(entity_id) for entity_id
                          in self.hass.states.entity_ids(geo_location.DOMAIN)]
            assert len(all_states) == NUMBER_OF_DEMO_DEVICES

            for state in all_states:
                # Check a single device's attributes.
                if state.domain != geo_location.DOMAIN:
                    # ignore home zone state
                    continue
                assert abs(
                    state.attributes['latitude'] -
                    self.hass.config.latitude
                ) < 1.0
                assert abs(
                    state.attributes['longitude'] -
                    self.hass.config.longitude
                ) < 1.0
                assert state.attributes['unit_of_measurement'] == \
                    DEFAULT_UNIT_OF_MEASUREMENT

            # Update (replaces 1 device).
            fire_time_changed(self.hass, utcnow + DEFAULT_UPDATE_INTERVAL)
            self.hass.block_till_done()
            # Get all states again, ensure that the number of states is still
            # the same, but the lists are different.
            all_states_updated = [
                self.hass.states.get(entity_id) for entity_id
                in self.hass.states.entity_ids(geo_location.DOMAIN)]
            assert len(all_states_updated) == NUMBER_OF_DEMO_DEVICES
            assert all_states != all_states_updated
