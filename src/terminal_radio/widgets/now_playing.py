"""Now-playing panel: station, channel, state and elapsed time."""

from __future__ import annotations

from rich.markup import escape

from textual.widgets import Static

from ..models import Channel, Station

GLYPHS = {
    "playing": ("[green]\u25b6[/green]", "playing"),
    "stopped": ("[red]\u23f9[/red]", "stopped"),
    "loading": ("[cyan]\u25cc[/cyan]", "connecting"),
    "idle": ("[dim]\u25a0[/dim]", "idle"),
}


def format_time(seconds: int | None) -> str:
    if seconds is None or seconds < 0:
        return "--:--"
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


class NowPlaying(Static):
    """Displays the current playback context and elapsed listening time."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._channel: Channel | None = None
        self._station_name: str = ""
        self._state: str = "idle"
        self._elapsed: int | None = None

    def on_mount(self) -> None:
        self.show_idle("Ready \u2014 pick a station, then a channel, and press [bold]Enter[/bold]")

    def show_idle(self, message: str) -> None:
        self._channel = None
        self._station_name = ""
        self._state = "idle"
        self._elapsed = None
        glyph, _ = GLYPHS["idle"]
        self.update(f"{glyph}  {message}")

    def set_channel(
        self, channel: Channel, station_name: str, state: str, elapsed: int | None
    ) -> None:
        self._channel = channel
        self._station_name = station_name
        self._state = state
        self._elapsed = elapsed
        self._paint()

    def _paint(self) -> None:
        glyph, state_label = GLYPHS.get(self._state, GLYPHS["idle"])
        lines: list[str] = []
        channel_name = escape(self._channel.name) if self._channel else "?"
        station_name = escape(self._station_name) if self._station_name else "?"
        lines.append(
            f"{glyph}  [bold]{channel_name}[/bold]  [dim]\u00b7 {state_label}[/dim]"
        )
        lines.append(f"     [dim]{station_name}[/dim]")

        if self._channel is not None and self._channel.now_playing:
            lines.append(f"     [cyan]{escape(self._channel.now_playing)}[/cyan]")

        if self._state == "loading":
            lines.append("     [dim]tuning in\u2026[/dim]")
        elif self._state == "playing":
            lines.append(f"     [dim]{format_time(self._elapsed)} elapsed[/dim]")

        self.update("\n".join(lines))
