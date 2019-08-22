"""HTTP Support for Hass.io."""
import asyncio
import logging
import os
import re
from typing import Dict, Union

import aiohttp
from aiohttp import web
from aiohttp.hdrs import CONTENT_TYPE, CONTENT_LENGTH
from aiohttp.web_exceptions import HTTPBadGateway
import async_timeout

from homeassistant.components.http import KEY_AUTHENTICATED, HomeAssistantView

from .const import X_HASS_IS_ADMIN, X_HASS_USER_ID, X_HASSIO

_LOGGER = logging.getLogger(__name__)


NO_TIMEOUT = re.compile(
    r'^(?:'
    r'|homeassistant/update'
    r'|hassos/update'
    r'|hassos/update/cli'
    r'|supervisor/update'
    r'|addons/[^/]+/(?:update|install|rebuild)'
    r'|snapshots/.+/full'
    r'|snapshots/.+/partial'
    r'|snapshots/[^/]+/(?:upload|download)'
    r')$'
)

NO_AUTH = re.compile(
    r'^(?:'
    r'|app/.*'
    r'|addons/[^/]+/logo'
    r')$'
)


class HassIOView(HomeAssistantView):
    """Hass.io view to handle base part."""

    name = "api:hassio"
    url = "/api/hassio/{path:.+}"
    requires_auth = False

    def __init__(self, host: str, websession: aiohttp.ClientSession):
        """Initialize a Hass.io base view."""
        self._host = host
        self._websession = websession

    async def _handle(
            self, request: web.Request, path: str
    ) -> Union[web.Response, web.StreamResponse]:
        """Route data to Hass.io."""
        if _need_auth(path) and not request[KEY_AUTHENTICATED]:
            return web.Response(status=401)

        return await self._command_proxy(path, request)

    get = _handle
    post = _handle

    async def _command_proxy(
            self, path: str, request: web.Request
    ) -> Union[web.Response, web.StreamResponse]:
        """Return a client request with proxy origin for Hass.io supervisor.

        This method is a coroutine.
        """
        read_timeout = _get_timeout(path)
        data = None
        headers = _init_header(request)

        try:
            with async_timeout.timeout(10):
                data = await request.read()

            method = getattr(self._websession, request.method.lower())
            client = await method(
                "http://{}/{}".format(self._host, path), data=data,
                headers=headers, timeout=read_timeout
            )

            # Simple request
            if int(client.headers.get(CONTENT_LENGTH, 0)) < 4194000:
                # Return Response
                body = await client.read()
                return web.Response(
                    content_type=client.content_type,
                    status=client.status,
                    body=body,
                )

            # Stream response
            response = web.StreamResponse(status=client.status)
            response.content_type = client.content_type

            await response.prepare(request)
            async for data in client.content.iter_chunked(4096):
                await response.write(data)

            return response

        except aiohttp.ClientError as err:
            _LOGGER.error("Client error on api %s request %s", path, err)

        except asyncio.TimeoutError:
            _LOGGER.error("Client timeout error on API request %s", path)

        raise HTTPBadGateway()


def _init_header(request: web.Request) -> Dict[str, str]:
    """Create initial header."""
    headers = {
        X_HASSIO: os.environ.get('HASSIO_TOKEN', ""),
        CONTENT_TYPE: request.content_type,
    }

    # Add user data
    user = request.get('hass_user')
    if user is not None:
        headers[X_HASS_USER_ID] = request['hass_user'].id
        headers[X_HASS_IS_ADMIN] = str(int(request['hass_user'].is_admin))

    return headers


def _get_timeout(path: str) -> int:
    """Return timeout for a URL path."""
    if NO_TIMEOUT.match(path):
        return 0
    return 300


def _need_auth(path: str) -> bool:
    """Return if a path need authentication."""
    if NO_AUTH.match(path):
        return False
    return True
