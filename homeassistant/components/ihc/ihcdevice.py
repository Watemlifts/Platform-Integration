"""Implementation of a base class for all IHC devices."""
from homeassistant.helpers.entity import Entity


class IHCDevice(Entity):
    """Base class for all IHC devices.

    All IHC devices have an associated IHC resource. IHCDevice handled the
    registration of the IHC controller callback when the IHC resource changes.
    Derived classes must implement the on_ihc_change method
    """

    def __init__(self, ihc_controller, name, ihc_id: int, info: bool,
                 product=None) -> None:
        """Initialize IHC attributes."""
        self.ihc_controller = ihc_controller
        self._name = name
        self.ihc_id = ihc_id
        self.info = info
        if product:
            self.ihc_name = product['name']
            self.ihc_note = product['note']
            self.ihc_position = product['position']
        else:
            self.ihc_name = ''
            self.ihc_note = ''
            self.ihc_position = ''

    async def async_added_to_hass(self):
        """Add callback for IHC changes."""
        self.ihc_controller.add_notify_event(
            self.ihc_id, self.on_ihc_change, True)

    @property
    def should_poll(self) -> bool:
        """No polling needed for IHC devices."""
        return False

    @property
    def name(self):
        """Return the device name."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if not self.info:
            return {}
        return {
            'ihc_id': self.ihc_id,
            'ihc_name': self.ihc_name,
            'ihc_note': self.ihc_note,
            'ihc_position': self.ihc_position,
        }

    def on_ihc_change(self, ihc_id, value):
        """Handle IHC resource change.

        Derived classes must overwrite this to do device specific stuff.
        """
        raise NotImplementedError
