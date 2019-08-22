"""Tests for the Config Entry Flow helper."""
from unittest.mock import patch, Mock

import pytest

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.helpers import config_entry_flow
from tests.common import (
    MockConfigEntry, MockModule, mock_coro, mock_integration,
    mock_entity_platform)


@pytest.fixture
def discovery_flow_conf(hass):
    """Register a handler."""
    handler_conf = {
        'discovered': False,
    }

    async def has_discovered_devices(hass):
        """Mock if we have discovered devices."""
        return handler_conf['discovered']

    with patch.dict(config_entries.HANDLERS):
        config_entry_flow.register_discovery_flow(
            'test', 'Test', has_discovered_devices,
            config_entries.CONN_CLASS_LOCAL_POLL)
        yield handler_conf


@pytest.fixture
def webhook_flow_conf(hass):
    """Register a handler."""
    with patch.dict(config_entries.HANDLERS):
        config_entry_flow.register_webhook_flow(
            'test_single', 'Test Single', {}, False)
        config_entry_flow.register_webhook_flow(
            'test_multiple', 'Test Multiple', {}, True)
        yield {}


async def test_single_entry_allowed(hass, discovery_flow_conf):
    """Test only a single entry is allowed."""
    flow = config_entries.HANDLERS['test']()
    flow.hass = hass

    MockConfigEntry(domain='test').add_to_hass(hass)
    result = await flow.async_step_user()

    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'single_instance_allowed'


async def test_user_no_devices_found(hass, discovery_flow_conf):
    """Test if no devices found."""
    flow = config_entries.HANDLERS['test']()
    flow.hass = hass
    flow.context = {
        'source': config_entries.SOURCE_USER
    }
    result = await flow.async_step_confirm(user_input={})

    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'no_devices_found'


async def test_user_has_confirmation(hass, discovery_flow_conf):
    """Test user requires no confirmation to setup."""
    flow = config_entries.HANDLERS['test']()
    flow.hass = hass
    discovery_flow_conf['discovered'] = True

    result = await flow.async_step_user()

    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM


@pytest.mark.parametrize('source', ['discovery', 'ssdp', 'zeroconf'])
async def test_discovery_single_instance(hass, discovery_flow_conf, source):
    """Test we not allow duplicates."""
    flow = config_entries.HANDLERS['test']()
    flow.hass = hass

    MockConfigEntry(domain='test').add_to_hass(hass)
    result = await getattr(flow, "async_step_{}".format(source))({})

    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'single_instance_allowed'


@pytest.mark.parametrize('source', ['discovery', 'ssdp', 'zeroconf'])
async def test_discovery_confirmation(hass, discovery_flow_conf, source):
    """Test we ask for confirmation via discovery."""
    flow = config_entries.HANDLERS['test']()
    flow.hass = hass

    result = await getattr(flow, "async_step_{}".format(source))({})

    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'confirm'

    result = await flow.async_step_confirm({})
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY


async def test_multiple_discoveries(hass, discovery_flow_conf):
    """Test we only create one instance for multiple discoveries."""
    mock_entity_platform(hass, 'config_flow.test', None)

    result = await hass.config_entries.flow.async_init(
        'test', context={'source': config_entries.SOURCE_DISCOVERY}, data={})
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM

    # Second discovery
    result = await hass.config_entries.flow.async_init(
        'test', context={'source': config_entries.SOURCE_DISCOVERY}, data={})
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT


async def test_only_one_in_progress(hass, discovery_flow_conf):
    """Test a user initialized one will finish and cancel discovered one."""
    mock_entity_platform(hass, 'config_flow.test', None)

    # Discovery starts flow
    result = await hass.config_entries.flow.async_init(
        'test', context={'source': config_entries.SOURCE_DISCOVERY}, data={})
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM

    # User starts flow
    result = await hass.config_entries.flow.async_init(
        'test', context={'source': config_entries.SOURCE_USER}, data={})

    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM

    # Discovery flow has not been aborted
    assert len(hass.config_entries.flow.async_progress()) == 2

    # Discovery should be aborted once user confirms
    result = await hass.config_entries.flow.async_configure(
        result['flow_id'], {})
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert len(hass.config_entries.flow.async_progress()) == 0


async def test_import_no_confirmation(hass, discovery_flow_conf):
    """Test import requires no confirmation to set up."""
    flow = config_entries.HANDLERS['test']()
    flow.hass = hass
    discovery_flow_conf['discovered'] = True

    result = await flow.async_step_import(None)
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY


async def test_import_single_instance(hass, discovery_flow_conf):
    """Test import doesn't create second instance."""
    flow = config_entries.HANDLERS['test']()
    flow.hass = hass
    discovery_flow_conf['discovered'] = True
    MockConfigEntry(domain='test').add_to_hass(hass)

    result = await flow.async_step_import(None)
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT


async def test_webhook_single_entry_allowed(hass, webhook_flow_conf):
    """Test only a single entry is allowed."""
    flow = config_entries.HANDLERS['test_single']()
    flow.hass = hass

    MockConfigEntry(domain='test_single').add_to_hass(hass)
    result = await flow.async_step_user()

    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'one_instance_allowed'


async def test_webhook_multiple_entries_allowed(hass, webhook_flow_conf):
    """Test multiple entries are allowed when specified."""
    flow = config_entries.HANDLERS['test_multiple']()
    flow.hass = hass

    MockConfigEntry(domain='test_multiple').add_to_hass(hass)
    hass.config.api = Mock(base_url='http://example.com')

    result = await flow.async_step_user()
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM


async def test_webhook_config_flow_registers_webhook(hass, webhook_flow_conf):
    """Test setting up an entry creates a webhook."""
    flow = config_entries.HANDLERS['test_single']()
    flow.hass = hass

    hass.config.api = Mock(base_url='http://example.com')
    result = await flow.async_step_user(user_input={})

    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result['data']['webhook_id'] is not None


async def test_webhook_create_cloudhook(hass, webhook_flow_conf):
    """Test only a single entry is allowed."""
    assert await setup.async_setup_component(hass, 'cloud', {})

    async_setup_entry = Mock(return_value=mock_coro(True))
    async_unload_entry = Mock(return_value=mock_coro(True))

    mock_integration(hass, MockModule(
        'test_single',
        async_setup_entry=async_setup_entry,
        async_unload_entry=async_unload_entry,
        async_remove_entry=config_entry_flow.webhook_async_remove_entry,
    ))
    mock_entity_platform(hass, 'config_flow.test_single', None)

    result = await hass.config_entries.flow.async_init(
        'test_single', context={'source': config_entries.SOURCE_USER})
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM

    coro = mock_coro({
        'cloudhook_url': 'https://example.com'
    })

    with patch('hass_nabucasa.cloudhooks.Cloudhooks.async_create',
               return_value=coro) as mock_create, \
            patch('homeassistant.components.cloud.async_active_subscription',
                  return_value=True), \
            patch('homeassistant.components.cloud.async_is_logged_in',
                  return_value=True):

        result = await hass.config_entries.flow.async_configure(
            result['flow_id'], {})

    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result['description_placeholders']['webhook_url'] == \
        'https://example.com'
    assert len(mock_create.mock_calls) == 1
    assert len(async_setup_entry.mock_calls) == 1

    with patch('hass_nabucasa.cloudhooks.Cloudhooks.async_delete',
               return_value=coro) as mock_delete:

        result = \
            await hass.config_entries.async_remove(result['result'].entry_id)

    assert len(mock_delete.mock_calls) == 1
    assert result['require_restart'] is False
