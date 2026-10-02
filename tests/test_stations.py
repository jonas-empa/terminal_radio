"""Tests for station registries and channel catalog parsing."""

from __future__ import annotations

from terminal_radio.models import FAVORITES_KEY, Channel, Station
from terminal_radio.stations import SOURCES, StationSource
from terminal_radio.stations import hardcoreradio, nightride, radioparadise, somafm

SOMAFM_SAMPLE = {
    "channels": [
        {
            "id": "groovesalad",
            "title": "Groove Salad",
            "description": "ambient/downtempo",
            "genre": "ambient",
            "lastPlaying": "Mandrillus Sphynx - The Drill",
            "playlists": [
                {"url": "https://api.somafm.com/groovesalad.pls", "format": "mp3", "quality": "highest"},
                {"url": "https://api.somafm.com/groovesalad130.pls", "format": "aac", "quality": "highest"},
                {"url": "https://api.somafm.com/groovesalad64.pls", "format": "aacp", "quality": "high"},
            ],
        },
        {
            "id": "",
            "title": "Broken Entry",
            "playlists": [],
        },
        {
            "id": "thetrip",
            "title": "The Trip",
            "description": "progressive house / trance",
            "playlists": [
                {"url": "https://api.somafm.com/thetrip64.pls", "format": "aacp", "quality": "high"},
                {"url": "https://api.somafm.com/thetrip.pls", "format": "mp3", "quality": "highest"},
            ],
        },
    ]
}


def test_registry_has_unique_station_keys():
    keys = [source.station.key for source in SOURCES]
    assert len(keys) == len(set(keys))
    # stable, explicit display order
    assert keys == ["radioparadise", "somafm", "nightride", "hardcoreradio"]
    assert FAVORITES_KEY not in keys


def test_registry_matches_shipped_stations():
    keys = {source.station.key for source in SOURCES}
    assert keys == {"radioparadise", "somafm", "nightride", "hardcoreradio"}


def test_somafm_parse_channels():
    channels = somafm.parse_channels(SOMAFM_SAMPLE)
    # the broken entry (no id/title) is skipped
    assert [c.key for c in channels] == ["groovesalad", "thetrip"]
    groove = channels[0]
    assert groove.station == "somafm"
    assert groove.name == "Groove Salad"
    assert groove.description == "ambient/downtempo"
    assert groove.now_playing == "Mandrillus Sphynx - The Drill"
    # highest-quality MP3 wins even when it is not the first entry
    assert groove.stream_url == "https://api.somafm.com/groovesalad.pls"


def test_somafm_parse_rejects_non_dict_payload():
    assert somafm.parse_channels(None) == []
    assert somafm.parse_channels([1, 2, 3]) == []


def test_somafm_pick_stream_falls_back():
    # no mp3 available: falls back to the best remaining option
    aac = [{"url": "https://x/64.pls", "format": "aacp", "quality": "high"}]
    assert somafm.pick_stream(aac) == "https://x/64.pls"
    assert somafm.pick_stream([]) == ""


async def test_somafm_fetch_channels(monkeypatch):
    async def fake_get(client, url, **params):
        assert url == somafm.CATALOG_URL
        return SOMAFM_SAMPLE

    monkeypatch.setattr(somafm, "fetch_json", fake_get)
    channels = await somafm.fetch_channels(None)
    assert len(channels) == 2


async def test_radioparadise_catalog():
    channels = await radioparadise.fetch_channels(None)
    assert len(channels) >= 6
    assert all(c.station == "radioparadise" for c in channels)
    assert all(c.stream_url.startswith("https://stream.radioparadise.com/") for c in channels)
    # every slug previously verified live
    slugs = {c.stream_url.rsplit("/", 1)[-1] for c in channels}
    assert slugs == {"mp3-192", "mellow-192", "rock-192", "world-etc-192", "global-192", "beyond-192"}


async def test_nightride_catalog():
    channels = await nightride.fetch_channels(None)
    assert len(channels) == 7
    assert all(c.station == "nightride" for c in channels)
    assert all(c.stream_url.startswith("https://stream.nightride.fm/") for c in channels)
    mounts = {c.stream_url.rsplit("/", 1)[-1] for c in channels}
    assert mounts == {
        "nightride.mp3",
        "chillsynth.mp3",
        "datawave.mp3",
        "spacesynth.mp3",
        "darksynth.mp3",
        "horrorsynth.mp3",
        "ebsm.mp3",
    }


async def test_hardcoreradio_catalog():
    channels = await hardcoreradio.fetch_channels(None)
    assert len(channels) == 1
    channel = channels[0]
    assert channel.station == "hardcoreradio"
    assert channel.stream_url == "http://shoutcast1.hardcoreradio.nl/"


def test_channel_composite_id():
    channel = Channel(station="somafm", key="groovesalad", name="Groove Salad")
    assert channel.id == "somafm:groovesalad"


def test_station_source_is_dataclass():
    station = Station(key="x", name="X")
    source = StationSource(station=station, fetch=None)
    assert source.station.key == "x"
