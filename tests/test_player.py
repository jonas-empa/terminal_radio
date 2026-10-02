"""Tests for VLC RC response parsing and helpers."""

import pytest

import terminal_radio.player as player_module
from terminal_radio.player import (
    PlayerError,
    VlcPlayer,
    find_vlc,
    parse_int,
    parse_status,
    volume_to_rc,
    volume_to_ui,
)


PLAYING = (
    "( new input: https://stream.nightride.fm/nightride.mp3 )\r\n"
    "( audio volume: 180 )\r\n"
    "( state playing )\r\n"
    ">"
)

PAUSED = "( state paused )\n>"

STOPPED_AFTER_END = "( audio volume: 180 )\r\n( state stopped )\r\n>"

FRESH = "( audio volume: 0 )\r\n( state stopped )\r\n>"


def test_parse_status_playing():
    st = parse_status(PLAYING)
    assert st.state == "playing"
    assert st.url == "https://stream.nightride.fm/nightride.mp3"
    assert st.volume == 180


def test_parse_status_paused_without_input():
    st = parse_status(PAUSED)
    assert st.state == "paused"
    assert st.url is None


def test_parse_status_stopped():
    st = parse_status(STOPPED_AFTER_END)
    assert st.state == "stopped"
    assert st.url is None
    assert st.volume == 180


def test_parse_status_fresh():
    st = parse_status(FRESH)
    assert st.state == "stopped"
    assert st.url is None
    assert st.volume == 0


def test_parse_status_ignores_noise():
    st = parse_status(
        "VLC media player 3.0.20 Vetinari\n"
        "Command Line Interface initialized.\n"
        "( state playing )\n>"
    )
    assert st.state == "playing"


def test_parse_int():
    assert parse_int("42\r\n>") == 42
    assert parse_int("-1\n>") == -1
    assert parse_int(">") is None
    assert parse_int("") is None


def test_volume_scaling():
    assert volume_to_rc(0) == 0
    assert volume_to_rc(100) == 256
    assert volume_to_rc(70) == 179
    assert volume_to_rc(250) == 256  # clamped to UI range first
    assert volume_to_ui(256) == 100
    assert volume_to_ui(128) == 50


# --------------------------------------------------------------------- #
# VLC discovery / missing-VLC reporting
# --------------------------------------------------------------------- #
def test_find_vlc_returns_path(monkeypatch):
    monkeypatch.setattr(
        player_module.shutil, "which", lambda name: f"/usr/bin/{name}"
    )
    assert find_vlc() == "/usr/bin/vlc"


def test_find_vlc_returns_none_when_absent(monkeypatch):
    monkeypatch.setattr(player_module.shutil, "which", lambda name: None)
    assert find_vlc() is None


def test_find_vlc_raises_helpful_error_when_absent(monkeypatch):
    monkeypatch.setattr(player_module.shutil, "which", lambda name: None)
    with pytest.raises(PlayerError, match="apt install vlc"):
        player_module._find_vlc()


async def test_start_fails_cleanly_without_vlc(monkeypatch):
    """No VLC: start() raises a clear error instead of a FileNotFoundError."""
    monkeypatch.setattr(player_module.shutil, "which", lambda name: None)
    player = VlcPlayer()
    try:
        with pytest.raises(PlayerError, match="apt install vlc"):
            await player.start(70)
        assert player._proc is None  # nothing was spawned
    finally:
        await player.close()  # unregister the atexit hook
