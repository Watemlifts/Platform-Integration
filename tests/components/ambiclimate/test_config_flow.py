"""Tests for the Ambiclimate config flow."""
import ambiclimate
from unittest.mock import Mock, patch

from homeassistant.components.ambiclimate import config_flow
from homeassistant.setup import async_setup_component
from homeassistant.util import aiohttp
from homeassistant import data_entry_flow
from tests.common import mock_coro


async def init_config_flow(hass):
    """Init a configuration flow."""
    await async_setup_component(hass, 'http', {
        'http': {
            'base_url': 'https://hass.com'
        }
    })

    config_flow.register_flow_implementation(hass, 'id', 'secret')
    flow = config_flow.AmbiclimateFlowHandler()

    flow.hass = hass
    return flow


async def test_abort_if_no_implementation_registered(hass):
    """Test we abort if no implementation is registered."""
    flow = config_flow.AmbiclimateFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user()
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'no_config'


async def test_abort_if_already_setup(hass):
    """Test we abort if Ambiclimate is already setup."""
    flow = await init_config_flow(hass)

    with patch.object(hass.config_entries, 'async_entries', return_value=[{}]):
        result = await flow.async_step_user()
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'already_setup'

    with patch.object(hass.config_entries, 'async_entries', return_value=[{}]):
        result = await flow.async_step_code()
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'already_setup'


async def test_full_flow_implementation(hass):
    """Test registering an implementation and finishing flow works."""
    config_flow.register_flow_implementation(hass, None, None)
    flow = await init_config_flow(hass)

    result = await flow.async_step_user()
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'auth'
    assert result['description_placeholders']['cb_url']\
        == 'https://hass.com/api/ambiclimate'

    url = result['description_placeholders']['authorization_url']
    assert 'https://api.ambiclimate.com/oauth2/authorize' in url
    assert 'client_id=id' in url
    assert 'response_type=code' in url
    assert 'redirect_uri=https%3A%2F%2Fhass.com%2Fapi%2Fambiclimate' in url

    with patch('ambiclimate.AmbiclimateOAuth.get_access_token',
               return_value=mock_coro('test')):
        result = await flow.async_step_code('123ABC')
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result['title'] == 'Ambiclimate'
    assert result['data']['callback_url'] == 'https://hass.com/api/ambiclimate'
    assert result['data']['client_secret'] == 'secret'
    assert result['data']['client_id'] == 'id'

    with patch('ambiclimate.AmbiclimateOAuth.get_access_token',
               return_value=mock_coro(None)):
        result = await flow.async_step_code('123ABC')
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT

    with patch('ambiclimate.AmbiclimateOAuth.get_access_token',
               side_effect=ambiclimate.AmbiclimateOauthError()):
        result = await flow.async_step_code('123ABC')
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT


async def test_abort_invalid_code(hass):
    """Test if no code is given to step_code."""
    config_flow.register_flow_implementation(hass, None, None)
    flow = await init_config_flow(hass)

    with patch('ambiclimate.AmbiclimateOAuth.get_access_token',
               return_value=mock_coro(None)):
        result = await flow.async_step_code('invalid')
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'access_token'


async def test_already_setup(hass):
    """Test when already setup."""
    config_flow.register_flow_implementation(hass, None, None)
    flow = await init_config_flow(hass)

    with patch.object(hass.config_entries, 'async_entries', return_value=True):
        result = await flow.async_step_user()

    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'already_setup'


async def test_view(hass):
    """Test view."""
    hass.config_entries.flow.async_init = Mock()

    request = aiohttp.MockRequest(b'', query_string='code=test_code')
    request.app = {'hass': hass}
    view = config_flow.AmbiclimateAuthCallbackView()
    assert await view.get(request) == 'OK!'

    request = aiohttp.MockRequest(b'', query_string='')
    request.app = {'hass': hass}
    view = config_flow.AmbiclimateAuthCallbackView()
    assert await view.get(request) == 'No code'
