"""Tests for the agent-screen dashboard plugin (standalone install).

Contract, not a change-detector:

* the FastAPI router imports and exposes /status /start /stop
* /status always reports platform + supported
* /start and /stop are 501 off macOS and never spawn/kill
* a healthy running instance makes /start a no-op (no second Popen)
* process control uses ``pgrep -x`` / ``pkill -x``, never ``-f``
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

PLUGIN_MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "dashboard" / "plugin_api.py"
)


@pytest.fixture
def plugin_api(monkeypatch):
    spec = importlib.util.spec_from_file_location(
        f"agent_screen_plugin_api_{id(monkeypatch)}", PLUGIN_MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def client(plugin_api):
    app = FastAPI()
    app.include_router(plugin_api.router, prefix="/api/plugins/agent-screen")
    return TestClient(app)


def test_router_exports_expected_routes(plugin_api):
    paths = {route.path for route in plugin_api.router.routes}
    assert "/status" in paths
    assert "/start" in paths
    assert "/stop" in paths


def test_status_reports_platform_and_supported(client, plugin_api, monkeypatch):
    monkeypatch.setattr(plugin_api, "_supported", lambda: False)
    monkeypatch.setattr(plugin_api, "_app_running", lambda: False)
    monkeypatch.setattr(plugin_api, "_stream_ok", lambda: False)
    monkeypatch.setattr(plugin_api.sys, "platform", "linux")
    r = client.get("/api/plugins/agent-screen/status")
    assert r.status_code == 200
    body = r.json()
    assert body["supported"] is False
    assert body["running"] is False
    assert body["stream"] is False
    assert body["platform"] == "linux"
    assert "macOS" in body["error"]


def test_start_stop_are_501_off_macos(client, plugin_api, monkeypatch):
    spawned = []
    killed = []

    monkeypatch.setattr(plugin_api, "_supported", lambda: False)
    monkeypatch.setattr(plugin_api, "_spawn", lambda: spawned.append(True))
    monkeypatch.setattr(
        plugin_api.subprocess,
        "run",
        lambda *a, **k: killed.append(a) or type("R", (), {"returncode": 1, "stdout": ""})(),
    )

    start = client.post("/api/plugins/agent-screen/start")
    stop = client.post("/api/plugins/agent-screen/stop")
    assert start.status_code == 501
    assert stop.status_code == 501
    assert spawned == []
    assert killed == []


def test_start_is_noop_when_healthy(client, plugin_api, monkeypatch):
    spawned = []
    monkeypatch.setattr(plugin_api, "_supported", lambda: True)
    monkeypatch.setattr(plugin_api, "_app_running", lambda: True)
    monkeypatch.setattr(plugin_api, "_stream_ok", lambda: True)
    monkeypatch.setattr(plugin_api, "_spawn", lambda: spawned.append(True))
    monkeypatch.setattr(plugin_api, "_launcher_ok", lambda: True)

    r = client.post("/api/plugins/agent-screen/start")
    assert r.status_code == 200
    assert r.json()["running"] is True
    assert spawned == []


def test_start_errors_when_launcher_missing(client, plugin_api, monkeypatch):
    monkeypatch.setattr(plugin_api, "_supported", lambda: True)
    monkeypatch.setattr(plugin_api, "_app_running", lambda: False)
    monkeypatch.setattr(plugin_api, "_stream_ok", lambda: False)
    monkeypatch.setattr(plugin_api, "_launcher_ok", lambda: False)

    r = client.post("/api/plugins/agent-screen/start")
    assert r.status_code == 200
    assert "launcher missing" in r.json()["error"]


def test_stop_is_noop_when_not_running(client, plugin_api, monkeypatch):
    calls = []
    monkeypatch.setattr(plugin_api, "_supported", lambda: True)
    monkeypatch.setattr(plugin_api, "_app_running", lambda: False)
    monkeypatch.setattr(plugin_api, "_stream_ok", lambda: False)
    monkeypatch.setattr(
        plugin_api.subprocess,
        "run",
        lambda *a, **k: calls.append(a[0]) or type("R", (), {"returncode": 1, "stdout": ""})(),
    )

    r = client.post("/api/plugins/agent-screen/stop")
    assert r.status_code == 200
    assert calls == []


def test_status_reports_effective_config_values(client, plugin_api, monkeypatch, tmp_path):
    monkeypatch.setattr(plugin_api, "_supported", lambda: False)
    monkeypatch.setattr(plugin_api, "_app_running", lambda: False)
    monkeypatch.setattr(plugin_api, "_stream_ok", lambda: False)
    cfg_path = tmp_path / "agent-screen.json"
    cfg_path.write_text(
        '{"displayName": "  Konfig Display  ", "jpegEveryNthFrame": 42}',
        encoding="utf-8",
    )
    # Point the standalone-loaded config module at our temp file.
    monkeypatch.setattr(plugin_api.config, "DEFAULT_CONFIG_PATH", cfg_path)
    r = client.get("/api/plugins/agent-screen/status")
    assert r.status_code == 200
    body = r.json()
    assert body["displayName"] == "Konfig Display"
    assert body["jpegEveryNthFrame"] == 42


def test_status_defaults_when_no_config(client, plugin_api, monkeypatch, tmp_path):
    monkeypatch.setattr(plugin_api, "_supported", lambda: False)
    monkeypatch.setattr(plugin_api, "_app_running", lambda: False)
    monkeypatch.setattr(plugin_api, "_stream_ok", lambda: False)
    # Point at a path that does not exist -> parser must fall back to defaults.
    monkeypatch.setattr(
        plugin_api.config,
        "DEFAULT_CONFIG_PATH",
        tmp_path / "no-such-config.json",
    )
    r = client.get("/api/plugins/agent-screen/status")
    assert r.status_code == 200
    body = r.json()
    assert body["displayName"] == plugin_api.config.DEFAULT_DISPLAY_NAME
    assert body["jpegEveryNthFrame"] == plugin_api.config.DEFAULT_JPEG_EVERY_NTH_FRAME
    assert body["nativeWidth"] == plugin_api.config.DEFAULT_NATIVE_WIDTH
    assert body["nativeHeight"] == plugin_api.config.DEFAULT_NATIVE_HEIGHT
    assert body["modes"] == plugin_api.config.DEFAULT_MODES


def test_status_reports_native_and_modes(client, plugin_api, monkeypatch, tmp_path):
    monkeypatch.setattr(plugin_api, "_supported", lambda: False)
    monkeypatch.setattr(plugin_api, "_app_running", lambda: False)
    monkeypatch.setattr(plugin_api, "_stream_ok", lambda: False)
    cfg_path = tmp_path / "agent-screen.json"
    cfg_path.write_text(
        '{"nativeWidth": 1920, "nativeHeight": 1080,'
        ' "modes": [[1920, 1080], [1280, 720]]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(plugin_api.config, "DEFAULT_CONFIG_PATH", cfg_path)
    r = client.get("/api/plugins/agent-screen/status")
    assert r.status_code == 200
    body = r.json()
    assert body["nativeWidth"] == 1920
    assert body["nativeHeight"] == 1080
    assert body["modes"] == [[1920, 1080], [1280, 720]]


def test_process_control_uses_exact_name_not_full_cmdline(plugin_api):
    src = PLUGIN_MODULE_PATH.read_text()
    assert '["pgrep", "-x", PROC_NAME]' in src
    assert '["pkill", "-x", PROC_NAME]' in src
    assert plugin_api.PROC_NAME == "agent-screen-app"
    # The old footgun must not come back.
    assert 'pgrep", "-f"' not in src
    assert 'pkill", "-f"' not in src


def test_status_probes_are_cached_until_invalidated(client, plugin_api, monkeypatch):
    counts = {"app": 0, "stream": 0}

    def app_running_uncached():
        counts["app"] += 1
        return False

    def stream_ok_uncached():
        counts["stream"] += 1
        return False

    monkeypatch.setattr(plugin_api, "_supported", lambda: True)
    monkeypatch.setattr(plugin_api, "_app_running_uncached", app_running_uncached)
    monkeypatch.setattr(plugin_api, "_stream_ok_uncached", stream_ok_uncached)

    # Two back-to-back polls fall inside the TTL -> each probe runs once.
    client.get("/api/plugins/agent-screen/status")
    client.get("/api/plugins/agent-screen/status")
    assert counts["app"] == 1
    assert counts["stream"] == 1

    # Invalidation forces a fresh probe on the next poll.
    plugin_api._invalidate_probes()
    client.get("/api/plugins/agent-screen/status")
    assert counts["app"] == 2
    assert counts["stream"] == 2


class _FastClock:
    """Deterministic stand-in for ``time``: no-op sleeps, fast-advancing clock.

    Replaces the ``time`` name inside plugin_api only (the stdlib module is
    untouched), so ``_wait_until`` degenerates to a few instant iterations
    instead of real multi-second sleeps.
    """

    def __init__(self):
        self._t = 0.0

    def time(self):
        self._t += 1.0
        return self._t

    def sleep(self, seconds):
        pass


def test_start_respawns_hung_instance(client, plugin_api, monkeypatch):
    """A hung process (up, stream down, refuses to die) is killed once and
    respawned once — never two instances side by side."""
    calls = {"kill": 0, "spawn": 0}
    state = {"running": True, "stream": False}

    def app_running_uncached():
        return state["running"]

    def stream_ok_uncached():
        return state["stream"]

    def kill():
        calls["kill"] += 1
        state["running"] = False

    def spawn():
        calls["spawn"] += 1
        state["running"] = True
        state["stream"] = True

    monkeypatch.setattr(plugin_api, "_supported", lambda: True)
    monkeypatch.setattr(plugin_api, "_launcher_ok", lambda: True)
    monkeypatch.setattr(plugin_api, "_app_running_uncached", app_running_uncached)
    monkeypatch.setattr(plugin_api, "_stream_ok_uncached", stream_ok_uncached)
    monkeypatch.setattr(plugin_api, "_kill", kill)
    monkeypatch.setattr(plugin_api, "_spawn", spawn)
    monkeypatch.setattr(plugin_api, "time", _FastClock())

    r = client.post("/api/plugins/agent-screen/start")
    assert r.status_code == 200
    assert calls["kill"] == 1
    assert calls["spawn"] == 1
    assert r.json()["stream"] is True
