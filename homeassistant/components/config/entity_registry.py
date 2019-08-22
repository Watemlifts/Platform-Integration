"""HTTP views to interact with the entity registry."""
import voluptuous as vol

from homeassistant.core import callback
from homeassistant.helpers.entity_registry import async_get_registry
from homeassistant.components import websocket_api
from homeassistant.components.websocket_api.const import ERR_NOT_FOUND
from homeassistant.components.websocket_api.decorators import (
    async_response, require_admin)
from homeassistant.helpers import config_validation as cv

WS_TYPE_LIST = 'config/entity_registry/list'
SCHEMA_WS_LIST = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_LIST,
})

WS_TYPE_GET = 'config/entity_registry/get'
SCHEMA_WS_GET = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_GET,
    vol.Required('entity_id'): cv.entity_id
})

WS_TYPE_UPDATE = 'config/entity_registry/update'
SCHEMA_WS_UPDATE = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_UPDATE,
    vol.Required('entity_id'): cv.entity_id,
    # If passed in, we update value. Passing None will remove old value.
    vol.Optional('name'): vol.Any(str, None),
    vol.Optional('new_entity_id'): str,
})

WS_TYPE_REMOVE = 'config/entity_registry/remove'
SCHEMA_WS_REMOVE = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_REMOVE,
    vol.Required('entity_id'): cv.entity_id
})


async def async_setup(hass):
    """Enable the Entity Registry views."""
    hass.components.websocket_api.async_register_command(
        WS_TYPE_LIST, websocket_list_entities,
        SCHEMA_WS_LIST
    )
    hass.components.websocket_api.async_register_command(
        WS_TYPE_GET, websocket_get_entity,
        SCHEMA_WS_GET
    )
    hass.components.websocket_api.async_register_command(
        WS_TYPE_UPDATE, websocket_update_entity,
        SCHEMA_WS_UPDATE
    )
    hass.components.websocket_api.async_register_command(
        WS_TYPE_REMOVE, websocket_remove_entity,
        SCHEMA_WS_REMOVE
    )
    return True


@async_response
async def websocket_list_entities(hass, connection, msg):
    """Handle list registry entries command.

    Async friendly.
    """
    registry = await async_get_registry(hass)
    connection.send_message(websocket_api.result_message(
        msg['id'], [_entry_dict(entry) for entry in registry.entities.values()]
    ))


@async_response
async def websocket_get_entity(hass, connection, msg):
    """Handle get entity registry entry command.

    Async friendly.
    """
    registry = await async_get_registry(hass)
    entry = registry.entities.get(msg['entity_id'])

    if entry is None:
        connection.send_message(websocket_api.error_message(
            msg['id'], ERR_NOT_FOUND, 'Entity not found'))
        return

    connection.send_message(websocket_api.result_message(
        msg['id'], _entry_dict(entry)
    ))


@require_admin
@async_response
async def websocket_update_entity(hass, connection, msg):
    """Handle update entity websocket command.

    Async friendly.
    """
    registry = await async_get_registry(hass)

    if msg['entity_id'] not in registry.entities:
        connection.send_message(websocket_api.error_message(
            msg['id'], ERR_NOT_FOUND, 'Entity not found'))
        return

    changes = {}

    if 'name' in msg:
        changes['name'] = msg['name']

    if 'new_entity_id' in msg and msg['new_entity_id'] != msg['entity_id']:
        changes['new_entity_id'] = msg['new_entity_id']
        if hass.states.get(msg['new_entity_id']) is not None:
            connection.send_message(websocket_api.error_message(
                msg['id'], 'invalid_info', 'Entity is already registered'))
            return

    try:
        if changes:
            entry = registry.async_update_entity(
                msg['entity_id'], **changes)
    except ValueError as err:
        connection.send_message(websocket_api.error_message(
            msg['id'], 'invalid_info', str(err)
        ))
    else:
        connection.send_message(websocket_api.result_message(
            msg['id'], _entry_dict(entry)
        ))


@require_admin
@async_response
async def websocket_remove_entity(hass, connection, msg):
    """Handle remove entity websocket command.

    Async friendly.
    """
    registry = await async_get_registry(hass)

    if msg['entity_id'] not in registry.entities:
        connection.send_message(websocket_api.error_message(
            msg['id'], ERR_NOT_FOUND, 'Entity not found'))
        return

    registry.async_remove(msg['entity_id'])
    connection.send_message(websocket_api.result_message(msg['id']))


@callback
def _entry_dict(entry):
    """Convert entry to API format."""
    return {
        'config_entry_id': entry.config_entry_id,
        'device_id': entry.device_id,
        'disabled_by': entry.disabled_by,
        'entity_id': entry.entity_id,
        'name': entry.name,
        'platform': entry.platform,
    }
