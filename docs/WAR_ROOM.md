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
- **Eich-02 Nachzug (18:30):** `CGVirtualDisplayMode(width:height:)` nimmt NSUInteger;
  Config-Ints wurden nicht implizit gecastet (nur Literale) → Build-Fehler behoben mit
  explizitem `UInt(...)`. Bundle wirklich neu gebaut + signiert (Agent Screen Dev,
  Signed 15.08. 18:37:56), Binary enthält `nativeWidth`. Nicht gemergt.

## Kernursache 17.08.: Input-Probleme beim Arbeiten auf dem Agent-Screen
Live-Nutzung (16.08., SEO-Abend): Capture zeigte nach jedem Klick das falsche
Fenster („Space-Flackern"), Enter-Taste kam nicht an, Vollbild = keine Frames.
**Eine Wurzel:** Das per Drag-Portal verschobene Fremd-Fenster ist nie das
„main window" der App — das bleibt das Hauptfenster auf dem Hauptdisplay.
Jede Input-Aktion aktiviert die App (Event-Routing), macOS holt das main
window nach vorn → nächster Capture (app-weit) zeigt X/Twitch statt Ziel;
Tastatur-Events gehen an den Key-Fokus im Hauptfenster (Enter tot). Vollbild
auf dem virtuellen Display = eigenes Space + ScreenCaptureKit liefert von
virtuellen Displays keine Frames → 19px-Capture. Workaround gestern:
`osascript set index of window 2 to 1` + `activate` nach jedem Klick
(fokusklauend). **Fix-Optionen:** exakte (pid, window_id)-Bindung +
element_token statt `app=`; px-Fokus-Klick vor Tastatur (`type_text`/`press_key`
mit x,y); kein Vollbild auf dem Agent-Screen; für Web: Chromium-Browser
(Comet wird von cua-driver nicht als Browser erkannt → keine DOM-Route).

## Lösung 17.08.: Agent-Browser via CDP (bewiesen)
**Comet-Befund:** Comet = Chromium (Bundle ai.perplexity.comet, 151.0.7922.247),
CDP per `--remote-debugging-port` aktivierbar (Perplexity: RemoteDebuggingAllowed),
aber als Agent-Browser UNBRAUCHBAR: Target.createTarget-Tabs werden unsichtbar
erzeugt (nie aktiver Tab im Fenster), Target.activateTarget/closeTarget werden
ignoriert, Hermes-Supervisor hängt am frontmost-Tab ≠ Tool-Tab → Enter/Fokus
scheitern. Dazu Telemetrie-Frames (count.perplexity.ai).
**Lösung (live bewiesen):** Chrome for Testing (Playwright-Bundle,
`~/Library/Caches/ms-playwright/chromium-1208/...`) mit eigenem Profil
`~/.hermes/agent-browser` + `--remote-debugging-port=9224`, Fenster per AX-PID
aufs virtuelle Display. Hermes: `browser.cdp_url: http://127.0.0.1:9224` in
config.yaml → ALLE browser_* Tools steuern den sichtbaren Browser DOM-Level:
kein AX-Fokus-Chaos, kein SCK-Problem (Screenshots via CDP), Enter funktioniert
(Playwright-Key-Sequenz; Form-Submit live verifiziert: `?q=agent-screen-rockt`).
Start: `~/.hermes/scripts/agent-browser.sh` (idempotent, positioniert Fenster).
**VERIFIZIERT 17.08. 08:20 (nach Hermes-Neustart):** browser_exec (Browser-Use)
läuft im Agent-Browser, Enter-Form-Submit live („SUBMITTED: agent-screen-rockt"),
Tab-Aktivierung per `Target.activateTarget` nötig (bei Comet wurde sie ignoriert —
der entscheidende Unterschied). Logins im Agent-Profil (LinkedIn/X) einmalig
einrichten — Nimars Comet-Hauptprofil bleibt unberührt.

## Lösung 17.08.: Agent-Screen-Display auf 1080p-Default
Symptom: Desktop lief immer auf 3360×2100, Stream skalierte auf 1080p runter
→ winzige UI auf allen Captures. Kernursache: Der WindowServer wählt den
HÖCHSTEN angebotenen Modus; die App bot alle 6 Whitelist-Modi an. Fix: Die App
bietet nur noch den effektiven Modus an (nativeWidth×nativeHeight, hiDPI=1)
→ Display deterministisch 1920×1080 (NSScreen verifiziert, scale 2 =
retina-scharf im Stream). Defaults in Swift + `dashboard/config.py` auf
1920×1080, `.example` + Live-Config `~/.hermes/agent-screen.json` gesetzt.
Tests 21/21, Build signiert „Agent Screen Dev". Branch
`fix/default-resolution-1080p`.

## Test 17.08. 09:15: Klick-Tour nimar.moradbakhti.de (1080p-Display)
Agent-Browser (Chrome for Testing, CDP 9224) auf dem virtuellen Display:
Seite lädt, Klicks kommen an — These-Anker, Blog, Impressum, Datenschutz,
Artikel per CDP-Input.dispatchMouseEvent. Befunde: (1) Blog-Artikel öffnen
als MODAL (URL bleibt /blog — Seitenverhalten, kein Bug). (2) DOM-
dispatchEvent reicht bei den Next.js-Links nicht — trusted Mausklick (CDP)
nötig, wie ein echter Nutzer. (3) Screen 1920×1080 gestochen scharf (Vision:
„keine Pixelbildung"), Stream liefert 1280×720-Frames. (4) cua-driver erfasst
den Browser auf dem virtuellen Display per exakter (pid, window_id)-Bindung
— das Gegenstück zur Main-Window-Falle: gezielte Bindung statt app-weit.

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
