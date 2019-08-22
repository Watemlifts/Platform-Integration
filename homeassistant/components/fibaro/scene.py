"""Support for Fibaro scenes."""
import logging

from homeassistant.components.scene import Scene

from . import FIBARO_DEVICES, FibaroDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Perform the setup for Fibaro scenes."""
    if discovery_info is None:
        return

    async_add_entities(
        [FibaroScene(scene)
         for scene in hass.data[FIBARO_DEVICES]['scene']], True)


class FibaroScene(FibaroDevice, Scene):
    """Representation of a Fibaro scene entity."""

    def activate(self):
        """Activate the scene."""
        self.fibaro_device.start()
