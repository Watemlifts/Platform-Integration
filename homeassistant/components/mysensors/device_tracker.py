"""Support for tracking MySensors devices."""
from homeassistant.components import mysensors
from homeassistant.components.device_tracker import DOMAIN
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import slugify


async def async_setup_scanner(hass, config, async_see, discovery_info=None):
    """Set up the MySensors device scanner."""
    new_devices = mysensors.setup_mysensors_platform(
        hass, DOMAIN, discovery_info, MySensorsDeviceScanner,
        device_args=(hass, async_see))
    if not new_devices:
        return False

    for device in new_devices:
        gateway_id = id(device.gateway)
        dev_id = (
            gateway_id, device.node_id, device.child_id,
            device.value_type)
        async_dispatcher_connect(
            hass, mysensors.const.CHILD_CALLBACK.format(*dev_id),
            device.async_update_callback)
        async_dispatcher_connect(
            hass,
            mysensors.const.NODE_CALLBACK.format(gateway_id, device.node_id),
            device.async_update_callback)

    return True


class MySensorsDeviceScanner(mysensors.device.MySensorsDevice):
    """Represent a MySensors scanner."""

    def __init__(self, hass, async_see, *args):
        """Set up instance."""
        super().__init__(*args)
        self.async_see = async_see
        self.hass = hass

    async def _async_update_callback(self):
        """Update the device."""
        await self.async_update()
        node = self.gateway.sensors[self.node_id]
        child = node.children[self.child_id]
        position = child.values[self.value_type]
        latitude, longitude, _ = position.split(',')

        await self.async_see(
            dev_id=slugify(self.name),
            host_name=self.name,
            gps=(latitude, longitude),
            battery=node.battery_level,
            attributes=self.device_state_attributes
        )
