"""Provide the functionality to group entities."""
import asyncio
import logging

import voluptuous as vol

from homeassistant import core as ha
from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_ICON, CONF_NAME, STATE_CLOSED, STATE_HOME,
    STATE_NOT_HOME, STATE_OFF, STATE_ON, STATE_OPEN, STATE_LOCKED,
    STATE_UNLOCKED, STATE_OK, STATE_PROBLEM, STATE_UNKNOWN,
    ATTR_ASSUMED_STATE, SERVICE_RELOAD, ATTR_NAME, ATTR_ICON)
from homeassistant.core import callback
from homeassistant.loader import bind_hass
from homeassistant.helpers.entity import Entity, async_generate_entity_id
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.event import async_track_state_change
import homeassistant.helpers.config_validation as cv
from homeassistant.util.async_ import run_coroutine_threadsafe

from .reproduce_state import async_reproduce_states  # noqa

DOMAIN = 'group'

ENTITY_ID_FORMAT = DOMAIN + '.{}'

CONF_ENTITIES = 'entities'
CONF_VIEW = 'view'
CONF_CONTROL = 'control'
CONF_ALL = 'all'

ATTR_ADD_ENTITIES = 'add_entities'
ATTR_AUTO = 'auto'
ATTR_CONTROL = 'control'
ATTR_ENTITIES = 'entities'
ATTR_OBJECT_ID = 'object_id'
ATTR_ORDER = 'order'
ATTR_VIEW = 'view'
ATTR_VISIBLE = 'visible'
ATTR_ALL = 'all'

SERVICE_SET_VISIBILITY = 'set_visibility'
SERVICE_SET = 'set'
SERVICE_REMOVE = 'remove'

CONTROL_TYPES = vol.In(['hidden', None])

SET_VISIBILITY_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.comp_entity_ids,
    vol.Required(ATTR_VISIBLE): cv.boolean
})

RELOAD_SERVICE_SCHEMA = vol.Schema({})

SET_SERVICE_SCHEMA = vol.Schema({
    vol.Required(ATTR_OBJECT_ID): cv.slug,
    vol.Optional(ATTR_NAME): cv.string,
    vol.Optional(ATTR_VIEW): cv.boolean,
    vol.Optional(ATTR_ICON): cv.string,
    vol.Optional(ATTR_CONTROL): CONTROL_TYPES,
    vol.Optional(ATTR_VISIBLE): cv.boolean,
    vol.Optional(ATTR_ALL): cv.boolean,
    vol.Exclusive(ATTR_ENTITIES, 'entities'): cv.entity_ids,
    vol.Exclusive(ATTR_ADD_ENTITIES, 'entities'): cv.entity_ids,
})

REMOVE_SERVICE_SCHEMA = vol.Schema({
    vol.Required(ATTR_OBJECT_ID): cv.slug,
})

_LOGGER = logging.getLogger(__name__)


def _conf_preprocess(value):
    """Preprocess alternative configuration formats."""
    if not isinstance(value, dict):
        value = {CONF_ENTITIES: value}

    return value


GROUP_SCHEMA = vol.Schema({
    vol.Optional(CONF_ENTITIES): vol.Any(cv.entity_ids, None),
    CONF_VIEW: cv.boolean,
    CONF_NAME: cv.string,
    CONF_ICON: cv.icon,
    CONF_CONTROL: CONTROL_TYPES,
    CONF_ALL: cv.boolean,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({cv.match_all: vol.All(_conf_preprocess, GROUP_SCHEMA)})
}, extra=vol.ALLOW_EXTRA)

# List of ON/OFF state tuples for groupable states
_GROUP_TYPES = [(STATE_ON, STATE_OFF), (STATE_HOME, STATE_NOT_HOME),
                (STATE_OPEN, STATE_CLOSED), (STATE_LOCKED, STATE_UNLOCKED),
                (STATE_PROBLEM, STATE_OK)]


def _get_group_on_off(state):
    """Determine the group on/off states based on a state."""
    for states in _GROUP_TYPES:
        if state in states:
            return states

    return None, None


@bind_hass
def is_on(hass, entity_id):
    """Test if the group state is in its ON-state."""
    state = hass.states.get(entity_id)

    if state:
        group_on, _ = _get_group_on_off(state.state)

        # If we found a group_type, compare to ON-state
        return group_on is not None and state.state == group_on

    return False


@bind_hass
def expand_entity_ids(hass, entity_ids):
    """Return entity_ids with group entity ids replaced by their members.

    Async friendly.
    """
    found_ids = []
    for entity_id in entity_ids:
        if not isinstance(entity_id, str):
            continue

        entity_id = entity_id.lower()

        try:
            # If entity_id points at a group, expand it
            domain, _ = ha.split_entity_id(entity_id)

            if domain == DOMAIN:
                child_entities = get_entity_ids(hass, entity_id)
                if entity_id in child_entities:
                    child_entities = list(child_entities)
                    child_entities.remove(entity_id)
                found_ids.extend(
                    ent_id for ent_id
                    in expand_entity_ids(hass, child_entities)
                    if ent_id not in found_ids)

            else:
                if entity_id not in found_ids:
                    found_ids.append(entity_id)

        except AttributeError:
            # Raised by split_entity_id if entity_id is not a string
            pass

    return found_ids


@bind_hass
def get_entity_ids(hass, entity_id, domain_filter=None):
    """Get members of this group.

    Async friendly.
    """
    group = hass.states.get(entity_id)

    if not group or ATTR_ENTITY_ID not in group.attributes:
        return []

    entity_ids = group.attributes[ATTR_ENTITY_ID]
    if not domain_filter:
        return entity_ids

    domain_filter = domain_filter.lower() + '.'

    return [ent_id for ent_id in entity_ids
            if ent_id.startswith(domain_filter)]


async def async_setup(hass, config):
    """Set up all groups found defined in the configuration."""
    component = hass.data.get(DOMAIN)

    if component is None:
        component = hass.data[DOMAIN] = EntityComponent(_LOGGER, DOMAIN, hass)

    await _async_process_config(hass, config, component)

    async def reload_service_handler(service):
        """Remove all user-defined groups and load new ones from config."""
        auto = list(filter(lambda e: not e.user_defined, component.entities))

        conf = await component.async_prepare_reload()
        if conf is None:
            return
        await _async_process_config(hass, conf, component)

        await component.async_add_entities(auto)

    hass.services.async_register(
        DOMAIN, SERVICE_RELOAD, reload_service_handler,
        schema=RELOAD_SERVICE_SCHEMA)

    service_lock = asyncio.Lock()

    async def locked_service_handler(service):
        """Handle a service with an async lock."""
        async with service_lock:
            await groups_service_handler(service)

    async def groups_service_handler(service):
        """Handle dynamic group service functions."""
        object_id = service.data[ATTR_OBJECT_ID]
        entity_id = ENTITY_ID_FORMAT.format(object_id)
        group = component.get_entity(entity_id)

        # new group
        if service.service == SERVICE_SET and group is None:
            entity_ids = service.data.get(ATTR_ENTITIES) or \
                service.data.get(ATTR_ADD_ENTITIES) or None

            extra_arg = {attr: service.data[attr] for attr in (
                ATTR_VISIBLE, ATTR_ICON, ATTR_VIEW, ATTR_CONTROL
            ) if service.data.get(attr) is not None}

            await Group.async_create_group(
                hass, service.data.get(ATTR_NAME, object_id),
                object_id=object_id,
                entity_ids=entity_ids,
                user_defined=False,
                mode=service.data.get(ATTR_ALL),
                **extra_arg
            )
            return

        if group is None:
            _LOGGER.warning("%s:Group '%s' doesn't exist!",
                            service.service, object_id)
            return

        # update group
        if service.service == SERVICE_SET:
            need_update = False

            if ATTR_ADD_ENTITIES in service.data:
                delta = service.data[ATTR_ADD_ENTITIES]
                entity_ids = set(group.tracking) | set(delta)
                await group.async_update_tracked_entity_ids(entity_ids)

            if ATTR_ENTITIES in service.data:
                entity_ids = service.data[ATTR_ENTITIES]
                await group.async_update_tracked_entity_ids(entity_ids)

            if ATTR_NAME in service.data:
                group.name = service.data[ATTR_NAME]
                need_update = True

            if ATTR_VISIBLE in service.data:
                group.visible = service.data[ATTR_VISIBLE]
                need_update = True

            if ATTR_ICON in service.data:
                group.icon = service.data[ATTR_ICON]
                need_update = True

            if ATTR_CONTROL in service.data:
                group.control = service.data[ATTR_CONTROL]
                need_update = True

            if ATTR_VIEW in service.data:
                group.view = service.data[ATTR_VIEW]
                need_update = True

            if ATTR_ALL in service.data:
                group.mode = all if service.data[ATTR_ALL] else any
                need_update = True

            if need_update:
                await group.async_update_ha_state()

            return

        # remove group
        if service.service == SERVICE_REMOVE:
            await component.async_remove_entity(entity_id)

    hass.services.async_register(
        DOMAIN, SERVICE_SET, locked_service_handler,
        schema=SET_SERVICE_SCHEMA)

    hass.services.async_register(
        DOMAIN, SERVICE_REMOVE, groups_service_handler,
        schema=REMOVE_SERVICE_SCHEMA)

    async def visibility_service_handler(service):
        """Change visibility of a group."""
        visible = service.data.get(ATTR_VISIBLE)

        tasks = []
        for group in await component.async_extract_from_service(
                service, expand_group=False):
            group.visible = visible
            tasks.append(group.async_update_ha_state())

        if tasks:
            await asyncio.wait(tasks)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_VISIBILITY, visibility_service_handler,
        schema=SET_VISIBILITY_SERVICE_SCHEMA)

    return True


async def _async_process_config(hass, config, component):
    """Process group configuration."""
    for object_id, conf in config.get(DOMAIN, {}).items():
        name = conf.get(CONF_NAME, object_id)
        entity_ids = conf.get(CONF_ENTITIES) or []
        icon = conf.get(CONF_ICON)
        view = conf.get(CONF_VIEW)
        control = conf.get(CONF_CONTROL)
        mode = conf.get(CONF_ALL)

        # Don't create tasks and await them all. The order is important as
        # groups get a number based on creation order.
        await Group.async_create_group(
            hass, name, entity_ids, icon=icon, view=view,
            control=control, object_id=object_id, mode=mode)


class Group(Entity):
    """Track a group of entity ids."""

    def __init__(self, hass, name, order=None, visible=True, icon=None,
                 view=False, control=None, user_defined=True, entity_ids=None,
                 mode=None):
        """Initialize a group.

        This Object has factory function for creation.
        """
        self.hass = hass
        self._name = name
        self._state = STATE_UNKNOWN
        self._icon = icon
        self.view = view
        if entity_ids:
            self.tracking = tuple(ent_id.lower() for ent_id in entity_ids)
        else:
            self.tracking = tuple()
        self.group_on = None
        self.group_off = None
        self.visible = visible
        self.control = control
        self.user_defined = user_defined
        self.mode = any
        if mode:
            self.mode = all
        self._order = order
        self._assumed_state = False
        self._async_unsub_state_changed = None

    @staticmethod
    def create_group(hass, name, entity_ids=None, user_defined=True,
                     visible=True, icon=None, view=False, control=None,
                     object_id=None, mode=None):
        """Initialize a group."""
        return run_coroutine_threadsafe(
            Group.async_create_group(
                hass, name, entity_ids, user_defined, visible, icon, view,
                control, object_id, mode),
            hass.loop).result()

    @staticmethod
    async def async_create_group(hass, name, entity_ids=None,
                                 user_defined=True, visible=True, icon=None,
                                 view=False, control=None, object_id=None,
                                 mode=None):
        """Initialize a group.

        This method must be run in the event loop.
        """
        group = Group(
            hass, name,
            order=len(hass.states.async_entity_ids(DOMAIN)),
            visible=visible, icon=icon, view=view, control=control,
            user_defined=user_defined, entity_ids=entity_ids, mode=mode
        )

        group.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, object_id or name, hass=hass)

        # If called before the platform async_setup is called (test cases)
        component = hass.data.get(DOMAIN)

        if component is None:
            component = hass.data[DOMAIN] = \
                EntityComponent(_LOGGER, DOMAIN, hass)

        await component.async_add_entities([group], True)

        return group

    @property
    def should_poll(self):
        """No need to poll because groups will update themselves."""
        return False

    @property
    def name(self):
        """Return the name of the group."""
        return self._name

    @name.setter
    def name(self, value):
        """Set Group name."""
        self._name = value

    @property
    def state(self):
        """Return the state of the group."""
        return self._state

    @property
    def icon(self):
        """Return the icon of the group."""
        return self._icon

    @icon.setter
    def icon(self, value):
        """Set Icon for group."""
        self._icon = value

    @property
    def hidden(self):
        """If group should be hidden or not."""
        if self.visible and not self.view:
            return False
        return True

    @property
    def state_attributes(self):
        """Return the state attributes for the group."""
        data = {
            ATTR_ENTITY_ID: self.tracking,
            ATTR_ORDER: self._order,
        }
        if not self.user_defined:
            data[ATTR_AUTO] = True
        if self.view:
            data[ATTR_VIEW] = True
        if self.control:
            data[ATTR_CONTROL] = self.control
        return data

    @property
    def assumed_state(self):
        """Test if any member has an assumed state."""
        return self._assumed_state

    def update_tracked_entity_ids(self, entity_ids):
        """Update the member entity IDs."""
        run_coroutine_threadsafe(
            self.async_update_tracked_entity_ids(entity_ids), self.hass.loop
        ).result()

    async def async_update_tracked_entity_ids(self, entity_ids):
        """Update the member entity IDs.

        This method must be run in the event loop.
        """
        await self.async_stop()
        self.tracking = tuple(ent_id.lower() for ent_id in entity_ids)
        self.group_on, self.group_off = None, None

        await self.async_update_ha_state(True)
        self.async_start()

    @callback
    def async_start(self):
        """Start tracking members.

        This method must be run in the event loop.
        """
        if self._async_unsub_state_changed is None:
            self._async_unsub_state_changed = async_track_state_change(
                self.hass, self.tracking, self._async_state_changed_listener
            )

    async def async_stop(self):
        """Unregister the group from Home Assistant.

        This method must be run in the event loop.
        """
        if self._async_unsub_state_changed:
            self._async_unsub_state_changed()
            self._async_unsub_state_changed = None

    async def async_update(self):
        """Query all members and determine current group state."""
        self._state = STATE_UNKNOWN
        self._async_update_group_state()

    async def async_added_to_hass(self):
        """Handle addition to HASS."""
        if self.tracking:
            self.async_start()

    async def async_will_remove_from_hass(self):
        """Handle removal from HASS."""
        if self._async_unsub_state_changed:
            self._async_unsub_state_changed()
            self._async_unsub_state_changed = None

    async def _async_state_changed_listener(self, entity_id, old_state,
                                            new_state):
        """Respond to a member state changing.

        This method must be run in the event loop.
        """
        # removed
        if self._async_unsub_state_changed is None:
            return

        self._async_update_group_state(new_state)
        await self.async_update_ha_state()

    @property
    def _tracking_states(self):
        """Return the states that the group is tracking."""
        states = []

        for entity_id in self.tracking:
            state = self.hass.states.get(entity_id)

            if state is not None:
                states.append(state)

        return states

    @callback
    def _async_update_group_state(self, tr_state=None):
        """Update group state.

        Optionally you can provide the only state changed since last update
        allowing this method to take shortcuts.

        This method must be run in the event loop.
        """
        # To store current states of group entities. Might not be needed.
        states = None
        gr_state = self._state
        gr_on = self.group_on
        gr_off = self.group_off

        # We have not determined type of group yet
        if gr_on is None:
            if tr_state is None:
                states = self._tracking_states

                for state in states:
                    gr_on, gr_off = \
                        _get_group_on_off(state.state)
                    if gr_on is not None:
                        break
            else:
                gr_on, gr_off = _get_group_on_off(tr_state.state)

            if gr_on is not None:
                self.group_on, self.group_off = gr_on, gr_off

        # We cannot determine state of the group
        if gr_on is None:
            return

        # pylint: disable=too-many-boolean-expressions
        if tr_state is None or ((gr_state == gr_on and
                                 tr_state.state == gr_off) or
                                (gr_state == gr_off and
                                 tr_state.state == gr_on) or
                                tr_state.state not in (gr_on, gr_off)):
            if states is None:
                states = self._tracking_states

            if self.mode(state.state == gr_on for state in states):
                self._state = gr_on
            else:
                self._state = gr_off

        elif tr_state.state in (gr_on, gr_off):
            self._state = tr_state.state

        if tr_state is None or self._assumed_state and \
           not tr_state.attributes.get(ATTR_ASSUMED_STATE):
            if states is None:
                states = self._tracking_states

            self._assumed_state = self.mode(
                state.attributes.get(ATTR_ASSUMED_STATE) for state
                in states)

        elif tr_state.attributes.get(ATTR_ASSUMED_STATE):
            self._assumed_state = True
