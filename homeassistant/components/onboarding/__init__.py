"""Support to help onboard new users."""
from homeassistant.core import callback
from homeassistant.loader import bind_hass
from homeassistant.helpers.storage import Store

from .const import (
    DOMAIN, STEP_USER, STEPS, STEP_INTEGRATION, STEP_CORE_CONFIG)

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 3


class OnboadingStorage(Store):
    """Store onboarding data."""

    async def _async_migrate_func(self, old_version, old_data):
        """Migrate to the new version."""
        # From version 1 -> 2, we automatically mark the integration step done
        if old_version < 2:
            old_data['done'].append(STEP_INTEGRATION)
        if old_version < 3:
            old_data['done'].append(STEP_CORE_CONFIG)
        return old_data


@bind_hass
@callback
def async_is_onboarded(hass):
    """Return if Home Assistant has been onboarded."""
    data = hass.data.get(DOMAIN)
    return data is None or data is True


@bind_hass
@callback
def async_is_user_onboarded(hass):
    """Return if a user has been created as part of onboarding."""
    return async_is_onboarded(hass) or STEP_USER in hass.data[DOMAIN]['done']


async def async_setup(hass, config):
    """Set up the onboarding component."""
    store = OnboadingStorage(hass, STORAGE_VERSION, STORAGE_KEY, private=True)
    data = await store.async_load()

    if data is None:
        data = {
            'done': []
        }

    if STEP_USER not in data['done']:
        # Users can already have created an owner account via the command line
        # If so, mark the user step as done.
        has_owner = False

        for user in await hass.auth.async_get_users():
            if user.is_owner:
                has_owner = True
                break

        if has_owner:
            data['done'].append(STEP_USER)
            await store.async_save(data)

    if set(data['done']) == set(STEPS):
        return True

    hass.data[DOMAIN] = data

    from . import views

    await views.async_setup(hass, data, store)

    return True
