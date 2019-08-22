"""Component to interface with cameras."""
import asyncio
import base64
import collections
from contextlib import suppress
from datetime import timedelta
import logging
import hashlib
from random import SystemRandom

import attr
from aiohttp import web
import async_timeout
import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, \
    SERVICE_TURN_ON, CONF_FILENAME
from homeassistant.exceptions import HomeAssistantError
from homeassistant.loader import bind_hass
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.config_validation import (  # noqa
    PLATFORM_SCHEMA, PLATFORM_SCHEMA_BASE)
from homeassistant.components.http import HomeAssistantView, KEY_AUTHENTICATED
from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID, ATTR_MEDIA_CONTENT_TYPE,
    SERVICE_PLAY_MEDIA, DOMAIN as DOMAIN_MP)
from homeassistant.components.stream import request_stream
from homeassistant.components.stream.const import (
    OUTPUT_FORMATS, FORMAT_CONTENT_TYPE, CONF_STREAM_SOURCE, CONF_LOOKBACK,
    CONF_DURATION, SERVICE_RECORD, DOMAIN as DOMAIN_STREAM)
from homeassistant.components import websocket_api
import homeassistant.helpers.config_validation as cv
from homeassistant.setup import async_when_setup

from .const import DOMAIN, DATA_CAMERA_PREFS
from .prefs import CameraPreferences

_LOGGER = logging.getLogger(__name__)

SERVICE_ENABLE_MOTION = 'enable_motion_detection'
SERVICE_DISABLE_MOTION = 'disable_motion_detection'
SERVICE_SNAPSHOT = 'snapshot'
SERVICE_PLAY_STREAM = 'play_stream'

SCAN_INTERVAL = timedelta(seconds=30)
ENTITY_ID_FORMAT = DOMAIN + '.{}'

ATTR_FILENAME = 'filename'
ATTR_MEDIA_PLAYER = 'media_player'
ATTR_FORMAT = 'format'

STATE_RECORDING = 'recording'
STATE_STREAMING = 'streaming'
STATE_IDLE = 'idle'

# Bitfield of features supported by the camera entity
SUPPORT_ON_OFF = 1
SUPPORT_STREAM = 2

DEFAULT_CONTENT_TYPE = 'image/jpeg'
ENTITY_IMAGE_URL = '/api/camera_proxy/{0}?token={1}'

TOKEN_CHANGE_INTERVAL = timedelta(minutes=5)
_RND = SystemRandom()

MIN_STREAM_INTERVAL = 0.5  # seconds

CAMERA_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.comp_entity_ids,
})

CAMERA_SERVICE_SNAPSHOT = CAMERA_SERVICE_SCHEMA.extend({
    vol.Required(ATTR_FILENAME): cv.template
})

CAMERA_SERVICE_PLAY_STREAM = CAMERA_SERVICE_SCHEMA.extend({
    vol.Required(ATTR_MEDIA_PLAYER): cv.entities_domain(DOMAIN_MP),
    vol.Optional(ATTR_FORMAT, default='hls'): vol.In(OUTPUT_FORMATS),
})

CAMERA_SERVICE_RECORD = CAMERA_SERVICE_SCHEMA.extend({
    vol.Required(CONF_FILENAME): cv.template,
    vol.Optional(CONF_DURATION, default=30): vol.Coerce(int),
    vol.Optional(CONF_LOOKBACK, default=0): vol.Coerce(int),
})

WS_TYPE_CAMERA_THUMBNAIL = 'camera_thumbnail'
SCHEMA_WS_CAMERA_THUMBNAIL = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_CAMERA_THUMBNAIL,
    vol.Required('entity_id'): cv.entity_id
})


@attr.s
class Image:
    """Represent an image."""

    content_type = attr.ib(type=str)
    content = attr.ib(type=bytes)


@bind_hass
async def async_request_stream(hass, entity_id, fmt):
    """Request a stream for a camera entity."""
    camera = _get_camera_from_entity_id(hass, entity_id)
    camera_prefs = hass.data[DATA_CAMERA_PREFS].get(entity_id)

    async with async_timeout.timeout(10):
        source = await camera.stream_source()

    if not source:
        raise HomeAssistantError("{} does not support play stream service"
                                 .format(camera.entity_id))

    return request_stream(hass, source, fmt=fmt,
                          keepalive=camera_prefs.preload_stream)


@bind_hass
async def async_get_image(hass, entity_id, timeout=10):
    """Fetch an image from a camera entity."""
    camera = _get_camera_from_entity_id(hass, entity_id)

    with suppress(asyncio.CancelledError, asyncio.TimeoutError):
        async with async_timeout.timeout(timeout):
            image = await camera.async_camera_image()

            if image:
                return Image(camera.content_type, image)

    raise HomeAssistantError('Unable to get image')


@bind_hass
async def async_get_mjpeg_stream(hass, request, entity_id):
    """Fetch an mjpeg stream from a camera entity."""
    camera = _get_camera_from_entity_id(hass, entity_id)

    return await camera.handle_async_mjpeg_stream(request)


async def async_get_still_stream(request, image_cb, content_type, interval):
    """Generate an HTTP MJPEG stream from camera images.

    This method must be run in the event loop.
    """
    response = web.StreamResponse()
    response.content_type = ('multipart/x-mixed-replace; '
                             'boundary=--frameboundary')
    await response.prepare(request)

    async def write_to_mjpeg_stream(img_bytes):
        """Write image to stream."""
        await response.write(bytes(
            '--frameboundary\r\n'
            'Content-Type: {}\r\n'
            'Content-Length: {}\r\n\r\n'.format(
                content_type, len(img_bytes)),
            'utf-8') + img_bytes + b'\r\n')

    last_image = None

    while True:
        img_bytes = await image_cb()
        if not img_bytes:
            break

        if img_bytes != last_image:
            await write_to_mjpeg_stream(img_bytes)

            # Chrome seems to always ignore first picture,
            # print it twice.
            if last_image is None:
                await write_to_mjpeg_stream(img_bytes)
            last_image = img_bytes

        await asyncio.sleep(interval)

    return response


def _get_camera_from_entity_id(hass, entity_id):
    """Get camera component from entity_id."""
    component = hass.data.get(DOMAIN)

    if component is None:
        raise HomeAssistantError('Camera component not set up')

    camera = component.get_entity(entity_id)

    if camera is None:
        raise HomeAssistantError('Camera not found')

    if not camera.is_on:
        raise HomeAssistantError('Camera is off')

    return camera


async def async_setup(hass, config):
    """Set up the camera component."""
    component = hass.data[DOMAIN] = \
        EntityComponent(_LOGGER, DOMAIN, hass, SCAN_INTERVAL)

    prefs = CameraPreferences(hass)
    await prefs.async_initialize()
    hass.data[DATA_CAMERA_PREFS] = prefs

    hass.http.register_view(CameraImageView(component))
    hass.http.register_view(CameraMjpegStream(component))
    hass.components.websocket_api.async_register_command(
        WS_TYPE_CAMERA_THUMBNAIL, websocket_camera_thumbnail,
        SCHEMA_WS_CAMERA_THUMBNAIL
    )
    hass.components.websocket_api.async_register_command(ws_camera_stream)
    hass.components.websocket_api.async_register_command(websocket_get_prefs)
    hass.components.websocket_api.async_register_command(
        websocket_update_prefs)

    await component.async_setup(config)

    async def preload_stream(hass, _):
        for camera in component.entities:
            camera_prefs = prefs.get(camera.entity_id)
            if not camera_prefs.preload_stream:
                continue

            async with async_timeout.timeout(10):
                source = await camera.stream_source()

            if not source:
                continue

            request_stream(hass, source, keepalive=True)

    async_when_setup(hass, DOMAIN_STREAM, preload_stream)

    @callback
    def update_tokens(time):
        """Update tokens of the entities."""
        for entity in component.entities:
            entity.async_update_token()
            hass.async_create_task(entity.async_update_ha_state())

    hass.helpers.event.async_track_time_interval(
        update_tokens, TOKEN_CHANGE_INTERVAL)

    component.async_register_entity_service(
        SERVICE_ENABLE_MOTION, CAMERA_SERVICE_SCHEMA,
        'async_enable_motion_detection'
    )
    component.async_register_entity_service(
        SERVICE_DISABLE_MOTION, CAMERA_SERVICE_SCHEMA,
        'async_disable_motion_detection'
    )
    component.async_register_entity_service(
        SERVICE_TURN_OFF, CAMERA_SERVICE_SCHEMA,
        'async_turn_off'
    )
    component.async_register_entity_service(
        SERVICE_TURN_ON, CAMERA_SERVICE_SCHEMA,
        'async_turn_on'
    )
    component.async_register_entity_service(
        SERVICE_SNAPSHOT, CAMERA_SERVICE_SNAPSHOT,
        async_handle_snapshot_service
    )
    component.async_register_entity_service(
        SERVICE_PLAY_STREAM, CAMERA_SERVICE_PLAY_STREAM,
        async_handle_play_stream_service
    )
    component.async_register_entity_service(
        SERVICE_RECORD, CAMERA_SERVICE_RECORD,
        async_handle_record_service
    )

    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)


class Camera(Entity):
    """The base class for camera entities."""

    def __init__(self):
        """Initialize a camera."""
        self.is_streaming = False
        self.content_type = DEFAULT_CONTENT_TYPE
        self.access_tokens = collections.deque([], 2)
        self.async_update_token()

    @property
    def should_poll(self):
        """No need to poll cameras."""
        return False

    @property
    def entity_picture(self):
        """Return a link to the camera feed as entity picture."""
        return ENTITY_IMAGE_URL.format(self.entity_id, self.access_tokens[-1])

    @property
    def supported_features(self):
        """Flag supported features."""
        return 0

    @property
    def is_recording(self):
        """Return true if the device is recording."""
        return False

    @property
    def brand(self):
        """Return the camera brand."""
        return None

    @property
    def motion_detection_enabled(self):
        """Return the camera motion detection status."""
        return None

    @property
    def model(self):
        """Return the camera model."""
        return None

    @property
    def frame_interval(self):
        """Return the interval between frames of the mjpeg stream."""
        return 0.5

    async def stream_source(self):
        """Return the source of the stream."""
        return None

    def camera_image(self):
        """Return bytes of camera image."""
        raise NotImplementedError()

    @callback
    def async_camera_image(self):
        """Return bytes of camera image.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.camera_image)

    async def handle_async_still_stream(self, request, interval):
        """Generate an HTTP MJPEG stream from camera images.

        This method must be run in the event loop.
        """
        return await async_get_still_stream(request, self.async_camera_image,
                                            self.content_type, interval)

    async def handle_async_mjpeg_stream(self, request):
        """Serve an HTTP MJPEG stream from the camera.

        This method can be overridden by camera plaforms to proxy
        a direct stream from the camera.
        This method must be run in the event loop.
        """
        return await self.handle_async_still_stream(
            request, self.frame_interval)

    @property
    def state(self):
        """Return the camera state."""
        if self.is_recording:
            return STATE_RECORDING
        if self.is_streaming:
            return STATE_STREAMING
        return STATE_IDLE

    @property
    def is_on(self):
        """Return true if on."""
        return True

    def turn_off(self):
        """Turn off camera."""
        raise NotImplementedError()

    @callback
    def async_turn_off(self):
        """Turn off camera."""
        return self.hass.async_add_job(self.turn_off)

    def turn_on(self):
        """Turn off camera."""
        raise NotImplementedError()

    @callback
    def async_turn_on(self):
        """Turn off camera."""
        return self.hass.async_add_job(self.turn_on)

    def enable_motion_detection(self):
        """Enable motion detection in the camera."""
        raise NotImplementedError()

    @callback
    def async_enable_motion_detection(self):
        """Call the job and enable motion detection."""
        return self.hass.async_add_job(self.enable_motion_detection)

    def disable_motion_detection(self):
        """Disable motion detection in camera."""
        raise NotImplementedError()

    @callback
    def async_disable_motion_detection(self):
        """Call the job and disable motion detection."""
        return self.hass.async_add_job(self.disable_motion_detection)

    @property
    def state_attributes(self):
        """Return the camera state attributes."""
        attrs = {
            'access_token': self.access_tokens[-1],
        }

        if self.model:
            attrs['model_name'] = self.model

        if self.brand:
            attrs['brand'] = self.brand

        if self.motion_detection_enabled:
            attrs['motion_detection'] = self.motion_detection_enabled

        return attrs

    @callback
    def async_update_token(self):
        """Update the used token."""
        self.access_tokens.append(
            hashlib.sha256(
                _RND.getrandbits(256).to_bytes(32, 'little')).hexdigest())


class CameraView(HomeAssistantView):
    """Base CameraView."""

    requires_auth = False

    def __init__(self, component):
        """Initialize a basic camera view."""
        self.component = component

    async def get(self, request, entity_id):
        """Start a GET request."""
        camera = self.component.get_entity(entity_id)

        if camera is None:
            raise web.HTTPNotFound()

        authenticated = (request[KEY_AUTHENTICATED] or
                         request.query.get('token') in camera.access_tokens)

        if not authenticated:
            raise web.HTTPUnauthorized()

        if not camera.is_on:
            _LOGGER.debug('Camera is off.')
            raise web.HTTPServiceUnavailable()

        return await self.handle(request, camera)

    async def handle(self, request, camera):
        """Handle the camera request."""
        raise NotImplementedError()


class CameraImageView(CameraView):
    """Camera view to serve an image."""

    url = '/api/camera_proxy/{entity_id}'
    name = 'api:camera:image'

    async def handle(self, request, camera):
        """Serve camera image."""
        with suppress(asyncio.CancelledError, asyncio.TimeoutError):
            async with async_timeout.timeout(10):
                image = await camera.async_camera_image()

            if image:
                return web.Response(body=image,
                                    content_type=camera.content_type)

        raise web.HTTPInternalServerError()


class CameraMjpegStream(CameraView):
    """Camera View to serve an MJPEG stream."""

    url = '/api/camera_proxy_stream/{entity_id}'
    name = 'api:camera:stream'

    async def handle(self, request, camera):
        """Serve camera stream, possibly with interval."""
        interval = request.query.get('interval')
        if interval is None:
            return await camera.handle_async_mjpeg_stream(request)

        try:
            # Compose camera stream from stills
            interval = float(request.query.get('interval'))
            if interval < MIN_STREAM_INTERVAL:
                raise ValueError("Stream interval must be be > {}"
                                 .format(MIN_STREAM_INTERVAL))
            return await camera.handle_async_still_stream(request, interval)
        except ValueError:
            raise web.HTTPBadRequest()


@websocket_api.async_response
async def websocket_camera_thumbnail(hass, connection, msg):
    """Handle get camera thumbnail websocket command.

    Async friendly.
    """
    try:
        image = await async_get_image(hass, msg['entity_id'])
        await connection.send_big_result(msg['id'], {
            'content_type': image.content_type,
            'content': base64.b64encode(image.content).decode('utf-8')
        })
    except HomeAssistantError:
        connection.send_message(websocket_api.error_message(
            msg['id'], 'image_fetch_failed', 'Unable to fetch image'))


@websocket_api.async_response
@websocket_api.websocket_command({
    vol.Required('type'): 'camera/stream',
    vol.Required('entity_id'): cv.entity_id,
    vol.Optional('format', default='hls'): vol.In(OUTPUT_FORMATS),
})
async def ws_camera_stream(hass, connection, msg):
    """Handle get camera stream websocket command.

    Async friendly.
    """
    try:
        entity_id = msg['entity_id']
        camera = _get_camera_from_entity_id(hass, entity_id)
        camera_prefs = hass.data[DATA_CAMERA_PREFS].get(entity_id)

        async with async_timeout.timeout(10):
            source = await camera.stream_source()

        if not source:
            raise HomeAssistantError("{} does not support play stream service"
                                     .format(camera.entity_id))

        fmt = msg['format']
        url = request_stream(hass, source, fmt=fmt,
                             keepalive=camera_prefs.preload_stream)
        connection.send_result(msg['id'], {'url': url})
    except HomeAssistantError as ex:
        _LOGGER.error("Error requesting stream: %s", ex)
        connection.send_error(
            msg['id'], 'start_stream_failed', str(ex))
    except asyncio.TimeoutError:
        _LOGGER.error("Timeout getting stream source")
        connection.send_error(
            msg['id'], 'start_stream_failed', "Timeout getting stream source")


@websocket_api.async_response
@websocket_api.websocket_command({
    vol.Required('type'): 'camera/get_prefs',
    vol.Required('entity_id'): cv.entity_id,
})
async def websocket_get_prefs(hass, connection, msg):
    """Handle request for account info."""
    prefs = hass.data[DATA_CAMERA_PREFS].get(msg['entity_id'])
    connection.send_result(msg['id'], prefs.as_dict())


@websocket_api.async_response
@websocket_api.websocket_command({
    vol.Required('type'): 'camera/update_prefs',
    vol.Required('entity_id'): cv.entity_id,
    vol.Optional('preload_stream'): bool,
})
async def websocket_update_prefs(hass, connection, msg):
    """Handle request for account info."""
    prefs = hass.data[DATA_CAMERA_PREFS]

    changes = dict(msg)
    changes.pop('id')
    changes.pop('type')
    entity_id = changes.pop('entity_id')
    await prefs.async_update(entity_id, **changes)

    connection.send_result(msg['id'], prefs.get(entity_id).as_dict())


async def async_handle_snapshot_service(camera, service):
    """Handle snapshot services calls."""
    hass = camera.hass
    filename = service.data[ATTR_FILENAME]
    filename.hass = hass

    snapshot_file = filename.async_render(
        variables={ATTR_ENTITY_ID: camera})

    # check if we allow to access to that file
    if not hass.config.is_allowed_path(snapshot_file):
        _LOGGER.error(
            "Can't write %s, no access to path!", snapshot_file)
        return

    image = await camera.async_camera_image()

    def _write_image(to_file, image_data):
        """Executor helper to write image."""
        with open(to_file, 'wb') as img_file:
            img_file.write(image_data)

    try:
        await hass.async_add_executor_job(
            _write_image, snapshot_file, image)
    except OSError as err:
        _LOGGER.error("Can't write image to file: %s", err)


async def async_handle_play_stream_service(camera, service_call):
    """Handle play stream services calls."""
    async with async_timeout.timeout(10):
        source = await camera.stream_source()

    if not source:
        raise HomeAssistantError("{} does not support play stream service"
                                 .format(camera.entity_id))

    hass = camera.hass
    camera_prefs = hass.data[DATA_CAMERA_PREFS].get(camera.entity_id)
    fmt = service_call.data[ATTR_FORMAT]
    entity_ids = service_call.data[ATTR_MEDIA_PLAYER]

    url = request_stream(hass, source, fmt=fmt,
                         keepalive=camera_prefs.preload_stream)
    data = {
        ATTR_ENTITY_ID: entity_ids,
        ATTR_MEDIA_CONTENT_ID: "{}{}".format(hass.config.api.base_url, url),
        ATTR_MEDIA_CONTENT_TYPE: FORMAT_CONTENT_TYPE[fmt]
    }

    await hass.services.async_call(
        DOMAIN_MP, SERVICE_PLAY_MEDIA, data,
        blocking=True, context=service_call.context)


async def async_handle_record_service(camera, call):
    """Handle stream recording service calls."""
    async with async_timeout.timeout(10):
        source = await camera.stream_source()

    if not source:
        raise HomeAssistantError("{} does not support record service"
                                 .format(camera.entity_id))

    hass = camera.hass
    filename = call.data[CONF_FILENAME]
    filename.hass = hass
    video_path = filename.async_render(
        variables={ATTR_ENTITY_ID: camera})

    data = {
        CONF_STREAM_SOURCE: source,
        CONF_FILENAME: video_path,
        CONF_DURATION: call.data[CONF_DURATION],
        CONF_LOOKBACK: call.data[CONF_LOOKBACK],
    }

    await hass.services.async_call(
        DOMAIN_STREAM, SERVICE_RECORD, data,
        blocking=True, context=call.context)
