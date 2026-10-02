"""Station registry: every streaming platform the app can browse."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx

from ..models import Channel, Station
from . import hardcoreradio, nightride, radioparadise, somafm

FetchChannels = Callable[[httpx.AsyncClient], Awaitable[list[Channel]]]


@dataclass(frozen=True, slots=True)
class StationSource:
    """A station plus the strategy that yields its channel list."""

    station: Station
    fetch: FetchChannels


# Display order — Favorites is synthesized by the app and always first.
SOURCES: tuple[StationSource, ...] = (
    StationSource(radioparadise.STATION, radioparadise.fetch_channels),
    StationSource(somafm.STATION, somafm.fetch_channels),
    StationSource(nightride.STATION, nightride.fetch_channels),
    StationSource(hardcoreradio.STATION, hardcoreradio.fetch_channels),
)

__all__ = ["SOURCES", "StationSource"]
