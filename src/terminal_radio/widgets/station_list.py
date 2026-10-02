"""Station list widget: Favorites first, then each station platform."""

from __future__ import annotations

from textual.widgets import DataTable

from ..models import FAVORITES_KEY, Station


class StationList(DataTable[str]):
    """DataTable of stations; the first row is the aggregated favorites."""

    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.zebra_stripes = True
        self.add_column(" ", width=3)
        self.add_column("Station")
        self._by_key: dict[str, Station] = {}
        self.selected_key: str | None = None

    @property
    def by_key(self) -> dict[str, Station]:
        return getattr(self, "_by_key", {})

    @property
    def favorites_station(self) -> Station:
        return Station(
            key=FAVORITES_KEY,
            name="Favorites",
            description=(
                "Every channel you starred, across all stations. Press "
                "f on a channel to add or remove it."
            ),
        )

    def set_data(self, stations: list[Station], favorites: list[str]) -> None:
        previous = self.selected_key
        self.clear()
        self._by_key = {}
        self.add_row(
            "\u2605" if favorites else "",
            "Favorites",
            key=FAVORITES_KEY,
        )
        self._by_key[FAVORITES_KEY] = self.favorites_station
        for station in stations:
            self._by_key[station.key] = station
            self.add_row("", station.name, key=station.key)

        target = previous if previous in self._by_key else FAVORITES_KEY
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

    def station_for_cursor(self) -> Station | None:
        try:
            row_key = self.coordinate_to_cell_key(self.cursor_coordinate).row_key
        except Exception:
            return None
        value = getattr(row_key, "value", None)
        if value is None:
            return None
        station = self._by_key.get(str(value))
        if station is not None:
            self.selected_key = station.key
        return station

    def select_station(self, key: str) -> None:
        row = self._row_of(key)
        if row is not None:
            self.move_cursor(row=row)
            self.selected_key = key

    def action_cursor_right(self) -> None:
        """Right arrow jumps from the stations column into the channels."""
        self.app.action_focus_channels()

    def on_data_table_row_highlighted(
        self, event: DataTable.RowHighlighted
    ) -> None:
        value = getattr(event.row_key, "value", None)
        if value:
            self.selected_key = str(value)
