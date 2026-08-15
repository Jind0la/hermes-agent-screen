# War Room — Hermes Agent Screen (Repo)

## Zweck
Standalone-Plugin-Repo für die macOS-App „Agent Screen": virtuelles Display
(CGVirtualDisplay-Fork von DeskPad, MIT) + MJPEG-Stream + Klick-Warp +
Hermes-Plugin (Desktop-Pane + Status-Chip + Backend plugin_api.py).
Install: `./install.sh` → `~/.hermes/plugins` + desktop-plugins + Skill.

## Aktueller Stand (13.08.2026)
- App läuft aus Bundle, signiert „Agent Screen Dev" (TCC-Grant überlebt Rebuilds)
- Drag-Portal fertig: Fenster per Drag auf das Agent-Screen-Fenster → landet
  zentriert auf dem virtuellen Display (live bewiesen)
- Plugin: Pane + Status-Chip (grün #16A34A / grau), Chip startet/stoppt via
  Backend — vom User bestätigt
- Dock-Icon V4 (Retro-Manga CRT, randlos)
- Autostart: entschieden — kein LaunchAgent, nur bei Bedarf
- Ausführliche lokale Checkliste + Fakten: `~/Workspace/projects/09-agent-screen/CHECKLISTE.md`
- **Eich-01 erledigt:** Display-Name + `jpegEveryNthFrame` aus `~/.hermes/agent-screen.json`
  gelesen (Backend `dashboard/config.py`, Swift-Spiegel in `native/agent-screen-app.swift`,
  Beispiel `native/agent-screen.json.example`). `/status` meldet die effektiven Werte.
- **Eich-02 erledigt:** Auflösung (`nativeWidth`/`nativeHeight`) + Modus-Liste (`modes`)
  kommen aus derselben Config (Whitelist von 6 Auflösungen, Float/Bool → Default),
  `/status` meldet die effektiven Werte, `kNativeWidth/Height` sind durch
  `runtimeConfig` ersetzt. Refresh bleibt 60, `descriptor.maxPixelsWide/High` 5120/2160.

## Laufende Tasks
- [ ] Kleinkram-Sammlung des Users
- [ ] Optional: ⌘K-Command „Shift <App>" — Auslösemethode offen

## Entscheidungen
- **Kein First-Party-PR an Nous:** private SPI (CGVirtualDisplay) = Wartungsrisiko;
  dieses Repo ist kanonisch. PR #85518 im hermes-agent ist nur Pointer + DeskPad-Credit
- Kein LaunchAgent-Autostart
- Git-Workflow: Feature-Branch → Push → Merge, nie direkt auf main; Push nur mit
  x-access-token-URL
- Zertifikat „Agent Screen Dev" / Bundle-ID ai.hermes.agent-screen — NIE ad-hoc
  signieren (TCC-Lektion)
- DeskPad-Fork (Stengo / Bastian Andelefski, MIT 2022) — NOTICE beachten

## Fehlschläge & Korrekturen
- **Crash EXC_BAD_ACCESS (3× am 13.08.):** use-after-free im Drag-Portal-Timer —
  Fenster per X geschlossen, während der 0.1s-Timer weiterlief. Fix:
  `isReleasedWhenClosed=false` + Timer-Stopp bei `willClose` +
  `applicationWillTerminate`-Backstop → 0 weitere Crashes
- **Drag-Portal, 3 Bugs:** (1) WindowServer schluckt Titelleisten-Drags → Polling
  (0.1s); (2) Dock (Layer 20) verdeckt Fenster im Hit-Test → oberstes Layer-0-Fenster;
  (3) CGWindowBounds/NSEvent (unten-links) vs. CGEventPost (oben-links) → Umrechnung
- **Dock-Icon-Cache:** `/var/folders`-Caches löschen, nicht nur `~/Library/Caches`

## Wichtige Pfade & Fakten
- App-Code: `native/` · Plugin: `desktop/` · Backend: `desktop/plugin_api.py`
- Stream: `http://127.0.0.1:8788/stream.mjpeg` · Ping: `/ping`
- Process-Match: `pgrep -x` / `pkill -x agent-screen-app` (nie `-f`)
- Skill: `computer-use` (Sektion „Agent Screen (macOS)")
