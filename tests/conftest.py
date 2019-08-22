"""Set up some common test helper things."""
import asyncio
import functools
import logging
import os
from unittest.mock import patch

import pytest
import requests_mock as _requests_mock

from homeassistant import util
from homeassistant.util import location
from homeassistant.auth.const import GROUP_ID_ADMIN, GROUP_ID_READ_ONLY
from homeassistant.auth.providers import legacy_api_password, homeassistant

from tests.common import (
    async_test_home_assistant, INSTANCES, mock_coro,
    mock_storage as mock_storage, MockUser, CLIENT_ID)
from tests.test_util.aiohttp import mock_aiohttp_client

if os.environ.get('UVLOOP') == '1':
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

logging.basicConfig(level=logging.DEBUG)
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)


def check_real(func):
    """Force a function to require a keyword _test_real to be passed in."""
    @functools.wraps(func)
    def guard_func(*args, **kwargs):
        real = kwargs.pop('_test_real', None)

        if not real:
            raise Exception('Forgot to mock or pass "_test_real=True" to %s',
                            func.__name__)

        return func(*args, **kwargs)

    return guard_func


# Guard a few functions that would make network connections
location.async_detect_location_info = \
    check_real(location.async_detect_location_info)
util.get_local_ip = lambda: '127.0.0.1'


@pytest.fixture(autouse=True)
def verify_cleanup():
    """Verify that the test has cleaned up resources correctly."""
    yield

    if len(INSTANCES) >= 2:
        count = len(INSTANCES)
        for inst in INSTANCES:
            inst.stop()
        pytest.exit("Detected non stopped instances "
                    "({}), aborting test run".format(count))


@pytest.fixture
def hass_storage():
    """Fixture to mock storage."""
    with mock_storage() as stored_data:
        yield stored_data


@pytest.fixture
def hass(loop, hass_storage):
    """Fixture to provide a test instance of HASS."""
    hass = loop.run_until_complete(async_test_home_assistant(loop))

    yield hass

    loop.run_until_complete(hass.async_stop(force=True))


@pytest.fixture
def requests_mock():
    """Fixture to provide a requests mocker."""
    with _requests_mock.mock() as m:
        yield m


@pytest.fixture
def aioclient_mock():
    """Fixture to mock aioclient calls."""
    with mock_aiohttp_client() as mock_session:
        yield mock_session


@pytest.fixture
def mock_device_tracker_conf():
    """Prevent device tracker from reading/writing data."""
    devices = []

    async def mock_update_config(path, id, entity):
        devices.append(entity)

    with patch(
        'homeassistant.components.device_tracker.legacy'
        '.DeviceTracker.async_update_config',
            side_effect=mock_update_config
    ), patch(
        'homeassistant.components.device_tracker.legacy.async_load_config',
            side_effect=lambda *args: mock_coro(devices)
    ):
        yield devices


@pytest.fixture
def hass_access_token(hass, hass_admin_user):
    """Return an access token to access Home Assistant."""
    refresh_token = hass.loop.run_until_complete(
        hass.auth.async_create_refresh_token(hass_admin_user, CLIENT_ID))
    return hass.auth.async_create_access_token(refresh_token)


@pytest.fixture
def hass_owner_user(hass, local_auth):
    """Return a Home Assistant admin user."""
    return MockUser(is_owner=True).add_to_hass(hass)


@pytest.fixture
def hass_admin_user(hass, local_auth):
    """Return a Home Assistant admin user."""
    admin_group = hass.loop.run_until_complete(hass.auth.async_get_group(
        GROUP_ID_ADMIN))
    return MockUser(groups=[admin_group]).add_to_hass(hass)


@pytest.fixture
def hass_read_only_user(hass, local_auth):
    """Return a Home Assistant read only user."""
    read_only_group = hass.loop.run_until_complete(hass.auth.async_get_group(
        GROUP_ID_READ_ONLY))
    return MockUser(groups=[read_only_group]).add_to_hass(hass)


@pytest.fixture
def hass_read_only_access_token(hass, hass_read_only_user):
    """Return a Home Assistant read only user."""
    refresh_token = hass.loop.run_until_complete(
        hass.auth.async_create_refresh_token(hass_read_only_user, CLIENT_ID))
    return hass.auth.async_create_access_token(refresh_token)


@pytest.fixture
def legacy_auth(hass):
    """Load legacy API password provider."""
    prv = legacy_api_password.LegacyApiPasswordAuthProvider(
        hass, hass.auth._store, {
            'type': 'legacy_api_password',
            'api_password': 'test-password',
        }
    )
    hass.auth._providers[(prv.type, prv.id)] = prv
    return prv


@pytest.fixture
def local_auth(hass):
    """Load local auth provider."""
    prv = homeassistant.HassAuthProvider(
        hass, hass.auth._store, {
            'type': 'homeassistant'
        }
    )
    hass.auth._providers[(prv.type, prv.id)] = prv
    return prv


@pytest.fixture
def hass_client(hass, aiohttp_client, hass_access_token):
    """Return an authenticated HTTP client."""
    async def auth_client():
        """Return an authenticated client."""
        return await aiohttp_client(hass.http.app, headers={
            'Authorization': "Bearer {}".format(hass_access_token)
        })

    return auth_client
