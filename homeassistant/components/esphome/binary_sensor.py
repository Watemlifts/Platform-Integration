"""Support for ESPHome binary sensors."""
import logging
from typing import Optional

from aioesphomeapi import BinarySensorInfo, BinarySensorState

from homeassistant.components.binary_sensor import BinarySensorDevice

from . import EsphomeEntity, platform_async_setup_entry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up ESPHome binary sensors based on a config entry."""
    await platform_async_setup_entry(
        hass, entry, async_add_entities,
        component_key='binary_sensor',
        info_type=BinarySensorInfo, entity_type=EsphomeBinarySensor,
        state_type=BinarySensorState
    )


class EsphomeBinarySensor(EsphomeEntity, BinarySensorDevice):
    """A binary sensor implementation for ESPHome."""

    @property
    def _static_info(self) -> BinarySensorInfo:
        return super()._static_info

    @property
    def _state(self) -> Optional[BinarySensorState]:
        return super()._state

    @property
    def is_on(self) -> Optional[bool]:
        """Return true if the binary sensor is on."""
        if self._static_info.is_status_binary_sensor:
            # Status binary sensors indicated connected state.
            # So in their case what's usually _availability_ is now state
            return self._entry_data.available
        if self._state is None:
            return None
        return self._state.state

    @property
    def device_class(self) -> str:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._static_info.device_class

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if self._static_info.is_status_binary_sensor:
            return True
        return super().available
