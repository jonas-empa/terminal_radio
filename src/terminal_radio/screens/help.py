"""Modal help screen listing keyboard shortcuts."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Markdown

HELP_MD = """\
# Terminal Radio

| Key | Action |
| --- | --- |
| **Space** | Play the selected channel — press again on the same channel to stop |
| **Enter** | Open a station's channels / play the highlighted channel |
| **→ / ←** | Jump right into the channels / back to the stations |
| **h / l** | Same as ← / → |
| **f** | Toggle favorite (favorites aggregate across all stations) |
| **/** | Search channels |
| **j / k** or **↑ / ↓** | Move the cursor |
| **+ / -** | Volume up / down |
| **r** | Reload the current station's channel list |
| **Esc** | Clear search / move focus back |
| **?** | This help |
| **q** | Quit |

**Space is the only playback control**: it plays the channel under the
cursor (stopping whatever was playing before), and pressing it again on
that same channel stops it.

The column with the **bright header and highlighted row** is the one you
are navigating; the other column is dimmed.

Bundled stations: Radio Paradise, SomaFM, Nightride FM and
Hardcoreradio.nl — all public streams, no account required.
The first item, **★ Favorites**, aggregates every channel you starred
across every station.

Playback is powered by VLC.
"""


class HelpScreen(ModalScreen[None]):
    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=False),
        Binding("question_mark", "dismiss", "Close", show=False),
        Binding("enter", "dismiss", "Close", show=False),
        Binding("q", "dismiss", "Close", show=False),
        Binding("f1", "dismiss", "Close", show=False),
        # Swallow Space so the play/stop binding can't fire behind the modal.
        Binding("space", "swallow", show=False),
    ]

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="help-box"):
            yield Markdown(HELP_MD, id="help-body")

    def action_dismiss(self) -> None:
        self.dismiss(None)

    def action_swallow(self) -> None:
        """Space intentionally does nothing while help is open."""
