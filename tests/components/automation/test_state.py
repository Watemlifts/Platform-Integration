"""The test for state automation."""
from datetime import timedelta

import pytest
from unittest.mock import patch

from homeassistant.core import Context
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util
import homeassistant.components.automation as automation

from tests.common import (
    async_fire_time_changed, assert_setup_component, mock_component)
from tests.components.automation import common
from tests.common import async_mock_service


@pytest.fixture
def calls(hass):
    """Track calls to a mock serivce."""
    return async_mock_service(hass, 'test', 'automation')


@pytest.fixture(autouse=True)
def setup_comp(hass):
    """Initialize components."""
    mock_component(hass, 'group')
    hass.states.async_set('test.entity', 'hello')


async def test_if_fires_on_entity_change(hass, calls):
    """Test for firing on entity change."""
    context = Context()
    hass.states.async_set('test.entity', 'hello')
    await hass.async_block_till_done()

    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'state',
                'entity_id': 'test.entity',
            },
            'action': {
                'service': 'test.automation',
                'data_template': {
                    'some': '{{ trigger.%s }}' % '}} - {{ trigger.'.join((
                        'platform', 'entity_id',
                        'from_state.state', 'to_state.state',
                        'for'))
                },
            }
        }
    })
    await hass.async_block_till_done()

    hass.states.async_set('test.entity', 'world', context=context)
    await hass.async_block_till_done()
    assert 1 == len(calls)
    assert calls[0].context.parent_id == context.id
    assert 'state - test.entity - hello - world - None' == \
        calls[0].data['some']

    await common.async_turn_off(hass)
    await hass.async_block_till_done()
    hass.states.async_set('test.entity', 'planet')
    await hass.async_block_till_done()
    assert 1 == len(calls)


async def test_if_fires_on_entity_change_with_from_filter(hass, calls):
    """Test for firing on entity change with filter."""
    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'state',
                'entity_id': 'test.entity',
                'from': 'hello'
            },
            'action': {
                'service': 'test.automation'
            }
        }
    })
    await hass.async_block_till_done()

    hass.states.async_set('test.entity', 'world')
    await hass.async_block_till_done()
    assert 1 == len(calls)


async def test_if_fires_on_entity_change_with_to_filter(hass, calls):
    """Test for firing on entity change with no filter."""
    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'state',
                'entity_id': 'test.entity',
                'to': 'world'
            },
            'action': {
                'service': 'test.automation'
            }
        }
    })
    await hass.async_block_till_done()

    hass.states.async_set('test.entity', 'world')
    await hass.async_block_till_done()
    assert 1 == len(calls)


async def test_if_fires_on_attribute_change_with_to_filter(hass, calls):
    """Test for not firing on attribute change."""
    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'state',
                'entity_id': 'test.entity',
                'to': 'world'
            },
            'action': {
                'service': 'test.automation'
            }
        }
    })
    await hass.async_block_till_done()

    hass.states.async_set('test.entity', 'world', {'test_attribute': 11})
    hass.states.async_set('test.entity', 'world', {'test_attribute': 12})
    await hass.async_block_till_done()
    assert 1 == len(calls)


async def test_if_fires_on_entity_change_with_both_filters(hass, calls):
    """Test for firing if both filters are a non match."""
    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'state',
                'entity_id': 'test.entity',
                'from': 'hello',
                'to': 'world'
            },
            'action': {
                'service': 'test.automation'
            }
        }
    })
    await hass.async_block_till_done()

    hass.states.async_set('test.entity', 'world')
    await hass.async_block_till_done()
    assert 1 == len(calls)


async def test_if_not_fires_if_to_filter_not_match(hass, calls):
    """Test for not firing if to filter is not a match."""
    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'state',
                'entity_id': 'test.entity',
                'from': 'hello',
                'to': 'world'
            },
            'action': {
                'service': 'test.automation'
            }
        }
    })
    await hass.async_block_till_done()

    hass.states.async_set('test.entity', 'moon')
    await hass.async_block_till_done()
    assert 0 == len(calls)


async def test_if_not_fires_if_from_filter_not_match(hass, calls):
    """Test for not firing if from filter is not a match."""
    hass.states.async_set('test.entity', 'bye')

    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'state',
                'entity_id': 'test.entity',
                'from': 'hello',
                'to': 'world'
            },
            'action': {
                'service': 'test.automation'
            }
        }
    })
    await hass.async_block_till_done()

    hass.states.async_set('test.entity', 'world')
    await hass.async_block_till_done()
    assert 0 == len(calls)


async def test_if_not_fires_if_entity_not_match(hass, calls):
    """Test for not firing if entity is not matching."""
    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'state',
                'entity_id': 'test.another_entity',
            },
            'action': {
                'service': 'test.automation'
            }
        }
    })
    await hass.async_block_till_done()

    hass.states.async_set('test.entity', 'world')
    await hass.async_block_till_done()
    assert 0 == len(calls)


async def test_if_action(hass, calls):
    """Test for to action."""
    entity_id = 'domain.test_entity'
    test_state = 'new_state'
    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'event',
                'event_type': 'test_event',
            },
            'condition': [{
                'condition': 'state',
                'entity_id': entity_id,
                'state': test_state
            }],
            'action': {
                'service': 'test.automation'
            }
        }
    })
    await hass.async_block_till_done()

    hass.states.async_set(entity_id, test_state)
    hass.bus.async_fire('test_event')
    await hass.async_block_till_done()

    assert 1 == len(calls)

    hass.states.async_set(entity_id, test_state + 'something')
    hass.bus.async_fire('test_event')
    await hass.async_block_till_done()

    assert 1 == len(calls)


async def test_if_fails_setup_if_to_boolean_value(hass, calls):
    """Test for setup failure for boolean to."""
    with assert_setup_component(0, automation.DOMAIN):
        assert await async_setup_component(hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'state',
                    'entity_id': 'test.entity',
                    'to': True,
                },
                'action': {
                    'service': 'homeassistant.turn_on',
                }
            }})


async def test_if_fails_setup_if_from_boolean_value(hass, calls):
    """Test for setup failure for boolean from."""
    with assert_setup_component(0, automation.DOMAIN):
        assert await async_setup_component(hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'state',
                    'entity_id': 'test.entity',
                    'from': True,
                },
                'action': {
                    'service': 'homeassistant.turn_on',
                }
            }})


async def test_if_fails_setup_bad_for(hass, calls):
    """Test for setup failure for bad for."""
    with assert_setup_component(0, automation.DOMAIN):
        assert await async_setup_component(hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'state',
                    'entity_id': 'test.entity',
                    'to': 'world',
                    'for': {
                        'invalid': 5
                    },
                },
                'action': {
                    'service': 'homeassistant.turn_on',
                }
            }})


async def test_if_fails_setup_for_without_to(hass, calls):
    """Test for setup failures for missing to."""
    with assert_setup_component(0, automation.DOMAIN):
        assert await async_setup_component(hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'state',
                    'entity_id': 'test.entity',
                    'for': {
                        'seconds': 5
                    },
                },
                'action': {
                    'service': 'homeassistant.turn_on',
                }
            }})


async def test_if_not_fires_on_entity_change_with_for(hass, calls):
    """Test for not firing on entity change with for."""
    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'state',
                'entity_id': 'test.entity',
                'to': 'world',
                'for': {
                    'seconds': 5
                },
            },
            'action': {
                'service': 'test.automation'
            }
        }
    })
    await hass.async_block_till_done()

    hass.states.async_set('test.entity', 'world')
    await hass.async_block_till_done()
    hass.states.async_set('test.entity', 'not_world')
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert 0 == len(calls)


async def test_if_not_fires_on_entities_change_with_for_after_stop(hass,
                                                                   calls):
    """Test for not firing on entity change with for after stop trigger."""
    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'state',
                'entity_id': [
                    'test.entity_1',
                    'test.entity_2',
                ],
                'to': 'world',
                'for': {
                    'seconds': 5
                },
            },
            'action': {
                'service': 'test.automation'
            }
        }
    })
    await hass.async_block_till_done()

    hass.states.async_set('test.entity_1', 'world')
    hass.states.async_set('test.entity_2', 'world')
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert 2 == len(calls)

    hass.states.async_set('test.entity_1', 'world_no')
    hass.states.async_set('test.entity_2', 'world_no')
    await hass.async_block_till_done()
    hass.states.async_set('test.entity_1', 'world')
    hass.states.async_set('test.entity_2', 'world')
    await hass.async_block_till_done()
    await common.async_turn_off(hass)
    await hass.async_block_till_done()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert 2 == len(calls)


async def test_if_fires_on_entity_change_with_for_attribute_change(hass,
                                                                   calls):
    """Test for firing on entity change with for and attribute change."""
    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'state',
                'entity_id': 'test.entity',
                'to': 'world',
                'for': {
                    'seconds': 5
                },
            },
            'action': {
                'service': 'test.automation'
            }
        }
    })
    await hass.async_block_till_done()

    utcnow = dt_util.utcnow()
    with patch('homeassistant.core.dt_util.utcnow') as mock_utcnow:
        mock_utcnow.return_value = utcnow
        hass.states.async_set('test.entity', 'world')
        await hass.async_block_till_done()
        mock_utcnow.return_value += timedelta(seconds=4)
        async_fire_time_changed(hass, mock_utcnow.return_value)
        hass.states.async_set('test.entity', 'world',
                              attributes={"mock_attr": "attr_change"})
        await hass.async_block_till_done()
        assert 0 == len(calls)
        mock_utcnow.return_value += timedelta(seconds=4)
        async_fire_time_changed(hass, mock_utcnow.return_value)
        await hass.async_block_till_done()
        assert 1 == len(calls)


async def test_if_fires_on_entity_change_with_for_multiple_force_update(hass,
                                                                        calls):
    """Test for firing on entity change with for and force update."""
    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'state',
                'entity_id': 'test.force_entity',
                'to': 'world',
                'for': {
                    'seconds': 5
                },
            },
            'action': {
                'service': 'test.automation'
            }
        }
    })
    await hass.async_block_till_done()

    utcnow = dt_util.utcnow()
    with patch('homeassistant.core.dt_util.utcnow') as mock_utcnow:
        mock_utcnow.return_value = utcnow
        hass.states.async_set('test.force_entity', 'world', None, True)
        await hass.async_block_till_done()
        for _ in range(0, 4):
            mock_utcnow.return_value += timedelta(seconds=1)
            async_fire_time_changed(hass, mock_utcnow.return_value)
            hass.states.async_set('test.force_entity', 'world', None, True)
            await hass.async_block_till_done()
        assert 0 == len(calls)
        mock_utcnow.return_value += timedelta(seconds=4)
        async_fire_time_changed(hass, mock_utcnow.return_value)
        await hass.async_block_till_done()
        assert 1 == len(calls)


async def test_if_fires_on_entity_change_with_for(hass, calls):
    """Test for firing on entity change with for."""
    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'state',
                'entity_id': 'test.entity',
                'to': 'world',
                'for': {
                    'seconds': 5
                },
            },
            'action': {
                'service': 'test.automation'
            }
        }
    })
    await hass.async_block_till_done()

    hass.states.async_set('test.entity', 'world')
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert 1 == len(calls)


async def test_if_fires_on_for_condition(hass, calls):
    """Test for firing if condition is on."""
    point1 = dt_util.utcnow()
    point2 = point1 + timedelta(seconds=10)
    with patch('homeassistant.core.dt_util.utcnow') as mock_utcnow:
        mock_utcnow.return_value = point1
        hass.states.async_set('test.entity', 'on')
        assert await async_setup_component(hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event',
                },
                'condition': {
                    'condition': 'state',
                    'entity_id': 'test.entity',
                    'state': 'on',
                    'for': {
                        'seconds': 5
                    },
                },
                'action': {'service': 'test.automation'},
            }
        })
        await hass.async_block_till_done()

        # not enough time has passed
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 0 == len(calls)

        # Time travel 10 secs into the future
        mock_utcnow.return_value = point2
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 1 == len(calls)


async def test_if_fires_on_for_condition_attribute_change(hass, calls):
    """Test for firing if condition is on with attribute change."""
    point1 = dt_util.utcnow()
    point2 = point1 + timedelta(seconds=4)
    point3 = point1 + timedelta(seconds=8)
    with patch('homeassistant.core.dt_util.utcnow') as mock_utcnow:
        mock_utcnow.return_value = point1
        hass.states.async_set('test.entity', 'on')
        assert await async_setup_component(hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'test_event',
                },
                'condition': {
                    'condition': 'state',
                    'entity_id': 'test.entity',
                    'state': 'on',
                    'for': {
                        'seconds': 5
                    },
                },
                'action': {'service': 'test.automation'},
            }
        })
        await hass.async_block_till_done()

        # not enough time has passed
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 0 == len(calls)

        # Still not enough time has passed, but an attribute is changed
        mock_utcnow.return_value = point2
        hass.states.async_set('test.entity', 'on',
                              attributes={"mock_attr": "attr_change"})
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 0 == len(calls)

        # Enough time has now passed
        mock_utcnow.return_value = point3
        hass.bus.async_fire('test_event')
        await hass.async_block_till_done()
        assert 1 == len(calls)


async def test_if_fails_setup_for_without_time(hass, calls):
    """Test for setup failure if no time is provided."""
    with assert_setup_component(0, automation.DOMAIN):
        assert await async_setup_component(hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {
                    'platform': 'event',
                    'event_type': 'bla'
                },
                'condition': {
                    'platform': 'state',
                    'entity_id': 'test.entity',
                    'state': 'on',
                    'for': {},
                },
                'action': {'service': 'test.automation'},
            }})


async def test_if_fails_setup_for_without_entity(hass, calls):
    """Test for setup failure if no entity is provided."""
    with assert_setup_component(0, automation.DOMAIN):
        assert await async_setup_component(hass, automation.DOMAIN, {
            automation.DOMAIN: {
                'trigger': {'event_type': 'bla'},
                'condition': {
                    'platform': 'state',
                    'state': 'on',
                    'for': {
                        'seconds': 5
                    },
                },
                'action': {'service': 'test.automation'},
            }})


async def test_wait_template_with_trigger(hass, calls):
    """Test using wait template with 'trigger.entity_id'."""
    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'state',
                'entity_id': 'test.entity',
                'to': 'world',
            },
            'action': [
                {'wait_template':
                    "{{ is_state(trigger.entity_id, 'hello') }}"},
                {'service': 'test.automation',
                 'data_template': {
                    'some':
                    '{{ trigger.%s }}' % '}} - {{ trigger.'.join((
                        'platform', 'entity_id', 'from_state.state',
                        'to_state.state'))
                    }}
            ],
        }
    })

    await hass.async_block_till_done()

    hass.states.async_set('test.entity', 'world')
    await hass.async_block_till_done()
    hass.states.async_set('test.entity', 'hello')
    await hass.async_block_till_done()
    assert 1 == len(calls)
    assert 'state - test.entity - hello - world' == \
        calls[0].data['some']


async def test_if_fires_on_entities_change_no_overlap(hass, calls):
    """Test for firing on entities change with no overlap."""
    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'state',
                'entity_id': [
                    'test.entity_1',
                    'test.entity_2',
                ],
                'to': 'world',
                'for': {
                    'seconds': 5
                },
            },
            'action': {
                'service': 'test.automation',
                'data_template': {
                    'some': '{{ trigger.entity_id }}',
                },
            }
        }
    })
    await hass.async_block_till_done()

    utcnow = dt_util.utcnow()
    with patch('homeassistant.core.dt_util.utcnow') as mock_utcnow:
        mock_utcnow.return_value = utcnow
        hass.states.async_set('test.entity_1', 'world')
        await hass.async_block_till_done()
        mock_utcnow.return_value += timedelta(seconds=10)
        async_fire_time_changed(hass, mock_utcnow.return_value)
        await hass.async_block_till_done()
        assert 1 == len(calls)
        assert 'test.entity_1' == calls[0].data['some']

        hass.states.async_set('test.entity_2', 'world')
        await hass.async_block_till_done()
        mock_utcnow.return_value += timedelta(seconds=10)
        async_fire_time_changed(hass, mock_utcnow.return_value)
        await hass.async_block_till_done()
        assert 2 == len(calls)
        assert 'test.entity_2' == calls[1].data['some']


async def test_if_fires_on_entities_change_overlap(hass, calls):
    """Test for firing on entities change with overlap."""
    assert await async_setup_component(hass, automation.DOMAIN, {
        automation.DOMAIN: {
            'trigger': {
                'platform': 'state',
                'entity_id': [
                    'test.entity_1',
                    'test.entity_2',
                ],
                'to': 'world',
                'for': {
                    'seconds': 5
                },
            },
            'action': {
                'service': 'test.automation',
                'data_template': {
                    'some': '{{ trigger.entity_id }}',
                },
            }
        }
    })
    await hass.async_block_till_done()

    utcnow = dt_util.utcnow()
    with patch('homeassistant.core.dt_util.utcnow') as mock_utcnow:
        mock_utcnow.return_value = utcnow
        hass.states.async_set('test.entity_1', 'world')
        await hass.async_block_till_done()
        mock_utcnow.return_value += timedelta(seconds=1)
        async_fire_time_changed(hass, mock_utcnow.return_value)
        hass.states.async_set('test.entity_2', 'world')
        await hass.async_block_till_done()
        mock_utcnow.return_value += timedelta(seconds=1)
        async_fire_time_changed(hass, mock_utcnow.return_value)
        hass.states.async_set('test.entity_2', 'hello')
        await hass.async_block_till_done()
        mock_utcnow.return_value += timedelta(seconds=1)
        async_fire_time_changed(hass, mock_utcnow.return_value)
        hass.states.async_set('test.entity_2', 'world')
        await hass.async_block_till_done()
        assert 0 == len(calls)
        mock_utcnow.return_value += timedelta(seconds=3)
        async_fire_time_changed(hass, mock_utcnow.return_value)
        await hass.async_block_till_done()
        assert 1 == len(calls)
        assert 'test.entity_1' == calls[0].data['some']

        mock_utcnow.return_value += timedelta(seconds=3)
        async_fire_time_changed(hass, mock_utcnow.return_value)
        await hass.async_block_till_done()
        assert 2 == len(calls)
        assert 'test.entity_2' == calls[1].data['some']
