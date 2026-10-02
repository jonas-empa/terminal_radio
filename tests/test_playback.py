"""Tests for the direct-stream playback session."""

from terminal_radio.models import Channel
from terminal_radio.playback import StreamSession


def make_session() -> StreamSession:
    channel = Channel(
        station="somafm", key="groovesalad", name="Groove Salad",
        stream_url="https://api.somafm.com/groovesalad.pls",
    )
    return StreamSession(channel=channel)


def test_fresh_session_defaults():
    session = make_session()
    assert session.active
    assert not session.progressed
    assert session.failures == 0
    assert session.started_since == 0.0
    assert session.elapsed_since_start == 0.0


def test_mark_started_resets_stall_tracking():
    session = make_session()
    session.progressed = True
    session.mark_started()
    assert session.started_since > 0.0
    assert not session.progressed
    assert session.elapsed_since_start >= 0.0
