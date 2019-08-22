"""Unit system helper class and methods."""

import logging
from typing import Optional
from numbers import Number

from homeassistant.const import (
    TEMP_CELSIUS, TEMP_FAHRENHEIT, LENGTH_MILES, LENGTH_KILOMETERS,
    PRESSURE_PA, PRESSURE_PSI, VOLUME_LITERS, VOLUME_GALLONS,
    MASS_GRAMS, MASS_KILOGRAMS, MASS_OUNCES, MASS_POUNDS,
    CONF_UNIT_SYSTEM_METRIC, CONF_UNIT_SYSTEM_IMPERIAL, LENGTH, MASS, PRESSURE,
    VOLUME, TEMPERATURE, UNIT_NOT_RECOGNIZED_TEMPLATE)
from homeassistant.util import temperature as temperature_util
from homeassistant.util import distance as distance_util
from homeassistant.util import pressure as pressure_util
from homeassistant.util import volume as volume_util

_LOGGER = logging.getLogger(__name__)

LENGTH_UNITS = distance_util.VALID_UNITS

MASS_UNITS = [
    MASS_POUNDS,
    MASS_OUNCES,
    MASS_KILOGRAMS,
    MASS_GRAMS,
]

PRESSURE_UNITS = pressure_util.VALID_UNITS

VOLUME_UNITS = volume_util.VALID_UNITS

TEMPERATURE_UNITS = [
    TEMP_FAHRENHEIT,
    TEMP_CELSIUS,
]


def is_valid_unit(unit: str, unit_type: str) -> bool:
    """Check if the unit is valid for it's type."""
    if unit_type == LENGTH:
        units = LENGTH_UNITS
    elif unit_type == TEMPERATURE:
        units = TEMPERATURE_UNITS
    elif unit_type == MASS:
        units = MASS_UNITS
    elif unit_type == VOLUME:
        units = VOLUME_UNITS
    elif unit_type == PRESSURE:
        units = PRESSURE_UNITS
    else:
        return False

    return unit in units


class UnitSystem:
    """A container for units of measure."""

    def __init__(self, name: str, temperature: str, length: str,
                 volume: str, mass: str, pressure: str) -> None:
        """Initialize the unit system object."""
        errors = \
            ', '.join(UNIT_NOT_RECOGNIZED_TEMPLATE.format(unit, unit_type)
                      for unit, unit_type in [
                          (temperature, TEMPERATURE),
                          (length, LENGTH),
                          (volume, VOLUME),
                          (mass, MASS),
                          (pressure, PRESSURE), ]
                      if not is_valid_unit(unit, unit_type))  # type: str

        if errors:
            raise ValueError(errors)

        self.name = name
        self.temperature_unit = temperature
        self.length_unit = length
        self.mass_unit = mass
        self.pressure_unit = pressure
        self.volume_unit = volume

    @property
    def is_metric(self) -> bool:
        """Determine if this is the metric unit system."""
        return self.name == CONF_UNIT_SYSTEM_METRIC

    def temperature(self, temperature: float, from_unit: str) -> float:
        """Convert the given temperature to this unit system."""
        if not isinstance(temperature, Number):
            raise TypeError(
                '{} is not a numeric value.'.format(str(temperature)))

        return temperature_util.convert(temperature,
                                        from_unit, self.temperature_unit)

    def length(self, length: Optional[float], from_unit: str) -> float:
        """Convert the given length to this unit system."""
        if not isinstance(length, Number):
            raise TypeError('{} is not a numeric value.'.format(str(length)))

        return distance_util.convert(length, from_unit,
                                     self.length_unit)

    def pressure(self, pressure: Optional[float], from_unit: str) -> float:
        """Convert the given pressure to this unit system."""
        if not isinstance(pressure, Number):
            raise TypeError('{} is not a numeric value.'.format(str(pressure)))

        return pressure_util.convert(pressure, from_unit,
                                     self.pressure_unit)

    def volume(self, volume: Optional[float], from_unit: str) -> float:
        """Convert the given volume to this unit system."""
        if not isinstance(volume, Number):
            raise TypeError('{} is not a numeric value.'.format(str(volume)))

        return volume_util.convert(volume, from_unit, self.volume_unit)

    def as_dict(self) -> dict:
        """Convert the unit system to a dictionary."""
        return {
            LENGTH: self.length_unit,
            MASS: self.mass_unit,
            PRESSURE: self.pressure_unit,
            TEMPERATURE: self.temperature_unit,
            VOLUME: self.volume_unit
        }


METRIC_SYSTEM = UnitSystem(CONF_UNIT_SYSTEM_METRIC, TEMP_CELSIUS,
                           LENGTH_KILOMETERS, VOLUME_LITERS, MASS_GRAMS,
                           PRESSURE_PA)

IMPERIAL_SYSTEM = UnitSystem(CONF_UNIT_SYSTEM_IMPERIAL, TEMP_FAHRENHEIT,
                             LENGTH_MILES, VOLUME_GALLONS, MASS_POUNDS,
                             PRESSURE_PSI)
