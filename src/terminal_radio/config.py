"""Configuration persistence for terminal-radio.

Stores favorites, volume and the last selected channel as JSON in the
user's config directory (``~/.config/terminal-radio/config.json`` on
Linux). There are no credentials: every station is public.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from platformdirs import user_config_dir

log = logging.getLogger(__name__)

CONFIG_DIR = Path(user_config_dir("terminal-radio"))
CONFIG_PATH = CONFIG_DIR / "config.json"


@dataclass
class Config:
    favorites: list[str] = field(default_factory=list)  # "<station>:<channel>"
    volume: int = 70
    last_station: str = ""
    last_channel: str = ""
    path: Path = CONFIG_PATH

    # ------------------------------------------------------------------ #
    # Favorites
    # ------------------------------------------------------------------ #
    def is_favorite(self, channel_id: str) -> bool:
        return channel_id in self.favorites

    def toggle_favorite(self, channel_id: str) -> bool:
        """Toggle a channel id in the favorites list.

        Returns True if it is now a favorite.
        """
        if channel_id in self.favorites:
            self.favorites.remove(channel_id)
            saved = False
        else:
            self.favorites.append(channel_id)
            saved = True
        self.save()
        return saved

    # ------------------------------------------------------------------ #
    # Load / save
    # ------------------------------------------------------------------ #
    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        path = path or CONFIG_PATH
        cfg = cls(path=path)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return cfg
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("Could not read config %s: %s", path, exc)
            return cfg

        if isinstance(raw, dict):
            favs = raw.get("favorites")
            if isinstance(favs, list):
                cfg.favorites = [str(f) for f in favs]
            if isinstance(raw.get("volume"), (int, float)):
                cfg.volume = max(0, min(100, int(raw["volume"])))
            cfg.last_station = str(raw.get("last_station") or "")
            cfg.last_channel = str(raw.get("last_channel") or "")
        return cfg

    def save(self) -> None:
        data = {
            "favorites": self.favorites,
            "volume": self.volume,
            "last_station": self.last_station,
            "last_channel": self.last_channel,
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
            tmp.replace(self.path)
        except OSError as exc:
            log.warning("Could not save config %s: %s", self.path, exc)
