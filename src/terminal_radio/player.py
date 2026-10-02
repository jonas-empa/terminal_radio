"""VLC backend control via the RC command interface.

The player runs ``vlc --intf rc --rc-host=127.0.0.1:<port>`` (no GUI) and is
driven over a local TCP socket. Verified behaviours:

* ``status`` returns, in one command: current input URL, volume and state
  (``playing`` / ``paused`` / ``stopped``) - this is the polling primitive.
* ``add <url>`` appends *and starts* the item when idle/stopped.
* ``enqueue <url>`` appends without interrupting the current item; VLC
  auto-advances through queued items.
* ``pause`` toggles pause; ``get_time`` returns the position (frozen while
  paused) and is empty once stopped.
* VLC emits no unsolicited events, hence the explicit ``status`` polling.
"""

from __future__ import annotations

import asyncio
import atexit
import logging
import shutil
import socket
from dataclasses import dataclass

log = logging.getLogger(__name__)

MAX_VOLUME = 256  # RC volume scale (256 == 100%)


class PlayerError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class VlcStatus:
    state: str  # "playing" | "paused" | "stopped"
    url: str | None
    volume: int  # raw 0-256 scale


def parse_status(text: str) -> VlcStatus:
    """Parse the output of the RC ``status`` command."""
    state = "stopped"
    url: str | None = None
    volume = 0
    for raw in text.replace("\r\n", "\n").split("\n"):
        line = raw.strip()
        if not (line.startswith("(") and line.endswith(")")):
            continue
        inner = line[1:-1].strip()
        if inner.startswith("state "):
            value = inner[len("state "):].strip()
            if value in ("playing", "paused", "stopped"):
                state = value
        elif inner.startswith("new input: "):
            url = inner[len("new input: "):].strip() or None
        elif inner.startswith("audio volume: "):
            try:
                volume = int(inner[len("audio volume: "):].strip())
            except ValueError:
                pass
    return VlcStatus(state=state, url=url, volume=volume)


def parse_int(text: str) -> int | None:
    for raw in text.replace("\r\n", "\n").split("\n"):
        raw = raw.strip()
        if raw.lstrip("-").isdigit():
            return int(raw)
    return None


def volume_to_rc(volume: int) -> int:
    """Convert a 0-100 UI volume to the RC 0-256 scale."""
    volume = max(0, min(100, int(volume)))
    return min(MAX_VOLUME, round(volume * MAX_VOLUME / 100))


def volume_to_ui(rc_volume: int) -> int:
    return max(0, min(100, round(rc_volume * 100 / MAX_VOLUME)))


VLC_MISSING_MSG = (
    "VLC was not found on this system. Install it with "
    "'sudo apt install vlc' (Linux) or vlc.media-player.org."
)


def find_vlc() -> str | None:
    """Locate a VLC executable, or ``None`` if there is none."""
    for name in ("vlc", "cvlc"):
        path = shutil.which(name)
        if path:
            return path
    return None


def _find_vlc() -> str:
    path = find_vlc()
    if path is None:
        raise PlayerError(VLC_MISSING_MSG)
    return path


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class VlcPlayer:
    """Manages a single headless VLC process and its RC connection."""

    def __init__(self) -> None:
        self._proc: asyncio.subprocess.Process | None = None
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()
        self._atexit_hook = atexit.register(self._kill_sync)

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    async def start(self, volume: int) -> None:
        if self._proc is not None:
            return
        executable = _find_vlc()
        port = _free_port()
        self._proc = await asyncio.create_subprocess_exec(
            executable,
            "--intf", "rc",
            f"--rc-host=127.0.0.1:{port}",
            "--no-video",
            "--no-video-title-show",
            "--no-random",
            "--no-loop",
            "--no-repeat",
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        # Wait for the RC port to come up.
        deadline = asyncio.get_running_loop().time() + 8.0
        last_error: Exception | None = None
        while True:
            if self._proc.returncode is not None:
                stderr = b""
                if self._proc.stderr:
                    stderr = await self._proc.stderr.read()
                self._proc = None
                raise PlayerError(
                    "VLC failed to start: "
                    + stderr.decode(errors="replace").strip()[:300]
                )
            try:
                self._reader, self._writer = await asyncio.open_connection(
                    "127.0.0.1", port
                )
                break
            except OSError as exc:
                last_error = exc
                if asyncio.get_running_loop().time() > deadline:
                    await self._kill()
                    raise PlayerError(f"Could not reach VLC's control port: {exc}")
                await asyncio.sleep(0.15)

        # Drain the banner, then apply the configured volume.
        await self._read_until_prompt(timeout=5.0)
        await self.set_volume(volume)
        log.info("VLC started on port %s (pid=%s)", port, self._proc.pid)

    async def close(self) -> None:
        if self._atexit_hook is not None:
            try:
                atexit.unregister(self._atexit_hook)
            except Exception:  # pragma: no cover - defensive
                pass
        try:
            if self._writer is not None:
                await self.command("quit", timeout=2.0)
        except Exception:
            pass
        await self._kill()

    async def _kill(self) -> None:
        if self._writer is not None:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None
            self._reader = None
        if self._proc is not None:
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                self._proc.terminate()
                try:
                    await asyncio.wait_for(self._proc.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    self._proc.kill()
                    await self._proc.wait()
            self._proc = None

    def _kill_sync(self) -> None:
        """Last-resort cleanup if the event loop never closed cleanly."""
        proc = self._proc
        if proc is not None and proc.returncode is None:
            try:
                proc.kill()
            except Exception:
                pass

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.returncode is None

    # ------------------------------------------------------------------ #
    # RC protocol
    # ------------------------------------------------------------------ #
    async def _read_until_prompt(self, timeout: float = 5.0) -> str:
        """Read command output until the RC prompt ``> `` is seen.

        VLC's RC prompt is written *without* a trailing newline, so we scan
        the accumulated buffer for the ``> `` suffix instead of using
        ``readline``.
        """
        assert self._reader is not None

        async def _read() -> bytes:
            buf = b""
            while not buf.endswith(b"> "):
                chunk = await self._reader.read(4096)  # type: ignore[union-attr]
                if not chunk:
                    raise PlayerError("VLC closed the control connection.")
                buf += chunk
            return buf

        data = await asyncio.wait_for(_read(), timeout)
        return data.decode(errors="replace")

    async def command(self, cmd: str, timeout: float = 5.0) -> str:
        if self._writer is None:
            raise PlayerError("Player is not running.")
        async with self._lock:
            self._writer.write(cmd.encode() + b"\n")
            try:
                await self._writer.drain()
            except (BrokenPipeError, ConnectionResetError) as exc:
                raise PlayerError("Lost connection to VLC.") from exc
            return await self._read_until_prompt(timeout=timeout)

    # ------------------------------------------------------------------ #
    # Commands
    # ------------------------------------------------------------------ #
    async def status(self) -> VlcStatus:
        return parse_status(await self.command("status"))

    async def get_time(self) -> int | None:
        return parse_int(await self.command("get_time"))

    async def play_url(self, url: str) -> None:
        """Start playing ``url`` immediately (clearing happens separately)."""
        await self.command(f"add {url}")

    async def enqueue(self, url: str) -> None:
        await self.command(f"enqueue {url}")

    async def stop(self) -> None:
        await self.command("stop")

    async def clear(self) -> None:
        await self.command("clear")

    async def toggle_pause(self) -> None:
        await self.command("pause")

    async def set_volume(self, volume: int) -> None:
        await self.command(f"volume {volume_to_rc(volume)}")
