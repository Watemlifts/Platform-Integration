"""Tests for Logi Circle config flow."""
import asyncio
from unittest.mock import Mock, patch

import pytest

from homeassistant import data_entry_flow
from homeassistant.components.logi_circle import config_flow
from homeassistant.components.logi_circle.config_flow import (
    DOMAIN, LogiCircleAuthCallbackView)
from homeassistant.setup import async_setup_component

from tests.common import MockDependency, mock_coro


class AuthorizationFailed(Exception):
    """Dummy Exception."""


class MockRequest():
    """Mock request passed to HomeAssistantView."""

    def __init__(self, hass, query):
        """Init request object."""
        self.app = {"hass": hass}
        self.query = query


def init_config_flow(hass):
    """Init a configuration flow."""
    config_flow.register_flow_implementation(hass,
                                             DOMAIN,
                                             client_id='id',
                                             client_secret='secret',
                                             api_key='123',
                                             redirect_uri='http://example.com',
                                             sensors=None)
    flow = config_flow.LogiCircleFlowHandler()
    flow._get_authorization_url = Mock(  # pylint: disable=W0212
        return_value='http://example.com')
    flow.hass = hass
    return flow


@pytest.fixture
def mock_logi_circle():
    """Mock logi_circle."""
    with MockDependency('logi_circle', 'exception') as mock_logi_circle_:
        mock_logi_circle_.exception.AuthorizationFailed = AuthorizationFailed
        mock_logi_circle_.LogiCircle().authorize = Mock(
            return_value=mock_coro(return_value=True))
        mock_logi_circle_.LogiCircle().close = Mock(
            return_value=mock_coro(return_value=True))
        mock_logi_circle_.LogiCircle().account = mock_coro(
            return_value={'accountId': 'testId'})
        mock_logi_circle_.LogiCircle().authorize_url = 'http://authorize.url'
        yield mock_logi_circle_


async def test_step_import(hass, mock_logi_circle):  # pylint: disable=W0621
    """Test that we trigger import when configuring with client."""
    flow = init_config_flow(hass)

    result = await flow.async_step_import()
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'auth'


async def test_full_flow_implementation(hass, mock_logi_circle):  # noqa pylint: disable=W0621
    """Test registering an implementation and finishing flow works."""
    config_flow.register_flow_implementation(
        hass,
        'test-other',
        client_id=None,
        client_secret=None,
        api_key=None,
        redirect_uri=None,
        sensors=None)
    flow = init_config_flow(hass)

    result = await flow.async_step_user()
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'user'

    result = await flow.async_step_user({'flow_impl': 'test-other'})
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'auth'
    assert result['description_placeholders'] == {
        'authorization_url': 'http://example.com',
    }

    result = await flow.async_step_code('123ABC')
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result['title'] == 'Logi Circle ({})'.format('testId')


async def test_we_reprompt_user_to_follow_link(hass):
    """Test we prompt user to follow link if previously prompted."""
    flow = init_config_flow(hass)

    result = await flow.async_step_auth('dummy')
    assert result['errors']['base'] == 'follow_link'


async def test_abort_if_no_implementation_registered(hass):
    """Test we abort if no implementation is registered."""
    flow = config_flow.LogiCircleFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user()
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'no_flows'


async def test_abort_if_already_setup(hass):
    """Test we abort if Logi Circle is already setup."""
    flow = init_config_flow(hass)

    with patch.object(hass.config_entries, 'async_entries', return_value=[{}]):
        result = await flow.async_step_user()
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'already_setup'

    with patch.object(hass.config_entries, 'async_entries', return_value=[{}]):
        result = await flow.async_step_import()
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'already_setup'

    with patch.object(hass.config_entries, 'async_entries', return_value=[{}]):
        result = await flow.async_step_code()
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'already_setup'

    with patch.object(hass.config_entries, 'async_entries', return_value=[{}]):
        result = await flow.async_step_auth()
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'external_setup'


@pytest.mark.parametrize('side_effect,error',
                         [(asyncio.TimeoutError, 'auth_timeout'),
                          (AuthorizationFailed, 'auth_error')])
async def test_abort_if_authorize_fails(hass, mock_logi_circle, side_effect, error):  # noqa pylint: disable=W0621
    """Test we abort if authorizing fails."""
    flow = init_config_flow(hass)
    mock_logi_circle.LogiCircle().authorize.side_effect = side_effect

    result = await flow.async_step_code('123ABC')
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'external_error'

    result = await flow.async_step_auth()
    assert result['errors']['base'] == error


async def test_not_pick_implementation_if_only_one(hass):
    """Test we bypass picking implementation if we have one flow_imp."""
    flow = init_config_flow(hass)

    result = await flow.async_step_user()
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'auth'


async def test_gen_auth_url(hass, mock_logi_circle):  # pylint: disable=W0621
    """Test generating authorize URL from Logi Circle API."""
    config_flow.register_flow_implementation(hass,
                                             'test-auth-url',
                                             client_id='id',
                                             client_secret='secret',
                                             api_key='123',
                                             redirect_uri='http://example.com',
                                             sensors=None)
    flow = config_flow.LogiCircleFlowHandler()
    flow.hass = hass
    flow.flow_impl = 'test-auth-url'
    await async_setup_component(hass, 'http', {})

    result = flow._get_authorization_url()  # pylint: disable=W0212
    assert result == 'http://authorize.url'


async def test_callback_view_rejects_missing_code(hass):
    """Test the auth callback view rejects requests with no code."""
    view = LogiCircleAuthCallbackView()
    resp = await view.get(MockRequest(hass, {}))

    assert resp.status == 400


async def test_callback_view_accepts_code(hass, mock_logi_circle):  # noqa pylint: disable=W0621
    """Test the auth callback view handles requests with auth code."""
    init_config_flow(hass)
    view = LogiCircleAuthCallbackView()

    resp = await view.get(MockRequest(hass, {"code": "456"}))
    assert resp.status == 200

    await hass.async_block_till_done()
    mock_logi_circle.LogiCircle.return_value.authorize.assert_called_with(
        '456')
