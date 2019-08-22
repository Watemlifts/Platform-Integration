"""Support for the myStrom buttons."""
import logging

from homeassistant.components.binary_sensor import DOMAIN, BinarySensorDevice
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import HTTP_UNPROCESSABLE_ENTITY

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up myStrom Binary Sensor."""
    hass.http.register_view(MyStromView(async_add_entities))

    return True


class MyStromView(HomeAssistantView):
    """View to handle requests from myStrom buttons."""

    url = '/api/mystrom'
    name = 'api:mystrom'
    supported_actions = ['single', 'double', 'long', 'touch']

    def __init__(self, add_entities):
        """Initialize the myStrom URL endpoint."""
        self.buttons = {}
        self.add_entities = add_entities

    async def get(self, request):
        """Handle the GET request received from a myStrom button."""
        res = await self._handle(request.app['hass'], request.query)
        return res

    async def _handle(self, hass, data):
        """Handle requests to the myStrom endpoint."""
        button_action = next((
            parameter for parameter in data
            if parameter in self.supported_actions), None)

        if button_action is None:
            _LOGGER.error(
                "Received unidentified message from myStrom button: %s", data)
            return ("Received unidentified message: {}".format(data),
                    HTTP_UNPROCESSABLE_ENTITY)

        button_id = data[button_action]
        entity_id = '{}.{}_{}'.format(DOMAIN, button_id, button_action)
        if entity_id not in self.buttons:
            _LOGGER.info("New myStrom button/action detected: %s/%s",
                         button_id, button_action)
            self.buttons[entity_id] = MyStromBinarySensor(
                '{}_{}'.format(button_id, button_action))
            self.add_entities([self.buttons[entity_id]])
        else:
            new_state = self.buttons[entity_id].state == 'off'
            self.buttons[entity_id].async_on_update(new_state)


class MyStromBinarySensor(BinarySensorDevice):
    """Representation of a myStrom button."""

    def __init__(self, button_id):
        """Initialize the myStrom Binary sensor."""
        self._button_id = button_id
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._button_id

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    def async_on_update(self, value):
        """Receive an update."""
        self._state = value
        self.async_schedule_update_ha_state()
