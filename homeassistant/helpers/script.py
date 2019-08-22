"""Helpers to execute scripts."""

import logging
from contextlib import suppress
from itertools import islice
from typing import Optional, Sequence

import voluptuous as vol

from homeassistant.core import HomeAssistant, Context, callback
from homeassistant.const import CONF_CONDITION, CONF_TIMEOUT
from homeassistant import exceptions
from homeassistant.helpers import (
    service, condition, template as template,
    config_validation as cv)
from homeassistant.helpers.event import (
    async_track_point_in_utc_time, async_track_template)
from homeassistant.helpers.typing import ConfigType
import homeassistant.util.dt as date_util
from homeassistant.util.async_ import (
    run_coroutine_threadsafe, run_callback_threadsafe)

_LOGGER = logging.getLogger(__name__)

CONF_ALIAS = 'alias'
CONF_SERVICE = 'service'
CONF_SERVICE_DATA = 'data'
CONF_SEQUENCE = 'sequence'
CONF_EVENT = 'event'
CONF_EVENT_DATA = 'event_data'
CONF_EVENT_DATA_TEMPLATE = 'event_data_template'
CONF_DELAY = 'delay'
CONF_WAIT_TEMPLATE = 'wait_template'
CONF_CONTINUE = 'continue_on_timeout'


ACTION_DELAY = 'delay'
ACTION_WAIT_TEMPLATE = 'wait_template'
ACTION_CHECK_CONDITION = 'condition'
ACTION_FIRE_EVENT = 'event'
ACTION_CALL_SERVICE = 'call_service'


def _determine_action(action):
    """Determine action type."""
    if CONF_DELAY in action:
        return ACTION_DELAY

    if CONF_WAIT_TEMPLATE in action:
        return ACTION_WAIT_TEMPLATE

    if CONF_CONDITION in action:
        return ACTION_CHECK_CONDITION

    if CONF_EVENT in action:
        return ACTION_FIRE_EVENT

    return ACTION_CALL_SERVICE


def call_from_config(hass: HomeAssistant, config: ConfigType,
                     variables: Optional[Sequence] = None,
                     context: Optional[Context] = None) -> None:
    """Call a script based on a config entry."""
    Script(hass, cv.SCRIPT_SCHEMA(config)).run(variables, context)


class _StopScript(Exception):
    """Throw if script needs to stop."""


class _SuspendScript(Exception):
    """Throw if script needs to suspend."""


class Script():
    """Representation of a script."""

    def __init__(self, hass: HomeAssistant, sequence, name: str = None,
                 change_listener=None) -> None:
        """Initialize the script."""
        self.hass = hass
        self.sequence = sequence
        template.attach(hass, self.sequence)
        self.name = name
        self._change_listener = change_listener
        self._cur = -1
        self._exception_step = None
        self.last_action = None
        self.last_triggered = None
        self.can_cancel = any(CONF_DELAY in action or CONF_WAIT_TEMPLATE
                              in action for action in self.sequence)
        self._async_listener = []
        self._template_cache = {}
        self._config_cache = {}
        self._actions = {
            ACTION_DELAY: self._async_delay,
            ACTION_WAIT_TEMPLATE: self._async_wait_template,
            ACTION_CHECK_CONDITION: self._async_check_condition,
            ACTION_FIRE_EVENT: self._async_fire_event,
            ACTION_CALL_SERVICE: self._async_call_service,
        }

    @property
    def is_running(self) -> bool:
        """Return true if script is on."""
        return self._cur != -1

    def run(self, variables=None, context=None):
        """Run script."""
        run_coroutine_threadsafe(
            self.async_run(variables, context), self.hass.loop).result()

    async def async_run(self, variables: Optional[Sequence] = None,
                        context: Optional[Context] = None) -> None:
        """Run script.

        This method is a coroutine.
        """
        self.last_triggered = date_util.utcnow()
        if self._cur == -1:
            self._log('Running script')
            self._cur = 0

        # Unregister callback if we were in a delay or wait but turn on is
        # called again. In that case we just continue execution.
        self._async_remove_listener()

        for cur, action in islice(enumerate(self.sequence), self._cur, None):
            try:
                await self._handle_action(action, variables, context)
            except _SuspendScript:
                # Store next step to take and notify change listeners
                self._cur = cur + 1
                if self._change_listener:
                    self.hass.async_add_job(self._change_listener)
                return
            except _StopScript:
                break
            except Exception:
                # Store the step that had an exception
                self._exception_step = cur
                # Set script to not running
                self._cur = -1
                self.last_action = None
                # Pass exception on.
                raise

        # Set script to not-running.
        self._cur = -1
        self.last_action = None
        if self._change_listener:
            self.hass.async_add_job(self._change_listener)

    def stop(self) -> None:
        """Stop running script."""
        run_callback_threadsafe(self.hass.loop, self.async_stop).result()

    def async_stop(self) -> None:
        """Stop running script."""
        if self._cur == -1:
            return

        self._cur = -1
        self._async_remove_listener()
        if self._change_listener:
            self.hass.async_add_job(self._change_listener)

    @callback
    def async_log_exception(self, logger, message_base, exception):
        """Log an exception for this script.

        Should only be called on exceptions raised by this scripts async_run.
        """
        # pylint: disable=protected-access
        step = self._exception_step
        action = self.sequence[step]
        action_type = _determine_action(action)

        error = None
        meth = logger.error

        if isinstance(exception, vol.Invalid):
            error_desc = "Invalid data"

        elif isinstance(exception, exceptions.TemplateError):
            error_desc = "Error rendering template"

        elif isinstance(exception, exceptions.Unauthorized):
            error_desc = "Unauthorized"

        elif isinstance(exception, exceptions.ServiceNotFound):
            error_desc = "Service not found"

        else:
            # Print the full stack trace, unknown error
            error_desc = 'Unknown error'
            meth = logger.exception
            error = ""

        if error is None:
            error = str(exception)

        meth("%s. %s for %s at pos %s: %s",
             message_base, error_desc, action_type, step + 1, error)

    async def _handle_action(self, action, variables, context):
        """Handle an action."""
        await self._actions[_determine_action(action)](
            action, variables, context)

    async def _async_delay(self, action, variables, context):
        """Handle delay."""
        # Call ourselves in the future to continue work
        unsub = None

        @callback
        def async_script_delay(now):
            """Handle delay."""
            # pylint: disable=cell-var-from-loop
            with suppress(ValueError):
                self._async_listener.remove(unsub)

            self.hass.async_create_task(
                self.async_run(variables, context))

        delay = action[CONF_DELAY]

        try:
            if isinstance(delay, template.Template):
                delay = vol.All(
                    cv.time_period,
                    cv.positive_timedelta)(
                        delay.async_render(variables))
            elif isinstance(delay, dict):
                delay_data = {}
                delay_data.update(
                    template.render_complex(delay, variables))
                delay = cv.time_period(delay_data)
        except (exceptions.TemplateError, vol.Invalid) as ex:
            _LOGGER.error("Error rendering '%s' delay template: %s",
                          self.name, ex)
            raise _StopScript

        self.last_action = action.get(
            CONF_ALIAS, 'delay {}'.format(delay))
        self._log("Executing step %s" % self.last_action)

        unsub = async_track_point_in_utc_time(
            self.hass, async_script_delay,
            date_util.utcnow() + delay
        )
        self._async_listener.append(unsub)
        raise _SuspendScript

    async def _async_wait_template(self, action, variables, context):
        """Handle a wait template."""
        # Call ourselves in the future to continue work
        wait_template = action[CONF_WAIT_TEMPLATE]
        wait_template.hass = self.hass

        self.last_action = action.get(CONF_ALIAS, 'wait template')
        self._log("Executing step %s" % self.last_action)

        # check if condition already okay
        if condition.async_template(
                self.hass, wait_template, variables):
            return

        @callback
        def async_script_wait(entity_id, from_s, to_s):
            """Handle script after template condition is true."""
            self._async_remove_listener()
            self.hass.async_create_task(
                self.async_run(variables, context))

        self._async_listener.append(async_track_template(
            self.hass, wait_template, async_script_wait, variables))

        if CONF_TIMEOUT in action:
            self._async_set_timeout(
                action, variables, context,
                action.get(CONF_CONTINUE, True))

        raise _SuspendScript

    async def _async_call_service(self, action, variables, context):
        """Call the service specified in the action.

        This method is a coroutine.
        """
        self.last_action = action.get(CONF_ALIAS, 'call service')
        self._log("Executing step %s" % self.last_action)
        await service.async_call_from_config(
            self.hass, action,
            blocking=True,
            variables=variables,
            validate_config=False,
            context=context
        )

    async def _async_fire_event(self, action, variables, context):
        """Fire an event."""
        self.last_action = action.get(CONF_ALIAS, action[CONF_EVENT])
        self._log("Executing step %s" % self.last_action)
        event_data = dict(action.get(CONF_EVENT_DATA, {}))
        if CONF_EVENT_DATA_TEMPLATE in action:
            try:
                event_data.update(template.render_complex(
                    action[CONF_EVENT_DATA_TEMPLATE], variables))
            except exceptions.TemplateError as ex:
                _LOGGER.error('Error rendering event data template: %s', ex)

        self.hass.bus.async_fire(action[CONF_EVENT],
                                 event_data, context=context)

    async def _async_check_condition(self, action, variables, context):
        """Test if condition is matching."""
        config_cache_key = frozenset((k, str(v)) for k, v in action.items())
        config = self._config_cache.get(config_cache_key)
        if not config:
            config = condition.async_from_config(action, False)
            self._config_cache[config_cache_key] = config

        self.last_action = action.get(CONF_ALIAS, action[CONF_CONDITION])
        check = config(self.hass, variables)
        self._log("Test condition {}: {}".format(self.last_action, check))

        if not check:
            raise _StopScript

    def _async_set_timeout(self, action, variables, context,
                           continue_on_timeout):
        """Schedule a timeout to abort or continue script."""
        timeout = action[CONF_TIMEOUT]
        unsub = None

        @callback
        def async_script_timeout(now):
            """Call after timeout is retrieve."""
            with suppress(ValueError):
                self._async_listener.remove(unsub)

            # Check if we want to continue to execute
            # the script after the timeout
            if continue_on_timeout:
                self.hass.async_create_task(
                    self.async_run(variables, context))
            else:
                self._log("Timeout reached, abort script.")
                self.async_stop()

        unsub = async_track_point_in_utc_time(
            self.hass, async_script_timeout,
            date_util.utcnow() + timeout
        )
        self._async_listener.append(unsub)

    def _async_remove_listener(self):
        """Remove point in time listener, if any."""
        for unsub in self._async_listener:
            unsub()
        self._async_listener.clear()

    def _log(self, msg):
        """Logger helper."""
        if self.name is not None:
            msg = "Script {}: {}".format(self.name, msg)

        _LOGGER.info(msg)
