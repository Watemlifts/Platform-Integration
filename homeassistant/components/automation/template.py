"""Offer template automation rules."""
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import CONF_VALUE_TEMPLATE, CONF_PLATFORM, CONF_FOR
from homeassistant import exceptions
from homeassistant.helpers import condition
from homeassistant.helpers.event import (
    async_track_same_state, async_track_template)
from homeassistant.helpers import config_validation as cv, template

_LOGGER = logging.getLogger(__name__)

TRIGGER_SCHEMA = IF_ACTION_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): 'template',
    vol.Required(CONF_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_FOR): vol.Any(
        vol.All(cv.time_period, cv.positive_timedelta),
        cv.template, cv.template_complex),
})


async def async_trigger(hass, config, action, automation_info):
    """Listen for state changes based on configuration."""
    value_template = config.get(CONF_VALUE_TEMPLATE)
    value_template.hass = hass
    time_delta = config.get(CONF_FOR)
    template.attach(hass, time_delta)
    unsub_track_same = None

    @callback
    def template_listener(entity_id, from_s, to_s):
        """Listen for state changes and calls action."""
        nonlocal unsub_track_same

        @callback
        def call_action():
            """Call action with right context."""
            hass.async_run_job(action({
                'trigger': {
                    'platform': 'template',
                    'entity_id': entity_id,
                    'from_state': from_s,
                    'to_state': to_s,
                    'for': time_delta if not time_delta else period
                },
            }, context=(to_s.context if to_s else None)))

        if not time_delta:
            call_action()
            return

        variables = {
            'trigger': {
                'platform': 'template',
                'entity_id': entity_id,
                'from_state': from_s,
                'to_state': to_s,
            },
        }

        try:
            if isinstance(time_delta, template.Template):
                period = vol.All(
                    cv.time_period,
                    cv.positive_timedelta)(
                        time_delta.async_render(variables))
            elif isinstance(time_delta, dict):
                time_delta_data = {}
                time_delta_data.update(
                    template.render_complex(time_delta, variables))
                period = vol.All(
                    cv.time_period,
                    cv.positive_timedelta)(
                        time_delta_data)
            else:
                period = time_delta
        except (exceptions.TemplateError, vol.Invalid) as ex:
            _LOGGER.error("Error rendering '%s' for template: %s",
                          automation_info['name'], ex)
            return

        unsub_track_same = async_track_same_state(
            hass, period, call_action,
            lambda _, _2, _3: condition.async_template(hass, value_template),
            value_template.extract_entities())

    unsub = async_track_template(
        hass, value_template, template_listener)

    @callback
    def async_remove():
        """Remove state listeners async."""
        unsub()
        if unsub_track_same:
            # pylint: disable=not-callable
            unsub_track_same()

    return async_remove
