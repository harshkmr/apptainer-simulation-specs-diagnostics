"""
Unit conversion utilities for finite-volume groundwater simulation diagnostics.
Standardizes pressure head, flux, hydraulic conductivity, and time to SI base units.
"""

# Constants for groundwater modeling
RHO_WATER = 1000.0  # kg/m3
GRAVITY = 9.80665  # m/s2
PASCAL_PER_METER_HEAD = RHO_WATER * GRAVITY  # ~9806.65 Pa/m


def convert_head_to_meters(value: float, unit: str = "m") -> float:
    """
    Converts pressure head / hydraulic head to meters.
    """
    if not unit:
        return value

    u = unit.strip().lower()
    if u in ("m", "meter", "meters"):
        return value
    elif u in ("ft", "feet", "foot"):
        return value * 0.3048
    elif u in ("in", "inch", "inches"):
        return value * 0.0254
    elif u in ("cm", "centimeter"):
        return value * 0.01
    elif u in ("pa", "pascal", "pascals"):
        return value / PASCAL_PER_METER_HEAD
    elif u in ("kpa", "kilopascal", "kilopascals"):
        return (value * 1000.0) / PASCAL_PER_METER_HEAD
    elif u in ("bar", "bars"):
        return (value * 100000.0) / PASCAL_PER_METER_HEAD
    elif u in ("psi", "lb/in2"):
        return (value * 6894.75729) / PASCAL_PER_METER_HEAD

    return value


def convert_flux_to_m3_per_sec(value: float, unit: str = "m3/s") -> float:
    """
    Converts fluid volumetric flux rate to cubic meters per second (m^3/s).
    """
    if not unit:
        return value

    u = unit.strip().lower()
    if u in ("m3/s", "m^3/s", "m3_per_sec", "cumec"):
        return value
    elif u in ("m3/d", "m^3/d", "m3/day", "m^3/day"):
        return value / 86400.0
    elif u in ("m3/h", "m^3/h", "m3/hour"):
        return value / 3600.0
    elif u in ("ft3/s", "ft^3/s", "cfs"):
        return value * 0.028316846592
    elif u in ("l/s", "liter/s", "liters/sec"):
        return value / 1000.0
    elif u in ("l/min", "liter/min", "lpm"):
        return value / 60000.0
    elif u in ("gpm", "gal/min", "gallon/min"):
        return value * 0.0000630901964

    return value


def convert_conductivity_to_m_per_sec(value: float, unit: str = "m/s") -> float:
    """
    Converts hydraulic conductivity (K) to meters per second (m/s).
    """
    if not unit:
        return value

    u = unit.strip().lower()
    if u in ("m/s", "m_per_sec"):
        return value
    elif u in ("m/d", "m/day"):
        return value / 86400.0
    elif u in ("ft/d", "ft/day"):
        return (value * 0.3048) / 86400.0
    elif u in ("cm/s", "cm_per_sec"):
        return value / 100.0

    return value


def convert_time_to_seconds(value: float, unit: str = "s") -> float:
    """
    Converts time duration to seconds.
    """
    if not unit:
        return value

    u = unit.strip().lower()
    if u in ("s", "sec", "second", "seconds"):
        return value
    elif u in ("min", "minute", "minutes"):
        return value * 60.0
    elif u in ("h", "hr", "hour", "hours"):
        return value * 3600.0
    elif u in ("d", "day", "days"):
        return value * 86400.0

    return value
