"""The tests for the hassio component."""

from aiohttp.hdrs import X_FORWARDED_FOR, X_FORWARDED_HOST, X_FORWARDED_PROTO
import pytest


@pytest.mark.parametrize(
    'build_type', [
        ("a3_vl", "test/beer/ping?index=1"), ("core", "index.html"),
        ("local", "panel/config"), ("jk_921", "editor.php?idx=3&ping=5"),
        ("fsadjf10312", "")
    ])
async def test_ingress_request_get(
        hassio_client, build_type, aioclient_mock):
    """Test no auth needed for ."""
    aioclient_mock.get("http://127.0.0.1/ingress/{}/{}".format(
        build_type[0], build_type[1]), text="test")

    resp = await hassio_client.get(
        '/api/hassio_ingress/{}/{}'.format(build_type[0], build_type[1]),
        headers={"X-Test-Header": "beer"}
    )

    # Check we got right response
    assert resp.status == 200
    body = await resp.text()
    assert body == "test"

    # Check we forwarded command
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[-1][3]["X-Hassio-Key"] == "123456"
    assert aioclient_mock.mock_calls[-1][3]["X-Ingress-Path"] == \
        "/api/hassio_ingress/{}".format(build_type[0])
    assert aioclient_mock.mock_calls[-1][3]["X-Test-Header"] == "beer"
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_FOR]
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_HOST]
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_PROTO]


@pytest.mark.parametrize(
    'build_type', [
        ("a3_vl", "test/beer/ping?index=1"), ("core", "index.html"),
        ("local", "panel/config"), ("jk_921", "editor.php?idx=3&ping=5"),
        ("fsadjf10312", "")
    ])
async def test_ingress_request_post(
        hassio_client, build_type, aioclient_mock):
    """Test no auth needed for ."""
    aioclient_mock.post("http://127.0.0.1/ingress/{}/{}".format(
        build_type[0], build_type[1]), text="test")

    resp = await hassio_client.post(
        '/api/hassio_ingress/{}/{}'.format(build_type[0], build_type[1]),
        headers={"X-Test-Header": "beer"}
    )

    # Check we got right response
    assert resp.status == 200
    body = await resp.text()
    assert body == "test"

    # Check we forwarded command
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[-1][3]["X-Hassio-Key"] == "123456"
    assert aioclient_mock.mock_calls[-1][3]["X-Ingress-Path"] == \
        "/api/hassio_ingress/{}".format(build_type[0])
    assert aioclient_mock.mock_calls[-1][3]["X-Test-Header"] == "beer"
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_FOR]
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_HOST]
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_PROTO]


@pytest.mark.parametrize(
    'build_type', [
        ("a3_vl", "test/beer/ping?index=1"), ("core", "index.html"),
        ("local", "panel/config"), ("jk_921", "editor.php?idx=3&ping=5"),
        ("fsadjf10312", "")
    ])
async def test_ingress_request_put(
        hassio_client, build_type, aioclient_mock):
    """Test no auth needed for ."""
    aioclient_mock.put("http://127.0.0.1/ingress/{}/{}".format(
        build_type[0], build_type[1]), text="test")

    resp = await hassio_client.put(
        '/api/hassio_ingress/{}/{}'.format(build_type[0], build_type[1]),
        headers={"X-Test-Header": "beer"}
    )

    # Check we got right response
    assert resp.status == 200
    body = await resp.text()
    assert body == "test"

    # Check we forwarded command
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[-1][3]["X-Hassio-Key"] == "123456"
    assert aioclient_mock.mock_calls[-1][3]["X-Ingress-Path"] == \
        "/api/hassio_ingress/{}".format(build_type[0])
    assert aioclient_mock.mock_calls[-1][3]["X-Test-Header"] == "beer"
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_FOR]
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_HOST]
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_PROTO]


@pytest.mark.parametrize(
    'build_type', [
        ("a3_vl", "test/beer/ping?index=1"), ("core", "index.html"),
        ("local", "panel/config"), ("jk_921", "editor.php?idx=3&ping=5"),
        ("fsadjf10312", "")
    ])
async def test_ingress_request_delete(
        hassio_client, build_type, aioclient_mock):
    """Test no auth needed for ."""
    aioclient_mock.delete("http://127.0.0.1/ingress/{}/{}".format(
        build_type[0], build_type[1]), text="test")

    resp = await hassio_client.delete(
        '/api/hassio_ingress/{}/{}'.format(build_type[0], build_type[1]),
        headers={"X-Test-Header": "beer"}
    )

    # Check we got right response
    assert resp.status == 200
    body = await resp.text()
    assert body == "test"

    # Check we forwarded command
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[-1][3]["X-Hassio-Key"] == "123456"
    assert aioclient_mock.mock_calls[-1][3]["X-Ingress-Path"] == \
        "/api/hassio_ingress/{}".format(build_type[0])
    assert aioclient_mock.mock_calls[-1][3]["X-Test-Header"] == "beer"
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_FOR]
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_HOST]
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_PROTO]


@pytest.mark.parametrize(
    'build_type', [
        ("a3_vl", "test/beer/ping?index=1"), ("core", "index.html"),
        ("local", "panel/config"), ("jk_921", "editor.php?idx=3&ping=5"),
        ("fsadjf10312", "")
    ])
async def test_ingress_request_patch(
        hassio_client, build_type, aioclient_mock):
    """Test no auth needed for ."""
    aioclient_mock.patch("http://127.0.0.1/ingress/{}/{}".format(
        build_type[0], build_type[1]), text="test")

    resp = await hassio_client.patch(
        '/api/hassio_ingress/{}/{}'.format(build_type[0], build_type[1]),
        headers={"X-Test-Header": "beer"}
    )

    # Check we got right response
    assert resp.status == 200
    body = await resp.text()
    assert body == "test"

    # Check we forwarded command
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[-1][3]["X-Hassio-Key"] == "123456"
    assert aioclient_mock.mock_calls[-1][3]["X-Ingress-Path"] == \
        "/api/hassio_ingress/{}".format(build_type[0])
    assert aioclient_mock.mock_calls[-1][3]["X-Test-Header"] == "beer"
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_FOR]
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_HOST]
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_PROTO]


@pytest.mark.parametrize(
    'build_type', [
        ("a3_vl", "test/beer/ping?index=1"), ("core", "index.html"),
        ("local", "panel/config"), ("jk_921", "editor.php?idx=3&ping=5"),
        ("fsadjf10312", "")
    ])
async def test_ingress_request_options(
        hassio_client, build_type, aioclient_mock):
    """Test no auth needed for ."""
    aioclient_mock.options("http://127.0.0.1/ingress/{}/{}".format(
        build_type[0], build_type[1]), text="test")

    resp = await hassio_client.options(
        '/api/hassio_ingress/{}/{}'.format(build_type[0], build_type[1]),
        headers={"X-Test-Header": "beer"}
    )

    # Check we got right response
    assert resp.status == 200
    body = await resp.text()
    assert body == "test"

    # Check we forwarded command
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[-1][3]["X-Hassio-Key"] == "123456"
    assert aioclient_mock.mock_calls[-1][3]["X-Ingress-Path"] == \
        "/api/hassio_ingress/{}".format(build_type[0])
    assert aioclient_mock.mock_calls[-1][3]["X-Test-Header"] == "beer"
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_FOR]
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_HOST]
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_PROTO]


@pytest.mark.parametrize(
    'build_type', [
        ("a3_vl", "test/beer/ws"), ("core", "ws.php"),
        ("local", "panel/config/stream"), ("jk_921", "hulk"),
        ("demo", "ws/connection?id=9&token=SJAKWS283")
    ])
async def test_ingress_websocket(
        hassio_client, build_type, aioclient_mock):
    """Test no auth needed for ."""
    aioclient_mock.get("http://127.0.0.1/ingress/{}/{}".format(
        build_type[0], build_type[1]))

    # Ignore error because we can setup a full IO infrastructure
    await hassio_client.ws_connect(
        '/api/hassio_ingress/{}/{}'.format(build_type[0], build_type[1]),
        headers={"X-Test-Header": "beer"}
    )

    # Check we forwarded command
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[-1][3]["X-Hassio-Key"] == "123456"
    assert aioclient_mock.mock_calls[-1][3]["X-Ingress-Path"] == \
        "/api/hassio_ingress/{}".format(build_type[0])
    assert aioclient_mock.mock_calls[-1][3]["X-Test-Header"] == "beer"
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_FOR]
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_HOST]
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_PROTO]
