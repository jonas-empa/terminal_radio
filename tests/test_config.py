"""Tests for config persistence."""

from terminal_radio.config import Config


def test_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    cfg = Config(path=path)
    cfg.favorites = ["somafm:groovesalad", "radioparadise:main"]
    cfg.volume = 42
    cfg.last_station = "somafm"
    cfg.last_channel = "somafm:groovesalad"
    cfg.save()

    loaded = Config.load(path)
    assert loaded.favorites == ["somafm:groovesalad", "radioparadise:main"]
    assert loaded.volume == 42
    assert loaded.last_station == "somafm"
    assert loaded.last_channel == "somafm:groovesalad"


def test_missing_file_returns_defaults(tmp_path):
    cfg = Config.load(tmp_path / "nope.json")
    assert cfg.favorites == []
    assert cfg.volume == 70
    assert cfg.last_station == ""


def test_corrupt_file_returns_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{ not json")
    cfg = Config.load(path)
    assert cfg.favorites == []
    assert cfg.volume == 70


def test_toggle_favorite(tmp_path):
    cfg = Config(path=tmp_path / "c.json")
    assert cfg.toggle_favorite("nightride:nightride") is True
    assert cfg.is_favorite("nightride:nightride")
    assert cfg.toggle_favorite("nightride:nightride") is False
    assert not cfg.is_favorite("nightride:nightride")
    # persisted both times
    assert Config.load(cfg.path).favorites == []


def test_volume_clamped(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"volume": 9999}')
    assert Config.load(path).volume == 100
    path.write_text('{"volume": -5}')
    assert Config.load(path).volume == 0


def test_no_credentials_are_stored(tmp_path):
    """The generic player must not persist any account fields."""
    path = tmp_path / "config.json"
    cfg = Config(path=path)
    cfg.save()
    raw = path.read_text()
    for forbidden in ("username", "member_token", "audio_token", "session_key", "password"):
        assert forbidden not in raw
