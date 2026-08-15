"""config.py — read ~/.hermes/agent-screen.json into effective runtime values.

Pure parser: the only I/O lives in :func:`load` (which reads one file and
returns defaults on any error). Everything else is a pure function so it can
be unit-tested and reused verbatim by the native Swift loader
(see ``native/agent-screen-app.swift``, which implements the SAME rules and
points back here in a comment).

Schema (only these keys; anything else is ignored):

.. code-block:: json

    {
      "displayName": "Agent Screen Display",
      "jpegEveryNthFrame": 20,
      "nativeWidth": 3360,
      "nativeHeight": 2100,
      "modes": [[3360, 2100], [3840, 2160], [2560, 1440], [1920, 1080], [1600, 900], [1280, 720]]
    }

Defaults are used when the file is missing, invalid JSON, or a value fails
validation.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_DISPLAY_NAME = "Agent Screen Display"
DEFAULT_JPEG_EVERY_NTH_FRAME = 20
MAX_DISPLAY_NAME_LEN = 40
JPEG_EVERY_NTH_FRAME_MIN = 1
JPEG_EVERY_NTH_FRAME_MAX = 60

DEFAULT_NATIVE_WIDTH = 3360
DEFAULT_NATIVE_HEIGHT = 2100
DEFAULT_MODES: list[list[int]] = [
    [3360, 2100],
    [3840, 2160],
    [2560, 1440],
    [1920, 1080],
    [1600, 900],
    [1280, 720],
]

# Whitelist of allowed resolutions (width, height). Anything not in here falls
# back to defaults — mirrors native/agent-screen-app.swift.
_ALLOWED_RESOLUTIONS = {tuple(m) for m in DEFAULT_MODES}

# Config file read at app start. It lives under ~/.hermes (install dir), not
# the repo, so it survives plugin re-installs and is user-editable.
DEFAULT_CONFIG_PATH = Path.home() / ".hermes" / "agent-screen.json"


def parse_display_name(raw: Any) -> str:
    """Effective displayName: non-empty after trim and ≤40 chars, else default."""
    if not isinstance(raw, str):
        return DEFAULT_DISPLAY_NAME
    name = raw.strip()
    if not name:
        return DEFAULT_DISPLAY_NAME
    if len(name) > MAX_DISPLAY_NAME_LEN:
        return DEFAULT_DISPLAY_NAME
    return name


def parse_jpeg_every_nth_frame(raw: Any) -> int:
    """Effective jpegEveryNthFrame: integer clamped to [1, 60], else default."""
    if isinstance(raw, bool) or not isinstance(raw, int):
        return DEFAULT_JPEG_EVERY_NTH_FRAME
    if raw < JPEG_EVERY_NTH_FRAME_MIN:
        return JPEG_EVERY_NTH_FRAME_MIN
    if raw > JPEG_EVERY_NTH_FRAME_MAX:
        return JPEG_EVERY_NTH_FRAME_MAX
    return raw


def _is_int(v: Any) -> bool:
    """A JSON integer: an int that is not a bool (bool is a subclass in Python)."""
    return isinstance(v, int) and not isinstance(v, bool)


def parse_native(raw_width: Any, raw_height: Any) -> tuple[int, int]:
    """Effective native resolution as (width, height).

    Valid only when BOTH values are integers (not bool, not float) AND the pair
    is on the resolution whitelist. Anything else -> (3360, 2100).
    """
    if _is_int(raw_width) and _is_int(raw_height):
        if (raw_width, raw_height) in _ALLOWED_RESOLUTIONS:
            return raw_width, raw_height
    return DEFAULT_NATIVE_WIDTH, DEFAULT_NATIVE_HEIGHT


def parse_modes(raw: Any) -> list[list[int]]:
    """Effective mode list (in config order).

    Must be an array of [width, height] pairs where EVERY pair is on the
    whitelist (and both entries are integers, not floats/bools). Empty list,
    non-list, or any invalid pair -> the default six modes.
    """
    if not isinstance(raw, list) or not raw:
        return [list(m) for m in DEFAULT_MODES]
    modes: list[list[int]] = []
    for item in raw:
        if not isinstance(item, list) or len(item) != 2:
            return [list(m) for m in DEFAULT_MODES]
        w, h = item
        if not _is_int(w) or not _is_int(h):
            return [list(m) for m in DEFAULT_MODES]
        if (w, h) not in _ALLOWED_RESOLUTIONS:
            return [list(m) for m in DEFAULT_MODES]
        modes.append([w, h])
    return modes


def parse(raw: Any) -> dict:
    """Turn an already-parsed JSON object into effective values (pure)."""
    if not isinstance(raw, dict):
        raw = {}
    native_width, native_height = parse_native(
        raw.get("nativeWidth"), raw.get("nativeHeight")
    )
    return {
        "displayName": parse_display_name(raw.get("displayName")),
        "jpegEveryNthFrame": parse_jpeg_every_nth_frame(raw.get("jpegEveryNthFrame")),
        "nativeWidth": native_width,
        "nativeHeight": native_height,
        "modes": parse_modes(raw.get("modes")),
    }


def load(path: str | Path | None = None) -> dict:
    """Read a config file, falling back to defaults on ANY error (no crash).

    A missing file, unreadable file, or invalid JSON is not fatal — defaults
    win. ``path`` defaults to ``~/.hermes/agent-screen.json``.
    """
    p = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    try:
        with open(p, encoding="utf-8") as fh:
            return parse(json.load(fh))
    except Exception:
        return parse(None)
