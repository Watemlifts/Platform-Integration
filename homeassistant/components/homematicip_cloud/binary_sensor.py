"""Support for HomematicIP Cloud binary sensor."""
import logging

from homematicip.aio.device import (
    AsyncDevice, AsyncMotionDetectorIndoor, AsyncMotionDetectorOutdoor,
    AsyncMotionDetectorPushButton, AsyncPresenceDetectorIndoor,
    AsyncRotaryHandleSensor, AsyncShutterContact, AsyncSmokeDetector,
    AsyncWaterSensor, AsyncWeatherSensor, AsyncWeatherSensorPlus,
    AsyncWeatherSensorPro)
from homematicip.aio.group import AsyncSecurityGroup, AsyncSecurityZoneGroup
from homematicip.aio.home import AsyncHome
from homematicip.base.enums import SmokeDetectorAlarmType, WindowState

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY, DEVICE_CLASS_DOOR, DEVICE_CLASS_LIGHT,
    DEVICE_CLASS_MOISTURE, DEVICE_CLASS_MOTION, DEVICE_CLASS_PRESENCE,
    DEVICE_CLASS_SAFETY, DEVICE_CLASS_SMOKE, BinarySensorDevice)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import DOMAIN as HMIPC_DOMAIN, HMIPC_HAPID, HomematicipGenericDevice
from .device import ATTR_GROUP_MEMBER_UNREACHABLE

_LOGGER = logging.getLogger(__name__)

ATTR_LOW_BATTERY = 'low_battery'
ATTR_MOTIONDETECTED = 'motion detected'
ATTR_PRESENCEDETECTED = 'presence detected'
ATTR_POWERMAINSFAILURE = 'power mains failure'
ATTR_WINDOWSTATE = 'window state'
ATTR_MOISTUREDETECTED = 'moisture detected'
ATTR_WATERLEVELDETECTED = 'water level detected'
ATTR_SMOKEDETECTORALARM = 'smoke detector alarm'
ATTR_TODAY_SUNSHINE_DURATION = 'today_sunshine_duration_in_minutes'


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the HomematicIP Cloud binary sensor devices."""
    pass


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry,
                            async_add_entities) -> None:
    """Set up the HomematicIP Cloud binary sensor from a config entry."""
    home = hass.data[HMIPC_DOMAIN][config_entry.data[HMIPC_HAPID]].home
    devices = []
    for device in home.devices:
        if isinstance(device, (AsyncShutterContact, AsyncRotaryHandleSensor)):
            devices.append(HomematicipShutterContact(home, device))
        if isinstance(device, (AsyncMotionDetectorIndoor,
                               AsyncMotionDetectorOutdoor,
                               AsyncMotionDetectorPushButton)):
            devices.append(HomematicipMotionDetector(home, device))
        if isinstance(device, AsyncPresenceDetectorIndoor):
            devices.append(HomematicipPresenceDetector(home, device))
        if isinstance(device, AsyncSmokeDetector):
            devices.append(HomematicipSmokeDetector(home, device))
        if isinstance(device, AsyncWaterSensor):
            devices.append(HomematicipWaterDetector(home, device))
        if isinstance(device, (AsyncWeatherSensorPlus,
                               AsyncWeatherSensorPro)):
            devices.append(HomematicipRainSensor(home, device))
        if isinstance(device, (AsyncWeatherSensor, AsyncWeatherSensorPlus,
                               AsyncWeatherSensorPro)):
            devices.append(HomematicipStormSensor(home, device))
            devices.append(HomematicipSunshineSensor(home, device))
        if isinstance(device, AsyncDevice) and device.lowBat is not None:
            devices.append(HomematicipBatterySensor(home, device))

    for group in home.groups:
        if isinstance(group, AsyncSecurityGroup):
            devices.append(HomematicipSecuritySensorGroup(home, group))
        elif isinstance(group, AsyncSecurityZoneGroup):
            devices.append(HomematicipSecurityZoneSensorGroup(home, group))

    if devices:
        async_add_entities(devices)


class HomematicipShutterContact(HomematicipGenericDevice, BinarySensorDevice):
    """Representation of a HomematicIP Cloud shutter contact."""

    @property
    def device_class(self) -> str:
        """Return the class of this sensor."""
        return DEVICE_CLASS_DOOR

    @property
    def is_on(self) -> bool:
        """Return true if the shutter contact is on/open."""
        if hasattr(self._device, 'sabotage') and self._device.sabotage:
            return True
        if self._device.windowState is None:
            return None
        return self._device.windowState != WindowState.CLOSED


class HomematicipMotionDetector(HomematicipGenericDevice, BinarySensorDevice):
    """Representation of a HomematicIP Cloud motion detector."""

    @property
    def device_class(self) -> str:
        """Return the class of this sensor."""
        return DEVICE_CLASS_MOTION

    @property
    def is_on(self) -> bool:
        """Return true if motion is detected."""
        if hasattr(self._device, 'sabotage') and self._device.sabotage:
            return True
        return self._device.motionDetected


class HomematicipPresenceDetector(HomematicipGenericDevice,
                                  BinarySensorDevice):
    """Representation of a HomematicIP Cloud presence detector."""

    @property
    def device_class(self) -> str:
        """Return the class of this sensor."""
        return DEVICE_CLASS_PRESENCE

    @property
    def is_on(self) -> bool:
        """Return true if presence is detected."""
        if hasattr(self._device, 'sabotage') and self._device.sabotage:
            return True
        return self._device.presenceDetected


class HomematicipSmokeDetector(HomematicipGenericDevice, BinarySensorDevice):
    """Representation of a HomematicIP Cloud smoke detector."""

    @property
    def device_class(self) -> str:
        """Return the class of this sensor."""
        return DEVICE_CLASS_SMOKE

    @property
    def is_on(self) -> bool:
        """Return true if smoke is detected."""
        return (self._device.smokeDetectorAlarmType
                != SmokeDetectorAlarmType.IDLE_OFF)


class HomematicipWaterDetector(HomematicipGenericDevice, BinarySensorDevice):
    """Representation of a HomematicIP Cloud water detector."""

    @property
    def device_class(self) -> str:
        """Return the class of this sensor."""
        return DEVICE_CLASS_MOISTURE

    @property
    def is_on(self) -> bool:
        """Return true, if moisture or waterlevel is detected."""
        return self._device.moistureDetected or self._device.waterlevelDetected


class HomematicipStormSensor(HomematicipGenericDevice, BinarySensorDevice):
    """Representation of a HomematicIP Cloud storm sensor."""

    def __init__(self, home: AsyncHome, device) -> None:
        """Initialize storm sensor."""
        super().__init__(home, device, "Storm")

    @property
    def icon(self) -> str:
        """Return the icon."""
        return 'mdi:weather-windy' if self.is_on else 'mdi:pinwheel-outline'

    @property
    def is_on(self) -> bool:
        """Return true, if storm is detected."""
        return self._device.storm


class HomematicipRainSensor(HomematicipGenericDevice, BinarySensorDevice):
    """Representation of a HomematicIP Cloud rain sensor."""

    def __init__(self, home: AsyncHome, device) -> None:
        """Initialize rain sensor."""
        super().__init__(home, device, "Raining")

    @property
    def device_class(self) -> str:
        """Return the class of this sensor."""
        return DEVICE_CLASS_MOISTURE

    @property
    def is_on(self) -> bool:
        """Return true, if it is raining."""
        return self._device.raining


class HomematicipSunshineSensor(HomematicipGenericDevice, BinarySensorDevice):
    """Representation of a HomematicIP Cloud sunshine sensor."""

    def __init__(self, home: AsyncHome, device) -> None:
        """Initialize sunshine sensor."""
        super().__init__(home, device, 'Sunshine')

    @property
    def device_class(self) -> str:
        """Return the class of this sensor."""
        return DEVICE_CLASS_LIGHT

    @property
    def is_on(self) -> bool:
        """Return true if sun is shining."""
        return self._device.sunshine

    @property
    def device_state_attributes(self):
        """Return the state attributes of the illuminance sensor."""
        attr = super().device_state_attributes
        if hasattr(self._device, 'todaySunshineDuration') and \
                self._device.todaySunshineDuration:
            attr[ATTR_TODAY_SUNSHINE_DURATION] = \
                self._device.todaySunshineDuration
        return attr


class HomematicipBatterySensor(HomematicipGenericDevice, BinarySensorDevice):
    """Representation of a HomematicIP Cloud low battery sensor."""

    def __init__(self, home: AsyncHome, device) -> None:
        """Initialize battery sensor."""
        super().__init__(home, device, 'Battery')

    @property
    def device_class(self) -> str:
        """Return the class of this sensor."""
        return DEVICE_CLASS_BATTERY

    @property
    def is_on(self) -> bool:
        """Return true if battery is low."""
        return self._device.lowBat


class HomematicipSecurityZoneSensorGroup(HomematicipGenericDevice,
                                         BinarySensorDevice):
    """Representation of a HomematicIP Cloud security zone group."""

    def __init__(self, home: AsyncHome, device,
                 post: str = 'SecurityZone') -> None:
        """Initialize security zone group."""
        device.modelType = 'HmIP-{}'.format(post)
        super().__init__(home, device, post)

    @property
    def device_class(self) -> str:
        """Return the class of this sensor."""
        return DEVICE_CLASS_SAFETY

    @property
    def available(self) -> bool:
        """Security-Group available."""
        # A security-group must be available, and should not be affected by
        # the individual availability of group members.
        return True

    @property
    def device_state_attributes(self):
        """Return the state attributes of the security zone group."""
        attr = super().device_state_attributes

        if self._device.motionDetected:
            attr[ATTR_MOTIONDETECTED] = True
        if self._device.presenceDetected:
            attr[ATTR_PRESENCEDETECTED] = True

        if self._device.windowState is not None and \
                self._device.windowState != WindowState.CLOSED:
            attr[ATTR_WINDOWSTATE] = str(self._device.windowState)
        if self._device.unreach:
            attr[ATTR_GROUP_MEMBER_UNREACHABLE] = True
        return attr

    @property
    def is_on(self) -> bool:
        """Return true if security issue detected."""
        if self._device.motionDetected or \
                self._device.presenceDetected or \
                self._device.unreach or \
                self._device.sabotage:
            return True

        if self._device.windowState is not None and \
                self._device.windowState != WindowState.CLOSED:
            return True
        return False


class HomematicipSecuritySensorGroup(HomematicipSecurityZoneSensorGroup,
                                     BinarySensorDevice):
    """Representation of a HomematicIP security group."""

    def __init__(self, home: AsyncHome, device) -> None:
        """Initialize security group."""
        super().__init__(home, device, 'Sensors')

    @property
    def device_state_attributes(self):
        """Return the state attributes of the security group."""
        attr = super().device_state_attributes

        if self._device.powerMainsFailure:
            attr[ATTR_POWERMAINSFAILURE] = True
        if self._device.moistureDetected:
            attr[ATTR_MOISTUREDETECTED] = True
        if self._device.waterlevelDetected:
            attr[ATTR_WATERLEVELDETECTED] = True
        if self._device.lowBat:
            attr[ATTR_LOW_BATTERY] = True
        if self._device.smokeDetectorAlarmType is not None and \
                self._device.smokeDetectorAlarmType != \
                SmokeDetectorAlarmType.IDLE_OFF:
            attr[ATTR_SMOKEDETECTORALARM] = \
                str(self._device.smokeDetectorAlarmType)

        return attr

    @property
    def is_on(self) -> bool:
        """Return true if safety issue detected."""
        parent_is_on = super().is_on
        if parent_is_on or \
                self._device.powerMainsFailure or \
                self._device.moistureDetected or \
                self._device.waterlevelDetected or \
                self._device.lowBat:
            return True
        if self._device.smokeDetectorAlarmType is not None and \
                self._device.smokeDetectorAlarmType != \
                SmokeDetectorAlarmType.IDLE_OFF:
            return True
        return False
