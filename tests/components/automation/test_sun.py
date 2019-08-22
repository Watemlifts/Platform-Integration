"""The tests for the sun automation."""
from datetime import datetime

import pytest
from unittest.mock import patch

from homeassistant.const import SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET
from homeassistant.setup import async_setup_component
from homeassistant.components import sun
import homeassistant.components.automation as automation
import homeassistant.util.dt as dt_util

from tests.common import (
    async_fire_time_changed, mock_component, async_mock_service)
from tests.components.automation import common

ORIG_TIME_ZONE = dt_util.DEFAULT_TIME_ZONE


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, 'test', 'automation')


@pytest.fixture(autouse=True)
def setup_comp(hass):
    """Initialize components."""
    mock_component(hass, 'group')
    dt_util.set_default_time_zone(hass.config.time_zone)
    hass.loop.run_until_complete(async_setup_component(hass, sun.DOMAIN, {
            sun.DOMAIN: {sun.CONF_ELEVATION: 0}}))


def teardown():
    """Restore."""
    dt_util.set_default_time_zone(ORIG_TIME_ZONE)


async def test_sunset_trigger(hass, calls):
    """Test the sunset trigger."""
    now = datetime(2015, 9, 15, 23, tzinfo=dt_util.UTC)
    trigger_time = datetime(2015, 9, 16, 2, tzinfo=dt_util.UTC)

    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        await async_setup_component(hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'sun',
                    'event': SUN_EVENT_SUNSET,
                },
                'action': {
                    'service': 'test.automation',
                }
            }
        })

    await common.async_turn_off(hass)
    await hass.async_block_till_done()

    async_fire_time_changed(hass, trigger_time)
    await hass.async_block_till_done()
    assert 0 == len(calls)

    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        await common.async_turn_on(hass)
        await hass.async_block_till_done()

    async_fire_time_changed(hass, trigger_time)
    await hass.async_block_till_done()
    assert 1 == len(calls)


async def test_sunrise_trigger(hass, calls):
    """Test the sunrise trigger."""
    now = datetime(2015, 9, 13, 23, tzinfo=dt_util.UTC)
    trigger_time = datetime(2015, 9, 16, 14, tzinfo=dt_util.UTC)

    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        await async_setup_component(hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'sun',
                    'event': SUN_EVENT_SUNRISE,
                },
                'action': {
                    'service': 'test.automation',
                }
            }
        })

    async_fire_time_changed(hass, trigger_time)
    await hass.async_block_till_done()
    assert 1 == len(calls)


async def test_sunset_trigger_with_offset(hass, calls):
    """Test the sunset trigger with offset."""
    now = datetime(2015, 9, 15, 23, tzinfo=dt_util.UTC)
    trigger_time = datetime(2015, 9, 16, 2, 30, tzinfo=dt_util.UTC)

    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        await async_setup_component(hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'sun',
                    'event': SUN_EVENT_SUNSET,
                    'offset': '0:30:00'
                },
                'action': {
                    'service': 'test.automation',
                    'data_template': {
                        'some':
                        '{{ trigger.%s }}' % '}} - {{ trigger.'.join((
                            'platform', 'event', 'offset'))
                    },
                }
            }
        })

    async_fire_time_changed(hass, trigger_time)
    await hass.async_block_till_done()
    assert 1 == len(calls)
    assert 'sun - sunset - 0:30:00' == calls[0].data['some']


async def test_sunrise_trigger_with_offset(hass, calls):
    """Test the sunrise trigger with offset."""
    now = datetime(2015, 9, 13, 23, tzinfo=dt_util.UTC)
    trigger_time = datetime(2015, 9, 16, 13, 30, tzinfo=dt_util.UTC)

    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        await async_setup_component(hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'sun',
                    'event': SUN_EVENT_SUNRISE,
                    'offset': '-0:30:00'
                },
                'action': {
                    'service': 'test.automation',
                }
            }
        })

    async_fire_time_changed(hass, trigger_time)
    await hass.async_block_till_done()
    assert 1 == len(calls)


async def test_if_action_before_sunrise_no_offset(hass, calls):
    """
    Test if action was before sunrise.

    Before sunrise is true from midnight until sunset, local time.
    """
    await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'event',
                'event_type': 'test_event',
            },
            'condition': {
                'condition': 'sun',
                'before': SUN_EVENT_SUNRISE,
            },
            'action': {
                'service': 'test.automation'
            }
        }
    })

    # sunrise: 2015-09-16 06:32:43 local, sunset: 2015-09-16 18:55:24 local
    # sunrise: 2015-09-16 13:32:43 UTC,   sunset: 2015-09-17 01:55:24 UTC
    # now = sunrise + 1s -> 'before sunrise' not true
    now = datetime(2015, 9, 16, 13, 32, 44, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 0 == len(calls)

    # now = sunrise -> 'before sunrise' true
    now = datetime(2015, 9, 16, 13, 32, 43, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 1 == len(calls)

    # now = local midnight -> 'before sunrise' true
    now = datetime(2015, 9, 16, 7, 0, 0, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 2 == len(calls)

    # now = local midnight - 1s -> 'before sunrise' not true
    now = datetime(2015, 9, 17, 6, 59, 59, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 2 == len(calls)


async def test_if_action_after_sunrise_no_offset(hass, calls):
    """
    Test if action was after sunrise.

    After sunrise is true from sunrise until midnight, local time.
    """
    await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'event',
                'event_type': 'test_event',
            },
            'condition': {
                'condition': 'sun',
                'after': SUN_EVENT_SUNRISE,
            },
            'action': {
                'service': 'test.automation'
            }
        }
    })

    # sunrise: 2015-09-16 06:32:43 local, sunset: 2015-09-16 18:55:24 local
    # sunrise: 2015-09-16 13:32:43 UTC,   sunset: 2015-09-17 01:55:24 UTC
    # now = sunrise - 1s -> 'after sunrise' not true
    now = datetime(2015, 9, 16, 13, 32, 42, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 0 == len(calls)

    # now = sunrise + 1s -> 'after sunrise' true
    now = datetime(2015, 9, 16, 13, 32, 43, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 1 == len(calls)

    # now = local midnight -> 'after sunrise' not true
    now = datetime(2015, 9, 16, 7, 0, 0, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 1 == len(calls)

    # now = local midnight - 1s -> 'after sunrise' true
    now = datetime(2015, 9, 17, 6, 59, 59, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 2 == len(calls)


async def test_if_action_before_sunrise_with_offset(hass, calls):
    """
    Test if action was before sunrise with offset.

    Before sunrise is true from midnight until sunset, local time.
    """
    await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'event',
                'event_type': 'test_event',
            },
            'condition': {
                'condition': 'sun',
                'before': SUN_EVENT_SUNRISE,
                'before_offset': '+1:00:00'
            },
            'action': {
                'service': 'test.automation'
            }
        }
    })

    # sunrise: 2015-09-16 06:32:43 local, sunset: 2015-09-16 18:55:24 local
    # sunrise: 2015-09-16 13:32:43 UTC,   sunset: 2015-09-17 01:55:24 UTC
    # now = sunrise + 1s + 1h -> 'before sunrise' with offset +1h not true
    now = datetime(2015, 9, 16, 14, 32, 44, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 0 == len(calls)

    # now = sunrise + 1h -> 'before sunrise' with offset +1h true
    now = datetime(2015, 9, 16, 14, 32, 43, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 1 == len(calls)

    # now = UTC midnight -> 'before sunrise' with offset +1h not true
    now = datetime(2015, 9, 17, 0, 0, 0, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 1 == len(calls)

    # now = UTC midnight - 1s -> 'before sunrise' with offset +1h not true
    now = datetime(2015, 9, 16, 23, 59, 59, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 1 == len(calls)

    # now = local midnight -> 'before sunrise' with offset +1h true
    now = datetime(2015, 9, 16, 7, 0, 0, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 2 == len(calls)

    # now = local midnight - 1s -> 'before sunrise' with offset +1h not true
    now = datetime(2015, 9, 17, 6, 59, 59, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 2 == len(calls)

    # now = sunset -> 'before sunrise' with offset +1h not true
    now = datetime(2015, 9, 17, 1, 56, 48, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 2 == len(calls)

    # now = sunset -1s -> 'before sunrise' with offset +1h not true
    now = datetime(2015, 9, 17, 1, 56, 45, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 2 == len(calls)


async def test_if_action_before_sunset_with_offset(hass, calls):
    """
    Test if action was before sunset with offset.

    Before sunset is true from midnight until sunset, local time.
    """
    await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'event',
                'event_type': 'test_event',
            },
            'condition': {
                'condition': 'sun',
                'before': 'sunset',
                'before_offset': '+1:00:00'
            },
            'action': {
                'service': 'test.automation'
            }
        }
    })

    # sunrise: 2015-09-16 06:32:43 local, sunset: 2015-09-16 18:55:24 local
    # sunrise: 2015-09-16 13:32:43 UTC,   sunset: 2015-09-17 01:55:24 UTC
    # now = local midnight -> 'before sunset' with offset +1h true
    now = datetime(2015, 9, 16, 7, 0, 0, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 1 == len(calls)

    # now = sunset + 1s + 1h -> 'before sunset' with offset +1h not true
    now = datetime(2015, 9, 17, 2, 55, 25, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 1 == len(calls)

    # now = sunset + 1h -> 'before sunset' with offset +1h true
    now = datetime(2015, 9, 17, 2, 55, 24, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 2 == len(calls)

    # now = UTC midnight -> 'before sunset' with offset +1h true
    now = datetime(2015, 9, 17, 0, 0, 0, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 3 == len(calls)

    # now = UTC midnight - 1s -> 'before sunset' with offset +1h true
    now = datetime(2015, 9, 16, 23, 59, 59, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 4 == len(calls)

    # now = sunrise -> 'before sunset' with offset +1h true
    now = datetime(2015, 9, 16, 13, 32, 43, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 5 == len(calls)

    # now = sunrise -1s -> 'before sunset' with offset +1h true
    now = datetime(2015, 9, 16, 13, 32, 42, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 6 == len(calls)

    # now = local midnight-1s -> 'after sunrise' with offset +1h not true
    now = datetime(2015, 9, 17, 6, 59, 59, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 6 == len(calls)


async def test_if_action_after_sunrise_with_offset(hass, calls):
    """
    Test if action was after sunrise with offset.

    After sunrise is true from sunrise until midnight, local time.
    """
    await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'event',
                'event_type': 'test_event',
            },
            'condition': {
                'condition': 'sun',
                'after': SUN_EVENT_SUNRISE,
                'after_offset': '+1:00:00'
            },
            'action': {
                'service': 'test.automation'
            }
        }
    })

    # sunrise: 2015-09-16 06:32:43 local, sunset: 2015-09-16 18:55:24 local
    # sunrise: 2015-09-16 13:32:43 UTC,   sunset: 2015-09-17 01:55:24 UTC
    # now = sunrise - 1s + 1h -> 'after sunrise' with offset +1h not true
    now = datetime(2015, 9, 16, 14, 32, 42, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 0 == len(calls)

    # now = sunrise + 1h -> 'after sunrise' with offset +1h true
    now = datetime(2015, 9, 16, 14, 32, 43, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 1 == len(calls)

    # now = UTC noon -> 'after sunrise' with offset +1h not true
    now = datetime(2015, 9, 16, 12, 0, 0, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 1 == len(calls)

    # now = UTC noon - 1s -> 'after sunrise' with offset +1h not true
    now = datetime(2015, 9, 16, 11, 59, 59, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 1 == len(calls)

    # now = local noon -> 'after sunrise' with offset +1h true
    now = datetime(2015, 9, 16, 19, 1, 0, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 2 == len(calls)

    # now = local noon - 1s -> 'after sunrise' with offset +1h true
    now = datetime(2015, 9, 16, 18, 59, 59, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 3 == len(calls)

    # now = sunset -> 'after sunrise' with offset +1h true
    now = datetime(2015, 9, 17, 1, 55, 24, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 4 == len(calls)

    # now = sunset + 1s -> 'after sunrise' with offset +1h true
    now = datetime(2015, 9, 17, 1, 55, 25, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 5 == len(calls)

    # now = local midnight-1s -> 'after sunrise' with offset +1h true
    now = datetime(2015, 9, 17, 6, 59, 59, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 6 == len(calls)

    # now = local midnight -> 'after sunrise' with offset +1h not true
    now = datetime(2015, 9, 17, 7, 0, 0, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 6 == len(calls)


async def test_if_action_after_sunset_with_offset(hass, calls):
    """
    Test if action was after sunset with offset.

    After sunset is true from sunset until midnight, local time.
    """
    await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'event',
                'event_type': 'test_event',
            },
            'condition': {
                'condition': 'sun',
                'after': 'sunset',
                'after_offset': '+1:00:00'
            },
            'action': {
                'service': 'test.automation'
            }
        }
    })

    # sunrise: 2015-09-15 06:32:05 local, sunset: 2015-09-15 18:56:46 local
    # sunrise: 2015-09-15 13:32:05 UTC,   sunset: 2015-09-16 01:56:46 UTC
    # now = sunset - 1s + 1h -> 'after sunset' with offset +1h not true
    now = datetime(2015, 9, 16, 2, 56, 45, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 0 == len(calls)

    # now = sunset + 1h -> 'after sunset' with offset +1h true
    now = datetime(2015, 9, 16, 2, 56, 46, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 1 == len(calls)

    # now = midnight-1s -> 'after sunset' with offset +1h true
    now = datetime(2015, 9, 16, 6, 59, 59, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 2 == len(calls)

    # now = midnight -> 'after sunset' with offset +1h not true
    now = datetime(2015, 9, 16, 7, 0, 0, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 2 == len(calls)


async def test_if_action_before_and_after_during(hass, calls):
    """
    Test if action was after sunset and before sunrise.

    This is true from sunrise until sunset.
    """
    await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'event',
                'event_type': 'test_event',
            },
            'condition': {
                'condition': 'sun',
                'after': SUN_EVENT_SUNRISE,
                'before': SUN_EVENT_SUNSET
            },
            'action': {
                'service': 'test.automation'
            }
        }
    })

    # sunrise: 2015-09-16 06:32:43 local, sunset: 2015-09-16 18:55:24 local
    # sunrise: 2015-09-16 13:32:43 UTC,   sunset: 2015-09-17 01:55:24 UTC
    # now = sunrise - 1s -> 'after sunrise' + 'before sunset' not true
    now = datetime(2015, 9, 16, 13, 32, 42, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 0 == len(calls)

    # now = sunset + 1s -> 'after sunrise' + 'before sunset' not true
    now = datetime(2015, 9, 17, 1, 55, 25, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 0 == len(calls)

    # now = sunrise -> 'after sunrise' + 'before sunset' true
    now = datetime(2015, 9, 16, 13, 32, 43, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 1 == len(calls)

    # now = sunset -> 'after sunrise' + 'before sunset' true
    now = datetime(2015, 9, 17, 1, 55, 24, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 2 == len(calls)

    # now = 9AM local  -> 'after sunrise' + 'before sunset' true
    now = datetime(2015, 9, 16, 16, tzinfo=dt_util.UTC)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 3 == len(calls)
