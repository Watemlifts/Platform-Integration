"""Provide methods to bootstrap a Home Assistant instance."""
import asyncio
import logging
import logging.handlers
import os
import sys
from time import time
from collections import OrderedDict
from typing import Any, Optional, Dict, Set

import voluptuous as vol

from homeassistant import core, config as conf_util, config_entries, loader
from homeassistant.const import EVENT_HOMEASSISTANT_CLOSE
from homeassistant.setup import async_setup_component
from homeassistant.util.logging import AsyncHandler
from homeassistant.util.package import async_get_user_site, is_virtual_env
from homeassistant.util.yaml import clear_secret_cache
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)

ERROR_LOG_FILENAME = 'home-assistant.log'

# hass.data key for logging information.
DATA_LOGGING = 'logging'

DEBUGGER_INTEGRATIONS = {'ptvsd', }
CORE_INTEGRATIONS = ('homeassistant', 'persistent_notification')
LOGGING_INTEGRATIONS = {'logger', 'system_log'}
STAGE_1_INTEGRATIONS = {
    # To record data
    'recorder',
    # To make sure we forward data to other instances
    'mqtt_eventstream',
}


async def async_from_config_dict(config: Dict[str, Any],
                                 hass: core.HomeAssistant,
                                 config_dir: Optional[str] = None,
                                 enable_log: bool = True,
                                 verbose: bool = False,
                                 skip_pip: bool = False,
                                 log_rotate_days: Any = None,
                                 log_file: Any = None,
                                 log_no_color: bool = False) \
                           -> Optional[core.HomeAssistant]:
    """Try to configure Home Assistant from a configuration dictionary.

    Dynamically loads required components and its dependencies.
    This method is a coroutine.
    """
    start = time()

    if enable_log:
        async_enable_logging(hass, verbose, log_rotate_days, log_file,
                             log_no_color)

    hass.config.skip_pip = skip_pip
    if skip_pip:
        _LOGGER.warning("Skipping pip installation of required modules. "
                        "This may cause issues")

    core_config = config.get(core.DOMAIN, {})
    api_password = config.get('http', {}).get('api_password')
    trusted_networks = config.get('http', {}).get('trusted_networks')

    try:
        await conf_util.async_process_ha_core_config(
            hass, core_config, api_password, trusted_networks)
    except vol.Invalid as config_err:
        conf_util.async_log_exception(
            config_err, 'homeassistant', core_config, hass)
        return None
    except HomeAssistantError:
        _LOGGER.error("Home Assistant core failed to initialize. "
                      "Further initialization aborted")
        return None

    # Make a copy because we are mutating it.
    config = OrderedDict(config)

    # Merge packages
    await conf_util.merge_packages_config(
        hass, config, core_config.get(conf_util.CONF_PACKAGES, {}))

    hass.config_entries = config_entries.ConfigEntries(hass, config)
    await hass.config_entries.async_initialize()

    await _async_set_up_integrations(hass, config)

    stop = time()
    _LOGGER.info("Home Assistant initialized in %.2fs", stop-start)

    if sys.version_info[:3] < (3, 6, 0):
        hass.components.persistent_notification.async_create(
            "Python 3.5 support is deprecated and will "
            "be removed in the first release after August 1. Please "
            "upgrade Python.", "Python version", "python_version"
        )

    return hass


async def async_from_config_file(config_path: str,
                                 hass: core.HomeAssistant,
                                 verbose: bool = False,
                                 skip_pip: bool = True,
                                 log_rotate_days: Any = None,
                                 log_file: Any = None,
                                 log_no_color: bool = False)\
        -> Optional[core.HomeAssistant]:
    """Read the configuration file and try to start all the functionality.

    Will add functionality to 'hass' parameter.
    This method is a coroutine.
    """
    # Set config dir to directory holding config file
    config_dir = os.path.abspath(os.path.dirname(config_path))
    hass.config.config_dir = config_dir

    if not is_virtual_env():
        await async_mount_local_lib_path(config_dir)

    async_enable_logging(hass, verbose, log_rotate_days, log_file,
                         log_no_color)

    await hass.async_add_executor_job(
        conf_util.process_ha_config_upgrade, hass)

    try:
        config_dict = await hass.async_add_executor_job(
            conf_util.load_yaml_config_file, config_path)
    except HomeAssistantError as err:
        _LOGGER.error("Error loading %s: %s", config_path, err)
        return None
    finally:
        clear_secret_cache()

    return await async_from_config_dict(
        config_dict, hass, enable_log=False, skip_pip=skip_pip)


@core.callback
def async_enable_logging(hass: core.HomeAssistant,
                         verbose: bool = False,
                         log_rotate_days: Optional[int] = None,
                         log_file: Optional[str] = None,
                         log_no_color: bool = False) -> None:
    """Set up the logging.

    This method must be run in the event loop.
    """
    fmt = ("%(asctime)s %(levelname)s (%(threadName)s) "
           "[%(name)s] %(message)s")
    datefmt = '%Y-%m-%d %H:%M:%S'

    if not log_no_color:
        try:
            from colorlog import ColoredFormatter
            # basicConfig must be called after importing colorlog in order to
            # ensure that the handlers it sets up wraps the correct streams.
            logging.basicConfig(level=logging.INFO)

            colorfmt = "%(log_color)s{}%(reset)s".format(fmt)
            logging.getLogger().handlers[0].setFormatter(ColoredFormatter(
                colorfmt,
                datefmt=datefmt,
                reset=True,
                log_colors={
                    'DEBUG': 'cyan',
                    'INFO': 'green',
                    'WARNING': 'yellow',
                    'ERROR': 'red',
                    'CRITICAL': 'red',
                }
            ))
        except ImportError:
            pass

    # If the above initialization failed for any reason, setup the default
    # formatting.  If the above succeeds, this wil result in a no-op.
    logging.basicConfig(format=fmt, datefmt=datefmt, level=logging.INFO)

    # Suppress overly verbose logs from libraries that aren't helpful
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('aiohttp.access').setLevel(logging.WARNING)

    # Log errors to a file if we have write access to file or config dir
    if log_file is None:
        err_log_path = hass.config.path(ERROR_LOG_FILENAME)
    else:
        err_log_path = os.path.abspath(log_file)

    err_path_exists = os.path.isfile(err_log_path)
    err_dir = os.path.dirname(err_log_path)

    # Check if we can write to the error log if it exists or that
    # we can create files in the containing directory if not.
    if (err_path_exists and os.access(err_log_path, os.W_OK)) or \
       (not err_path_exists and os.access(err_dir, os.W_OK)):

        if log_rotate_days:
            err_handler = logging.handlers.TimedRotatingFileHandler(
                err_log_path, when='midnight',
                backupCount=log_rotate_days)  # type: logging.FileHandler
        else:
            err_handler = logging.FileHandler(
                err_log_path, mode='w', delay=True)

        err_handler.setLevel(logging.INFO if verbose else logging.WARNING)
        err_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))

        async_handler = AsyncHandler(hass.loop, err_handler)

        async def async_stop_async_handler(_: Any) -> None:
            """Cleanup async handler."""
            logging.getLogger('').removeHandler(async_handler)  # type: ignore
            await async_handler.async_close(blocking=True)

        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_CLOSE, async_stop_async_handler)

        logger = logging.getLogger('')
        logger.addHandler(async_handler)  # type: ignore
        logger.setLevel(logging.INFO)

        # Save the log file location for access by other components.
        hass.data[DATA_LOGGING] = err_log_path
    else:
        _LOGGER.error(
            "Unable to set up error log %s (access denied)", err_log_path)


async def async_mount_local_lib_path(config_dir: str) -> str:
    """Add local library to Python Path.

    This function is a coroutine.
    """
    deps_dir = os.path.join(config_dir, 'deps')
    lib_dir = await async_get_user_site(deps_dir)
    if lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)
    return deps_dir


@core.callback
def _get_domains(hass: core.HomeAssistant, config: Dict[str, Any]) -> Set[str]:
    """Get domains of components to set up."""
    # Filter out the repeating and common config section [homeassistant]
    domains = set(key.split(' ')[0] for key in config.keys()
                  if key != core.DOMAIN)

    # Add config entry domains
    domains.update(hass.config_entries.async_domains())  # type: ignore

    # Make sure the Hass.io component is loaded
    if 'HASSIO' in os.environ:
        domains.add('hassio')

    return domains


async def _async_set_up_integrations(
        hass: core.HomeAssistant, config: Dict[str, Any]) -> None:
    """Set up all the integrations."""
    domains = _get_domains(hass, config)

    # Start up debuggers. Start these first in case they want to wait.
    debuggers = domains & DEBUGGER_INTEGRATIONS
    if debuggers:
        _LOGGER.debug("Starting up debuggers %s", debuggers)
        await asyncio.gather(*[
            async_setup_component(hass, domain, config)
            for domain in debuggers])
        domains -= DEBUGGER_INTEGRATIONS

    # Resolve all dependencies of all components so we can find the logging
    # and integrations that need faster initialization.
    resolved_domains_task = asyncio.gather(*[
        loader.async_component_dependencies(hass, domain)
        for domain in domains
    ], return_exceptions=True)

    # Set up core.
    _LOGGER.debug("Setting up %s", CORE_INTEGRATIONS)

    if not all(await asyncio.gather(*[
            async_setup_component(hass, domain, config)
            for domain in CORE_INTEGRATIONS
    ])):
        _LOGGER.error("Home Assistant core failed to initialize. "
                      "Further initialization aborted")
        return

    _LOGGER.debug("Home Assistant core initialized")

    # Finish resolving domains
    for dep_domains in await resolved_domains_task:
        # Result is either a set or an exception. We ignore exceptions
        # It will be properly handled during setup of the domain.
        if isinstance(dep_domains, set):
            domains.update(dep_domains)

    # setup components
    logging_domains = domains & LOGGING_INTEGRATIONS
    stage_1_domains = domains & STAGE_1_INTEGRATIONS
    stage_2_domains = domains - logging_domains - stage_1_domains

    if logging_domains:
        _LOGGER.info("Setting up %s", logging_domains)

        await asyncio.gather(*[
            async_setup_component(hass, domain, config)
            for domain in logging_domains
        ])

    # Kick off loading the registries. They don't need to be awaited.
    asyncio.gather(
        hass.helpers.device_registry.async_get_registry(),
        hass.helpers.entity_registry.async_get_registry(),
        hass.helpers.area_registry.async_get_registry())

    if stage_1_domains:
        await asyncio.gather(*[
            async_setup_component(hass, domain, config)
            for domain in stage_1_domains
        ])

    # Load all integrations
    after_dependencies = {}  # type: Dict[str, Set[str]]

    for int_or_exc in await asyncio.gather(*[
            loader.async_get_integration(hass, domain)
            for domain in stage_2_domains
    ], return_exceptions=True):
        # Exceptions are handled in async_setup_component.
        if (isinstance(int_or_exc, loader.Integration) and
                int_or_exc.after_dependencies):
            after_dependencies[int_or_exc.domain] = set(
                int_or_exc.after_dependencies
            )

    last_load = None
    while stage_2_domains:
        domains_to_load = set()

        for domain in stage_2_domains:
            after_deps = after_dependencies.get(domain)
            # Load if integration has no after_dependencies or they are
            # all loaded
            if (not after_deps or
                    not after_deps-hass.config.components):
                domains_to_load.add(domain)

        if not domains_to_load or domains_to_load == last_load:
            break

        _LOGGER.debug("Setting up %s", domains_to_load)

        await asyncio.gather(*[
            async_setup_component(hass, domain, config)
            for domain in domains_to_load
        ])

        last_load = domains_to_load
        stage_2_domains -= domains_to_load

    # These are stage 2 domains that never have their after_dependencies
    # satisfied.
    if stage_2_domains:
        _LOGGER.debug("Final set up: %s", stage_2_domains)

        await asyncio.gather(*[
            async_setup_component(hass, domain, config)
            for domain in stage_2_domains
        ])

    # Wrap up startup
    await hass.async_block_till_done()
