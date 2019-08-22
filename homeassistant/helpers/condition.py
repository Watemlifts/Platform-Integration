"""Offer reusable conditions."""
from datetime import datetime, timedelta
import functools as ft
import logging
import sys
from typing import Callable, Container, Optional, Union, cast

from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from homeassistant.core import HomeAssistant, State
from homeassistant.components import zone as zone_cmp
from homeassistant.const import (
    ATTR_GPS_ACCURACY, ATTR_LATITUDE, ATTR_LONGITUDE,
    CONF_ENTITY_ID, CONF_VALUE_TEMPLATE, CONF_CONDITION,
    WEEKDAYS, CONF_STATE, CONF_ZONE, CONF_BEFORE,
    CONF_AFTER, CONF_WEEKDAY, SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET,
    CONF_BELOW, CONF_ABOVE, STATE_UNAVAILABLE, STATE_UNKNOWN)
from homeassistant.exceptions import TemplateError, HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.sun import get_astral_event_date
import homeassistant.util.dt as dt_util
from homeassistant.util.async_ import run_callback_threadsafe

FROM_CONFIG_FORMAT = '{}_from_config'
ASYNC_FROM_CONFIG_FORMAT = 'async_{}_from_config'

_LOGGER = logging.getLogger(__name__)

# PyLint does not like the use of _threaded_factory
# pylint: disable=invalid-name


def _threaded_factory(async_factory:
                      Callable[[ConfigType, bool], Callable[..., bool]]) \
                      -> Callable[[ConfigType, bool], Callable[..., bool]]:
    """Create threaded versions of async factories."""
    @ft.wraps(async_factory)
    def factory(config: ConfigType,
                config_validation: bool = True) -> Callable[..., bool]:
        """Threaded factory."""
        async_check = async_factory(config, config_validation)

        def condition_if(hass: HomeAssistant,
                         variables: TemplateVarsType = None) -> bool:
            """Validate condition."""
            return cast(bool, run_callback_threadsafe(
                hass.loop, async_check, hass, variables,
            ).result())

        return condition_if

    return factory


def async_from_config(config: ConfigType,
                      config_validation: bool = True) -> Callable[..., bool]:
    """Turn a condition configuration into a method.

    Should be run on the event loop.
    """
    for fmt in (ASYNC_FROM_CONFIG_FORMAT, FROM_CONFIG_FORMAT):
        factory = getattr(
            sys.modules[__name__],
            fmt.format(config.get(CONF_CONDITION)), None)

        if factory:
            break

    if factory is None:
        raise HomeAssistantError('Invalid condition "{}" specified {}'.format(
            config.get(CONF_CONDITION), config))

    return cast(Callable[..., bool], factory(config, config_validation))


from_config = _threaded_factory(async_from_config)


def async_and_from_config(config: ConfigType,
                          config_validation: bool = True) \
                          -> Callable[..., bool]:
    """Create multi condition matcher using 'AND'."""
    if config_validation:
        config = cv.AND_CONDITION_SCHEMA(config)
    checks = None

    def if_and_condition(hass: HomeAssistant,
                         variables: TemplateVarsType = None) -> bool:
        """Test and condition."""
        nonlocal checks

        if checks is None:
            checks = [async_from_config(entry, False) for entry
                      in config['conditions']]

        try:
            for check in checks:
                if not check(hass, variables):
                    return False
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.warning("Error during and-condition: %s", ex)
            return False

        return True

    return if_and_condition


and_from_config = _threaded_factory(async_and_from_config)


def async_or_from_config(config: ConfigType,
                         config_validation: bool = True) \
                         -> Callable[..., bool]:
    """Create multi condition matcher using 'OR'."""
    if config_validation:
        config = cv.OR_CONDITION_SCHEMA(config)
    checks = None

    def if_or_condition(hass: HomeAssistant,
                        variables: TemplateVarsType = None) -> bool:
        """Test and condition."""
        nonlocal checks

        if checks is None:
            checks = [async_from_config(entry, False) for entry
                      in config['conditions']]

        try:
            for check in checks:
                if check(hass, variables):
                    return True
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.warning("Error during or-condition: %s", ex)

        return False

    return if_or_condition


or_from_config = _threaded_factory(async_or_from_config)


def numeric_state(hass: HomeAssistant, entity: Union[None, str, State],
                  below: Optional[float] = None, above: Optional[float] = None,
                  value_template: Optional[Template] = None,
                  variables: TemplateVarsType = None) -> bool:
    """Test a numeric state condition."""
    return cast(bool, run_callback_threadsafe(
        hass.loop, async_numeric_state, hass, entity, below, above,
        value_template, variables,
    ).result())


def async_numeric_state(hass: HomeAssistant, entity: Union[None, str, State],
                        below: Optional[float] = None,
                        above: Optional[float] = None,
                        value_template: Optional[Template] = None,
                        variables: TemplateVarsType = None) -> bool:
    """Test a numeric state condition."""
    if isinstance(entity, str):
        entity = hass.states.get(entity)

    if entity is None:
        return False

    if value_template is None:
        value = entity.state
    else:
        variables = dict(variables or {})
        variables['state'] = entity
        try:
            value = value_template.async_render(variables)
        except TemplateError as ex:
            _LOGGER.error("Template error: %s", ex)
            return False

    if value in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return False

    try:
        fvalue = float(value)
    except ValueError:
        _LOGGER.warning("Value cannot be processed as a number: %s "
                        "(Offending entity: %s)", entity, value)
        return False

    if below is not None and fvalue >= below:
        return False

    if above is not None and fvalue <= above:
        return False

    return True


def async_numeric_state_from_config(config: ConfigType,
                                    config_validation: bool = True) \
                                    -> Callable[..., bool]:
    """Wrap action method with state based condition."""
    if config_validation:
        config = cv.NUMERIC_STATE_CONDITION_SCHEMA(config)
    entity_id = config.get(CONF_ENTITY_ID)
    below = config.get(CONF_BELOW)
    above = config.get(CONF_ABOVE)
    value_template = config.get(CONF_VALUE_TEMPLATE)

    def if_numeric_state(hass: HomeAssistant,
                         variables: TemplateVarsType = None) -> bool:
        """Test numeric state condition."""
        if value_template is not None:
            value_template.hass = hass

        return async_numeric_state(
            hass, entity_id, below, above, value_template, variables)

    return if_numeric_state


numeric_state_from_config = _threaded_factory(async_numeric_state_from_config)


def state(hass: HomeAssistant, entity: Union[None, str, State], req_state: str,
          for_period: Optional[timedelta] = None) -> bool:
    """Test if state matches requirements.

    Async friendly.
    """
    if isinstance(entity, str):
        entity = hass.states.get(entity)

    if entity is None:
        return False
    assert isinstance(entity, State)

    is_state = entity.state == req_state

    if for_period is None or not is_state:
        return is_state

    return dt_util.utcnow() - for_period > entity.last_changed


def state_from_config(config: ConfigType,
                      config_validation: bool = True) -> Callable[..., bool]:
    """Wrap action method with state based condition."""
    if config_validation:
        config = cv.STATE_CONDITION_SCHEMA(config)
    entity_id = config.get(CONF_ENTITY_ID)
    req_state = cast(str, config.get(CONF_STATE))
    for_period = config.get('for')

    def if_state(hass: HomeAssistant,
                 variables: TemplateVarsType = None) -> bool:
        """Test if condition."""
        return state(hass, entity_id, req_state, for_period)

    return if_state


def sun(hass: HomeAssistant, before: Optional[str] = None,
        after: Optional[str] = None, before_offset: Optional[timedelta] = None,
        after_offset: Optional[timedelta] = None) -> bool:
    """Test if current time matches sun requirements."""
    utcnow = dt_util.utcnow()
    today = dt_util.as_local(utcnow).date()
    before_offset = before_offset or timedelta(0)
    after_offset = after_offset or timedelta(0)

    sunrise = get_astral_event_date(hass, SUN_EVENT_SUNRISE, today)
    sunset = get_astral_event_date(hass, SUN_EVENT_SUNSET, today)

    if sunrise is None and SUN_EVENT_SUNRISE in (before, after):
        # There is no sunrise today
        return False

    if sunset is None and SUN_EVENT_SUNSET in (before, after):
        # There is no sunset today
        return False

    if before == SUN_EVENT_SUNRISE and \
       utcnow > cast(datetime, sunrise) + before_offset:
        return False

    if before == SUN_EVENT_SUNSET and \
       utcnow > cast(datetime, sunset) + before_offset:
        return False

    if after == SUN_EVENT_SUNRISE and \
       utcnow < cast(datetime, sunrise) + after_offset:
        return False

    if after == SUN_EVENT_SUNSET and \
       utcnow < cast(datetime, sunset) + after_offset:
        return False

    return True


def sun_from_config(config: ConfigType,
                    config_validation: bool = True) -> Callable[..., bool]:
    """Wrap action method with sun based condition."""
    if config_validation:
        config = cv.SUN_CONDITION_SCHEMA(config)
    before = config.get('before')
    after = config.get('after')
    before_offset = config.get('before_offset')
    after_offset = config.get('after_offset')

    def time_if(hass: HomeAssistant,
                variables: TemplateVarsType = None) -> bool:
        """Validate time based if-condition."""
        return sun(hass, before, after, before_offset, after_offset)

    return time_if


def template(hass: HomeAssistant, value_template: Template,
             variables: TemplateVarsType = None) -> bool:
    """Test if template condition matches."""
    return cast(bool, run_callback_threadsafe(
        hass.loop, async_template, hass, value_template, variables,
    ).result())


def async_template(hass: HomeAssistant, value_template: Template,
                   variables: TemplateVarsType = None) -> bool:
    """Test if template condition matches."""
    try:
        value = value_template.async_render(variables)
    except TemplateError as ex:
        _LOGGER.error("Error during template condition: %s", ex)
        return False

    return value.lower() == 'true'


def async_template_from_config(config: ConfigType,
                               config_validation: bool = True) \
                               -> Callable[..., bool]:
    """Wrap action method with state based condition."""
    if config_validation:
        config = cv.TEMPLATE_CONDITION_SCHEMA(config)
    value_template = cast(Template, config.get(CONF_VALUE_TEMPLATE))

    def template_if(hass: HomeAssistant,
                    variables: TemplateVarsType = None) -> bool:
        """Validate template based if-condition."""
        value_template.hass = hass

        return async_template(hass, value_template, variables)

    return template_if


template_from_config = _threaded_factory(async_template_from_config)


def time(before: Optional[dt_util.dt.time] = None,
         after: Optional[dt_util.dt.time] = None,
         weekday: Union[None, str, Container[str]] = None) -> bool:
    """Test if local time condition matches.

    Handle the fact that time is continuous and we may be testing for
    a period that crosses midnight. In that case it is easier to test
    for the opposite. "(23:59 <= now < 00:01)" would be the same as
    "not (00:01 <= now < 23:59)".
    """
    now = dt_util.now()
    now_time = now.time()

    if after is None:
        after = dt_util.dt.time(0)
    if before is None:
        before = dt_util.dt.time(23, 59, 59, 999999)

    if after < before:
        if not after <= now_time < before:
            return False
    else:
        if before <= now_time < after:
            return False

    if weekday is not None:
        now_weekday = WEEKDAYS[now.weekday()]

        if isinstance(weekday, str) and weekday != now_weekday or \
           now_weekday not in weekday:
            return False

    return True


def time_from_config(config: ConfigType,
                     config_validation: bool = True) -> Callable[..., bool]:
    """Wrap action method with time based condition."""
    if config_validation:
        config = cv.TIME_CONDITION_SCHEMA(config)
    before = config.get(CONF_BEFORE)
    after = config.get(CONF_AFTER)
    weekday = config.get(CONF_WEEKDAY)

    def time_if(hass: HomeAssistant,
                variables: TemplateVarsType = None) -> bool:
        """Validate time based if-condition."""
        return time(before, after, weekday)

    return time_if


def zone(hass: HomeAssistant, zone_ent: Union[None, str, State],
         entity: Union[None, str, State]) -> bool:
    """Test if zone-condition matches.

    Async friendly.
    """
    if isinstance(zone_ent, str):
        zone_ent = hass.states.get(zone_ent)

    if zone_ent is None:
        return False

    if isinstance(entity, str):
        entity = hass.states.get(entity)

    if entity is None:
        return False

    latitude = entity.attributes.get(ATTR_LATITUDE)
    longitude = entity.attributes.get(ATTR_LONGITUDE)

    if latitude is None or longitude is None:
        return False

    return zone_cmp.zone.in_zone(zone_ent, latitude, longitude,
                                 entity.attributes.get(ATTR_GPS_ACCURACY, 0))


def zone_from_config(config: ConfigType,
                     config_validation: bool = True) -> Callable[..., bool]:
    """Wrap action method with zone based condition."""
    if config_validation:
        config = cv.ZONE_CONDITION_SCHEMA(config)
    entity_id = config.get(CONF_ENTITY_ID)
    zone_entity_id = config.get(CONF_ZONE)

    def if_in_zone(hass: HomeAssistant,
                   variables: TemplateVarsType = None) -> bool:
        """Test if condition."""
        return zone(hass, zone_entity_id, entity_id)

    return if_in_zone
