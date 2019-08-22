"""Support for Template vacuums."""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.vacuum import (
    ATTR_FAN_SPEED, DOMAIN, SERVICE_CLEAN_SPOT, SERVICE_LOCATE, SERVICE_PAUSE,
    SERVICE_RETURN_TO_BASE, SERVICE_SET_FAN_SPEED, SERVICE_START,
    SERVICE_STOP, SUPPORT_BATTERY, SUPPORT_CLEAN_SPOT, SUPPORT_FAN_SPEED,
    SUPPORT_LOCATE, SUPPORT_PAUSE, SUPPORT_RETURN_HOME, SUPPORT_STOP,
    SUPPORT_STATE, SUPPORT_START, StateVacuumDevice, STATE_CLEANING,
    STATE_DOCKED, STATE_PAUSED, STATE_IDLE, STATE_RETURNING, STATE_ERROR)
from homeassistant.const import (
    CONF_FRIENDLY_NAME, CONF_VALUE_TEMPLATE, CONF_ENTITY_ID,
    MATCH_ALL, EVENT_HOMEASSISTANT_START, STATE_UNKNOWN)
from homeassistant.core import callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.script import Script

_LOGGER = logging.getLogger(__name__)

CONF_VACUUMS = 'vacuums'
CONF_BATTERY_LEVEL_TEMPLATE = 'battery_level_template'
CONF_FAN_SPEED_LIST = 'fan_speeds'
CONF_FAN_SPEED_TEMPLATE = 'fan_speed_template'

ENTITY_ID_FORMAT = DOMAIN + '.{}'
_VALID_STATES = [STATE_CLEANING, STATE_DOCKED, STATE_PAUSED, STATE_IDLE,
                 STATE_RETURNING, STATE_ERROR]

VACUUM_SCHEMA = vol.Schema({
    vol.Optional(CONF_FRIENDLY_NAME): cv.string,
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_BATTERY_LEVEL_TEMPLATE): cv.template,
    vol.Optional(CONF_FAN_SPEED_TEMPLATE): cv.template,

    vol.Required(SERVICE_START): cv.SCRIPT_SCHEMA,
    vol.Optional(SERVICE_PAUSE): cv.SCRIPT_SCHEMA,
    vol.Optional(SERVICE_STOP): cv.SCRIPT_SCHEMA,
    vol.Optional(SERVICE_RETURN_TO_BASE): cv.SCRIPT_SCHEMA,
    vol.Optional(SERVICE_CLEAN_SPOT): cv.SCRIPT_SCHEMA,
    vol.Optional(SERVICE_LOCATE): cv.SCRIPT_SCHEMA,
    vol.Optional(SERVICE_SET_FAN_SPEED): cv.SCRIPT_SCHEMA,

    vol.Optional(
        CONF_FAN_SPEED_LIST,
        default=[]
    ): cv.ensure_list,

    vol.Optional(CONF_ENTITY_ID): cv.entity_ids
})

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend({
    vol.Required(CONF_VACUUMS): vol.Schema({cv.slug: VACUUM_SCHEMA}),
})


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None
):
    """Set up the Template Vacuums."""
    vacuums = []

    for device, device_config in config[CONF_VACUUMS].items():
        friendly_name = device_config.get(CONF_FRIENDLY_NAME, device)

        state_template = device_config.get(CONF_VALUE_TEMPLATE)
        battery_level_template = device_config.get(CONF_BATTERY_LEVEL_TEMPLATE)
        fan_speed_template = device_config.get(CONF_FAN_SPEED_TEMPLATE)

        start_action = device_config[SERVICE_START]
        pause_action = device_config.get(SERVICE_PAUSE)
        stop_action = device_config.get(SERVICE_STOP)
        return_to_base_action = device_config.get(SERVICE_RETURN_TO_BASE)
        clean_spot_action = device_config.get(SERVICE_CLEAN_SPOT)
        locate_action = device_config.get(SERVICE_LOCATE)
        set_fan_speed_action = device_config.get(SERVICE_SET_FAN_SPEED)

        fan_speed_list = device_config[CONF_FAN_SPEED_LIST]

        entity_ids = set()
        manual_entity_ids = device_config.get(CONF_ENTITY_ID)
        invalid_templates = []

        for tpl_name, template in (
                (CONF_VALUE_TEMPLATE, state_template),
                (CONF_BATTERY_LEVEL_TEMPLATE, battery_level_template),
                (CONF_FAN_SPEED_TEMPLATE, fan_speed_template)
        ):
            if template is None:
                continue
            template.hass = hass

            if manual_entity_ids is not None:
                continue

            template_entity_ids = template.extract_entities()
            if template_entity_ids == MATCH_ALL:
                entity_ids = MATCH_ALL
                # Cut off _template from name
                invalid_templates.append(tpl_name[:-9])
            elif entity_ids != MATCH_ALL:
                entity_ids |= set(template_entity_ids)

        if invalid_templates:
            _LOGGER.warning(
                'Template vacuum %s has no entity ids configured to track nor'
                ' were we able to extract the entities to track from the %s '
                'template(s). This entity will only be able to be updated '
                'manually.', device, ', '.join(invalid_templates))

        if manual_entity_ids is not None:
            entity_ids = manual_entity_ids
        elif entity_ids != MATCH_ALL:
            entity_ids = list(entity_ids)

        vacuums.append(
            TemplateVacuum(
                hass, device, friendly_name,
                state_template, battery_level_template, fan_speed_template,
                start_action, pause_action, stop_action, return_to_base_action,
                clean_spot_action, locate_action, set_fan_speed_action,
                fan_speed_list, entity_ids
            )
        )

    async_add_entities(vacuums)


class TemplateVacuum(StateVacuumDevice):
    """A template vacuum component."""

    def __init__(self, hass, device_id, friendly_name,
                 state_template, battery_level_template, fan_speed_template,
                 start_action, pause_action, stop_action,
                 return_to_base_action, clean_spot_action, locate_action,
                 set_fan_speed_action, fan_speed_list, entity_ids):
        """Initialize the vacuum."""
        self.hass = hass
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, device_id, hass=hass)
        self._name = friendly_name

        self._template = state_template
        self._battery_level_template = battery_level_template
        self._fan_speed_template = fan_speed_template
        self._supported_features = SUPPORT_START

        self._start_script = Script(hass, start_action)

        self._pause_script = None
        if pause_action:
            self._pause_script = Script(hass, pause_action)
            self._supported_features |= SUPPORT_PAUSE

        self._stop_script = None
        if stop_action:
            self._stop_script = Script(hass, stop_action)
            self._supported_features |= SUPPORT_STOP

        self._return_to_base_script = None
        if return_to_base_action:
            self._return_to_base_script = Script(hass, return_to_base_action)
            self._supported_features |= SUPPORT_RETURN_HOME

        self._clean_spot_script = None
        if clean_spot_action:
            self._clean_spot_script = Script(hass, clean_spot_action)
            self._supported_features |= SUPPORT_CLEAN_SPOT

        self._locate_script = None
        if locate_action:
            self._locate_script = Script(hass, locate_action)
            self._supported_features |= SUPPORT_LOCATE

        self._set_fan_speed_script = None
        if set_fan_speed_action:
            self._set_fan_speed_script = Script(hass, set_fan_speed_action)
            self._supported_features |= SUPPORT_FAN_SPEED

        self._state = None
        self._battery_level = None
        self._fan_speed = None

        if self._template:
            self._supported_features |= SUPPORT_STATE
        if self._battery_level_template:
            self._supported_features |= SUPPORT_BATTERY

        self._entities = entity_ids
        # List of valid fan speeds
        self._fan_speed_list = fan_speed_list

    @property
    def name(self):
        """Return the display name of this vacuum."""
        return self._name

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return self._supported_features

    @property
    def state(self):
        """Return the status of the vacuum cleaner."""
        return self._state

    @property
    def battery_level(self):
        """Return the battery level of the vacuum cleaner."""
        return self._battery_level

    @property
    def fan_speed(self):
        """Return the fan speed of the vacuum cleaner."""
        return self._fan_speed

    @property
    def fan_speed_list(self) -> list:
        """Get the list of available fan speeds."""
        return self._fan_speed_list

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    async def async_start(self):
        """Start or resume the cleaning task."""
        await self._start_script.async_run(context=self._context)

    async def async_pause(self):
        """Pause the cleaning task."""
        if self._pause_script is None:
            return

        await self._pause_script.async_run(context=self._context)

    async def async_stop(self, **kwargs):
        """Stop the cleaning task."""
        if self._stop_script is None:
            return

        await self._stop_script.async_run(context=self._context)

    async def async_return_to_base(self, **kwargs):
        """Set the vacuum cleaner to return to the dock."""
        if self._return_to_base_script is None:
            return

        await self._return_to_base_script.async_run(context=self._context)

    async def async_clean_spot(self, **kwargs):
        """Perform a spot clean-up."""
        if self._clean_spot_script is None:
            return

        await self._clean_spot_script.async_run(context=self._context)

    async def async_locate(self, **kwargs):
        """Locate the vacuum cleaner."""
        if self._locate_script is None:
            return

        await self._locate_script.async_run(context=self._context)

    async def async_set_fan_speed(self, fan_speed, **kwargs):
        """Set fan speed."""
        if self._set_fan_speed_script is None:
            return

        if fan_speed in self._fan_speed_list:
            self._fan_speed = fan_speed
            await self._set_fan_speed_script.async_run(
                {ATTR_FAN_SPEED: fan_speed}, context=self._context)
        else:
            _LOGGER.error(
                'Received invalid fan speed: %s. Expected: %s.',
                fan_speed, self._fan_speed_list)

    async def async_added_to_hass(self):
        """Register callbacks."""
        @callback
        def template_vacuum_state_listener(entity, old_state, new_state):
            """Handle target device state changes."""
            self.async_schedule_update_ha_state(True)

        @callback
        def template_vacuum_startup(event):
            """Update template on startup."""
            if self._entities != MATCH_ALL:
                # Track state changes only for valid templates
                self.hass.helpers.event.async_track_state_change(
                    self._entities, template_vacuum_state_listener)

            self.async_schedule_update_ha_state(True)

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, template_vacuum_startup)

    async def async_update(self):
        """Update the state from the template."""
        # Update state
        if self._template is not None:
            try:
                state = self._template.async_render()
            except TemplateError as ex:
                _LOGGER.error(ex)
                state = None
                self._state = None

            # Validate state
            if state in _VALID_STATES:
                self._state = state
            elif state == STATE_UNKNOWN:
                self._state = None
            else:
                _LOGGER.error(
                    'Received invalid vacuum state: %s. Expected: %s.',
                    state, ', '.join(_VALID_STATES))
                self._state = None

        # Update battery level if 'battery_level_template' is configured
        if self._battery_level_template is not None:
            try:
                battery_level = self._battery_level_template.async_render()
            except TemplateError as ex:
                _LOGGER.error(ex)
                battery_level = None

            # Validate battery level
            if battery_level and 0 <= int(battery_level) <= 100:
                self._battery_level = int(battery_level)
            else:
                _LOGGER.error(
                    'Received invalid battery level: %s. Expected: 0-100',
                    battery_level)
                self._battery_level = None

        # Update fan speed if 'fan_speed_template' is configured
        if self._fan_speed_template is not None:
            try:
                fan_speed = self._fan_speed_template.async_render()
            except TemplateError as ex:
                _LOGGER.error(ex)
                fan_speed = None
                self._state = None

            # Validate fan speed
            if fan_speed in self._fan_speed_list:
                self._fan_speed = fan_speed
            elif fan_speed == STATE_UNKNOWN:
                self._fan_speed = None
            else:
                _LOGGER.error(
                    'Received invalid fan speed: %s. Expected: %s.',
                    fan_speed, self._fan_speed_list)
                self._fan_speed = None
