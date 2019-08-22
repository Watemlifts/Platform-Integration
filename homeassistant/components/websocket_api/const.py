"""Websocket constants."""
import asyncio
from concurrent import futures
from functools import partial
import json
from homeassistant.helpers.json import JSONEncoder

DOMAIN = 'websocket_api'
URL = '/api/websocket'
MAX_PENDING_MSG = 512

ERR_ID_REUSE = 'id_reuse'
ERR_INVALID_FORMAT = 'invalid_format'
ERR_NOT_FOUND = 'not_found'
ERR_HOME_ASSISTANT_ERROR = 'home_assistant_error'
ERR_UNKNOWN_COMMAND = 'unknown_command'
ERR_UNKNOWN_ERROR = 'unknown_error'
ERR_UNAUTHORIZED = 'unauthorized'
ERR_TIMEOUT = 'timeout'

TYPE_RESULT = 'result'

# Define the possible errors that occur when connections are cancelled.
# Originally, this was just asyncio.CancelledError, but issue #9546 showed
# that futures.CancelledErrors can also occur in some situations.
CANCELLATION_ERRORS = (asyncio.CancelledError, futures.CancelledError)

# Event types
SIGNAL_WEBSOCKET_CONNECTED = 'websocket_connected'
SIGNAL_WEBSOCKET_DISCONNECTED = 'websocket_disconnected'

# Data used to store the current connection list
DATA_CONNECTIONS = DOMAIN + '.connections'

JSON_DUMP = partial(json.dumps, cls=JSONEncoder, allow_nan=False)
