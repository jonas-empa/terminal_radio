"""Data models for stations and channels."""

from __future__ import annotations

from dataclasses import dataclass

# Pseudo-station key used for the aggregated favorites view.
FAVORITES_KEY = "*"


@dataclass(frozen=True, slots=True)
class Station:
    """A streaming platform (SomaFM, Radio Paradise, ...)."""

    key: str
    name: str
    description: str = ""


@dataclass(frozen=True, slots=True)
class Channel:
    """A single playable channel of a station.

    ``stream_url`` is a direct Icecast/Shoutcast/playlist URL that VLC can
    open as-is — there is no per-track resolution step.
    """

    station: str  # Station.key of the owning station
    key: str  # unique within the station
    name: str
    description: str = ""
    stream_url: str = ""
    now_playing: str = ""  # best-effort "currently on air" text

    @property
    def id(self) -> str:
        """Globally unique id, safe to use as a favorites key or row key."""
        return f"{self.station}:{self.key}"
