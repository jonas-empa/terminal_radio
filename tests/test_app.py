"""Headless UI tests: station browsing, favorites, playback orchestration.

No network and no VLC: stations are injected fakes and the player is a
stub, so these run entirely offline.
"""

from __future__ import annotations

from terminal_radio import app as app_module
from terminal_radio import net
from terminal_radio.app import TerminalRadioApp
from terminal_radio.config import Config
from terminal_radio.models import Channel, Station
from terminal_radio.player import VlcStatus
from terminal_radio.stations import StationSource


def make_source(key: str, name: str, count: int = 2) -> StationSource:
    station = Station(key=key, name=name, description=f"{name} station")

    async def fetch(client) -> list[Channel]:
        return [
            Channel(
                station=key,
                key=f"ch{i}",
                name=f"{name} {i + 1}",
                description=f"channel {i + 1}",
                stream_url=f"https://streams.example/{key}/{i + 1}",
            )
            for i in range(count)
        ]

    return StationSource(station=station, fetch=fetch)


FAKE_SOURCES = [make_source("aaa", "Alpha FM"), make_source("bbb", "Beta Radio")]


class FakePlayer:
    """Stands in for VlcPlayer: records what would have been played."""

    def __init__(self, get_time_value: int = 42) -> None:
        self.running = False
        self.played: list[str] = []
        self._get_time = get_time_value

    async def start(self, volume: int) -> None:
        self.running = True

    async def play_url(self, url: str) -> None:
        self.played.append(url)

    async def enqueue(self, url: str) -> None:
        self.played.append(url)

    async def stop(self) -> None:
        pass

    async def clear(self) -> None:
        pass

    async def status(self) -> VlcStatus:
        return VlcStatus(state="playing", url=None, volume=256)

    async def get_time(self) -> int:
        return self._get_time

    async def toggle_pause(self) -> None:
        pass

    async def set_volume(self, volume: int) -> None:
        pass

    async def close(self) -> None:
        pass


def make_app(tmp_path) -> TerminalRadioApp:
    app = TerminalRadioApp(sources=FAKE_SOURCES)
    # Keep tests away from the user's real config file.
    app.config = Config(path=tmp_path / "config.json")
    return app


async def settle(pilot, rounds: int = 10) -> None:
    for _ in range(rounds):
        await pilot.pause(0.05)


def row_values(table, index: int) -> tuple:
    return table.get_row_at(index)


async def test_starts_without_login_screen(tmp_path):
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await settle(pilot)
        assert app.screen.__class__.__name__ != "LoginScreen"
        stations = app.query_one("#stations")
        assert stations.row_count == 3  # Favorites + 2 stations
        rows = [row_values(stations, i) for i in range(stations.row_count)]
        assert rows[0][1] == "Favorites"
        assert rows[0][0] == ""  # no favorites yet, so no star marker
        assert [r[1] for r in rows[1:]] == ["Alpha FM", "Beta Radio"]


async def test_selecting_station_loads_its_channels(tmp_path):
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await settle(pilot)
        channels = app.query_one("#channels")
        # no last_channel saved: cursor starts on the first station (Alpha FM)
        names = [row_values(channels, i)[1] for i in range(channels.row_count)]
        assert names == ["Alpha FM 1", "Alpha FM 2"]

        # move up onto Favorites -> empty aggregated view
        await pilot.press("up")
        await settle(pilot)
        assert app.current_station_key == "*"
        assert channels.row_count == 0

        # move down onto Beta Radio -> its channels appear
        await pilot.press("down", "down")
        await settle(pilot)
        assert app.current_station_key == "bbb"
        names = [row_values(channels, i)[1] for i in range(channels.row_count)]
        assert names == ["Beta Radio 1", "Beta Radio 2"]


async def test_favorites_aggregate_across_stations(tmp_path):
    app = make_app(tmp_path)
    app.config.favorites = ["aaa:ch0", "bbb:ch1"]
    async with app.run_test() as pilot:
        await settle(pilot)
        await pilot.press("up")  # onto the Favorites row
        await settle(pilot)
        channels = app.query_one("#channels")
        rows = [row_values(channels, i) for i in range(channels.row_count)]
        # starred channels from both stations, ordered by station then name
        assert [r[1] for r in rows] == ["Alpha FM 1", "Beta Radio 2"]
        assert [r[2] for r in rows] == ["Alpha FM", "Beta Radio"]
        assert all(r[0] == "\u2605" for r in rows)


async def test_toggle_favorite_persists_composite_key(tmp_path):
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await settle(pilot)
        channels = app.query_one("#channels")
        await pilot.press("l")  # focus the channel list
        await pilot.press("f")
        await settle(pilot)
        assert app.config.favorites == ["aaa:ch0"]
        assert row_values(channels, 0)[0] == "\u2605"
        # the Favorites row in the station list gets a star too
        assert row_values(app.query_one("#stations"), 0)[0] == "\u2605"
        # toggle back off
        await pilot.press("f")
        await settle(pilot)
        assert app.config.favorites == []


async def test_unfavorite_removes_channel_from_favorites_view(tmp_path):
    app = make_app(tmp_path)
    app.config.favorites = ["aaa:ch0"]
    async with app.run_test() as pilot:
        await settle(pilot)
        await pilot.press("up")  # Favorites view
        await settle(pilot)
        channels = app.query_one("#channels")
        assert channels.row_count == 1
        await pilot.press("l", "f")  # un-favorite it
        await settle(pilot, rounds=20)
        assert app.config.favorites == []
        assert channels.row_count == 0


async def test_search_filters_current_station(tmp_path):
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await settle(pilot)
        channels = app.query_one("#channels")
        await pilot.press("slash")
        await pilot.press("2")
        await settle(pilot)
        names = [row_values(channels, i)[1] for i in range(channels.row_count)]
        assert names == ["Alpha FM 2"]
        # Escape clears the search
        await pilot.press("escape")
        await settle(pilot)
        assert channels.row_count == 2


async def test_arrow_keys_move_between_columns(tmp_path):
    """Right arrow jumps stations -> channels, left arrow jumps back."""
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await settle(pilot)
        stations = app.query_one("#stations")
        channels = app.query_one("#channels")
        assert stations.has_focus  # stations column starts active

        await pilot.press("right")
        await pilot.pause(0.05)
        assert channels.has_focus
        assert not stations.has_focus

        await pilot.press("left")
        await pilot.pause(0.05)
        assert stations.has_focus
        assert not channels.has_focus


async def test_h_l_bindings_switch_columns(tmp_path):
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await settle(pilot)
        stations = app.query_one("#stations")
        channels = app.query_one("#channels")
        await pilot.press("l")
        await pilot.pause(0.05)
        assert channels.has_focus
        await pilot.press("h")
        await pilot.pause(0.05)
        assert stations.has_focus


async def test_enter_on_station_focuses_channels(tmp_path):
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await settle(pilot)
        await pilot.press("enter")
        await pilot.pause(0.05)
        assert app.query_one("#channels").has_focus
        # the detail pane follows the focused column: it shows a channel now
        detail = str(app.query_one("#detail").content)
        assert "channel 1" in detail


async def test_space_plays_then_stops_selected_channel(tmp_path, monkeypatch):
    """Space plays the selected channel; Space on that same channel stops."""
    async def fake_probe(client, url):
        return 200

    monkeypatch.setattr(net, "probe_stream", fake_probe)

    app = make_app(tmp_path)
    fake = FakePlayer(get_time_value=42)
    app.player = fake
    async with app.run_test() as pilot:
        await settle(pilot)
        # Space with nothing playing starts the highlighted channel
        await pilot.press("space")
        await settle(pilot)
        assert app.session is not None and app.session.active
        assert app.session.channel.id == "aaa:ch0"
        assert fake.played == ["https://streams.example/aaa/1"]
        assert app._last_state == "loading"

        # Space again on the same (active) channel -> stop
        await pilot.press("space")
        await settle(pilot)
        assert app.session is None
        assert app._last_state == "idle"

        # ...and Space starts it again
        await pilot.press("space")
        await settle(pilot)
        assert app.session is not None and app.session.active


async def test_space_on_different_channel_switches_playback(tmp_path, monkeypatch):
    async def fake_probe(client, url):
        return 200

    monkeypatch.setattr(net, "probe_stream", fake_probe)

    app = make_app(tmp_path)
    fake = FakePlayer()
    app.player = fake
    async with app.run_test() as pilot:
        await settle(pilot)
        await pilot.press("l")  # focus the channels column
        await pilot.press("space")  # plays Alpha FM 1
        await settle(pilot)
        assert app.session.channel.id == "aaa:ch0"

        await pilot.press("down")  # highlight Alpha FM 2
        await settle(pilot)
        await pilot.press("space")
        await settle(pilot)
        # the previous channel was stopped first, then the new one started
        assert app.session is not None and app.session.active
        assert app.session.channel.id == "aaa:ch1"
        assert fake.played == [
            "https://streams.example/aaa/1",
            "https://streams.example/aaa/2",
        ]


async def test_escape_does_not_stop_playback(tmp_path, monkeypatch):
    """Escape only navigates now; Space is the sole play/stop control."""
    async def fake_probe(client, url):
        return 200

    monkeypatch.setattr(net, "probe_stream", fake_probe)

    app = make_app(tmp_path)
    app.player = FakePlayer()
    async with app.run_test() as pilot:
        await settle(pilot)
        await pilot.press("l")  # focus channels
        await pilot.press("space")
        await settle(pilot)
        assert app.session is not None and app.session.active

        await pilot.press("escape")  # back to stations, playback untouched
        await pilot.pause(0.05)
        assert app.query_one("#stations").has_focus
        assert app.session is not None and app.session.active
        assert app._last_state != "idle"


async def test_missing_vlc_is_reported_at_startup(tmp_path, monkeypatch):
    """The app flags a missing VLC immediately, not on first play."""
    monkeypatch.setattr(app_module, "find_vlc", lambda: None)
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await settle(pilot)
        assert app.vlc_missing is True


async def test_vlc_present_reports_ok(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "find_vlc", lambda: "/usr/bin/vlc")
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await settle(pilot)
        assert app.vlc_missing is False


def test_css_path_resolves_to_stylesheet():
    """The stylesheet must be found in normal and frozen (PyInstaller) runs."""
    from terminal_radio.app import CSS_PATH

    assert CSS_PATH.name == "terminal_radio.tcss"
    assert CSS_PATH.exists(), f"stylesheet missing: {CSS_PATH}"


async def test_help_screen_opens_and_closes(tmp_path):
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await settle(pilot)
        await pilot.press("question_mark")
        await settle(pilot)
        assert app.screen.__class__.__name__ == "HelpScreen"
        await pilot.press("escape")
        await settle(pilot)
        assert app.screen.__class__.__name__ != "HelpScreen"


async def test_volume_binding(tmp_path):
    app = make_app(tmp_path)
    async with app.run_test() as pilot:
        await settle(pilot)
        start = app.config.volume
        await pilot.press("ctrl+up")
        await pilot.pause(0.05)
        assert app.config.volume == start + 5
        await pilot.press("ctrl+down")
        await pilot.pause(0.05)
        assert app.config.volume == start


async def test_enter_plays_highlighted_channel(tmp_path, monkeypatch):
    async def fake_probe(client, url):
        return 200

    monkeypatch.setattr(net, "probe_stream", fake_probe)

    app = make_app(tmp_path)
    fake = FakePlayer(get_time_value=42)
    app.player = fake
    async with app.run_test() as pilot:
        await settle(pilot)
        await pilot.press("l")  # focus channels
        await pilot.press("enter")
        await settle(pilot)
        assert app.session is not None
        assert app.session.channel.id == "aaa:ch0"
        assert fake.played == ["https://streams.example/aaa/1"]
        assert app.config.last_channel == "aaa:ch0"
        # the poll loop sees advancing get_time and reports "playing"
        await pilot.pause(2.0)
        assert app.session.progressed
        assert app._last_state == "playing"


async def test_stream_that_never_delivers_audio_is_reported(tmp_path, monkeypatch):
    """Regression: VLC says 'playing' but no audio flows (dead stream)."""
    async def fake_probe(client, url):
        return 200

    monkeypatch.setattr(net, "probe_stream", fake_probe)
    monkeypatch.setattr(app_module, "POLL_INTERVAL", 0.1)
    monkeypatch.setattr(app_module, "START_GRACE", 0.2)
    monkeypatch.setattr(app_module, "MAX_FAILURES", 2)

    app = make_app(tmp_path)
    fake = FakePlayer(get_time_value=0)  # playback position never advances
    app.player = fake
    async with app.run_test() as pilot:
        await settle(pilot)
        await pilot.press("l", "enter")
        await settle(pilot, rounds=40)
        assert app.session is not None
        assert not app.session.active  # detected as failed, not "playing"
        assert app._last_state == "stopped"
        # it retried the stream URL before giving up
        assert len(fake.played) >= 2


async def test_authorization_failure_is_reported_before_play(tmp_path, monkeypatch):
    async def fake_probe(client, url):
        return 401

    monkeypatch.setattr(net, "probe_stream", fake_probe)

    app = make_app(tmp_path)
    fake = FakePlayer()
    app.player = fake
    async with app.run_test() as pilot:
        await settle(pilot)
        await pilot.press("l", "enter")
        await settle(pilot)
        assert app.session is not None
        assert not app.session.active
        assert fake.played == []  # VLC was never told to play a dead URL
        assert app._last_state == "stopped"
