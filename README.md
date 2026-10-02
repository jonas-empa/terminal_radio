# terminal-radio

A generic **terminal internet radio player**, built with
[Textual](https://textual.textualize.io/) and powered by VLC.

- Three-pane browser: **now playing / details** · **stations** · **channels** —
  the active column is highlighted with a bright header and cursor row
- Bundled stations: **Radio Paradise**, **SomaFM**, **Nightride FM**,
  **Hardcoreradio.nl** — all public streams, no account or login required
- **★ Favorites** aggregates starred channels across every station
- One-key playback: **Space** plays the selected channel and stops it again
  when pressed on the channel that is already on
- Search within a station's channels, volume control
- Streams are plain Icecast/Shoutcast URLs played by a headless VLC that
  is driven over its RC control socket

## Requirements

To run **from source**:

- Python 3.12+
- **VLC** (`sudo apt install vlc` on Debian/Ubuntu; available for
  macOS/Windows at vlc.media-player.org)
- Linux, macOS or Windows (developed/tested on Ubuntu 24.04)

To run the **standalone binary** (below): only **VLC** — no Python needed.

## Install & run

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/terminal-radio
# or:
.venv/bin/python -m terminal_radio
```

## Standalone binary for distribution (Ubuntu)

Build a single self-contained executable into `dist/`:

```bash
.venv/bin/pip install -e ".[dev]"
./scripts/build-dist.sh        # -> dist/terminal-radio (~14 MB)
```

Then just copy `dist/terminal-radio` to the other machine (file share,
`scp`, USB stick — it's one file) and run it:

```bash
chmod +x terminal-radio        # only if the exec bit got lost in transit
./terminal-radio
```

What's inside and around it:

- Everything (interpreter + all Python dependencies + the stylesheet) is
  bundled into the one file. **VLC is not and cannot be bundled** — it
  must be installed on the target: `sudo apt install vlc`.
- If VLC is missing, the app says so immediately at startup (error toast
  + status bar + log) instead of failing mysteriously when you press
  Space, e.g. *"VLC was not found on this system. Install it with
  'sudo apt install vlc' (Linux) or vlc.media-player.org."*
- Config lives in the same place as before:
  `~/.config/terminal-radio/config.json`.

Compatibility notes:

- The binary is **Linux x86_64** as built by `build-dist.sh`.
- PyInstaller links against the build machine's glibc, so build it on the
  **oldest Ubuntu version you need to support** — a binary built on an
  older glibc runs on newer systems, but not vice versa. (On Ubuntu
  versions older than 24.04 you'll also need Python 3.12 first, e.g.
  via the `deadsnakes` PPA.)

## Keys

| Key | Action |
| --- | --- |
| `Space` | **Play the selected channel — press again on the same channel to stop** |
| `Enter` | Open a station's channels / play the highlighted channel |
| `→` / `←` | Jump into the channels column / back to the stations column |
| `h` / `l` | Same as `←` / `→` |
| `f` | Toggle favorite |
| `/` | Search channels |
| `j` / `k` (or arrows) | Move cursor |
| `+` / `-` (or `Ctrl+↑`/`Ctrl+↓`) | Volume |
| `r` | Reload the current station's channel list |
| `?` | Help |
| `Esc` | Clear search / move focus back |
| `q` | Quit |

Space is the only playback control: whatever is under the channel cursor
gets played (stopping the previous channel first), and Space on the
channel that is already on stops it. There is no pause — a live radio
stream keeps broadcasting, so "stop" is the honest way to leave it.

## How it works

1. Each station is a small module under `src/terminal_radio/stations/`
   that yields `Channel` objects with a direct `stream_url`:
   - **SomaFM** — public JSON catalog (`channels.json`), highest-quality
     MP3 `.pls` playlist chosen per channel (VLC opens `.pls` natively).
   - **Radio Paradise / Nightride FM / Hardcoreradio.nl** — curated static
     lists of verified direct Icecast/Shoutcast stream URLs.
2. The middle pane lists stations; the first row is **★ Favorites**, an
   aggregated view of every starred channel across all stations
   (favorite ids are stored as `"station:channel"`).
3. Before tuning in, the stream URL is probed so an HTTP 401/403 surfaces
   as a clear error instead of VLC reporting a silent "playing" state.
4. Playback runs in a headless VLC (`vlc --intf rc`) controlled over a
   local TCP socket; a poll loop mirrors state and elapsed time into the
   UI. A stream that reports `playing` but never advances its position is
   detected as stalled, retried a couple of times, then reported.
5. If a live stream disconnects, it is restarted automatically (up to
   three consecutive failures before the session is stopped with an
   error).

## Configuration

`~/.config/terminal-radio/config.json`:

```json
{
  "favorites": ["somafm:groovesalad", "radioparadise:main"],
  "volume": 70,
  "last_station": "somafm",
  "last_channel": "somafm:groovesalad"
}
```

Delete the file to reset; re-add favorites with `f`.
There are no credentials — every station is public.

## Development

```bash
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

Debug logs: `terminal-radio --debug` writes `terminal-radio.log` into the
config dir.
