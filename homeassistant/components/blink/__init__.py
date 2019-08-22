"""Support for Blink Home Camera System."""
import logging
from datetime import timedelta
import voluptuous as vol

from homeassistant.helpers import (
    config_validation as cv, discovery)
from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD, CONF_NAME, CONF_SCAN_INTERVAL,
    CONF_BINARY_SENSORS, CONF_SENSORS, CONF_FILENAME,
    CONF_MONITORED_CONDITIONS, CONF_MODE, CONF_OFFSET, TEMP_FAHRENHEIT)

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'blink'
BLINK_DATA = 'blink'

CONF_CAMERA = 'camera'
CONF_ALARM_CONTROL_PANEL = 'alarm_control_panel'

DEFAULT_BRAND = 'Blink'
DEFAULT_ATTRIBUTION = "Data provided by immedia-semi.com"
SIGNAL_UPDATE_BLINK = "blink_update"

DEFAULT_SCAN_INTERVAL = timedelta(seconds=300)

TYPE_CAMERA_ARMED = 'motion_enabled'
TYPE_MOTION_DETECTED = 'motion_detected'
TYPE_TEMPERATURE = 'temperature'
TYPE_BATTERY = 'battery'
TYPE_WIFI_STRENGTH = 'wifi_strength'

SERVICE_REFRESH = 'blink_update'
SERVICE_TRIGGER = 'trigger_camera'
SERVICE_SAVE_VIDEO = 'save_video'

BINARY_SENSORS = {
    TYPE_CAMERA_ARMED: ['Camera Armed', 'mdi:verified'],
    TYPE_MOTION_DETECTED: ['Motion Detected', 'mdi:run-fast'],
}

SENSORS = {
    TYPE_TEMPERATURE: ['Temperature', TEMP_FAHRENHEIT, 'mdi:thermometer'],
    TYPE_BATTERY: ['Battery', '', 'mdi:battery-80'],
    TYPE_WIFI_STRENGTH: ['Wifi Signal', 'dBm', 'mdi:wifi-strength-2'],
}

BINARY_SENSOR_SCHEMA = vol.Schema({
    vol.Optional(CONF_MONITORED_CONDITIONS, default=list(BINARY_SENSORS)):
        vol.All(cv.ensure_list, [vol.In(BINARY_SENSORS)])
})

SENSOR_SCHEMA = vol.Schema({
    vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SENSORS)):
        vol.All(cv.ensure_list, [vol.In(SENSORS)])
})

SERVICE_TRIGGER_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string
})

SERVICE_SAVE_VIDEO_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_FILENAME): cv.string,
})

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN:
        vol.Schema({
            vol.Required(CONF_USERNAME): cv.string,
            vol.Required(CONF_PASSWORD): cv.string,
            vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL):
                cv.time_period,
            vol.Optional(CONF_BINARY_SENSORS, default={}):
                BINARY_SENSOR_SCHEMA,
            vol.Optional(CONF_SENSORS, default={}): SENSOR_SCHEMA,
            vol.Optional(CONF_OFFSET, default=1): int,
            vol.Optional(CONF_MODE, default=''): cv.string,
        })
    },
    extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up Blink System."""
    from blinkpy import blinkpy
    conf = config[BLINK_DATA]
    username = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]
    scan_interval = conf[CONF_SCAN_INTERVAL]
    is_legacy = bool(conf[CONF_MODE] == 'legacy')
    motion_interval = conf[CONF_OFFSET]
    hass.data[BLINK_DATA] = blinkpy.Blink(username=username,
                                          password=password,
                                          motion_interval=motion_interval,
                                          legacy_subdomain=is_legacy)
    hass.data[BLINK_DATA].refresh_rate = scan_interval.total_seconds()
    hass.data[BLINK_DATA].start()

    platforms = [
        ('alarm_control_panel', {}),
        ('binary_sensor', conf[CONF_BINARY_SENSORS]),
        ('camera', {}),
        ('sensor', conf[CONF_SENSORS]),
    ]

    for component, schema in platforms:
        discovery.load_platform(hass, component, DOMAIN, schema, config)

    def trigger_camera(call):
        """Trigger a camera."""
        cameras = hass.data[BLINK_DATA].cameras
        name = call.data[CONF_NAME]
        if name in cameras:
            cameras[name].snap_picture()
        hass.data[BLINK_DATA].refresh(force_cache=True)

    def blink_refresh(event_time):
        """Call blink to refresh info."""
        hass.data[BLINK_DATA].refresh(force_cache=True)

    async def async_save_video(call):
        """Call save video service handler."""
        await async_handle_save_video_service(hass, call)

    hass.services.register(DOMAIN, SERVICE_REFRESH, blink_refresh)
    hass.services.register(DOMAIN,
                           SERVICE_TRIGGER,
                           trigger_camera,
                           schema=SERVICE_TRIGGER_SCHEMA)
    hass.services.register(DOMAIN,
                           SERVICE_SAVE_VIDEO,
                           async_save_video,
                           schema=SERVICE_SAVE_VIDEO_SCHEMA)
    return True


async def async_handle_save_video_service(hass, call):
    """Handle save video service calls."""
    camera_name = call.data[CONF_NAME]
    video_path = call.data[CONF_FILENAME]
    if not hass.config.is_allowed_path(video_path):
        _LOGGER.error(
            "Can't write %s, no access to path!", video_path)
        return

    def _write_video(camera_name, video_path):
        """Call video write."""
        all_cameras = hass.data[BLINK_DATA].cameras
        if camera_name in all_cameras:
            all_cameras[camera_name].video_to_file(video_path)

    try:
        await hass.async_add_executor_job(
            _write_video, camera_name, video_path)
    except OSError as err:
        _LOGGER.error("Can't write image to file: %s", err)
