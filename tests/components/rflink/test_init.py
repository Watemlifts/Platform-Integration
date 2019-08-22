"""Common functions for RFLink component tests and generic platform tests."""

from unittest.mock import Mock

from homeassistant.bootstrap import async_setup_component
from homeassistant.components.rflink import (
    CONF_RECONNECT_INTERVAL, SERVICE_SEND_COMMAND, RflinkCommand,
    TMP_ENTITY, DATA_ENTITY_LOOKUP, EVENT_KEY_COMMAND, EVENT_KEY_SENSOR)
from homeassistant.const import (
    ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_STOP_COVER)


async def mock_rflink(hass, config, domain, monkeypatch, failures=None,
                      failcommand=False):
    """Create mock RFLink asyncio protocol, test component setup."""
    transport, protocol = (Mock(), Mock())

    async def send_command_ack(*command):
        return not failcommand
    protocol.send_command_ack = Mock(wraps=send_command_ack)

    def send_command(*command):
        return not failcommand
    protocol.send_command = Mock(wraps=send_command)

    async def create_rflink_connection(*args, **kwargs):
        """Return mocked transport and protocol."""
        # failures can be a list of booleans indicating in which sequence
        # creating a connection should success or fail
        if failures:
            fail = failures.pop()
        else:
            fail = False

        if fail:
            raise ConnectionRefusedError
        else:
            return transport, protocol

    mock_create = Mock(wraps=create_rflink_connection)
    monkeypatch.setattr(
        'rflink.protocol.create_rflink_connection',
        mock_create)

    await async_setup_component(hass, 'rflink', config)
    await async_setup_component(hass, domain, config)
    await hass.async_block_till_done()

    # hook into mock config for injecting events
    event_callback = mock_create.call_args_list[0][1]['event_callback']
    assert event_callback

    disconnect_callback = mock_create.call_args_list[
        0][1]['disconnect_callback']

    return event_callback, mock_create, protocol, disconnect_callback


async def test_version_banner(hass, monkeypatch):
    """Test sending unknown commands doesn't cause issues."""
    # use sensor domain during testing main platform
    domain = 'sensor'
    config = {
        'rflink': {'port': '/dev/ttyABC0', },
        domain: {
            'platform': 'rflink',
            'devices': {
                'test': {'name': 'test', 'sensor_type': 'temperature', },
            },
        },
    }

    # setup mocking rflink module
    event_callback, _, _, _ = await mock_rflink(
        hass, config, domain, monkeypatch)

    event_callback({
        'hardware': 'Nodo RadioFrequencyLink',
        'firmware': 'RFLink Gateway',
        'version': '1.1',
        'revision': '45',
    })


async def test_send_no_wait(hass, monkeypatch):
    """Test command sending without ack."""
    domain = 'switch'
    config = {
        'rflink': {
            'port': '/dev/ttyABC0',
            'wait_for_ack': False,
        },
        domain: {
            'platform': 'rflink',
            'devices': {
                'protocol_0_0': {
                    'name': 'test',
                    'aliases': ['test_alias_0_0'],
                },
            },
        },
    }

    # setup mocking rflink module
    _, _, protocol, _ = await mock_rflink(
        hass, config, domain, monkeypatch)

    hass.async_create_task(
        hass.services.async_call(domain, SERVICE_TURN_OFF,
                                 {ATTR_ENTITY_ID: 'switch.test'}))
    await hass.async_block_till_done()
    assert protocol.send_command.call_args_list[0][0][0] == 'protocol_0_0'
    assert protocol.send_command.call_args_list[0][0][1] == 'off'


async def test_cover_send_no_wait(hass, monkeypatch):
    """Test command sending to a cover device without ack."""
    domain = 'cover'
    config = {
        'rflink': {
            'port': '/dev/ttyABC0',
            'wait_for_ack': False,
        },
        domain: {
            'platform': 'rflink',
            'devices': {
                'RTS_0100F2_0': {
                    'name': 'test',
                    'aliases': ['test_alias_0_0'],
                },
            },
        },
    }

    # setup mocking rflink module
    _, _, protocol, _ = await mock_rflink(
        hass, config, domain, monkeypatch)

    hass.async_create_task(
        hass.services.async_call(domain, SERVICE_STOP_COVER,
                                 {ATTR_ENTITY_ID: 'cover.test'}))
    await hass.async_block_till_done()
    assert protocol.send_command.call_args_list[0][0][0] == 'RTS_0100F2_0'
    assert protocol.send_command.call_args_list[0][0][1] == 'STOP'


async def test_send_command(hass, monkeypatch):
    """Test send_command service."""
    domain = 'rflink'
    config = {
        'rflink': {
            'port': '/dev/ttyABC0',
        },
    }

    # setup mocking rflink module
    _, _, protocol, _ = await mock_rflink(
        hass, config, domain, monkeypatch)

    hass.async_create_task(
        hass.services.async_call(domain, SERVICE_SEND_COMMAND,
                                 {'device_id': 'newkaku_0000c6c2_1',
                                  'command': 'on'}))
    await hass.async_block_till_done()
    assert (protocol.send_command_ack.call_args_list[0][0][0]
            == 'newkaku_0000c6c2_1')
    assert protocol.send_command_ack.call_args_list[0][0][1] == 'on'


async def test_send_command_invalid_arguments(hass, monkeypatch):
    """Test send_command service."""
    domain = 'rflink'
    config = {
        'rflink': {
            'port': '/dev/ttyABC0',
        },
    }

    # setup mocking rflink module
    _, _, protocol, _ = await mock_rflink(
        hass, config, domain, monkeypatch)

    # one argument missing
    hass.async_create_task(
        hass.services.async_call(domain, SERVICE_SEND_COMMAND,
                                 {'command': 'on'}))
    hass.async_create_task(
        hass.services.async_call(domain, SERVICE_SEND_COMMAND,
                                 {'device_id': 'newkaku_0000c6c2_1'}))
    # no arguments
    hass.async_create_task(
        hass.services.async_call(domain, SERVICE_SEND_COMMAND, {}))

    await hass.async_block_till_done()
    assert protocol.send_command_ack.call_args_list == []

    # bad command (no_command)
    success = await hass.services.async_call(
        domain, SERVICE_SEND_COMMAND, {
            'device_id': 'newkaku_0000c6c2_1',
            'command': 'no_command'})
    assert not success, 'send command should not succeed for unknown command'


async def test_reconnecting_after_disconnect(hass, monkeypatch):
    """An unexpected disconnect should cause a reconnect."""
    domain = 'sensor'
    config = {
        'rflink': {
            'port': '/dev/ttyABC0',
            CONF_RECONNECT_INTERVAL: 0,
        },
        domain: {
            'platform': 'rflink',
        },
    }

    # setup mocking rflink module
    _, mock_create, _, disconnect_callback = await mock_rflink(
        hass, config, domain, monkeypatch)

    assert disconnect_callback, 'disconnect callback not passed to rflink'

    # rflink initiated disconnect
    disconnect_callback(None)

    await hass.async_block_till_done()

    # we expect 2 call, the initial and reconnect
    assert mock_create.call_count == 2


async def test_reconnecting_after_failure(hass, monkeypatch):
    """A failure to reconnect should be retried."""
    domain = 'sensor'
    config = {
        'rflink': {
            'port': '/dev/ttyABC0',
            CONF_RECONNECT_INTERVAL: 0,
        },
        domain: {
            'platform': 'rflink',
        },
    }

    # success first time but fail second
    failures = [False, True, False]

    # setup mocking rflink module
    _, mock_create, _, disconnect_callback = await mock_rflink(
        hass, config, domain, monkeypatch, failures=failures)

    # rflink initiated disconnect
    disconnect_callback(None)

    # wait for reconnects to have happened
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # we expect 3 calls, the initial and 2 reconnects
    assert mock_create.call_count == 3


async def test_error_when_not_connected(hass, monkeypatch):
    """Sending command should error when not connected."""
    domain = 'switch'
    config = {
        'rflink': {
            'port': '/dev/ttyABC0',
            CONF_RECONNECT_INTERVAL: 0,
        },
        domain: {
            'platform': 'rflink',
            'devices': {
                'protocol_0_0': {
                    'name': 'test',
                    'aliases': ['test_alias_0_0'],
                },
            },
        },
    }

    # success first time but fail second
    failures = [False, True, False]

    # setup mocking rflink module
    _, _, _, disconnect_callback = await mock_rflink(
        hass, config, domain, monkeypatch, failures=failures)

    # rflink initiated disconnect
    disconnect_callback(None)

    success = await hass.services.async_call(
        domain, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: 'switch.test'})
    assert not success, 'changing state should not succeed when disconnected'


async def test_async_send_command_error(hass, monkeypatch):
    """Sending command should error when protocol fails."""
    domain = 'rflink'
    config = {
        'rflink': {
            'port': '/dev/ttyABC0',
        },
    }

    # setup mocking rflink module
    _, _, protocol, _ = await mock_rflink(
        hass, config, domain, monkeypatch, failcommand=True)

    success = await hass.services.async_call(
        domain, SERVICE_SEND_COMMAND, {
            'device_id': 'newkaku_0000c6c2_1',
            'command': SERVICE_TURN_OFF})
    await hass.async_block_till_done()
    assert not success, 'send command should not succeed if failcommand=True'
    assert (protocol.send_command_ack.call_args_list[0][0][0]
            == 'newkaku_0000c6c2_1')
    assert (protocol.send_command_ack.call_args_list[0][0][1]
            == SERVICE_TURN_OFF)


async def test_race_condition(hass, monkeypatch):
    """Test race condition for unknown components."""
    domain = 'light'
    config = {
        'rflink': {
            'port': '/dev/ttyABC0',
        },
        domain: {
            'platform': 'rflink',
        },
    }
    tmp_entity = TMP_ENTITY.format('test3')

    # setup mocking rflink module
    event_callback, _, _, _ = await mock_rflink(
        hass, config, domain, monkeypatch)

    # test event for new unconfigured sensor
    event_callback({
        'id': 'test3',
        'command': 'off',
    })
    event_callback({
        'id': 'test3',
        'command': 'on',
    })

    # tmp_entity added to EVENT_KEY_COMMAND
    assert tmp_entity in hass.data[DATA_ENTITY_LOOKUP][
        EVENT_KEY_COMMAND]['test3']
    # tmp_entity must no be added to EVENT_KEY_SENSOR
    assert tmp_entity not in hass.data[DATA_ENTITY_LOOKUP][
        EVENT_KEY_SENSOR]['test3']

    await hass.async_block_till_done()

    # test  state of new sensor
    new_sensor = hass.states.get(domain+'.test3')
    assert new_sensor
    assert new_sensor.state == 'off'

    event_callback({
        'id': 'test3',
        'command': 'on',
    })
    await hass.async_block_till_done()
    # tmp_entity must be deleted from EVENT_KEY_COMMAND
    assert tmp_entity not in hass.data[DATA_ENTITY_LOOKUP][
        EVENT_KEY_COMMAND]['test3']

    # test  state of new sensor
    new_sensor = hass.states.get(domain+'.test3')
    assert new_sensor
    assert new_sensor.state == 'on'


async def test_not_connected(hass, monkeypatch):
    """Test Error when sending commands to a disconnected device."""
    import pytest
    from homeassistant.core import HomeAssistantError

    test_device = RflinkCommand('DUMMY_DEVICE')
    RflinkCommand.set_rflink_protocol(None)
    with pytest.raises(HomeAssistantError):
        await test_device._async_handle_command('turn_on')
