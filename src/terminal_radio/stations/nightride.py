"""Nightride FM and its sister synth channels: direct Icecast MP3 mounts.

All mounts live on ``stream.nightride.fm`` and were verified live
(HTTP 200, audio/mpeg). The ``.mp3`` variants are used (320 kbps).
"""

from __future__ import annotations

import httpx

from ..models import Channel, Station

STATION = Station(
    key="nightride",
    name="Nightride FM",
    description=(
        "Independent synthwave radio — outrun, chillsynth, darksynth and "
        "more, 24/7 with no account needed."
    ),
)

_BASE = "https://stream.nightride.fm"

# (channel key, display name, mount, description)
_CHANNELS = (
    ("nightride", "Nightride FM", "nightride",
     "Synthwave / Retrowave / Outrun — the original channel."),
    ("chillsynth", "Chillsynth FM", "chillsynth",
     "Chillsynth / chillwave / instrumental."),
    ("datawave", "Datawave FM", "datawave",
     "Glitchy synthwave / IDM / retro computing."),
    ("spacesynth", "Spacesynth FM", "spacesynth",
     "Spacesynth / space disco / vocoder italo."),
    ("darksynth", "Darksynth", "darksynth",
     "Darksynth / cyberpunk / synthmetal."),
    ("horrorsynth", "Horrorsynth", "horrorsynth",
     "Horrorsynth / witch house."),
    ("ebsm", "EBSM", "ebsm",
     "Electro-industrial / body music / clubbing."),
)


def parse_channels() -> list[Channel]:
    return [
        Channel(
            station=STATION.key,
            key=key,
            name=name,
            description=description,
            stream_url=f"{_BASE}/{mount}.mp3",
        )
        for key, name, mount, description in _CHANNELS
    ]


async def fetch_channels(client: httpx.AsyncClient) -> list[Channel]:
    del client  # static catalog, no network needed
    return parse_channels()
