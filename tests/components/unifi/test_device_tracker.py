"""The tests for the Unifi WAP device tracker platform."""
from unittest import mock
from datetime import datetime, timedelta

import pytest
import voluptuous as vol

import homeassistant.util.dt as dt_util
from homeassistant.components.device_tracker import DOMAIN
import homeassistant.components.unifi.device_tracker as unifi
from homeassistant.const import (CONF_HOST, CONF_USERNAME, CONF_PASSWORD,
                                 CONF_PLATFORM, CONF_VERIFY_SSL,
                                 CONF_MONITORED_CONDITIONS)

from tests.common import mock_coro
from asynctest import CoroutineMock
from aiounifi.clients import Clients

DEFAULT_DETECTION_TIME = timedelta(seconds=300)


@pytest.fixture
def mock_ctrl():
    """Mock pyunifi."""
    with mock.patch('aiounifi.Controller') as mock_control:
        mock_control.return_value.login.return_value = mock_coro()
        mock_control.return_value.initialize.return_value = mock_coro()
        yield mock_control


@pytest.fixture
def mock_scanner():
    """Mock UnifyScanner."""
    with mock.patch('homeassistant.components.unifi.device_tracker'
                    '.UnifiScanner') as scanner:
        yield scanner


@mock.patch('os.access', return_value=True)
@mock.patch('os.path.isfile', mock.Mock(return_value=True))
async def test_config_valid_verify_ssl(hass, mock_scanner, mock_ctrl):
    """Test the setup with a string for ssl_verify.

    Representing the absolute path to a CA certificate bundle.
    """
    config = {
        DOMAIN: unifi.PLATFORM_SCHEMA({
            CONF_PLATFORM: unifi.DOMAIN,
            CONF_USERNAME: 'foo',
            CONF_PASSWORD: 'password',
            CONF_VERIFY_SSL: "/tmp/unifi.crt"
        })
    }
    result = await unifi.async_get_scanner(hass, config)
    assert mock_scanner.return_value == result
    assert mock_ctrl.call_count == 1

    assert mock_scanner.call_count == 1
    assert mock_scanner.call_args == mock.call(mock_ctrl.return_value,
                                               DEFAULT_DETECTION_TIME,
                                               None, None)


async def test_config_minimal(hass, mock_scanner, mock_ctrl):
    """Test the setup with minimal configuration."""
    config = {
        DOMAIN: unifi.PLATFORM_SCHEMA({
            CONF_PLATFORM: unifi.DOMAIN,
            CONF_USERNAME: 'foo',
            CONF_PASSWORD: 'password',
        })
    }

    result = await unifi.async_get_scanner(hass, config)
    assert mock_scanner.return_value == result
    assert mock_ctrl.call_count == 1

    assert mock_scanner.call_count == 1
    assert mock_scanner.call_args == mock.call(mock_ctrl.return_value,
                                               DEFAULT_DETECTION_TIME,
                                               None, None)


async def test_config_full(hass, mock_scanner, mock_ctrl):
    """Test the setup with full configuration."""
    config = {
        DOMAIN: unifi.PLATFORM_SCHEMA({
            CONF_PLATFORM: unifi.DOMAIN,
            CONF_USERNAME: 'foo',
            CONF_PASSWORD: 'password',
            CONF_HOST: 'myhost',
            CONF_VERIFY_SSL: False,
            CONF_MONITORED_CONDITIONS: ['essid', 'signal'],
            'port': 123,
            'site_id': 'abcdef01',
            'detection_time': 300,
        })
    }
    result = await unifi.async_get_scanner(hass, config)
    assert mock_scanner.return_value == result
    assert mock_ctrl.call_count == 1

    assert mock_scanner.call_count == 1
    assert mock_scanner.call_args == mock.call(
        mock_ctrl.return_value,
        DEFAULT_DETECTION_TIME,
        None,
        config[DOMAIN][CONF_MONITORED_CONDITIONS])


def test_config_error():
    """Test for configuration errors."""
    with pytest.raises(vol.Invalid):
        unifi.PLATFORM_SCHEMA({
            # no username
            CONF_PLATFORM: unifi.DOMAIN,
            CONF_HOST: 'myhost',
            'port': 123,
        })
    with pytest.raises(vol.Invalid):
        unifi.PLATFORM_SCHEMA({
            CONF_PLATFORM: unifi.DOMAIN,
            CONF_USERNAME: 'foo',
            CONF_PASSWORD: 'password',
            CONF_HOST: 'myhost',
            'port': 'foo',  # bad port!
        })
    with pytest.raises(vol.Invalid):
        unifi.PLATFORM_SCHEMA({
            CONF_PLATFORM: unifi.DOMAIN,
            CONF_USERNAME: 'foo',
            CONF_PASSWORD: 'password',
            CONF_VERIFY_SSL: "dfdsfsdfsd",  # Invalid ssl_verify (no file)
        })


async def test_config_controller_failed(hass, mock_ctrl, mock_scanner):
    """Test for controller failure."""
    config = {
        'device_tracker': {
            CONF_PLATFORM: unifi.DOMAIN,
            CONF_USERNAME: 'foo',
            CONF_PASSWORD: 'password',
        }
    }
    mock_ctrl.side_effect = unifi.CannotConnect
    result = await unifi.async_get_scanner(hass, config)
    assert result is False


async def test_scanner_update():
    """Test the scanner update."""
    ctrl = mock.MagicMock()
    fake_clients = [
        {'mac': '123', 'essid': 'barnet',
         'last_seen': dt_util.as_timestamp(dt_util.utcnow())},
        {'mac': '234', 'essid': 'barnet',
         'last_seen': dt_util.as_timestamp(dt_util.utcnow())},
    ]
    ctrl.clients = Clients([], CoroutineMock(return_value=fake_clients))
    scnr = unifi.UnifiScanner(ctrl, DEFAULT_DETECTION_TIME, None, None)
    await scnr.async_update()
    assert len(scnr._clients) == 2


def test_scanner_update_error():
    """Test the scanner update for error."""
    ctrl = mock.MagicMock()
    ctrl.get_clients.side_effect = unifi.aiounifi.AiounifiException
    unifi.UnifiScanner(ctrl, DEFAULT_DETECTION_TIME, None, None)


async def test_scan_devices():
    """Test the scanning for devices."""
    ctrl = mock.MagicMock()
    fake_clients = [
        {'mac': '123', 'essid': 'barnet',
         'last_seen': dt_util.as_timestamp(dt_util.utcnow())},
        {'mac': '234', 'essid': 'barnet',
         'last_seen': dt_util.as_timestamp(dt_util.utcnow())},
    ]
    ctrl.clients = Clients([], CoroutineMock(return_value=fake_clients))
    scnr = unifi.UnifiScanner(ctrl, DEFAULT_DETECTION_TIME, None, None)
    await scnr.async_update()
    assert set(await scnr.async_scan_devices()) == set(['123', '234'])


async def test_scan_devices_filtered():
    """Test the scanning for devices based on SSID."""
    ctrl = mock.MagicMock()
    fake_clients = [
        {'mac': '123', 'essid': 'foonet',
         'last_seen': dt_util.as_timestamp(dt_util.utcnow())},
        {'mac': '234', 'essid': 'foonet',
         'last_seen': dt_util.as_timestamp(dt_util.utcnow())},
        {'mac': '567', 'essid': 'notnet',
         'last_seen': dt_util.as_timestamp(dt_util.utcnow())},
        {'mac': '890', 'essid': 'barnet',
         'last_seen': dt_util.as_timestamp(dt_util.utcnow())},
    ]

    ssid_filter = ['foonet', 'barnet']
    ctrl.clients = Clients([], CoroutineMock(return_value=fake_clients))
    scnr = unifi.UnifiScanner(ctrl, DEFAULT_DETECTION_TIME, ssid_filter, None)
    await scnr.async_update()
    assert set(await scnr.async_scan_devices()) == set(['123', '234', '890'])


async def test_get_device_name():
    """Test the getting of device names."""
    ctrl = mock.MagicMock()
    fake_clients = [
        {'mac': '123',
         'hostname': 'foobar',
         'essid': 'barnet',
         'last_seen': dt_util.as_timestamp(dt_util.utcnow())},
        {'mac': '234',
         'name': 'Nice Name',
         'essid': 'barnet',
         'last_seen': dt_util.as_timestamp(dt_util.utcnow())},
        {'mac': '456',
         'essid': 'barnet',
         'last_seen': '1504786810'},
    ]
    ctrl.clients = Clients([], CoroutineMock(return_value=fake_clients))
    scnr = unifi.UnifiScanner(ctrl, DEFAULT_DETECTION_TIME, None, None)
    await scnr.async_update()
    assert scnr.get_device_name('123') == 'foobar'
    assert scnr.get_device_name('234') == 'Nice Name'
    assert scnr.get_device_name('456') is None
    assert scnr.get_device_name('unknown') is None


async def test_monitored_conditions():
    """Test the filtering of attributes."""
    ctrl = mock.MagicMock()
    fake_clients = [
        {'mac': '123',
         'hostname': 'foobar',
         'essid': 'barnet',
         'signal': -60,
         'last_seen': dt_util.as_timestamp(dt_util.utcnow()),
         'latest_assoc_time': 946684800.0},
        {'mac': '234',
         'name': 'Nice Name',
         'essid': 'barnet',
         'signal': -42,
         'last_seen': dt_util.as_timestamp(dt_util.utcnow())},
        {'mac': '456',
         'hostname': 'wired',
         'essid': 'barnet',
         'last_seen': dt_util.as_timestamp(dt_util.utcnow())},
    ]
    ctrl.clients = Clients([], CoroutineMock(return_value=fake_clients))
    scnr = unifi.UnifiScanner(ctrl, DEFAULT_DETECTION_TIME, None,
                              ['essid', 'signal', 'latest_assoc_time'])
    await scnr.async_update()
    assert scnr.get_extra_attributes('123') == {
        'essid': 'barnet',
        'signal': -60,
        'latest_assoc_time': datetime(2000, 1, 1, 0, 0, tzinfo=dt_util.UTC)
    }
    assert scnr.get_extra_attributes('234') == {
        'essid': 'barnet',
        'signal': -42
    }
    assert scnr.get_extra_attributes('456') == {'essid': 'barnet'}
