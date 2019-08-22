"""Helpers for components that manage entities."""
import asyncio
from datetime import timedelta
from itertools import chain
import logging

from homeassistant import config as conf_util
from homeassistant.setup import async_prepare_setup_platform
from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_SCAN_INTERVAL, CONF_ENTITY_NAMESPACE,
    ENTITY_MATCH_ALL)
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_per_platform, discovery
from homeassistant.helpers.service import async_extract_entity_ids
from homeassistant.loader import bind_hass, async_get_integration
from homeassistant.util import slugify
from .entity_platform import EntityPlatform

DEFAULT_SCAN_INTERVAL = timedelta(seconds=15)
DATA_INSTANCES = 'entity_components'


@bind_hass
async def async_update_entity(hass, entity_id):
    """Trigger an update for an entity."""
    domain = entity_id.split('.', 1)[0]
    entity_comp = hass.data.get(DATA_INSTANCES, {}).get(domain)

    if entity_comp is None:
        logging.getLogger(__name__).warning(
            'Forced update failed. Component for %s not loaded.', entity_id)
        return

    entity = entity_comp.get_entity(entity_id)

    if entity is None:
        logging.getLogger(__name__).warning(
            'Forced update failed. Entity %s not found.', entity_id)
        return

    await entity.async_update_ha_state(True)


class EntityComponent:
    """The EntityComponent manages platforms that manages entities.

    This class has the following responsibilities:
     - Process the configuration and set up a platform based component.
     - Manage the platforms and their entities.
     - Help extract the entities from a service call.
     - Maintain a group that tracks all platform entities.
     - Listen for discovery events for platforms related to the domain.
    """

    def __init__(self, logger, domain, hass,
                 scan_interval=DEFAULT_SCAN_INTERVAL, group_name=None):
        """Initialize an entity component."""
        self.logger = logger
        self.hass = hass
        self.domain = domain
        self.scan_interval = scan_interval
        self.group_name = group_name

        self.config = None

        self._platforms = {
            domain: self._async_init_entity_platform(domain, None)
        }
        self.async_add_entities = self._platforms[domain].async_add_entities
        self.add_entities = self._platforms[domain].add_entities

        hass.data.setdefault(DATA_INSTANCES, {})[domain] = self

    @property
    def entities(self):
        """Return an iterable that returns all entities."""
        return chain.from_iterable(platform.entities.values() for platform
                                   in self._platforms.values())

    def get_entity(self, entity_id):
        """Get an entity."""
        for platform in self._platforms.values():
            entity = platform.entities.get(entity_id)
            if entity is not None:
                return entity
        return None

    def setup(self, config):
        """Set up a full entity component.

        This doesn't block the executor to protect from deadlocks.
        """
        self.hass.add_job(self.async_setup(config))

    async def async_setup(self, config):
        """Set up a full entity component.

        Loads the platforms from the config and will listen for supported
        discovered platforms.

        This method must be run in the event loop.
        """
        self.config = config

        # Look in config for Domain, Domain 2, Domain 3 etc and load them
        tasks = []
        for p_type, p_config in config_per_platform(config, self.domain):
            tasks.append(self._async_setup_platform(p_type, p_config))

        if tasks:
            await asyncio.wait(tasks)

        # Generic discovery listener for loading platform dynamically
        # Refer to: homeassistant.components.discovery.load_platform()
        async def component_platform_discovered(platform, info):
            """Handle the loading of a platform."""
            await self._async_setup_platform(platform, {}, info)

        discovery.async_listen_platform(
            self.hass, self.domain, component_platform_discovered)

    async def async_setup_entry(self, config_entry):
        """Set up a config entry."""
        platform_type = config_entry.domain
        platform = await async_prepare_setup_platform(
            self.hass,
            # In future PR we should make hass_config part of the constructor
            # params.
            self.config or {},
            self.domain, platform_type)

        if platform is None:
            return False

        key = config_entry.entry_id

        if key in self._platforms:
            raise ValueError('Config entry has already been setup!')

        self._platforms[key] = self._async_init_entity_platform(
            platform_type, platform,
            scan_interval=getattr(platform, 'SCAN_INTERVAL', None),
        )

        return await self._platforms[key].async_setup_entry(config_entry)

    async def async_unload_entry(self, config_entry):
        """Unload a config entry."""
        key = config_entry.entry_id

        platform = self._platforms.pop(key, None)

        if platform is None:
            raise ValueError('Config entry was never loaded!')

        await platform.async_reset()
        return True

    async def async_extract_from_service(self, service, expand_group=True):
        """Extract all known and available entities from a service call.

        Will return all entities if no entities specified in call.
        Will return an empty list if entities specified but unknown.

        This method must be run in the event loop.
        """
        data_ent_id = service.data.get(ATTR_ENTITY_ID)

        if data_ent_id in (None, ENTITY_MATCH_ALL):
            if data_ent_id is None:
                self.logger.warning(
                    'Not passing an entity ID to a service to target all '
                    'entities is deprecated. Update your call to %s.%s to be '
                    'instead: entity_id: %s', service.domain, service.service,
                    ENTITY_MATCH_ALL)

            return [entity for entity in self.entities if entity.available]

        entity_ids = await async_extract_entity_ids(
            self.hass, service, expand_group)
        return [entity for entity in self.entities
                if entity.available and entity.entity_id in entity_ids]

    @callback
    def async_register_entity_service(self, name, schema, func,
                                      required_features=None):
        """Register an entity service."""
        async def handle_service(call):
            """Handle the service."""
            service_name = "{}.{}".format(self.domain, name)
            await self.hass.helpers.service.entity_service_call(
                self._platforms.values(), func, call, service_name,
                required_features
            )

        self.hass.services.async_register(
            self.domain, name, handle_service, schema)

    async def _async_setup_platform(self, platform_type, platform_config,
                                    discovery_info=None):
        """Set up a platform for this component."""
        platform = await async_prepare_setup_platform(
            self.hass, self.config, self.domain, platform_type)

        if platform is None:
            return

        # Use config scan interval, fallback to platform if none set
        scan_interval = platform_config.get(
            CONF_SCAN_INTERVAL, getattr(platform, 'SCAN_INTERVAL', None))
        entity_namespace = platform_config.get(CONF_ENTITY_NAMESPACE)

        key = (platform_type, scan_interval, entity_namespace)

        if key not in self._platforms:
            self._platforms[key] = self._async_init_entity_platform(
                platform_type, platform, scan_interval, entity_namespace
            )

        await self._platforms[key].async_setup(platform_config, discovery_info)

    @callback
    def _async_update_group(self):
        """Set up and/or update component group.

        This method must be run in the event loop.
        """
        if self.group_name is None:
            return

        ids = [entity.entity_id for entity in
               sorted(self.entities,
                      key=lambda entity: entity.name or entity.entity_id)]

        self.hass.async_create_task(
            self.hass.services.async_call(
                'group', 'set', dict(
                    object_id=slugify(self.group_name),
                    name=self.group_name,
                    visible=False,
                    entities=ids)))

    async def _async_reset(self):
        """Remove entities and reset the entity component to initial values.

        This method must be run in the event loop.
        """
        tasks = [platform.async_reset() for platform
                 in self._platforms.values()]

        if tasks:
            await asyncio.wait(tasks)

        self._platforms = {
            self.domain: self._platforms[self.domain]
        }
        self.config = None

        if self.group_name is not None:
            await self.hass.services.async_call(
                'group', 'remove', dict(
                    object_id=slugify(self.group_name)))

    async def async_remove_entity(self, entity_id):
        """Remove an entity managed by one of the platforms."""
        for platform in self._platforms.values():
            if entity_id in platform.entities:
                await platform.async_remove_entity(entity_id)

    async def async_prepare_reload(self):
        """Prepare reloading this entity component.

        This method must be run in the event loop.
        """
        try:
            conf = await \
                conf_util.async_hass_config_yaml(self.hass)
        except HomeAssistantError as err:
            self.logger.error(err)
            return None

        integration = await async_get_integration(self.hass, self.domain)

        conf = await conf_util.async_process_component_config(
            self.hass, conf, integration)

        if conf is None:
            return None

        await self._async_reset()
        return conf

    def _async_init_entity_platform(self, platform_type, platform,
                                    scan_interval=None, entity_namespace=None):
        """Initialize an entity platform."""
        if scan_interval is None:
            scan_interval = self.scan_interval

        return EntityPlatform(
            hass=self.hass,
            logger=self.logger,
            domain=self.domain,
            platform_name=platform_type,
            platform=platform,
            scan_interval=scan_interval,
            entity_namespace=entity_namespace,
            async_entities_added_callback=self._async_update_group,
        )
