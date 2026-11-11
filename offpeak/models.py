"""Shared data types. Minimal for now: section 8 of docs/PLAN.md is agreed on Day 2."""

from dataclasses import dataclass


@dataclass
class Site:
    id: int
    name: str
    lat: float
    lon: float
    zone: str = "DE-LU"
    tilt_deg: float = 30.0
    azimuth_deg: float = 180.0  # compass bearing, 180 = south (see PLAN.md, conventions)
