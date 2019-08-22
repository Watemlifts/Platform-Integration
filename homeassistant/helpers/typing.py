"""Typing Helpers for Home Assistant."""
from typing import Dict, Any, Tuple, Optional

import homeassistant.core

# pylint: disable=invalid-name

GPSType = Tuple[float, float]
ConfigType = Dict[str, Any]
ContextType = homeassistant.core.Context
EventType = homeassistant.core.Event
HomeAssistantType = homeassistant.core.HomeAssistant
ServiceCallType = homeassistant.core.ServiceCall
ServiceDataType = Dict[str, Any]
TemplateVarsType = Optional[Dict[str, Any]]

# Custom type for recorder Queries
QueryType = Any
