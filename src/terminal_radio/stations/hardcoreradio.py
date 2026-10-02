"""Hardcoreradio.nl: Dutch 24/7 mainstream hardcore & gabber.

Single Shoutcast DNAS stream; VLC follows the ICY redirect natively.
Verified live (HTTP 200 after redirect, 256 kbps MP3).
"""

from __future__ import annotations

import httpx

from ..models import Channel, Station

STATION = Station(
    key="hardcoreradio",
    name="Hardcoreradio.nl",
    description="Dutch hardcore and gabber, 24/7 from the Netherlands.",
)

STREAM_URL = "http://shoutcast1.hardcoreradio.nl/"


def parse_channels() -> list[Channel]:
    return [
        Channel(
            station=STATION.key,
            key="main",
            name="Hardcore Radio",
            description=(
                "HARDCORERADIO.NL — 24/7 Mainstream Hardcore & Gabber "
                "(256 kbps MP3, Shoutcast)."
            ),
            stream_url=STREAM_URL,
        )
    ]


async def fetch_channels(client: httpx.AsyncClient) -> list[Channel]:
    del client  # static catalog, no network needed
    return parse_channels()
