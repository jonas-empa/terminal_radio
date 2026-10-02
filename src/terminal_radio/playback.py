"""Playback session state for a selected channel.

A session wraps a single continuous stream URL handed to VLC — there is
nothing to resolve or advance track-by-track, only to start the stream,
watch for stalls, and restart on disconnect.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from .models import Channel


@dataclass
class StreamSession:
    channel: Channel
    active: bool = True
    started_since: float = 0.0  # monotonic time of the last start attempt
    progressed: bool = False  # True once get_time has advanced past zero
    failures: int = 0  # consecutive failed starts / disconnects

    def mark_started(self) -> None:
        self.started_since = time.monotonic()
        self.progressed = False

    @property
    def elapsed_since_start(self) -> float:
        if not self.started_since:
            return 0.0
        return time.monotonic() - self.started_since
