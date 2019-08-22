"""Module to help with parsing and generating configuration files."""
from collections import OrderedDict
# pylint: disable=no-name-in-module
from distutils.version import LooseVersion  # pylint: disable=import-error
import logging
import os
import re
import shutil
from typing import (  # noqa: F401 pylint: disable=unused-import
    Any, Tuple, Optional, Dict, List, Union, Callable, Sequence, Set)
from types import ModuleType
import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant import auth
from homeassistant.auth import providers as auth_providers,\
    mfa_modules as auth_mfa_modules
from homeassistant.const import (
    ATTR_FRIENDLY_NAME, ATTR_HIDDEN, ATTR_ASSUMED_STATE,
    CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME, CONF_PACKAGES, CONF_UNIT_SYSTEM,
    CONF_TIME_ZONE, CONF_ELEVATION,
    CONF_UNIT_SYSTEM_IMPERIAL, CONF_TEMPERATURE_UNIT, TEMP_CELSIUS,
    __version__, CONF_CUSTOMIZE, CONF_CUSTOMIZE_DOMAIN, CONF_CUSTOMIZE_GLOB,
    CONF_WHITELIST_EXTERNAL_DIRS, CONF_AUTH_PROVIDERS, CONF_AUTH_MFA_MODULES,
    CONF_TYPE, CONF_ID)
from homeassistant.core import (
    DOMAIN as CONF_CORE, SOURCE_YAML, HomeAssistant,
    callback)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.loader import (
    Integration, async_get_integration, IntegrationNotFound
)
from homeassistant.util.yaml import load_yaml, SECRET_YAML
from homeassistant.util.package import is_docker_env
import homeassistant.helpers.config_validation as cv
from homeassistant.util.unit_system import IMPERIAL_SYSTEM, METRIC_SYSTEM
from homeassistant.helpers.entity_values import EntityValues
from homeassistant.helpers import config_per_platform, extract_domain_configs

_LOGGER = logging.getLogger(__name__)

DATA_PERSISTENT_ERRORS = 'bootstrap_persistent_errors'
RE_YAML_ERROR = re.compile(r"homeassistant\.util\.yaml")
RE_ASCII = re.compile(r"\033\[[^m]*m")
HA_COMPONENT_URL = '[{}](https://home-assistant.io/components/{}/)'
YAML_CONFIG_FILE = 'configuration.yaml'
VERSION_FILE = '.HA_VERSION'
CONFIG_DIR_NAME = '.homeassistant'
DATA_CUSTOMIZE = 'hass_customize'

FILE_MIGRATION = (
    ('ios.conf', '.ios.conf'),
)

DEFAULT_CONFIG = """
# Configure a default setup of Home Assistant (frontend, api, etc)
default_config:

# Uncomment this if you are using SSL/TLS, running in Docker container, etc.
# http:
#   base_url: example.duckdns.org:8123

# Text to speech
tts:
  - platform: google_translate

group: !include groups.yaml
automation: !include automations.yaml
script: !include scripts.yaml
"""
DEFAULT_SECRETS = """
# Use this file to store secrets like usernames and passwords.
# Learn more at https://home-assistant.io/docs/configuration/secrets/
some_password: welcome
"""
TTS_PRE_92 = """
tts:
  - platform: google
"""
TTS_92 = """
tts:
  - platform: google_translate
    service_name: google_say
"""


def _no_duplicate_auth_provider(configs: Sequence[Dict[str, Any]]) \
        -> Sequence[Dict[str, Any]]:
    """No duplicate auth provider config allowed in a list.

    Each type of auth provider can only have one config without optional id.
    Unique id is required if same type of auth provider used multiple times.
    """
    config_keys = set()  # type: Set[Tuple[str, Optional[str]]]
    for config in configs:
        key = (config[CONF_TYPE], config.get(CONF_ID))
        if key in config_keys:
            raise vol.Invalid(
                'Duplicate auth provider {} found. Please add unique IDs if '
                'you want to have the same auth provider twice'.format(
                    config[CONF_TYPE]
                ))
        config_keys.add(key)
    return configs


def _no_duplicate_auth_mfa_module(configs: Sequence[Dict[str, Any]]) \
        -> Sequence[Dict[str, Any]]:
    """No duplicate auth mfa module item allowed in a list.

    Each type of mfa module can only have one config without optional id.
    A global unique id is required if same type of mfa module used multiple
    times.
    Note: this is different than auth provider
    """
    config_keys = set()  # type: Set[str]
    for config in configs:
        key = config.get(CONF_ID, config[CONF_TYPE])
        if key in config_keys:
            raise vol.Invalid(
                'Duplicate mfa module {} found. Please add unique IDs if '
                'you want to have the same mfa module twice'.format(
                    config[CONF_TYPE]
                ))
        config_keys.add(key)
    return configs


PACKAGES_CONFIG_SCHEMA = cv.schema_with_slug_keys(  # Package names are slugs
    vol.Schema({cv.string: vol.Any(dict, list, None)})  # Component config
)

CUSTOMIZE_DICT_SCHEMA = vol.Schema({
    vol.Optional(ATTR_FRIENDLY_NAME): cv.string,
    vol.Optional(ATTR_HIDDEN): cv.boolean,
    vol.Optional(ATTR_ASSUMED_STATE): cv.boolean,
}, extra=vol.ALLOW_EXTRA)

CUSTOMIZE_CONFIG_SCHEMA = vol.Schema({
    vol.Optional(CONF_CUSTOMIZE, default={}):
        vol.Schema({cv.entity_id: CUSTOMIZE_DICT_SCHEMA}),
    vol.Optional(CONF_CUSTOMIZE_DOMAIN, default={}):
        vol.Schema({cv.string: CUSTOMIZE_DICT_SCHEMA}),
    vol.Optional(CONF_CUSTOMIZE_GLOB, default={}):
        vol.Schema({cv.string: CUSTOMIZE_DICT_SCHEMA}),
})

CORE_CONFIG_SCHEMA = CUSTOMIZE_CONFIG_SCHEMA.extend({
    CONF_NAME: vol.Coerce(str),
    CONF_LATITUDE: cv.latitude,
    CONF_LONGITUDE: cv.longitude,
    CONF_ELEVATION: vol.Coerce(int),
    vol.Optional(CONF_TEMPERATURE_UNIT): cv.temperature_unit,
    CONF_UNIT_SYSTEM: cv.unit_system,
    CONF_TIME_ZONE: cv.time_zone,
    vol.Optional(CONF_WHITELIST_EXTERNAL_DIRS):
        # pylint: disable=no-value-for-parameter
        vol.All(cv.ensure_list, [vol.IsDir()]),
    vol.Optional(CONF_PACKAGES, default={}): PACKAGES_CONFIG_SCHEMA,
    vol.Optional(CONF_AUTH_PROVIDERS):
        vol.All(cv.ensure_list,
                [auth_providers.AUTH_PROVIDER_SCHEMA.extend({
                    CONF_TYPE: vol.NotIn(['insecure_example'],
                                         'The insecure_example auth provider'
                                         ' is for testing only.')
                })],
                _no_duplicate_auth_provider),
    vol.Optional(CONF_AUTH_MFA_MODULES):
        vol.All(cv.ensure_list,
                [auth_mfa_modules.MULTI_FACTOR_AUTH_MODULE_SCHEMA.extend({
                    CONF_TYPE: vol.NotIn(['insecure_example'],
                                         'The insecure_example mfa module'
                                         ' is for testing only.')
                })],
                _no_duplicate_auth_mfa_module),
})


def get_default_config_dir() -> str:
    """Put together the default configuration directory based on the OS."""
    data_dir = os.getenv('APPDATA') if os.name == "nt" \
        else os.path.expanduser('~')
    return os.path.join(data_dir, CONFIG_DIR_NAME)  # type: ignore


async def async_ensure_config_exists(hass: HomeAssistant, config_dir: str) \
        -> Optional[str]:
    """Ensure a configuration file exists in given configuration directory.

    Creating a default one if needed.
    Return path to the configuration file.
    """
    config_path = find_config_file(config_dir)

    if config_path is None:
        print("Unable to find configuration. Creating default one in",
              config_dir)
        config_path = await async_create_default_config(hass, config_dir)

    return config_path


async def async_create_default_config(hass: HomeAssistant, config_dir: str) \
        -> Optional[str]:
    """Create a default configuration file in given configuration directory.

    Return path to new config file if success, None if failed.
    This method needs to run in an executor.
    """
    return await hass.async_add_executor_job(_write_default_config, config_dir)


def _write_default_config(config_dir: str)\
        -> Optional[str]:
    """Write the default config."""
    from homeassistant.components.config.group import (
        CONFIG_PATH as GROUP_CONFIG_PATH)
    from homeassistant.components.config.automation import (
        CONFIG_PATH as AUTOMATION_CONFIG_PATH)
    from homeassistant.components.config.script import (
        CONFIG_PATH as SCRIPT_CONFIG_PATH)

    config_path = os.path.join(config_dir, YAML_CONFIG_FILE)
    secret_path = os.path.join(config_dir, SECRET_YAML)
    version_path = os.path.join(config_dir, VERSION_FILE)
    group_yaml_path = os.path.join(config_dir, GROUP_CONFIG_PATH)
    automation_yaml_path = os.path.join(config_dir, AUTOMATION_CONFIG_PATH)
    script_yaml_path = os.path.join(config_dir, SCRIPT_CONFIG_PATH)

    # Writing files with YAML does not create the most human readable results
    # So we're hard coding a YAML template.
    try:
        with open(config_path, 'wt') as config_file:
            config_file.write(DEFAULT_CONFIG)

        with open(secret_path, 'wt') as secret_file:
            secret_file.write(DEFAULT_SECRETS)

        with open(version_path, 'wt') as version_file:
            version_file.write(__version__)

        with open(group_yaml_path, 'wt'):
            pass

        with open(automation_yaml_path, 'wt') as fil:
            fil.write('[]')

        with open(script_yaml_path, 'wt'):
            pass

        return config_path

    except IOError:
        print("Unable to create default configuration file", config_path)
        return None


async def async_hass_config_yaml(hass: HomeAssistant) -> Dict:
    """Load YAML from a Home Assistant configuration file.

    This function allow a component inside the asyncio loop to reload its
    configuration by itself. Include package merge.

    This method is a coroutine.
    """
    def _load_hass_yaml_config() -> Dict:
        path = find_config_file(hass.config.config_dir)
        if path is None:
            raise HomeAssistantError(
                "Config file not found in: {}".format(hass.config.config_dir))
        config = load_yaml_config_file(path)
        return config

    config = await hass.async_add_executor_job(_load_hass_yaml_config)
    core_config = config.get(CONF_CORE, {})
    await merge_packages_config(
        hass, config, core_config.get(CONF_PACKAGES, {})
    )
    return config


def find_config_file(config_dir: Optional[str]) -> Optional[str]:
    """Look in given directory for supported configuration files."""
    if config_dir is None:
        return None
    config_path = os.path.join(config_dir, YAML_CONFIG_FILE)

    return config_path if os.path.isfile(config_path) else None


def load_yaml_config_file(config_path: str) -> Dict[Any, Any]:
    """Parse a YAML configuration file.

    Raises FileNotFoundError or HomeAssistantError.

    This method needs to run in an executor.
    """
    conf_dict = load_yaml(config_path)

    if not isinstance(conf_dict, dict):
        msg = "The configuration file {} does not contain a dictionary".format(
            os.path.basename(config_path))
        _LOGGER.error(msg)
        raise HomeAssistantError(msg)

    # Convert values to dictionaries if they are None
    for key, value in conf_dict.items():
        conf_dict[key] = value or {}
    return conf_dict


def process_ha_config_upgrade(hass: HomeAssistant) -> None:
    """Upgrade configuration if necessary.

    This method needs to run in an executor.
    """
    version_path = hass.config.path(VERSION_FILE)

    try:
        with open(version_path, 'rt') as inp:
            conf_version = inp.readline().strip()
    except FileNotFoundError:
        # Last version to not have this file
        conf_version = '0.7.7'

    if conf_version == __version__:
        return

    _LOGGER.info("Upgrading configuration directory from %s to %s",
                 conf_version, __version__)

    version_obj = LooseVersion(conf_version)

    if version_obj < LooseVersion('0.50'):
        # 0.50 introduced persistent deps dir.
        lib_path = hass.config.path('deps')
        if os.path.isdir(lib_path):
            shutil.rmtree(lib_path)

    if version_obj < LooseVersion('0.92'):
        # 0.92 moved google/tts.py to google_translate/tts.py
        config_path = find_config_file(hass.config.config_dir)
        assert config_path is not None

        with open(config_path, 'rt', encoding='utf-8') as config_file:
            config_raw = config_file.read()

        if TTS_PRE_92 in config_raw:
            _LOGGER.info("Migrating google tts to google_translate tts")
            config_raw = config_raw.replace(TTS_PRE_92, TTS_92)
            try:
                with open(config_path, 'wt', encoding='utf-8') as config_file:
                    config_file.write(config_raw)
            except IOError:
                _LOGGER.exception("Migrating to google_translate tts failed")
                pass

    if version_obj < LooseVersion('0.94') and is_docker_env():
        # In 0.94 we no longer install packages inside the deps folder when
        # running inside a Docker container.
        lib_path = hass.config.path('deps')
        if os.path.isdir(lib_path):
            shutil.rmtree(lib_path)

    with open(version_path, 'wt') as outp:
        outp.write(__version__)

    _LOGGER.debug("Migrating old system configuration files to new locations")
    for oldf, newf in FILE_MIGRATION:
        if os.path.isfile(hass.config.path(oldf)):
            _LOGGER.info("Migrating %s to %s", oldf, newf)
            os.rename(hass.config.path(oldf), hass.config.path(newf))


@callback
def async_log_exception(ex: vol.Invalid, domain: str, config: Dict,
                        hass: HomeAssistant) -> None:
    """Log an error for configuration validation.

    This method must be run in the event loop.
    """
    if hass is not None:
        async_notify_setup_error(hass, domain, True)
    _LOGGER.error(_format_config_error(ex, domain, config))


@callback
def _format_config_error(ex: vol.Invalid, domain: str, config: Dict) -> str:
    """Generate log exception for configuration validation.

    This method must be run in the event loop.
    """
    message = "Invalid config for [{}]: ".format(domain)
    if 'extra keys not allowed' in ex.error_message:
        message += '[{option}] is an invalid option for [{domain}]. ' \
            'Check: {domain}->{path}.'.format(
                option=ex.path[-1], domain=domain,
                path='->'.join(str(m) for m in ex.path))
    else:
        message += '{}.'.format(humanize_error(config, ex))

    try:
        domain_config = config.get(domain, config)
    except AttributeError:
        domain_config = config

    message += " (See {}, line {}). ".format(
        getattr(domain_config, '__config_file__', '?'),
        getattr(domain_config, '__line__', '?'))

    if domain != CONF_CORE:
        message += ('Please check the docs at '
                    'https://home-assistant.io/components/{}/'.format(domain))

    return message


async def async_process_ha_core_config(
        hass: HomeAssistant, config: Dict,
        api_password: Optional[str] = None,
        trusted_networks: Optional[Any] = None) -> None:
    """Process the [homeassistant] section from the configuration.

    This method is a coroutine.
    """
    config = CORE_CONFIG_SCHEMA(config)

    # Only load auth during startup.
    if not hasattr(hass, 'auth'):
        auth_conf = config.get(CONF_AUTH_PROVIDERS)

        if auth_conf is None:
            auth_conf = [
                {'type': 'homeassistant'}
            ]
            if api_password:
                auth_conf.append({
                    'type': 'legacy_api_password',
                    'api_password': api_password,
                })
            if trusted_networks:
                auth_conf.append({
                    'type': 'trusted_networks',
                    'trusted_networks': trusted_networks,
                })

        mfa_conf = config.get(CONF_AUTH_MFA_MODULES, [
            {'type': 'totp', 'id': 'totp', 'name': 'Authenticator app'},
        ])

        setattr(hass, 'auth', await auth.auth_manager_from_config(
            hass,
            auth_conf,
            mfa_conf))

    await hass.config.async_load()

    hac = hass.config

    if any([k in config for k in [
            CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME, CONF_ELEVATION,
            CONF_TIME_ZONE, CONF_UNIT_SYSTEM]]):
        hac.config_source = SOURCE_YAML

    for key, attr in ((CONF_LATITUDE, 'latitude'),
                      (CONF_LONGITUDE, 'longitude'),
                      (CONF_NAME, 'location_name'),
                      (CONF_ELEVATION, 'elevation')):
        if key in config:
            setattr(hac, attr, config[key])

    if CONF_TIME_ZONE in config:
        hac.set_time_zone(config[CONF_TIME_ZONE])

    # Init whitelist external dir
    hac.whitelist_external_dirs = {hass.config.path('www')}
    if CONF_WHITELIST_EXTERNAL_DIRS in config:
        hac.whitelist_external_dirs.update(
            set(config[CONF_WHITELIST_EXTERNAL_DIRS]))

    # Customize
    cust_exact = dict(config[CONF_CUSTOMIZE])
    cust_domain = dict(config[CONF_CUSTOMIZE_DOMAIN])
    cust_glob = OrderedDict(config[CONF_CUSTOMIZE_GLOB])

    for name, pkg in config[CONF_PACKAGES].items():
        pkg_cust = pkg.get(CONF_CORE)

        if pkg_cust is None:
            continue

        try:
            pkg_cust = CUSTOMIZE_CONFIG_SCHEMA(pkg_cust)
        except vol.Invalid:
            _LOGGER.warning("Package %s contains invalid customize", name)
            continue

        cust_exact.update(pkg_cust[CONF_CUSTOMIZE])
        cust_domain.update(pkg_cust[CONF_CUSTOMIZE_DOMAIN])
        cust_glob.update(pkg_cust[CONF_CUSTOMIZE_GLOB])

    hass.data[DATA_CUSTOMIZE] = \
        EntityValues(cust_exact, cust_domain, cust_glob)

    if CONF_UNIT_SYSTEM in config:
        if config[CONF_UNIT_SYSTEM] == CONF_UNIT_SYSTEM_IMPERIAL:
            hac.units = IMPERIAL_SYSTEM
        else:
            hac.units = METRIC_SYSTEM
    elif CONF_TEMPERATURE_UNIT in config:
        unit = config[CONF_TEMPERATURE_UNIT]
        if unit == TEMP_CELSIUS:
            hac.units = METRIC_SYSTEM
        else:
            hac.units = IMPERIAL_SYSTEM
        _LOGGER.warning("Found deprecated temperature unit in core "
                        "configuration expected unit system. Replace '%s: %s' "
                        "with '%s: %s'", CONF_TEMPERATURE_UNIT, unit,
                        CONF_UNIT_SYSTEM, hac.units.name)


def _log_pkg_error(
        package: str, component: str, config: Dict, message: str) -> None:
    """Log an error while merging packages."""
    message = "Package {} setup failed. Component {} {}".format(
        package, component, message)

    pack_config = config[CONF_CORE][CONF_PACKAGES].get(package, config)
    message += " (See {}:{}). ".format(
        getattr(pack_config, '__config_file__', '?'),
        getattr(pack_config, '__line__', '?'))

    _LOGGER.error(message)


def _identify_config_schema(module: ModuleType) -> \
        Tuple[Optional[str], Optional[Dict]]:
    """Extract the schema and identify list or dict based."""
    try:
        schema = module.CONFIG_SCHEMA.schema[module.DOMAIN]  # type: ignore
    except (AttributeError, KeyError):
        return None, None
    t_schema = str(schema)
    if t_schema.startswith('{') or 'schema_with_slug_keys' in t_schema:
        return ('dict', schema)
    if t_schema.startswith(('[', 'All(<function ensure_list')):
        return ('list', schema)
    return '', schema


def _recursive_merge(
        conf: Dict[str, Any], package: Dict[str, Any]) -> Union[bool, str]:
    """Merge package into conf, recursively."""
    error = False  # type: Union[bool, str]
    for key, pack_conf in package.items():
        if isinstance(pack_conf, dict):
            if not pack_conf:
                continue
            conf[key] = conf.get(key, OrderedDict())
            error = _recursive_merge(conf=conf[key], package=pack_conf)

        elif isinstance(pack_conf, list):
            if not pack_conf:
                continue
            conf[key] = cv.ensure_list(conf.get(key))
            conf[key].extend(cv.ensure_list(pack_conf))

        else:
            if conf.get(key) is not None:
                return key
            conf[key] = pack_conf
    return error


async def merge_packages_config(hass: HomeAssistant, config: Dict,
                                packages: Dict,
                                _log_pkg_error: Callable = _log_pkg_error) \
        -> Dict:
    """Merge packages into the top-level configuration. Mutate config."""
    # pylint: disable=too-many-nested-blocks
    PACKAGES_CONFIG_SCHEMA(packages)
    for pack_name, pack_conf in packages.items():
        for comp_name, comp_conf in pack_conf.items():
            if comp_name == CONF_CORE:
                continue
            # If component name is given with a trailing description, remove it
            # when looking for component
            domain = comp_name.split(' ')[0]

            try:
                integration = await async_get_integration(hass, domain)
            except IntegrationNotFound:
                _log_pkg_error(pack_name, comp_name, config, "does not exist")
                continue

            try:
                component = integration.get_component()
            except ImportError:
                _log_pkg_error(pack_name, comp_name, config,
                               "unable to import")
                continue

            if hasattr(component, 'PLATFORM_SCHEMA'):
                if not comp_conf:
                    continue  # Ensure we dont add Falsy items to list
                config[comp_name] = cv.ensure_list(config.get(comp_name))
                config[comp_name].extend(cv.ensure_list(comp_conf))
                continue

            if hasattr(component, 'CONFIG_SCHEMA'):
                merge_type, _ = _identify_config_schema(component)

                if merge_type == 'list':
                    if not comp_conf:
                        continue  # Ensure we dont add Falsy items to list
                    config[comp_name] = cv.ensure_list(config.get(comp_name))
                    config[comp_name].extend(cv.ensure_list(comp_conf))
                    continue

            if comp_conf is None:
                comp_conf = OrderedDict()

            if not isinstance(comp_conf, dict):
                _log_pkg_error(
                    pack_name, comp_name, config,
                    "cannot be merged. Expected a dict.")
                continue

            if comp_name not in config or config[comp_name] is None:
                config[comp_name] = OrderedDict()

            if not isinstance(config[comp_name], dict):
                _log_pkg_error(
                    pack_name, comp_name, config,
                    "cannot be merged. Dict expected in main config.")
                continue
            if not isinstance(comp_conf, dict):
                _log_pkg_error(
                    pack_name, comp_name, config,
                    "cannot be merged. Dict expected in package.")
                continue

            error = _recursive_merge(conf=config[comp_name],
                                     package=comp_conf)
            if error:
                _log_pkg_error(pack_name, comp_name, config,
                               "has duplicate key '{}'".format(error))

    return config


async def async_process_component_config(
        hass: HomeAssistant, config: Dict, integration: Integration) \
            -> Optional[Dict]:
    """Check component configuration and return processed configuration.

    Returns None on error.

    This method must be run in the event loop.
    """
    domain = integration.domain
    try:
        component = integration.get_component()
    except ImportError as ex:
        _LOGGER.error("Unable to import %s: %s", domain, ex)
        return None

    if hasattr(component, 'CONFIG_SCHEMA'):
        try:
            return component.CONFIG_SCHEMA(config)  # type: ignore
        except vol.Invalid as ex:
            async_log_exception(ex, domain, config, hass)
            return None

    component_platform_schema = getattr(
        component, 'PLATFORM_SCHEMA_BASE',
        getattr(component, 'PLATFORM_SCHEMA', None))

    if component_platform_schema is None:
        return config

    platforms = []
    for p_name, p_config in config_per_platform(config, domain):
        # Validate component specific platform schema
        try:
            p_validated = component_platform_schema(p_config)
        except vol.Invalid as ex:
            async_log_exception(ex, domain, p_config, hass)
            continue

        # Not all platform components follow same pattern for platforms
        # So if p_name is None we are not going to validate platform
        # (the automation component is one of them)
        if p_name is None:
            platforms.append(p_validated)
            continue

        try:
            p_integration = await async_get_integration(hass, p_name)
            platform = p_integration.get_platform(domain)
        except (IntegrationNotFound, ImportError):
            continue

        # Validate platform specific schema
        if hasattr(platform, 'PLATFORM_SCHEMA'):
            # pylint: disable=no-member
            try:
                p_validated = platform.PLATFORM_SCHEMA(  # type: ignore
                    p_config)
            except vol.Invalid as ex:
                async_log_exception(ex, '{}.{}'.format(domain, p_name),
                                    p_config, hass)
                continue

        platforms.append(p_validated)

    # Create a copy of the configuration with all config for current
    # component removed and add validated config back in.
    config = config_without_domain(config, domain)
    config[domain] = platforms

    return config


@callback
def config_without_domain(config: Dict, domain: str) -> Dict:
    """Return a config with all configuration for a domain removed."""
    filter_keys = extract_domain_configs(config, domain)
    return {
        key: value for key, value in config.items()
        if key not in filter_keys
    }


async def async_check_ha_config_file(hass: HomeAssistant) -> Optional[str]:
    """Check if Home Assistant configuration file is valid.

    This method is a coroutine.
    """
    from homeassistant.scripts.check_config import check_ha_config_file

    res = await check_ha_config_file(hass)  # type: ignore

    if not res.errors:
        return None
    return '\n'.join([err.message for err in res.errors])


@callback
def async_notify_setup_error(
        hass: HomeAssistant, component: str,
        display_link: bool = False) -> None:
    """Print a persistent notification.

    This method must be run in the event loop.
    """
    from homeassistant.components import persistent_notification

    errors = hass.data.get(DATA_PERSISTENT_ERRORS)

    if errors is None:
        errors = hass.data[DATA_PERSISTENT_ERRORS] = {}

    errors[component] = errors.get(component) or display_link

    message = 'The following components and platforms could not be set up:\n\n'

    for name, link in errors.items():
        if link:
            part = HA_COMPONENT_URL.format(name.replace('_', '-'), name)
        else:
            part = name

        message += ' - {}\n'.format(part)

    message += '\nPlease check your config.'

    persistent_notification.async_create(
        hass, message, 'Invalid config', 'invalid_config')
