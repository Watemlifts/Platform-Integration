"""Test config entries API."""

import asyncio
from collections import OrderedDict
from unittest.mock import patch

import pytest
import voluptuous as vol

from homeassistant import config_entries as core_ce, data_entry_flow
from homeassistant.config_entries import HANDLERS
from homeassistant.core import callback
from homeassistant.setup import async_setup_component
from homeassistant.components.config import config_entries
from homeassistant.generated import config_flows

from tests.common import (
    MockConfigEntry, MockModule, mock_coro_func, mock_integration,
    mock_entity_platform)


@pytest.fixture(autouse=True)
def mock_test_component(hass):
    """Ensure a component called 'test' exists."""
    mock_integration(hass, MockModule('test'))


@pytest.fixture
def client(hass, hass_client):
    """Fixture that can interact with the config manager API."""
    hass.loop.run_until_complete(async_setup_component(hass, 'http', {}))
    hass.loop.run_until_complete(config_entries.async_setup(hass))
    yield hass.loop.run_until_complete(hass_client())


@HANDLERS.register('comp1')
class Comp1ConfigFlow:
    """Config flow with options flow."""

    @staticmethod
    @callback
    def async_get_options_flow(config, options):
        """Get options flow."""
        pass


@HANDLERS.register('comp2')
class Comp2ConfigFlow:
    """Config flow without options flow."""

    def __init__(self):
        """Init."""
        pass


async def test_get_entries(hass, client):
    """Test get entries."""
    MockConfigEntry(
        domain='comp1',
        title='Test 1',
        source='bla',
        connection_class=core_ce.CONN_CLASS_LOCAL_POLL,
    ).add_to_hass(hass)
    MockConfigEntry(
        domain='comp2',
        title='Test 2',
        source='bla2',
        state=core_ce.ENTRY_STATE_LOADED,
        connection_class=core_ce.CONN_CLASS_ASSUMED,
    ).add_to_hass(hass)

    resp = await client.get('/api/config/config_entries/entry')
    assert resp.status == 200
    data = await resp.json()
    for entry in data:
        entry.pop('entry_id')
    assert data == [
        {
            'domain': 'comp1',
            'title': 'Test 1',
            'source': 'bla',
            'state': 'not_loaded',
            'connection_class': 'local_poll',
            'supports_options': True,
        },
        {
            'domain': 'comp2',
            'title': 'Test 2',
            'source': 'bla2',
            'state': 'loaded',
            'connection_class': 'assumed',
            'supports_options': False,
        },
    ]


@asyncio.coroutine
def test_remove_entry(hass, client):
    """Test removing an entry via the API."""
    entry = MockConfigEntry(domain='demo', state=core_ce.ENTRY_STATE_LOADED)
    entry.add_to_hass(hass)
    resp = yield from client.delete(
        '/api/config/config_entries/entry/{}'.format(entry.entry_id))
    assert resp.status == 200
    data = yield from resp.json()
    assert data == {
        'require_restart': True
    }
    assert len(hass.config_entries.async_entries()) == 0


async def test_remove_entry_unauth(hass, client, hass_admin_user):
    """Test removing an entry via the API."""
    hass_admin_user.groups = []
    entry = MockConfigEntry(domain='demo', state=core_ce.ENTRY_STATE_LOADED)
    entry.add_to_hass(hass)
    resp = await client.delete(
        '/api/config/config_entries/entry/{}'.format(entry.entry_id))
    assert resp.status == 401
    assert len(hass.config_entries.async_entries()) == 1


@asyncio.coroutine
def test_available_flows(hass, client):
    """Test querying the available flows."""
    with patch.object(config_flows, 'FLOWS', ['hello', 'world']):
        resp = yield from client.get(
            '/api/config/config_entries/flow_handlers')
        assert resp.status == 200
        data = yield from resp.json()
        assert data == ['hello', 'world']


############################
#  FLOW MANAGER API TESTS  #
############################


@asyncio.coroutine
def test_initialize_flow(hass, client):
    """Test we can initialize a flow."""
    mock_entity_platform(hass, 'config_flow.test', None)

    class TestFlow(core_ce.ConfigFlow):
        @asyncio.coroutine
        def async_step_user(self, user_input=None):
            schema = OrderedDict()
            schema[vol.Required('username')] = str
            schema[vol.Required('password')] = str

            return self.async_show_form(
                step_id='user',
                data_schema=schema,
                description_placeholders={
                    'url': 'https://example.com',
                },
                errors={
                    'username': 'Should be unique.'
                }
            )

    with patch.dict(HANDLERS, {'test': TestFlow}):
        resp = yield from client.post('/api/config/config_entries/flow',
                                      json={'handler': 'test'})

    assert resp.status == 200
    data = yield from resp.json()

    data.pop('flow_id')

    assert data == {
        'type': 'form',
        'handler': 'test',
        'step_id': 'user',
        'data_schema': [
            {
                'name': 'username',
                'required': True,
                'type': 'string'
            },
            {
                'name': 'password',
                'required': True,
                'type': 'string'
            }
        ],
        'description_placeholders': {
            'url': 'https://example.com',
        },
        'errors': {
            'username': 'Should be unique.'
        }
    }


async def test_initialize_flow_unauth(hass, client, hass_admin_user):
    """Test we can initialize a flow."""
    hass_admin_user.groups = []

    class TestFlow(core_ce.ConfigFlow):
        @asyncio.coroutine
        def async_step_user(self, user_input=None):
            schema = OrderedDict()
            schema[vol.Required('username')] = str
            schema[vol.Required('password')] = str

            return self.async_show_form(
                step_id='user',
                data_schema=schema,
                description_placeholders={
                    'url': 'https://example.com',
                },
                errors={
                    'username': 'Should be unique.'
                }
            )

    with patch.dict(HANDLERS, {'test': TestFlow}):
        resp = await client.post('/api/config/config_entries/flow',
                                 json={'handler': 'test'})

    assert resp.status == 401


@asyncio.coroutine
def test_abort(hass, client):
    """Test a flow that aborts."""
    mock_entity_platform(hass, 'config_flow.test', None)

    class TestFlow(core_ce.ConfigFlow):
        @asyncio.coroutine
        def async_step_user(self, user_input=None):
            return self.async_abort(reason='bla')

    with patch.dict(HANDLERS, {'test': TestFlow}):
        resp = yield from client.post('/api/config/config_entries/flow',
                                      json={'handler': 'test'})

    assert resp.status == 200
    data = yield from resp.json()
    data.pop('flow_id')
    assert data == {
        'description_placeholders': None,
        'handler': 'test',
        'reason': 'bla',
        'type': 'abort'
    }


@asyncio.coroutine
def test_create_account(hass, client):
    """Test a flow that creates an account."""
    mock_entity_platform(hass, 'config_flow.test', None)

    mock_integration(
        hass,
        MockModule('test', async_setup_entry=mock_coro_func(True)))

    class TestFlow(core_ce.ConfigFlow):
        VERSION = 1

        @asyncio.coroutine
        def async_step_user(self, user_input=None):
            return self.async_create_entry(
                title='Test Entry',
                data={'secret': 'account_token'}
            )

    with patch.dict(HANDLERS, {'test': TestFlow}):
        resp = yield from client.post('/api/config/config_entries/flow',
                                      json={'handler': 'test'})

    assert resp.status == 200

    entries = hass.config_entries.async_entries('test')
    assert len(entries) == 1

    data = yield from resp.json()
    data.pop('flow_id')
    assert data == {
        'handler': 'test',
        'title': 'Test Entry',
        'type': 'create_entry',
        'version': 1,
        'result': entries[0].entry_id,
        'description': None,
        'description_placeholders': None,
    }


@asyncio.coroutine
def test_two_step_flow(hass, client):
    """Test we can finish a two step flow."""
    mock_integration(
        hass,
        MockModule('test', async_setup_entry=mock_coro_func(True)))
    mock_entity_platform(hass, 'config_flow.test', None)

    class TestFlow(core_ce.ConfigFlow):
        VERSION = 1

        @asyncio.coroutine
        def async_step_user(self, user_input=None):
            return self.async_show_form(
                step_id='account',
                data_schema=vol.Schema({
                    'user_title': str
                }))

        @asyncio.coroutine
        def async_step_account(self, user_input=None):
            return self.async_create_entry(
                title=user_input['user_title'],
                data={'secret': 'account_token'}
            )

    with patch.dict(HANDLERS, {'test': TestFlow}):
        resp = yield from client.post('/api/config/config_entries/flow',
                                      json={'handler': 'test'})
        assert resp.status == 200
        data = yield from resp.json()
        flow_id = data.pop('flow_id')
        assert data == {
            'type': 'form',
            'handler': 'test',
            'step_id': 'account',
            'data_schema': [
                {
                    'name': 'user_title',
                    'type': 'string'
                }
            ],
            'description_placeholders': None,
            'errors': None
        }

    with patch.dict(HANDLERS, {'test': TestFlow}):
        resp = yield from client.post(
            '/api/config/config_entries/flow/{}'.format(flow_id),
            json={'user_title': 'user-title'})
        assert resp.status == 200

        entries = hass.config_entries.async_entries('test')
        assert len(entries) == 1

        data = yield from resp.json()
        data.pop('flow_id')
        assert data == {
            'handler': 'test',
            'type': 'create_entry',
            'title': 'user-title',
            'version': 1,
            'result': entries[0].entry_id,
            'description': None,
            'description_placeholders': None,
        }


async def test_continue_flow_unauth(hass, client, hass_admin_user):
    """Test we can't finish a two step flow."""
    mock_integration(
        hass,
        MockModule('test', async_setup_entry=mock_coro_func(True)))
    mock_entity_platform(hass, 'config_flow.test', None)

    class TestFlow(core_ce.ConfigFlow):
        VERSION = 1

        @asyncio.coroutine
        def async_step_user(self, user_input=None):
            return self.async_show_form(
                step_id='account',
                data_schema=vol.Schema({
                    'user_title': str
                }))

        @asyncio.coroutine
        def async_step_account(self, user_input=None):
            return self.async_create_entry(
                title=user_input['user_title'],
                data={'secret': 'account_token'},
            )

    with patch.dict(HANDLERS, {'test': TestFlow}):
        resp = await client.post('/api/config/config_entries/flow',
                                 json={'handler': 'test'})
        assert resp.status == 200
        data = await resp.json()
        flow_id = data.pop('flow_id')
        assert data == {
            'type': 'form',
            'handler': 'test',
            'step_id': 'account',
            'data_schema': [
                {
                    'name': 'user_title',
                    'type': 'string'
                }
            ],
            'description_placeholders': None,
            'errors': None
        }

    hass_admin_user.groups = []

    resp = await client.post(
        '/api/config/config_entries/flow/{}'.format(flow_id),
        json={'user_title': 'user-title'})
    assert resp.status == 401


@asyncio.coroutine
def test_get_progress_index(hass, client):
    """Test querying for the flows that are in progress."""
    mock_entity_platform(hass, 'config_flow.test', None)

    class TestFlow(core_ce.ConfigFlow):
        VERSION = 5

        @asyncio.coroutine
        def async_step_hassio(self, info):
            return (yield from self.async_step_account())

        @asyncio.coroutine
        def async_step_account(self, user_input=None):
            return self.async_show_form(
                step_id='account',
            )

    with patch.dict(HANDLERS, {'test': TestFlow}):
        form = yield from hass.config_entries.flow.async_init(
            'test', context={'source': 'hassio'})

    resp = yield from client.get('/api/config/config_entries/flow')
    assert resp.status == 200
    data = yield from resp.json()
    assert data == [
        {
            'flow_id': form['flow_id'],
            'handler': 'test',
            'context': {'source': 'hassio'}
        }
    ]


async def test_get_progress_index_unauth(hass, client, hass_admin_user):
    """Test we can't get flows that are in progress."""
    hass_admin_user.groups = []
    resp = await client.get('/api/config/config_entries/flow')
    assert resp.status == 401


@asyncio.coroutine
def test_get_progress_flow(hass, client):
    """Test we can query the API for same result as we get from init a flow."""
    mock_entity_platform(hass, 'config_flow.test', None)

    class TestFlow(core_ce.ConfigFlow):
        @asyncio.coroutine
        def async_step_user(self, user_input=None):
            schema = OrderedDict()
            schema[vol.Required('username')] = str
            schema[vol.Required('password')] = str

            return self.async_show_form(
                step_id='user',
                data_schema=schema,
                errors={
                    'username': 'Should be unique.'
                }
            )

    with patch.dict(HANDLERS, {'test': TestFlow}):
        resp = yield from client.post('/api/config/config_entries/flow',
                                      json={'handler': 'test'})

    assert resp.status == 200
    data = yield from resp.json()

    resp2 = yield from client.get(
        '/api/config/config_entries/flow/{}'.format(data['flow_id']))

    assert resp2.status == 200
    data2 = yield from resp2.json()

    assert data == data2


async def test_get_progress_flow_unauth(hass, client, hass_admin_user):
    """Test we can can't query the API for result of flow."""
    mock_entity_platform(hass, 'config_flow.test', None)

    class TestFlow(core_ce.ConfigFlow):
        async def async_step_user(self, user_input=None):
            schema = OrderedDict()
            schema[vol.Required('username')] = str
            schema[vol.Required('password')] = str

            return self.async_show_form(
                step_id='user',
                data_schema=schema,
                errors={
                    'username': 'Should be unique.'
                }
            )

    with patch.dict(HANDLERS, {'test': TestFlow}):
        resp = await client.post('/api/config/config_entries/flow',
                                 json={'handler': 'test'})

    assert resp.status == 200
    data = await resp.json()

    hass_admin_user.groups = []

    resp2 = await client.get(
        '/api/config/config_entries/flow/{}'.format(data['flow_id']))

    assert resp2.status == 401


async def test_options_flow(hass, client):
    """Test we can change options."""
    class TestFlow(core_ce.ConfigFlow):
        @staticmethod
        @callback
        def async_get_options_flow(config, options):
            class OptionsFlowHandler(data_entry_flow.FlowHandler):
                def __init__(self, config, options):
                    self.config = config
                    self.options = options

                async def async_step_init(self, user_input=None):
                    schema = OrderedDict()
                    schema[vol.Required('enabled')] = bool
                    return self.async_show_form(
                        step_id='user',
                        data_schema=schema,
                        description_placeholders={
                            'enabled': 'Set to true to be true',
                        }
                    )
            return OptionsFlowHandler(config, options)

    MockConfigEntry(
        domain='test',
        entry_id='test1',
        source='bla',
        connection_class=core_ce.CONN_CLASS_LOCAL_POLL,
    ).add_to_hass(hass)
    entry = hass.config_entries._entries[0]

    with patch.dict(HANDLERS, {'test': TestFlow}):
        url = '/api/config/config_entries/entry/option/flow'
        resp = await client.post(url, json={'handler': entry.entry_id})

    assert resp.status == 200
    data = await resp.json()

    data.pop('flow_id')
    assert data == {
        'type': 'form',
        'handler': 'test1',
        'step_id': 'user',
        'data_schema': [
            {
                'name': 'enabled',
                'required': True,
                'type': 'boolean'
            },
        ],
        'description_placeholders': {
            'enabled': 'Set to true to be true',
        },
        'errors': None
    }


async def test_two_step_options_flow(hass, client):
    """Test we can finish a two step options flow."""
    mock_integration(
        hass,
        MockModule('test', async_setup_entry=mock_coro_func(True)))

    class TestFlow(core_ce.ConfigFlow):
        @staticmethod
        @callback
        def async_get_options_flow(config, options):
            class OptionsFlowHandler(data_entry_flow.FlowHandler):
                def __init__(self, config, options):
                    self.config = config
                    self.options = options

                async def async_step_init(self, user_input=None):
                    return self.async_show_form(
                        step_id='finish',
                        data_schema=vol.Schema({
                            'enabled': bool
                        })
                    )

                async def async_step_finish(self, user_input=None):
                    return self.async_create_entry(
                        title='Enable disable',
                        data=user_input
                    )
            return OptionsFlowHandler(config, options)

    MockConfigEntry(
        domain='test',
        entry_id='test1',
        source='bla',
        connection_class=core_ce.CONN_CLASS_LOCAL_POLL,
    ).add_to_hass(hass)
    entry = hass.config_entries._entries[0]

    with patch.dict(HANDLERS, {'test': TestFlow}):
        url = '/api/config/config_entries/entry/option/flow'
        resp = await client.post(url, json={'handler': entry.entry_id})

        assert resp.status == 200
        data = await resp.json()
        flow_id = data.pop('flow_id')
        assert data == {
            'type': 'form',
            'handler': 'test1',
            'step_id': 'finish',
            'data_schema': [
                {
                    'name': 'enabled',
                    'type': 'boolean'
                }
            ],
            'description_placeholders': None,
            'errors': None
        }

    with patch.dict(HANDLERS, {'test': TestFlow}):
        resp = await client.post(
            '/api/config/config_entries/options/flow/{}'.format(flow_id),
            json={'enabled': True})
        assert resp.status == 200
        data = await resp.json()
        data.pop('flow_id')
        assert data == {
            'handler': 'test1',
            'type': 'create_entry',
            'title': 'Enable disable',
            'version': 1,
            'description': None,
            'description_placeholders': None,
        }
