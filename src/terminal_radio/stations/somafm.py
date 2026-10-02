"""SomaFM: public JSON catalog of ~50 channels with direct .pls streams."""

from __future__ import annotations

from typing import Any

import httpx

from ..models import Channel, Station
from ..net import FetchError, fetch_json

STATION = Station(
    key="somafm",
    name="SomaFM",
    description=(
        "Listener-supported, commercial-free internet radio from San "
        "Francisco — Groove Salad, Drone Zone, Beat Blender and dozens more."
    ),
)

CATALOG_URL = "https://api.somafm.com/channels.json"


def pick_stream(playlists: list[dict]) -> str:
    """Pick the best playlist URL: prefer highest-quality MP3.

    SomaFM returns ``.pls`` files (which VLC opens natively) per format and
    bitrate, tagged with ``format`` (mp3/aac/aacp) and ``quality``
    (highest/high/low).
    """
    if not playlists:
        return ""
    mp3s = [p for p in playlists if p.get("format") == "mp3"]
    pool = mp3s or playlists
    best = [p for p in pool if p.get("quality") == "highest"]
    choice = best[0] if best else pool[0]
    return str(choice.get("url") or "")


def parse_channels(payload: Any) -> list[Channel]:
    """Parse the ``channels.json`` payload into Channel objects."""
    if not isinstance(payload, dict):
        return []
    channels: list[Channel] = []
    for item in payload.get("channels") or []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("id") or "").strip()
        title = str(item.get("title") or "").strip()
        if not key or not title:
            continue
        channels.append(
            Channel(
                station=STATION.key,
                key=key,
                name=title,
                description=str(item.get("description") or "").strip(),
                stream_url=pick_stream(item.get("playlists") or []),
                now_playing=str(item.get("lastPlaying") or "").strip(),
            )
        )
    channels.sort(key=lambda c: c.name.lower())
    return channels


async def fetch_channels(client: httpx.AsyncClient) -> list[Channel]:
    payload = await fetch_json(client, CATALOG_URL)
    channels = parse_channels(payload)
    if not channels:
        raise FetchError("SomaFM returned an empty channel catalog.")
    return channels
