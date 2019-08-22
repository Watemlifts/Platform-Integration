"""Provides functionality to interact with lights."""
import asyncio
import csv
from datetime import timedelta
import logging
import os

import voluptuous as vol

from homeassistant.auth.permissions.const import POLICY_CONTROL
from homeassistant.components.group import \
    ENTITY_ID_FORMAT as GROUP_ENTITY_ID_FORMAT
from homeassistant.const import (
    ATTR_ENTITY_ID, SERVICE_TOGGLE, SERVICE_TURN_OFF, SERVICE_TURN_ON,
    STATE_ON)
from homeassistant.exceptions import UnknownUser, Unauthorized
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import (  # noqa
    PLATFORM_SCHEMA, PLATFORM_SCHEMA_BASE)
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers import intent
from homeassistant.loader import bind_hass
import homeassistant.util.color as color_util

DOMAIN = 'light'
SCAN_INTERVAL = timedelta(seconds=30)

GROUP_NAME_ALL_LIGHTS = 'all lights'
ENTITY_ID_ALL_LIGHTS = GROUP_ENTITY_ID_FORMAT.format('all_lights')

ENTITY_ID_FORMAT = DOMAIN + '.{}'

# Bitfield of features supported by the light entity
SUPPORT_BRIGHTNESS = 1
SUPPORT_COLOR_TEMP = 2
SUPPORT_EFFECT = 4
SUPPORT_FLASH = 8
SUPPORT_COLOR = 16
SUPPORT_TRANSITION = 32
SUPPORT_WHITE_VALUE = 128

# Integer that represents transition time in seconds to make change.
ATTR_TRANSITION = "transition"

# Lists holding color values
ATTR_RGB_COLOR = "rgb_color"
ATTR_XY_COLOR = "xy_color"
ATTR_HS_COLOR = "hs_color"
ATTR_COLOR_TEMP = "color_temp"
ATTR_KELVIN = "kelvin"
ATTR_MIN_MIREDS = "min_mireds"
ATTR_MAX_MIREDS = "max_mireds"
ATTR_COLOR_NAME = "color_name"
ATTR_WHITE_VALUE = "white_value"

# Brightness of the light, 0..255 or percentage
ATTR_BRIGHTNESS = "brightness"
ATTR_BRIGHTNESS_PCT = "brightness_pct"

# String representing a profile (built-in ones or external defined).
ATTR_PROFILE = "profile"

# If the light should flash, can be FLASH_SHORT or FLASH_LONG.
ATTR_FLASH = "flash"
FLASH_SHORT = "short"
FLASH_LONG = "long"

# List of possible effects
ATTR_EFFECT_LIST = "effect_list"

# Apply an effect to the light, can be EFFECT_COLORLOOP.
ATTR_EFFECT = "effect"
EFFECT_COLORLOOP = "colorloop"
EFFECT_RANDOM = "random"
EFFECT_WHITE = "white"

COLOR_GROUP = "Color descriptors"

LIGHT_PROFILES_FILE = "light_profiles.csv"

# Service call validation schemas
VALID_TRANSITION = vol.All(vol.Coerce(float), vol.Clamp(min=0, max=6553))
VALID_BRIGHTNESS = vol.All(vol.Coerce(int), vol.Clamp(min=0, max=255))
VALID_BRIGHTNESS_PCT = vol.All(vol.Coerce(float), vol.Range(min=0, max=100))

LIGHT_TURN_ON_SCHEMA = vol.Schema({
    ATTR_ENTITY_ID: cv.comp_entity_ids,
    vol.Exclusive(ATTR_PROFILE, COLOR_GROUP): cv.string,
    ATTR_TRANSITION: VALID_TRANSITION,
    ATTR_BRIGHTNESS: VALID_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT: VALID_BRIGHTNESS_PCT,
    vol.Exclusive(ATTR_COLOR_NAME, COLOR_GROUP): cv.string,
    vol.Exclusive(ATTR_RGB_COLOR, COLOR_GROUP):
        vol.All(vol.ExactSequence((cv.byte, cv.byte, cv.byte)),
                vol.Coerce(tuple)),
    vol.Exclusive(ATTR_XY_COLOR, COLOR_GROUP):
        vol.All(vol.ExactSequence((cv.small_float, cv.small_float)),
                vol.Coerce(tuple)),
    vol.Exclusive(ATTR_HS_COLOR, COLOR_GROUP):
        vol.All(vol.ExactSequence(
            (vol.All(vol.Coerce(float), vol.Range(min=0, max=360)),
             vol.All(vol.Coerce(float), vol.Range(min=0, max=100)))),
                vol.Coerce(tuple)),
    vol.Exclusive(ATTR_COLOR_TEMP, COLOR_GROUP):
        vol.All(vol.Coerce(int), vol.Range(min=1)),
    vol.Exclusive(ATTR_KELVIN, COLOR_GROUP):
        vol.All(vol.Coerce(int), vol.Range(min=0)),
    ATTR_WHITE_VALUE: vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
    ATTR_FLASH: vol.In([FLASH_SHORT, FLASH_LONG]),
    ATTR_EFFECT: cv.string,
})

LIGHT_TURN_OFF_SCHEMA = vol.Schema({
    ATTR_ENTITY_ID: cv.comp_entity_ids,
    ATTR_TRANSITION: VALID_TRANSITION,
    ATTR_FLASH: vol.In([FLASH_SHORT, FLASH_LONG]),
})

LIGHT_TOGGLE_SCHEMA = LIGHT_TURN_ON_SCHEMA

PROFILE_SCHEMA = vol.Schema(
    vol.ExactSequence((str, cv.small_float, cv.small_float, cv.byte))
)

INTENT_SET = 'HassLightSet'

_LOGGER = logging.getLogger(__name__)


@bind_hass
def is_on(hass, entity_id=None):
    """Return if the lights are on based on the statemachine."""
    entity_id = entity_id or ENTITY_ID_ALL_LIGHTS
    return hass.states.is_state(entity_id, STATE_ON)


def preprocess_turn_on_alternatives(params):
    """Process extra data for turn light on request."""
    profile = Profiles.get(params.pop(ATTR_PROFILE, None))
    if profile is not None:
        params.setdefault(ATTR_XY_COLOR, profile[:2])
        params.setdefault(ATTR_BRIGHTNESS, profile[2])

    color_name = params.pop(ATTR_COLOR_NAME, None)
    if color_name is not None:
        try:
            params[ATTR_RGB_COLOR] = color_util.color_name_to_rgb(color_name)
        except ValueError:
            _LOGGER.warning('Got unknown color %s, falling back to white',
                            color_name)
            params[ATTR_RGB_COLOR] = (255, 255, 255)

    kelvin = params.pop(ATTR_KELVIN, None)
    if kelvin is not None:
        mired = color_util.color_temperature_kelvin_to_mired(kelvin)
        params[ATTR_COLOR_TEMP] = int(mired)

    brightness_pct = params.pop(ATTR_BRIGHTNESS_PCT, None)
    if brightness_pct is not None:
        params[ATTR_BRIGHTNESS] = int(255 * brightness_pct/100)

    xy_color = params.pop(ATTR_XY_COLOR, None)
    if xy_color is not None:
        params[ATTR_HS_COLOR] = color_util.color_xy_to_hs(*xy_color)

    rgb_color = params.pop(ATTR_RGB_COLOR, None)
    if rgb_color is not None:
        params[ATTR_HS_COLOR] = color_util.color_RGB_to_hs(*rgb_color)


def preprocess_turn_off(params):
    """Process data for turning light off if brightness is 0."""
    if ATTR_BRIGHTNESS in params and params[ATTR_BRIGHTNESS] == 0:
        # Zero brightness: Light will be turned off
        params = {k: v for k, v in params.items() if k in [ATTR_TRANSITION,
                                                           ATTR_FLASH]}
        return (True, params)  # Light should be turned off

    return (False, None)  # Light should be turned on


class SetIntentHandler(intent.IntentHandler):
    """Handle set color intents."""

    intent_type = INTENT_SET
    slot_schema = {
        vol.Required('name'): cv.string,
        vol.Optional('color'): color_util.color_name_to_rgb,
        vol.Optional('brightness'): vol.All(vol.Coerce(int), vol.Range(0, 100))
    }

    async def async_handle(self, intent_obj):
        """Handle the hass intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        state = hass.helpers.intent.async_match_state(
            slots['name']['value'],
            [state for state in hass.states.async_all()
             if state.domain == DOMAIN])

        service_data = {
            ATTR_ENTITY_ID: state.entity_id,
        }
        speech_parts = []

        if 'color' in slots:
            intent.async_test_feature(
                state, SUPPORT_COLOR, 'changing colors')
            service_data[ATTR_RGB_COLOR] = slots['color']['value']
            # Use original passed in value of the color because we don't have
            # human readable names for that internally.
            speech_parts.append('the color {}'.format(
                intent_obj.slots['color']['value']))

        if 'brightness' in slots:
            intent.async_test_feature(
                state, SUPPORT_BRIGHTNESS, 'changing brightness')
            service_data[ATTR_BRIGHTNESS_PCT] = slots['brightness']['value']
            speech_parts.append('{}% brightness'.format(
                slots['brightness']['value']))

        await hass.services.async_call(DOMAIN, SERVICE_TURN_ON, service_data)

        response = intent_obj.create_response()

        if not speech_parts:  # No attributes changed
            speech = 'Turned on {}'.format(state.name)
        else:
            parts = ['Changed {} to'.format(state.name)]
            for index, part in enumerate(speech_parts):
                if index == 0:
                    parts.append(' {}'.format(part))
                elif index != len(speech_parts) - 1:
                    parts.append(', {}'.format(part))
                else:
                    parts.append(' and {}'.format(part))
            speech = ''.join(parts)

        response.async_set_speech(speech)
        return response


async def async_setup(hass, config):
    """Expose light control via state machine and services."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL, GROUP_NAME_ALL_LIGHTS)
    await component.async_setup(config)

    # load profiles from files
    profiles_valid = await Profiles.load_profiles(hass)
    if not profiles_valid:
        return False

    async def async_handle_light_on_service(service):
        """Handle a turn light on service call."""
        # Get the validated data
        params = service.data.copy()

        # Convert the entity ids to valid light ids
        target_lights = await component.async_extract_from_service(service)
        params.pop(ATTR_ENTITY_ID, None)

        if service.context.user_id:
            user = await hass.auth.async_get_user(service.context.user_id)
            if user is None:
                raise UnknownUser(context=service.context)

            entity_perms = user.permissions.check_entity

            for light in target_lights:
                if not entity_perms(light, POLICY_CONTROL):
                    raise Unauthorized(
                        context=service.context,
                        entity_id=light,
                        permission=POLICY_CONTROL
                    )

        preprocess_turn_on_alternatives(params)
        turn_lights_off, off_params = preprocess_turn_off(params)

        update_tasks = []
        for light in target_lights:
            light.async_set_context(service.context)

            pars = params
            off_pars = off_params
            turn_light_off = turn_lights_off
            if not pars:
                pars = params.copy()
                pars[ATTR_PROFILE] = Profiles.get_default(light.entity_id)
                preprocess_turn_on_alternatives(pars)
                turn_light_off, off_pars = preprocess_turn_off(pars)
            if turn_light_off:
                await light.async_turn_off(**off_pars)
            else:
                await light.async_turn_on(**pars)

            if not light.should_poll:
                continue

            update_tasks.append(
                light.async_update_ha_state(True))

        if update_tasks:
            await asyncio.wait(update_tasks)

    # Listen for light on and light off service calls.
    hass.services.async_register(
        DOMAIN, SERVICE_TURN_ON, async_handle_light_on_service,
        schema=LIGHT_TURN_ON_SCHEMA)

    component.async_register_entity_service(
        SERVICE_TURN_OFF, LIGHT_TURN_OFF_SCHEMA,
        'async_turn_off'
    )

    component.async_register_entity_service(
        SERVICE_TOGGLE, LIGHT_TOGGLE_SCHEMA,
        'async_toggle'
    )

    hass.helpers.intent.async_register(SetIntentHandler())

    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)


class Profiles:
    """Representation of available color profiles."""

    _all = None

    @classmethod
    async def load_profiles(cls, hass):
        """Load and cache profiles."""
        def load_profile_data(hass):
            """Load built-in profiles and custom profiles."""
            profile_paths = [os.path.join(os.path.dirname(__file__),
                                          LIGHT_PROFILES_FILE),
                             hass.config.path(LIGHT_PROFILES_FILE)]
            profiles = {}

            for profile_path in profile_paths:
                if not os.path.isfile(profile_path):
                    continue
                with open(profile_path) as inp:
                    reader = csv.reader(inp)

                    # Skip the header
                    next(reader, None)

                    try:
                        for rec in reader:
                            profile, color_x, color_y, brightness = \
                                PROFILE_SCHEMA(rec)
                            profiles[profile] = (color_x, color_y, brightness)
                    except vol.MultipleInvalid as ex:
                        _LOGGER.error(
                            "Error parsing light profile from %s: %s",
                            profile_path, ex)
                        return None
            return profiles

        cls._all = await hass.async_add_job(load_profile_data, hass)
        return cls._all is not None

    @classmethod
    def get(cls, name):
        """Return a named profile."""
        return cls._all.get(name)

    @classmethod
    def get_default(cls, entity_id):
        """Return the default turn-on profile for the given light."""
        # pylint: disable=unsupported-membership-test
        name = entity_id + ".default"
        if name in cls._all:
            return name
        name = ENTITY_ID_ALL_LIGHTS + ".default"
        if name in cls._all:
            return name
        return None


class Light(ToggleEntity):
    """Representation of a light."""

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return None

    @property
    def hs_color(self):
        """Return the hue and saturation color value [float, float]."""
        return None

    @property
    def color_temp(self):
        """Return the CT color value in mireds."""
        return None

    @property
    def min_mireds(self):
        """Return the coldest color_temp that this light supports."""
        # Default to the Philips Hue value that HA has always assumed
        # https://developers.meethue.com/documentation/core-concepts
        return 153

    @property
    def max_mireds(self):
        """Return the warmest color_temp that this light supports."""
        # Default to the Philips Hue value that HA has always assumed
        # https://developers.meethue.com/documentation/core-concepts
        return 500

    @property
    def white_value(self):
        """Return the white value of this light between 0..255."""
        return None

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return None

    @property
    def effect(self):
        """Return the current effect."""
        return None

    @property
    def state_attributes(self):
        """Return optional state attributes."""
        data = {}
        supported_features = self.supported_features

        if supported_features & SUPPORT_COLOR_TEMP:
            data[ATTR_MIN_MIREDS] = self.min_mireds
            data[ATTR_MAX_MIREDS] = self.max_mireds

        if supported_features & SUPPORT_EFFECT:
            data[ATTR_EFFECT_LIST] = self.effect_list

        if self.is_on:
            if supported_features & SUPPORT_BRIGHTNESS:
                data[ATTR_BRIGHTNESS] = self.brightness

            if supported_features & SUPPORT_COLOR_TEMP:
                data[ATTR_COLOR_TEMP] = self.color_temp

            if supported_features & SUPPORT_COLOR and self.hs_color:
                # pylint: disable=unsubscriptable-object,not-an-iterable
                hs_color = self.hs_color
                data[ATTR_HS_COLOR] = (
                    round(hs_color[0], 3),
                    round(hs_color[1], 3),
                )
                data[ATTR_RGB_COLOR] = color_util.color_hs_to_RGB(*hs_color)
                data[ATTR_XY_COLOR] = color_util.color_hs_to_xy(*hs_color)

            if supported_features & SUPPORT_WHITE_VALUE:
                data[ATTR_WHITE_VALUE] = self.white_value

            if supported_features & SUPPORT_EFFECT:
                data[ATTR_EFFECT] = self.effect

        return {key: val for key, val in data.items() if val is not None}

    @property
    def supported_features(self):
        """Flag supported features."""
        return 0
