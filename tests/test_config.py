"""Tests for dashboard/config.py — the pure agent-screen runtime config parser.

Contract (mirrors the DoD in docs/plans/coder-eich-01-display-config.md):

* missing / unreadable / invalid-JSON file -> defaults, never a crash
* displayName: non-empty after trim and <=40 chars, else the default
* jpegEveryNthFrame: integer clamped to [1, 60], else the default
* valid file -> exact effective values
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

CONFIG_MODULE_PATH = Path(__file__).resolve().parents[1] / "dashboard" / "config.py"


@pytest.fixture
def config():
    spec = importlib.util.spec_from_file_location("agent_screen_config_under_test", CONFIG_MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(path: Path, content):
    path.write_text(content, encoding="utf-8")
    return str(path)


def test_missing_file_gives_defaults(config, tmp_path):
    eff = config.load(tmp_path / "does-not-exist.json")
    assert eff["displayName"] == config.DEFAULT_DISPLAY_NAME
    assert eff["jpegEveryNthFrame"] == config.DEFAULT_JPEG_EVERY_NTH_FRAME
    assert eff["nativeWidth"] == config.DEFAULT_NATIVE_WIDTH
    assert eff["nativeHeight"] == config.DEFAULT_NATIVE_HEIGHT
    assert eff["modes"] == config.DEFAULT_MODES


def test_invalid_json_gives_defaults(config, tmp_path):
    path = _write(tmp_path / "bad.json", "not json {")
    eff = config.load(path)
    assert eff["displayName"] == config.DEFAULT_DISPLAY_NAME
    assert eff["jpegEveryNthFrame"] == config.DEFAULT_JPEG_EVERY_NTH_FRAME
    assert eff["nativeWidth"] == config.DEFAULT_NATIVE_WIDTH
    assert eff["nativeHeight"] == config.DEFAULT_NATIVE_HEIGHT
    assert eff["modes"] == config.DEFAULT_MODES


def test_blank_and_too_long_name_fall_back_to_default(config):
    assert config.parse_display_name("   ") == config.DEFAULT_DISPLAY_NAME
    assert config.parse_display_name("") == config.DEFAULT_DISPLAY_NAME
    assert config.parse_display_name("x" * 41) == config.DEFAULT_DISPLAY_NAME
    assert config.parse_display_name(123) == config.DEFAULT_DISPLAY_NAME
    # 40 chars is the max and is accepted.
    assert config.parse_display_name("x" * 40) == "x" * 40


def test_jpeg_every_nth_frame_clamped(config):
    assert config.parse_jpeg_every_nth_frame(0) == 1
    assert config.parse_jpeg_every_nth_frame(99) == 60
    assert config.parse_jpeg_every_nth_frame(-5) == 1
    assert config.parse_jpeg_every_nth_frame(1) == 1
    assert config.parse_jpeg_every_nth_frame(60) == 60
    assert config.parse_jpeg_every_nth_frame(20) == 20
    # Non-integers (including bool) fall back to default.
    assert config.parse_jpeg_every_nth_frame("20") == config.DEFAULT_JPEG_EVERY_NTH_FRAME
    assert config.parse_jpeg_every_nth_frame(True) == config.DEFAULT_JPEG_EVERY_NTH_FRAME
    assert config.parse_jpeg_every_nth_frame(None) == config.DEFAULT_JPEG_EVERY_NTH_FRAME


def test_valid_file_gives_exact_values(config, tmp_path):
    path = _write(
        tmp_path / "ok.json",
        '{"displayName": "  Mein Screen  ", "jpegEveryNthFrame": 7, "ignoredKey": 999}',
    )
    eff = config.load(path)
    assert eff["displayName"] == "Mein Screen"  # trimmed
    assert eff["jpegEveryNthFrame"] == 7


def test_unknown_keys_ignored(config, tmp_path):
    path = _write(tmp_path / "extra.json", '{"other": 1, "displayName": "A"}')
    eff = config.load(path)
    assert eff["displayName"] == "A"
    assert eff["jpegEveryNthFrame"] == config.DEFAULT_JPEG_EVERY_NTH_FRAME


def test_invalid_native_pair_falls_back_to_default(config, tmp_path):
    # 1000x1000 not on whitelist.
    eff = config.load(
        _write(tmp_path / "p.json", '{"nativeWidth": 1000, "nativeHeight": 1000}')
    )
    assert (eff["nativeWidth"], eff["nativeHeight"]) == (
        config.DEFAULT_NATIVE_WIDTH,
        config.DEFAULT_NATIVE_HEIGHT,
    )
    # Only width present -> incomplete pair -> default.
    eff = config.load(_write(tmp_path / "p.json", '{"nativeWidth": 1920}'))
    assert (eff["nativeWidth"], eff["nativeHeight"]) == (
        config.DEFAULT_NATIVE_WIDTH,
        config.DEFAULT_NATIVE_HEIGHT,
    )
    # Float parity: 3360.0 is not an integer -> default (not 3360).
    eff = config.load(
        _write(tmp_path / "p.json", '{"nativeWidth": 3360.0, "nativeHeight": 2100}')
    )
    assert (eff["nativeWidth"], eff["nativeHeight"]) == (
        config.DEFAULT_NATIVE_WIDTH,
        config.DEFAULT_NATIVE_HEIGHT,
    )
    # Bool is not an integer -> default.
    eff = config.load(
        _write(tmp_path / "p.json", '{"nativeWidth": true, "nativeHeight": 2100}')
    )
    assert (eff["nativeWidth"], eff["nativeHeight"]) == (
        config.DEFAULT_NATIVE_WIDTH,
        config.DEFAULT_NATIVE_HEIGHT,
    )


def test_valid_native_pair_accepted(config, tmp_path):
    eff = config.load(
        _write(tmp_path / "ok.json", '{"nativeWidth": 1920, "nativeHeight": 1080}')
    )
    assert (eff["nativeWidth"], eff["nativeHeight"]) == (1920, 1080)


def test_modes_default_on_missing_empty_or_invalid(config, tmp_path):
    # Missing -> default.
    assert config.parse_modes(None) == config.DEFAULT_MODES
    # Empty array -> default.
    assert config.parse_modes([]) == config.DEFAULT_MODES
    # Not an array -> default.
    assert config.parse_modes("nope") == config.DEFAULT_MODES
    # One invalid pair poisons the whole list -> default.
    eff = config.load(
        _write(tmp_path / "m.json", '{"modes": [[1920, 1080], [1234, 567]]}')
    )
    assert eff["modes"] == config.DEFAULT_MODES
    # Float parity in a pair -> default.
    eff = config.load(_write(tmp_path / "m.json", '{"modes": [[1920, 1080.0]]}'))
    assert eff["modes"] == config.DEFAULT_MODES


def test_valid_modes_subset_preserves_order(config, tmp_path):
    eff = config.load(
        _write(tmp_path / "m.json", '{"modes": [[1920, 1080], [1280, 720]]}')
    )
    assert eff["modes"] == [[1920, 1080], [1280, 720]]


def test_valid_file_gives_all_exact_values(config, tmp_path):
    path = _write(
        tmp_path / "ok.json",
        json.dumps(
            {
                "displayName": "  Mein Screen  ",
                "jpegEveryNthFrame": 7,
                "nativeWidth": 1920,
                "nativeHeight": 1080,
                "modes": [[1920, 1080], [1600, 900]],
                "ignoredKey": 999,
            }
        ),
    )
    eff = config.load(path)
    assert eff["displayName"] == "Mein Screen"  # trimmed
    assert eff["jpegEveryNthFrame"] == 7
    assert (eff["nativeWidth"], eff["nativeHeight"]) == (1920, 1080)
    assert eff["modes"] == [[1920, 1080], [1600, 900]]
