"""Radio Paradise: hand-curated mixes as direct Icecast MP3 streams.

The six stream slugs below were verified live (HTTP 200, audio/mpeg).
"""

from __future__ import annotations

import httpx

from ..models import Channel, Station

STATION = Station(
    key="radioparadise",
    name="Radio Paradise",
    description=(
        "Human-curated eclectic mixes in high quality, commercial-free and "
        "donation-supported since 2000."
    ),
)

_BASE = "https://stream.radioparadise.com"

# (channel key, display name, stream slug, description)
_CHANNELS = (
    ("main", "The Main Mix", "mp3-192",
     "The original Radio Paradise mix — rock, pop, world and electronica, "
     "hand-picked and blended."),
    ("mellow", "The Mellow Mix", "mellow-192",
     "Softer, more relaxed selections from the RP library."),
    ("rock", "The Rock Mix", "rock-192",
     "Rock-oriented picks, classic and modern."),
    ("world-etc", "World / Etc", "world-etc-192",
     "World music, international folk, reggae and beyond."),
    ("global", "The Global Mix", "global-192",
     "A wider, more contemporary global selection."),
    ("beyond", "Beyond", "beyond-192",
     "Electronica, ambient, experimental and left-field tracks."),
)


def parse_channels() -> list[Channel]:
    return [
        Channel(
            station=STATION.key,
            key=key,
            name=name,
            description=description,
            stream_url=f"{_BASE}/{slug}",
        )
        for key, name, slug, description in _CHANNELS
    ]


async def fetch_channels(client: httpx.AsyncClient) -> list[Channel]:
    del client  # static catalog, no network needed
    return parse_channels()
