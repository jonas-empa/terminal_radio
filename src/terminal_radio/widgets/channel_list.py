"""Channel list widget (searchable, with favorites starred)."""

from __future__ import annotations

from textual.widgets import DataTable

from ..models import Channel


class ChannelList(DataTable[str]):
    """DataTable of channels for the currently selected station view.

    In the aggregated favorites view channels from every station appear
    together, so rows carry a Station column and composite row keys.
    """

    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.zebra_stripes = True
        self.add_column(" ", width=3)
        self.add_column("Channel")
        self.add_column("Station", width=20)
        self._by_key: dict[str, Channel] = {}
        self.selected_key: str | None = None

    @property
    def by_key(self) -> dict[str, Channel]:
        return getattr(self, "_by_key", {})

    def set_data(
        self,
        channels: list[Channel],
        favorites: list[str],
        needle: str = "",
        station_names: dict[str, str] | None = None,
    ) -> None:
        """Rebuild rows, preserving the cursor where possible."""
        fav_set = set(favorites)
        station_names = station_names or {}
        needle = needle.strip().lower()

        def matches(channel: Channel) -> bool:
            if not needle:
                return True
            return (
                needle in channel.name.lower()
                or needle in channel.key.lower()
                or needle in station_names.get(channel.station, channel.station).lower()
            )

        visible = [c for c in channels if matches(c)]
        favs = sorted(
            (c for c in visible if c.id in fav_set),
            key=lambda c: (
                station_names.get(c.station, c.station).lower(),
                c.name.lower(),
            ),
        )
        rest = sorted(
            (c for c in visible if c.id not in fav_set),
            key=lambda c: c.name.lower(),
        )

        previous = self.selected_key
        self.clear()
        self._by_key = {}
        for channel in favs + rest:
            self._by_key[channel.id] = channel
            star = "\u2605" if channel.id in fav_set else ""
            station_name = station_names.get(channel.station, channel.station)
            self.add_row(star, channel.name, station_name, key=channel.id)

        if not self._by_key:
            self.selected_key = None
            return
        target = previous if previous in self._by_key else None
        if target is None and favs:
            target = favs[0].id
        if target is None:
            target = next(iter(self._by_key))
        row = self._row_of(target)
        if row is not None:
            self.move_cursor(row=row)
            self.selected_key = target

    def _row_of(self, key: str) -> int | None:
        keys = list(self._by_key)
        try:
            return keys.index(key)
        except ValueError:
            return None

    def channel_for_cursor(self) -> Channel | None:
        """Return the channel under the cursor, if any."""
        try:
            row_key = self.coordinate_to_cell_key(self.cursor_coordinate).row_key
        except Exception:
            return None
        value = getattr(row_key, "value", None)
        if value is None:
            return None
        channel = self._by_key.get(str(value))
        if channel is not None:
            self.selected_key = channel.id
        return channel

    def select_channel(self, channel_id: str) -> None:
        """Move the cursor to a specific channel, if it is present."""
        row = self._row_of(channel_id)
        if row is not None:
            self.move_cursor(row=row)
            self.selected_key = channel_id

    def action_cursor_left(self) -> None:
        """Left arrow jumps from the channels column back to the stations."""
        self.app.action_focus_stations()

    def on_data_table_row_highlighted(
        self, event: DataTable.RowHighlighted
    ) -> None:
        value = getattr(event.row_key, "value", None)
        if value:
            self.selected_key = str(value)
