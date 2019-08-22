"""The tests for generic camera component."""
import asyncio

from unittest import mock

from homeassistant.setup import async_setup_component


@asyncio.coroutine
def test_fetching_url(aioclient_mock, hass, hass_client):
    """Test that it fetches the given url."""
    aioclient_mock.get('http://example.com', text='hello world')

    yield from async_setup_component(hass, 'camera', {
        'camera': {
            'name': 'config_test',
            'platform': 'generic',
            'still_image_url': 'http://example.com',
            'username': 'user',
            'password': 'pass'
        }})

    client = yield from hass_client()

    resp = yield from client.get('/api/camera_proxy/camera.config_test')

    assert resp.status == 200
    assert aioclient_mock.call_count == 1
    body = yield from resp.text()
    assert body == 'hello world'

    resp = yield from client.get('/api/camera_proxy/camera.config_test')
    assert aioclient_mock.call_count == 2


@asyncio.coroutine
def test_fetching_without_verify_ssl(aioclient_mock, hass, hass_client):
    """Test that it fetches the given url when ssl verify is off."""
    aioclient_mock.get('https://example.com', text='hello world')

    yield from async_setup_component(hass, 'camera', {
        'camera': {
            'name': 'config_test',
            'platform': 'generic',
            'still_image_url': 'https://example.com',
            'username': 'user',
            'password': 'pass',
            'verify_ssl': 'false',
        }})

    client = yield from hass_client()

    resp = yield from client.get('/api/camera_proxy/camera.config_test')

    assert resp.status == 200


@asyncio.coroutine
def test_fetching_url_with_verify_ssl(aioclient_mock, hass, hass_client):
    """Test that it fetches the given url when ssl verify is explicitly on."""
    aioclient_mock.get('https://example.com', text='hello world')

    yield from async_setup_component(hass, 'camera', {
        'camera': {
            'name': 'config_test',
            'platform': 'generic',
            'still_image_url': 'https://example.com',
            'username': 'user',
            'password': 'pass',
            'verify_ssl': 'true',
        }})

    client = yield from hass_client()

    resp = yield from client.get('/api/camera_proxy/camera.config_test')

    assert resp.status == 200


@asyncio.coroutine
def test_limit_refetch(aioclient_mock, hass, hass_client):
    """Test that it fetches the given url."""
    aioclient_mock.get('http://example.com/5a', text='hello world')
    aioclient_mock.get('http://example.com/10a', text='hello world')
    aioclient_mock.get('http://example.com/15a', text='hello planet')
    aioclient_mock.get('http://example.com/20a', status=404)

    yield from async_setup_component(hass, 'camera', {
        'camera': {
            'name': 'config_test',
            'platform': 'generic',
            'still_image_url':
            'http://example.com/{{ states.sensor.temp.state + "a" }}',
            'limit_refetch_to_url_change': True,
        }})

    client = yield from hass_client()

    resp = yield from client.get('/api/camera_proxy/camera.config_test')

    hass.states.async_set('sensor.temp', '5')

    with mock.patch('async_timeout.timeout',
                    side_effect=asyncio.TimeoutError()):
        resp = yield from client.get('/api/camera_proxy/camera.config_test')
        assert aioclient_mock.call_count == 0
        assert resp.status == 500

    hass.states.async_set('sensor.temp', '10')

    resp = yield from client.get('/api/camera_proxy/camera.config_test')
    assert aioclient_mock.call_count == 1
    assert resp.status == 200
    body = yield from resp.text()
    assert body == 'hello world'

    resp = yield from client.get('/api/camera_proxy/camera.config_test')
    assert aioclient_mock.call_count == 1
    assert resp.status == 200
    body = yield from resp.text()
    assert body == 'hello world'

    hass.states.async_set('sensor.temp', '15')

    # Url change = fetch new image
    resp = yield from client.get('/api/camera_proxy/camera.config_test')
    assert aioclient_mock.call_count == 2
    assert resp.status == 200
    body = yield from resp.text()
    assert body == 'hello planet'

    # Cause a template render error
    hass.states.async_remove('sensor.temp')
    resp = yield from client.get('/api/camera_proxy/camera.config_test')
    assert aioclient_mock.call_count == 2
    assert resp.status == 200
    body = yield from resp.text()
    assert body == 'hello planet'


@asyncio.coroutine
def test_camera_content_type(aioclient_mock, hass, hass_client):
    """Test generic camera with custom content_type."""
    svg_image = '<some image>'
    urlsvg = 'https://upload.wikimedia.org/wikipedia/commons/0/02/SVG_logo.svg'
    aioclient_mock.get(urlsvg, text=svg_image)

    cam_config_svg = {
        'name': 'config_test_svg',
        'platform': 'generic',
        'still_image_url': urlsvg,
        'content_type': 'image/svg+xml',
    }
    cam_config_normal = cam_config_svg.copy()
    cam_config_normal.pop('content_type')
    cam_config_normal['name'] = 'config_test_jpg'

    yield from async_setup_component(hass, 'camera', {
        'camera': [cam_config_svg, cam_config_normal]})

    client = yield from hass_client()

    resp_1 = yield from client.get('/api/camera_proxy/camera.config_test_svg')
    assert aioclient_mock.call_count == 1
    assert resp_1.status == 200
    assert resp_1.content_type == 'image/svg+xml'
    body = yield from resp_1.text()
    assert body == svg_image

    resp_2 = yield from client.get('/api/camera_proxy/camera.config_test_jpg')
    assert aioclient_mock.call_count == 2
    assert resp_2.status == 200
    assert resp_2.content_type == 'image/jpeg'
    body = yield from resp_2.text()
    assert body == svg_image
