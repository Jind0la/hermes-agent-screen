# Stream-Refresh-Timer — Fix-Plan

**Status:** Bau-Auftrag an Coder (17.08.2026)
**Branch:** `fix/stream-refresh-timer`
**Datei:** `native/agent-screen-app.swift` (einzige Code-Änderung)

## Problem (gemessen)

Der MJPEG-Stream friert bei statischem Display-Inhalt ein:
0,07 fps (1 Frame in ~15 s) statt der erwarteten ~3 fps.
CPU der App dabei nur ~5 % — kein Leistungsproblem.

**Kernursache:** `CGVirtualDisplay` + `CGDisplayStream` liefern Frames nur bei
**Inhaltänderung**. Auf einer statischen Seite (kein Video, kein Scroll)
kommen keine neuen Surfaces → `handleFrame` feuert nicht → kein JPEG-Broadcast.

## Fix-Design

1. **Letztes Frame cachen:** In `handleFrame` zusätzlich zum
   `contentView.layer?.contents = surface` das erzeugte `CGImage` in einem
   Property `lastFrameCG: CGImage?` speichern (das CGImage wird ohnehin
   erzeugt, bevor das Surface recycelt wird — bestehende Logik, nur aufheben).
2. **Refresh-Timer:** Neuer `Timer` (Intervall 0,2 s = 5 Hz, Konstante
   `kStreamRefreshInterval`), gestartet in `applicationDidFinishLaunching`
   neben `titlebarTimer`. Jeder Tick: `guard let cg = lastFrameCG` →
   `DispatchQueue.global(qos: .utility).async { broadcastJPEG(cg) }`.
   → konstante Mindest-Framerate ~5 fps auch bei statischem Inhalt.
3. **Timer sauber stoppen:** `stopTimers()` um `streamRefreshTimer` erweitern
   (gleiche Crash-Sicherheit wie `titlebarTimer`/`dragWatchTimer` —
   `isReleasedWhenClosed`-Lektion, kein Use-after-free).

## Explizit NICHT in diesem Schritt

- Kein neuer Config-Key (`streamRefreshHz` etc.) — Intervall als Konstante,
  später trivial konfigurierbar.
- Kein Umbau von `jpegEveryNthFrame` (bleibt für den Bewegungs-Pfad).
- Keine Änderung an `broadcastJPEG` (1280er-Skalierung, q0.55) und am Server.

## Regeln (AGENTS.md)

- Feature-Branch `fix/stream-refresh-timer` von main, NIE direkt auf main.
- Commit `git commit -s` mit Trailer `Co-authored-by: Coder <coder@hermes.agent>`.
- Push nur mit x-access-token-URL (`gh auth token` in Variable, Token nie ausgeben).
- Zur Kompilier-Prüfung `./native/build-app.sh` ausführen dürfen (ersetzt das
  Bundle; laufende App erst nach Freigabe von Era neu starten).
- Fertig/Blockiert an Era melden: `hermes -p default chat "..."`.

## Verifikation (macht Era, nicht Coder)

1. `./native/build-app.sh` → Bundle + Signatur OK
2. FPS-Messung bei statischem Inhalt: `scripts/fps_test.py` → ≥ 4 fps
3. `ps -o %cpu` der App: vertretbar (< 25 %)
4. App-Schließen ohne Crash (stopTimers)
5. `pytest tests/` grün (Config unverändert)
