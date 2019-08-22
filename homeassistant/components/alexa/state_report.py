"""Alexa state report code."""
import asyncio
import json
import logging

import aiohttp
import async_timeout

from homeassistant.const import MATCH_ALL

from .const import API_CHANGE, Cause
from .entities import ENTITY_ADAPTERS
from .messages import AlexaResponse

_LOGGER = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 10


async def async_enable_proactive_mode(hass, smart_home_config):
    """Enable the proactive mode.

    Proactive mode makes this component report state changes to Alexa.
    """
    # Validate we can get access token.
    await smart_home_config.async_get_access_token()

    async def async_entity_state_listener(changed_entity, old_state,
                                          new_state):
        if not new_state:
            return

        if new_state.domain not in ENTITY_ADAPTERS:
            return

        if not smart_home_config.should_expose(changed_entity):
            _LOGGER.debug("Not exposing %s because filtered by config",
                          changed_entity)
            return

        alexa_changed_entity = \
            ENTITY_ADAPTERS[new_state.domain](hass, smart_home_config,
                                              new_state)

        for interface in alexa_changed_entity.interfaces():
            if interface.properties_proactively_reported():
                await async_send_changereport_message(hass, smart_home_config,
                                                      alexa_changed_entity)
                return

    return hass.helpers.event.async_track_state_change(
        MATCH_ALL, async_entity_state_listener
    )


async def async_send_changereport_message(hass, config, alexa_entity):
    """Send a ChangeReport message for an Alexa entity.

    https://developer.amazon.com/docs/smarthome/state-reporting-for-a-smart-home-skill.html#report-state-with-changereport-events
    """
    token = await config.async_get_access_token()

    headers = {
        "Authorization": "Bearer {}".format(token)
    }

    endpoint = alexa_entity.alexa_id()

    # this sends all the properties of the Alexa Entity, whether they have
    # changed or not. this should be improved, and properties that have not
    # changed should be moved to the 'context' object
    properties = list(alexa_entity.serialize_properties())

    payload = {
        API_CHANGE: {
            'cause': {'type': Cause.APP_INTERACTION},
            'properties': properties
        }
    }

    message = AlexaResponse(name='ChangeReport', namespace='Alexa',
                            payload=payload)
    message.set_endpoint_full(token, endpoint)

    message_serialized = message.serialize()
    session = hass.helpers.aiohttp_client.async_get_clientsession()

    try:
        with async_timeout.timeout(DEFAULT_TIMEOUT):
            response = await session.post(config.endpoint,
                                          headers=headers,
                                          json=message_serialized,
                                          allow_redirects=True)

    except (asyncio.TimeoutError, aiohttp.ClientError):
        _LOGGER.error("Timeout sending report to Alexa.")
        return None

    response_text = await response.text()

    _LOGGER.debug("Sent: %s", json.dumps(message_serialized))
    _LOGGER.debug("Received (%s): %s", response.status, response_text)

    if response.status != 202:
        response_json = json.loads(response_text)
        _LOGGER.error("Error when sending ChangeReport to Alexa: %s: %s",
                      response_json["payload"]["code"],
                      response_json["payload"]["description"])


async def async_send_add_or_update_message(hass, config, entity_ids):
    """Send an AddOrUpdateReport message for entities.

    https://developer.amazon.com/docs/device-apis/alexa-discovery.html#add-or-update-report
    """
    token = await config.async_get_access_token()

    headers = {
        "Authorization": "Bearer {}".format(token)
    }

    endpoints = []

    for entity_id in entity_ids:
        domain = entity_id.split('.', 1)[0]
        alexa_entity = ENTITY_ADAPTERS[domain](
            hass, config, hass.states.get(entity_id)
        )
        endpoints.append(alexa_entity.serialize_discovery())

    payload = {
        'endpoints': endpoints,
        'scope': {
            'type': 'BearerToken',
            'token': token,
        }
    }

    message = AlexaResponse(
        name='AddOrUpdateReport', namespace='Alexa.Discovery', payload=payload)

    message_serialized = message.serialize()
    session = hass.helpers.aiohttp_client.async_get_clientsession()

    return await session.post(config.endpoint, headers=headers,
                              json=message_serialized, allow_redirects=True)


async def async_send_delete_message(hass, config, entity_ids):
    """Send an DeleteReport message for entities.

    https://developer.amazon.com/docs/device-apis/alexa-discovery.html#deletereport-event
    """
    token = await config.async_get_access_token()

    headers = {
        "Authorization": "Bearer {}".format(token)
    }

    endpoints = []

    for entity_id in entity_ids:
        domain = entity_id.split('.', 1)[0]
        alexa_entity = ENTITY_ADAPTERS[domain](
            hass, config, hass.states.get(entity_id)
        )
        endpoints.append({
            'endpointId': alexa_entity.alexa_id()
        })

    payload = {
        'endpoints': endpoints,
        'scope': {
            'type': 'BearerToken',
            'token': token,
        }
    }

    message = AlexaResponse(name='DeleteReport', namespace='Alexa.Discovery',
                            payload=payload)

    message_serialized = message.serialize()
    session = hass.helpers.aiohttp_client.async_get_clientsession()

    return await session.post(config.endpoint, headers=headers,
                              json=message_serialized, allow_redirects=True)
