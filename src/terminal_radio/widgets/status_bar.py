"""Bottom status bar: playback state, volume and quick hints."""

from __future__ import annotations

from rich.markup import escape

from textual.widgets import Static


class StatusBar(Static):
    def on_mount(self) -> None:
        self.show_message("Ready")

    def show_message(self, message: str) -> None:
        self.update(
            f" [dim]{escape(message)}[/dim]"
            f"{' ' * 4}[dim]\u00b7[/dim]  [dim]? help \u00b7 Enter play \u00b7 "
            f"Space play/stop \u00b7 f favorite \u00b7 / search[/dim]"
        )

    def show_state(self, state: str, volume: int) -> None:
        glyphs = {
            "playing": "[green]\u25b6 playing[/green]",
            "stopped": "[red]\u23f9 stopped[/red]",
            "loading": "[cyan]\u25cc connecting[/cyan]",
        }
        icon = glyphs.get(state, "[dim]\u25a0 idle[/dim]")
        self.update(
            f" {icon}   [dim]\u00b7[/dim]   "
            f"[dim]VOL {volume:3d}%[/dim]   "
            f"{' ' * 4}[dim]\u00b7[/dim]  [dim]? help \u00b7 Enter play \u00b7 "
            f"Space play/stop \u00b7 f favorite \u00b7 / search[/dim]"
        )
