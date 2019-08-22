"""Support for Template lights."""
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ENTITY_ID_FORMAT, Light, SUPPORT_BRIGHTNESS)
from homeassistant.const import (
    CONF_VALUE_TEMPLATE, CONF_ICON_TEMPLATE, CONF_ENTITY_PICTURE_TEMPLATE,
    CONF_ENTITY_ID, CONF_FRIENDLY_NAME, STATE_ON, STATE_OFF,
    EVENT_HOMEASSISTANT_START, MATCH_ALL, CONF_LIGHTS
)
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.script import Script

_LOGGER = logging.getLogger(__name__)
_VALID_STATES = [STATE_ON, STATE_OFF, 'true', 'false']

CONF_ON_ACTION = 'turn_on'
CONF_OFF_ACTION = 'turn_off'
CONF_LEVEL_ACTION = 'set_level'
CONF_LEVEL_TEMPLATE = 'level_template'

LIGHT_SCHEMA = vol.Schema({
    vol.Required(CONF_ON_ACTION): cv.SCRIPT_SCHEMA,
    vol.Required(CONF_OFF_ACTION): cv.SCRIPT_SCHEMA,
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_ICON_TEMPLATE): cv.template,
    vol.Optional(CONF_ENTITY_PICTURE_TEMPLATE): cv.template,
    vol.Optional(CONF_LEVEL_ACTION): cv.SCRIPT_SCHEMA,
    vol.Optional(CONF_LEVEL_TEMPLATE): cv.template,
    vol.Optional(CONF_FRIENDLY_NAME): cv.string,
    vol.Optional(CONF_ENTITY_ID): cv.entity_ids
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_LIGHTS): cv.schema_with_slug_keys(LIGHT_SCHEMA),
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Template Lights."""
    lights = []

    for device, device_config in config[CONF_LIGHTS].items():
        friendly_name = device_config.get(CONF_FRIENDLY_NAME, device)
        state_template = device_config.get(CONF_VALUE_TEMPLATE)
        icon_template = device_config.get(CONF_ICON_TEMPLATE)
        entity_picture_template = device_config.get(
            CONF_ENTITY_PICTURE_TEMPLATE)
        on_action = device_config[CONF_ON_ACTION]
        off_action = device_config[CONF_OFF_ACTION]
        level_action = device_config.get(CONF_LEVEL_ACTION)
        level_template = device_config.get(CONF_LEVEL_TEMPLATE)

        template_entity_ids = set()

        if state_template is not None:
            temp_ids = state_template.extract_entities()
            if str(temp_ids) != MATCH_ALL:
                template_entity_ids |= set(temp_ids)

        if level_template is not None:
            temp_ids = level_template.extract_entities()
            if str(temp_ids) != MATCH_ALL:
                template_entity_ids |= set(temp_ids)

        if icon_template is not None:
            temp_ids = icon_template.extract_entities()
            if str(temp_ids) != MATCH_ALL:
                template_entity_ids |= set(temp_ids)

        if entity_picture_template is not None:
            temp_ids = entity_picture_template.extract_entities()
            if str(temp_ids) != MATCH_ALL:
                template_entity_ids |= set(temp_ids)

        if not template_entity_ids:
            template_entity_ids = MATCH_ALL

        entity_ids = device_config.get(CONF_ENTITY_ID, template_entity_ids)

        lights.append(
            LightTemplate(
                hass, device, friendly_name, state_template,
                icon_template, entity_picture_template, on_action,
                off_action, level_action, level_template, entity_ids)
        )

    if not lights:
        _LOGGER.error("No lights added")
        return False

    async_add_entities(lights)
    return True


class LightTemplate(Light):
    """Representation of a templated Light, including dimmable."""

    def __init__(self, hass, device_id, friendly_name, state_template,
                 icon_template, entity_picture_template, on_action,
                 off_action, level_action, level_template, entity_ids):
        """Initialize the light."""
        self.hass = hass
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, device_id, hass=hass)
        self._name = friendly_name
        self._template = state_template
        self._icon_template = icon_template
        self._entity_picture_template = entity_picture_template
        self._on_script = Script(hass, on_action)
        self._off_script = Script(hass, off_action)
        self._level_script = None
        if level_action is not None:
            self._level_script = Script(hass, level_action)
        self._level_template = level_template

        self._state = False
        self._icon = None
        self._entity_picture = None
        self._brightness = None
        self._entities = entity_ids

        if self._template is not None:
            self._template.hass = self.hass
        if self._level_template is not None:
            self._level_template.hass = self.hass
        if self._icon_template is not None:
            self._icon_template.hass = self.hass
        if self._entity_picture_template is not None:
            self._entity_picture_template.hass = self.hass

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def supported_features(self):
        """Flag supported features."""
        if self._level_script is not None:
            return SUPPORT_BRIGHTNESS

        return 0

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._icon

    @property
    def entity_picture(self):
        """Return the entity picture to use in the frontend, if any."""
        return self._entity_picture

    async def async_added_to_hass(self):
        """Register callbacks."""
        @callback
        def template_light_state_listener(entity, old_state, new_state):
            """Handle target device state changes."""
            self.async_schedule_update_ha_state(True)

        @callback
        def template_light_startup(event):
            """Update template on startup."""
            if (self._template is not None or
                    self._level_template is not None):
                async_track_state_change(
                    self.hass, self._entities, template_light_state_listener)

            self.async_schedule_update_ha_state(True)

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, template_light_startup)

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""
        optimistic_set = False
        # set optimistic states
        if self._template is None:
            self._state = True
            optimistic_set = True

        if self._level_template is None and ATTR_BRIGHTNESS in kwargs:
            _LOGGER.info("Optimistically setting brightness to %s",
                         kwargs[ATTR_BRIGHTNESS])
            self._brightness = kwargs[ATTR_BRIGHTNESS]
            optimistic_set = True

        if ATTR_BRIGHTNESS in kwargs and self._level_script:
            await self._level_script.async_run(
                {"brightness": kwargs[ATTR_BRIGHTNESS]}, context=self._context)
        else:
            await self._on_script.async_run()

        if optimistic_set:
            self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        await self._off_script.async_run(context=self._context)
        if self._template is None:
            self._state = False
            self.async_schedule_update_ha_state()

    async def async_update(self):
        """Update the state from the template."""
        if self._template is not None:
            try:
                state = self._template.async_render().lower()
            except TemplateError as ex:
                _LOGGER.error(ex)
                self._state = None

            if state in _VALID_STATES:
                self._state = state in ('true', STATE_ON)
            else:
                _LOGGER.error(
                    'Received invalid light is_on state: %s. Expected: %s',
                    state, ', '.join(_VALID_STATES))
                self._state = None

        if self._level_template is not None:
            try:
                brightness = self._level_template.async_render()
            except TemplateError as ex:
                _LOGGER.error(ex)
                self._state = None

            if 0 <= int(brightness) <= 255:
                self._brightness = int(brightness)
            else:
                _LOGGER.error(
                    'Received invalid brightness : %s. Expected: 0-255',
                    brightness)
                self._brightness = None

        for property_name, template in (
                ('_icon', self._icon_template),
                ('_entity_picture', self._entity_picture_template)):
            if template is None:
                continue

            try:
                setattr(self, property_name, template.async_render())
            except TemplateError as ex:
                friendly_property_name = property_name[1:].replace('_', ' ')
                if ex.args and ex.args[0].startswith(
                        "UndefinedError: 'None' has no attribute"):
                    # Common during HA startup - so just a warning
                    _LOGGER.warning('Could not render %s template %s,'
                                    ' the state is unknown.',
                                    friendly_property_name, self._name)
                    return

                try:
                    setattr(self, property_name,
                            getattr(super(), property_name))
                except AttributeError:
                    _LOGGER.error('Could not render %s template %s: %s',
                                  friendly_property_name, self._name, ex)
