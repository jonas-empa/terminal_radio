"""The Textual application: three-pane browsing and stream playback.

Layout: now-playing/details (left) · stations (middle) · channels (right).
Selecting a station loads its channels into the right pane; the first
station row is an aggregated cross-station Favorites view.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from rich.markup import escape
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, Input, Static

from . import net, stations
from .config import Config
from .models import FAVORITES_KEY, Channel, Station
from .playback import StreamSession
from .player import VLC_MISSING_MSG, PlayerError, VlcPlayer, find_vlc
from .screens import HelpScreen
from .widgets import ChannelList, NowPlaying, StationList, StatusBar

log = logging.getLogger(__name__)


def _css_path() -> Path:
    """Locate the stylesheet, also when frozen by PyInstaller.

    Normal runs find it next to this module. A PyInstaller onefile bundle
    extracts to ``sys._MEIPASS``; the data file is added at
    ``terminal_radio/terminal_radio.tcss`` relative to that root.
    """
    path = Path(__file__).with_name("terminal_radio.tcss")
    if path.exists():
        return path
    if getattr(sys, "frozen", False):  # PyInstaller onefile
        base = Path(getattr(sys, "_MEIPASS", ""))
        return base / "terminal_radio" / "terminal_radio.tcss"
    return path


CSS_PATH = _css_path()

POLL_INTERVAL = 1.5
START_GRACE = 8.0  # seconds to allow a stream to deliver audio before blaming it
MAX_FAILURES = 3  # consecutive failed start attempts before giving up


class TerminalRadioApp(App[None]):
    """Multi-station terminal radio player."""

    CSS_PATH = CSS_PATH
    TITLE = "Terminal Radio"
    SUB_TITLE = "internet radio"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("question_mark", "show_help", "Help"),
        Binding("f1", "show_help", "Help", show=False),
        Binding("space", "play_stop", "Play / Stop"),
        Binding("f", "toggle_favorite", "Favorite"),
        Binding("slash", "focus_search", "Search"),
        Binding("plus", "vol_up", "Volume +", show=False),
        Binding("minus", "vol_down", "Volume -", show=False),
        Binding("ctrl+up", "vol_up", show=False),
        Binding("ctrl+down", "vol_down", show=False),
        Binding("j", "cursor_down", show=False),
        Binding("k", "cursor_up", show=False),
        Binding("h", "focus_stations", show=False),
        Binding("l", "focus_channels", show=False),
        Binding("r", "refresh", "Reload", show=False),
        Binding("escape", "escape", show=False),
    ]

    def __init__(
        self, sources: list[stations.StationSource] | None = None
    ) -> None:
        super().__init__()
        self.config = Config.load()
        self.http = net.make_client()
        self.player = VlcPlayer()
        self.sources: list[stations.StationSource] = list(
            sources if sources is not None else stations.SOURCES
        )
        self.channel_cache: dict[str, list[Channel]] = {}
        self.current_station_key: str = FAVORITES_KEY
        self.session: StreamSession | None = None
        self.vlc_missing = False  # set by the startup dependency check
        self._visible_channels: list[Channel] = []
        self._last_state = "idle"
        self._station_detail: str = "Select a station to see its channels."
        self._channel_detail: str = "Select a channel to see its details."

    # ------------------------------------------------------------------ #
    # Composition / mount
    # ------------------------------------------------------------------ #
    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="layout"):
            with Vertical(id="info-pane"):
                yield NowPlaying(id="now-playing")
                yield Static(self._station_detail, id="detail")
            with Vertical(id="sidebar"):
                yield Static("TERMINAL RADIO", id="brand")
                yield Static(
                    "\u2190 / \u2192 switch columns \u00b7 Space play/stop\n"
                    "The bright column is the one you're navigating.\n"
                    "First row: \u2605 aggregated favorites.",
                    id="legend",
                )
                yield StationList(id="stations")
            with Vertical(id="channel-pane"):
                yield Input(placeholder="Search channels  ( / )", id="search")
                yield ChannelList(id="channels")
        yield StatusBar(id="status-bar")
        yield Footer()

    async def on_mount(self) -> None:
        self.query_one(StatusBar).show_state("idle", self.config.volume)
        self._check_dependencies()
        self._poll_loop()
        station_list = self.query_one(StationList)
        station_list.set_data(
            [source.station for source in self.sources], self.config.favorites
        )
        station_list.focus()
        initial = self.config.last_station
        if initial not in station_list.by_key:
            initial = self.sources[0].station.key if self.sources else FAVORITES_KEY
        station_list.select_station(initial)
        self.select_station(initial)

    def _check_dependencies(self) -> None:
        """Warn early about missing runtime dependencies (VLC).

        Without this the first signal would only come when the user tries
        to play something; report it right away instead.
        """
        if find_vlc() is None:
            self.vlc_missing = True
            log.error("Dependency missing: %s", VLC_MISSING_MSG)
            self.query_one(StatusBar).show_message(f"Error: {VLC_MISSING_MSG}")
            self.notify(
                VLC_MISSING_MSG,
                title="VLC not found",
                severity="error",
                timeout=15,
            )
        else:
            self.vlc_missing = False

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @property
    def station_names(self) -> dict[str, str]:
        return {source.station.key: source.station.name for source in self.sources}

    @property
    def station_names_full(self) -> dict[str, str]:
        names = self.station_names
        names[FAVORITES_KEY] = "Favorites"
        return names

    def _station_for(self, key: str) -> Station | None:
        for source in self.sources:
            if source.station.key == key:
                return source.station
        if key == FAVORITES_KEY:
            return self.query_one(StationList).favorites_station
        return None

    async def _station_channels(self, key: str) -> list[Channel]:
        if key in self.channel_cache:
            return self.channel_cache[key]
        for source in self.sources:
            if source.station.key == key:
                channels = await source.fetch(self.http)
                self.channel_cache[key] = channels
                return channels
        return []

    async def _favorites_channels(self) -> list[Channel]:
        results = await asyncio.gather(
            *(self._station_channels(s.station.key) for s in self.sources),
            return_exceptions=True,
        )
        failed = [r for r in results if isinstance(r, Exception)]
        if failed:
            log.warning("Could not load %d station(s) for favorites: %s", len(failed), failed[0])
        fav_set = set(self.config.favorites)
        all_channels: list[Channel] = []
        for result in results:
            if isinstance(result, list):
                all_channels.extend(result)
        return [c for c in all_channels if c.id in fav_set]

    # ------------------------------------------------------------------ #
    # Station selection / channel loading
    # ------------------------------------------------------------------ #
    @work(exclusive=True, group="select-station")
    async def select_station(self, key: str) -> None:
        """Load ``key``'s channels into the right-hand pane."""
        station = self._station_for(key)
        if station is None:
            return
        status = self.query_one(StatusBar)
        self.current_station_key = key
        self._station_detail = self._station_detail_html(station)

        try:
            if key == FAVORITES_KEY:
                channels = await self._favorites_channels()
            else:
                status.show_message(f"Loading {station.name}\u2026")
                channels = await self._station_channels(key)
        except net.FetchError as exc:
            channels = []
            status.show_message(f"Could not load {station.name}: {exc}")
            self.notify(str(exc), title="Network error", severity="warning")

        self._visible_channels = channels
        self._render_channel_view()

        if not channels:
            self._channel_detail = (
                "[dim]"
                + escape(
                    "No favorites yet \u2014 press f on a channel to add one."
                    if key == FAVORITES_KEY
                    else "No channels available."
                )
                + "[/dim]"
            )
            self.query_one("#detail", Static).update(self._channel_detail)
        elif self.config.last_station == key and self.config.last_channel:
            self.query_one(ChannelList).select_channel(self.config.last_channel)

        status.show_state(self._last_state, self.config.volume)
        log.info("Showing %d channels for station %r", len(channels), key)

    def _render_channel_view(self) -> None:
        search = self.query_one("#search", Input)
        self.query_one(ChannelList).set_data(
            self._visible_channels,
            self.config.favorites,
            search.value,
            self.station_names_full,
        )

    def _station_detail_html(self, station: Station) -> str:
        body = escape(station.description or "No description available.")
        extra = ""
        if station.key != FAVORITES_KEY:
            cached = self.channel_cache.get(station.key)
            if cached:
                extra = f"\n\n[dim]{len(cached)} channels[/dim]"
        return (
            f"[bold #248efb]{escape(station.name)}[/bold #248efb]\n\n"
            f"{body}{extra}\n\n[dim]key: {escape(station.key)}[/dim]"
        )

    def _channel_detail_html(self, channel: Channel) -> str:
        station_name = self.station_names.get(channel.station, channel.station)
        body = escape(channel.description or "No description available.")
        lines = [
            f"[bold #248efb]{escape(channel.name)}[/bold #248efb]\n",
            body,
            f"\n[dim]{escape(station_name)} \u00b7 {escape(channel.id)}[/dim]",
        ]
        if channel.now_playing:
            lines.append(f"\n[cyan]On air: {escape(channel.now_playing)}[/cyan]")
        return "".join(lines)

    # ------------------------------------------------------------------ #
    # Playback
    # ------------------------------------------------------------------ #
    @work(exclusive=True, group="channel-switch")
    async def start_channel(self, channel: Channel) -> None:
        """Tune to ``channel``; a no-op if it is already on (playing or
        still connecting). Stopping the current channel is Space's job."""
        existing = self.session
        if (
            existing is not None
            and existing.active
            and existing.channel.id == channel.id
            and self.player.running
        ):
            return
        await self._start_fresh(channel)

    async def _start_fresh(self, channel: Channel) -> None:
        old = self.session
        if old is not None:
            old.active = False
        if self.player.running:
            try:
                await self.player.stop()
                await self.player.clear()
            except PlayerError:
                pass

        session = StreamSession(channel=channel)
        self.session = session
        self._last_state = "loading"
        station_name = self.station_names.get(channel.station, channel.station)
        self.query_one(NowPlaying).set_channel(channel, station_name, "loading", None)
        self.query_one(StatusBar).show_state("loading", self.config.volume)

        try:
            # Preflight: catch authorization failures before VLC reports a
            # silent, zombie "playing" state for a dead stream.
            status_code = await net.probe_stream(self.http, channel.stream_url)
            if status_code in net.AUTH_FAILURE_STATUSES:
                raise net.FetchError(
                    f"The stream rejected the request (HTTP {status_code})."
                )
            if not self.player.running:
                await self.player.start(self.config.volume)
            await self.player.play_url(channel.stream_url)
            session.mark_started()
        except (net.FetchError, PlayerError) as exc:
            await self._session_failed(session, str(exc))
            return

        self.config.last_station = self.current_station_key
        self.config.last_channel = channel.id
        self.config.save()
        self._paint_state(session, "loading", None)
        log.info("Tuning %s (%s) -> %s", channel.name, channel.id, channel.stream_url)

    async def _retry_or_fail(self, session: StreamSession, reason: str) -> None:
        """Replay the stream URL a few times before reporting failure."""
        if not session.active:
            return
        session.failures += 1
        if session.failures >= MAX_FAILURES:
            await self._session_failed(
                session,
                f"The stream {reason} after {session.failures} attempts.",
            )
            return
        try:
            await self.player.stop()
            await self.player.clear()
            await self.player.play_url(session.channel.stream_url)
            session.mark_started()
        except PlayerError as exc:
            await self._session_failed(session, str(exc))
            return
        self._paint_state(session, "loading", None)
        log.info("Restarting %s (attempt %d)", session.channel.id, session.failures)

    # ------------------------------------------------------------------ #
    # Polling
    # ------------------------------------------------------------------ #
    @work(group="poll", exclusive=True)
    async def _poll_loop(self) -> None:
        """Long-lived loop mirroring VLC state into the UI."""
        while True:
            await asyncio.sleep(POLL_INTERVAL)
            session = self.session
            if session is None or not session.active or not self.player.running:
                continue
            try:
                status = await self.player.status()
                if self.session is not session or not session.active:
                    continue
                if status.state == "playing":
                    elapsed = await self.player.get_time()
                    if elapsed is not None and elapsed > 0:
                        session.progressed = True
                    if not session.progressed:
                        # VLC accepted the input but no audio has flowed yet.
                        if session.elapsed_since_start > START_GRACE:
                            await self._retry_or_fail(
                                session, "connected but delivered no audio"
                            )
                        else:
                            self._paint_state(session, "loading", None)
                        continue
                    session.failures = 0
                    self._paint_state(session, "playing", elapsed)
                elif status.state == "paused":
                    # Nothing in the UI pauses anymore; if VLC ends up paused
                    # anyway, resume it (stall detection covers a dead resume).
                    log.debug("Resuming unexpectedly paused stream")
                    await self.player.toggle_pause()
                    continue
                else:  # stopped: stream ended or never started
                    if (
                        not session.progressed
                        and session.elapsed_since_start <= START_GRACE
                    ):
                        continue  # still connecting; keep the loading state
                    await self._retry_or_fail(session, "disconnected unexpectedly")
            except (net.FetchError, PlayerError) as exc:
                await self._session_failed(session, str(exc))

    # ------------------------------------------------------------------ #
    # State helpers
    # ------------------------------------------------------------------ #
    def _paint_state(
        self, session: StreamSession, state: str, elapsed: int | None
    ) -> None:
        if self.session is not session:
            return
        self._last_state = state
        station_name = self.station_names.get(
            session.channel.station, session.channel.station
        )
        self.query_one(NowPlaying).set_channel(
            session.channel, station_name, state, elapsed
        )
        self.query_one(StatusBar).show_state(state, self.config.volume)

    async def _session_failed(self, session: StreamSession, message: str) -> None:
        if not session.active:
            return
        session.active = False
        self._last_state = "stopped"
        station_name = self.station_names.get(
            session.channel.station, session.channel.station
        )
        self.query_one(NowPlaying).set_channel(
            session.channel, station_name, "stopped", None
        )
        self.query_one(StatusBar).show_message(f"Error: {message}")
        self.notify(message, title="Playback stopped", severity="warning")
        log.warning("Stream %s stopped: %s", session.channel.id, message)

    # ------------------------------------------------------------------ #
    # Actions
    # ------------------------------------------------------------------ #
    def action_play_stop(self) -> None:
        """Space: play the highlighted channel, or stop it if it is the
        channel that is currently on."""
        channel = self.query_one(ChannelList).channel_for_cursor()
        if channel is None:
            return
        session = self.session
        if (
            session is not None
            and session.active
            and session.channel.id == channel.id
            and self.player.running
        ):
            self.action_stop()  # the highlighted channel is on -> stop it
            return
        self.start_channel(channel)

    def action_stop(self) -> None:
        session = self.session
        if session is not None:
            session.active = False
            self.session = None
        self._stop_player()
        self._last_state = "idle"
        self.query_one(NowPlaying).show_idle("Stopped.")
        self.query_one(StatusBar).show_state("idle", self.config.volume)

    @work(group="stop", exclusive=True)
    async def _stop_player(self) -> None:
        if not self.player.running:
            return
        try:
            await self.player.stop()
            await self.player.clear()
        except PlayerError:
            pass

    def action_toggle_favorite(self) -> None:
        channel = self.query_one(ChannelList).channel_for_cursor()
        if channel is None:
            return
        added = self.config.toggle_favorite(channel.id)
        self.query_one(StationList).set_data(
            [source.station for source in self.sources], self.config.favorites
        )
        if self.current_station_key == FAVORITES_KEY:
            # The favorites view must drop channels that were just removed.
            self.select_station(FAVORITES_KEY)
        else:
            self._render_channel_view()
        self.notify(
            ("Added to" if added else "Removed from") + f" favorites: {channel.name}",
            title="Favorites",
        )

    def action_focus_search(self) -> None:
        self.query_one("#search", Input).focus()

    def action_focus_stations(self) -> None:
        stations = self.query_one(StationList)
        stations.focus()
        station = stations.station_for_cursor()
        if station is not None:
            self._station_detail = self._station_detail_html(station)
            self.query_one("#detail", Static).update(self._station_detail)

    def action_focus_channels(self) -> None:
        channels = self.query_one(ChannelList)
        channels.focus()
        channel = channels.channel_for_cursor()
        if channel is not None:
            self._channel_detail = self._channel_detail_html(channel)
            self.query_one("#detail", Static).update(self._channel_detail)

    def action_cursor_down(self) -> None:
        self._move_cursor(1)

    def action_cursor_up(self) -> None:
        self._move_cursor(-1)

    def _move_cursor(self, delta: int) -> None:
        widget = self.focused
        if not isinstance(widget, DataTable) or not widget.row_count:
            return
        row = max(0, min(widget.row_count - 1, widget.cursor_coordinate.row + delta))
        widget.move_cursor(row=row)

    def action_escape(self) -> None:
        if isinstance(self.focused, Input):
            search = self.query_one("#search", Input)
            if search.value:
                search.value = ""
                return
            self.action_focus_channels()
            return
        # Escape only navigates; Space is the sole play/stop control.
        if self.focused is self.query_one(ChannelList):
            self.action_focus_stations()

    def action_refresh(self) -> None:
        key = self.current_station_key
        if key == FAVORITES_KEY:
            self.channel_cache.clear()
        else:
            self.channel_cache.pop(key, None)
        self.select_station(key)

    @on(Input.Submitted, "#search")
    def on_search_submitted(self, event: Input.Submitted) -> None:
        self.action_focus_channels()

    @on(Input.Changed, "#search")
    def on_search_changed(self, event: Input.Changed) -> None:
        self._render_channel_view()

    @on(DataTable.RowSelected, "#channels")
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        key = str(getattr(event.row_key, "value", "") or "")
        channel = self.query_one(ChannelList).by_key.get(key)
        if channel is not None:
            self.start_channel(channel)

    @on(DataTable.RowHighlighted, "#channels")
    def on_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        key = str(getattr(event.row_key, "value", "") or "")
        channel = self.query_one(ChannelList).by_key.get(key)
        if channel is None:
            return
        self._channel_detail = self._channel_detail_html(channel)
        self.query_one("#detail", Static).update(self._channel_detail)

    @on(DataTable.RowHighlighted, "#stations")
    def on_station_highlighted(self, event: DataTable.RowHighlighted) -> None:
        stations = self.query_one(StationList)
        # Drop stale highlights queued before the cursor settled: set_data()
        # and select_station() both move the cursor programmatically, and a
        # queued event from the initial row must not override the selection.
        if event.cursor_row != stations.cursor_coordinate.row:
            return
        key = str(getattr(event.row_key, "value", "") or "")
        station = self._station_for(key)
        if station is None:
            return
        self._station_detail = self._station_detail_html(station)
        self.query_one("#detail", Static).update(self._station_detail)
        if key != self.current_station_key:
            self.select_station(key)

    @on(DataTable.RowSelected, "#stations")
    def on_station_selected(self, event: DataTable.RowSelected) -> None:
        self.action_focus_channels()

    async def action_vol_up(self) -> None:
        await self._change_volume(5)

    async def action_vol_down(self) -> None:
        await self._change_volume(-5)

    async def _change_volume(self, delta: int) -> None:
        self.config.volume = max(0, min(100, self.config.volume + delta))
        self.config.save()
        if self.player.running:
            try:
                await self.player.set_volume(self.config.volume)
            except PlayerError:
                pass
        session = self.session
        if session is not None and session.active:
            self.query_one(StatusBar).show_state(
                self._last_state, self.config.volume
            )
        else:
            self.query_one(StatusBar).show_state("idle", self.config.volume)

    def action_show_help(self) -> None:
        self.push_screen(HelpScreen())

    async def action_quit(self) -> None:
        if self.session is not None:
            self.session.active = False
            self.session = None
        self.config.save()
        try:
            await self.player.close()
        except Exception:  # pragma: no cover - best effort cleanup
            log.exception("Error while closing the player")
        try:
            await self.http.aclose()
        except Exception:  # pragma: no cover
            pass
        self.exit()
