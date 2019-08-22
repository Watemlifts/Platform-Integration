"""Support for Ubiquiti's UVC cameras."""
import logging
import socket

import requests
import voluptuous as vol

from homeassistant.const import CONF_PORT, CONF_SSL
from homeassistant.components.camera import Camera, PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.exceptions import PlatformNotReady

_LOGGER = logging.getLogger(__name__)

CONF_NVR = 'nvr'
CONF_KEY = 'key'
CONF_PASSWORD = 'password'

DEFAULT_PASSWORD = 'ubnt'
DEFAULT_PORT = 7080
DEFAULT_SSL = False

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NVR): cv.string,
    vol.Required(CONF_KEY): cv.string,
    vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Discover cameras on a Unifi NVR."""
    addr = config[CONF_NVR]
    key = config[CONF_KEY]
    password = config[CONF_PASSWORD]
    port = config[CONF_PORT]
    ssl = config[CONF_SSL]

    from uvcclient import nvr
    try:
        # Exceptions may be raised in all method calls to the nvr library.
        nvrconn = nvr.UVCRemote(addr, port, key, ssl=ssl)
        cameras = nvrconn.index()

        identifier = 'id' if nvrconn.server_version >= (3, 2, 0) else 'uuid'
        # Filter out airCam models, which are not supported in the latest
        # version of UnifiVideo and which are EOL by Ubiquiti
        cameras = [
            camera for camera in cameras
            if 'airCam' not in nvrconn.get_camera(camera[identifier])['model']]
    except nvr.NotAuthorized:
        _LOGGER.error("Authorization failure while connecting to NVR")
        return False
    except nvr.NvrError as ex:
        _LOGGER.error("NVR refuses to talk to me: %s", str(ex))
        raise PlatformNotReady
    except requests.exceptions.ConnectionError as ex:
        _LOGGER.error("Unable to connect to NVR: %s", str(ex))
        raise PlatformNotReady

    add_entities([UnifiVideoCamera(nvrconn,
                                   camera[identifier],
                                   camera['name'],
                                   password)
                  for camera in cameras])
    return True


class UnifiVideoCamera(Camera):
    """A Ubiquiti Unifi Video Camera."""

    def __init__(self, nvr, uuid, name, password):
        """Initialize an Unifi camera."""
        super(UnifiVideoCamera, self).__init__()
        self._nvr = nvr
        self._uuid = uuid
        self._name = name
        self._password = password
        self.is_streaming = False
        self._connect_addr = None
        self._camera = None
        self._motion_status = False

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def is_recording(self):
        """Return true if the camera is recording."""
        caminfo = self._nvr.get_camera(self._uuid)
        return caminfo['recordingSettings']['fullTimeRecordEnabled']

    @property
    def motion_detection_enabled(self):
        """Camera Motion Detection Status."""
        caminfo = self._nvr.get_camera(self._uuid)
        return caminfo['recordingSettings']['motionRecordEnabled']

    @property
    def brand(self):
        """Return the brand of this camera."""
        return 'Ubiquiti'

    @property
    def model(self):
        """Return the model of this camera."""
        caminfo = self._nvr.get_camera(self._uuid)
        return caminfo['model']

    def _login(self):
        """Login to the camera."""
        from uvcclient import camera as uvc_camera

        caminfo = self._nvr.get_camera(self._uuid)
        if self._connect_addr:
            addrs = [self._connect_addr]
        else:
            addrs = [caminfo['host'], caminfo['internalHost']]

        if self._nvr.server_version >= (3, 2, 0):
            client_cls = uvc_camera.UVCCameraClientV320
        else:
            client_cls = uvc_camera.UVCCameraClient

        if caminfo['username'] is None:
            caminfo['username'] = 'ubnt'

        camera = None
        for addr in addrs:
            try:
                camera = client_cls(
                    addr, caminfo['username'], self._password)
                camera.login()
                _LOGGER.debug("Logged into UVC camera %(name)s via %(addr)s",
                              dict(name=self._name, addr=addr))
                self._connect_addr = addr
                break
            except socket.error:
                pass
            except uvc_camera.CameraConnectError:
                pass
            except uvc_camera.CameraAuthError:
                pass
        if not self._connect_addr:
            _LOGGER.error("Unable to login to camera")
            return None

        self._camera = camera
        return True

    def camera_image(self):
        """Return the image of this camera."""
        from uvcclient import camera as uvc_camera
        if not self._camera:
            if not self._login():
                return

        def _get_image(retry=True):
            try:
                return self._camera.get_snapshot()
            except uvc_camera.CameraConnectError:
                _LOGGER.error("Unable to contact camera")
            except uvc_camera.CameraAuthError:
                if retry:
                    self._login()
                    return _get_image(retry=False)
                _LOGGER.error(
                    "Unable to log into camera, unable to get snapshot")
                raise

        return _get_image()

    def set_motion_detection(self, mode):
        """Set motion detection on or off."""
        from uvcclient.nvr import NvrError
        if mode is True:
            set_mode = 'motion'
        else:
            set_mode = 'none'

        try:
            self._nvr.set_recordmode(self._uuid, set_mode)
            self._motion_status = mode
        except NvrError as err:
            _LOGGER.error("Unable to set recordmode to %s", set_mode)
            _LOGGER.debug(err)

    def enable_motion_detection(self):
        """Enable motion detection in camera."""
        self.set_motion_detection(True)

    def disable_motion_detection(self):
        """Disable motion detection in camera."""
        self.set_motion_detection(False)
