# War Room — Hermes Agent Screen (Repo)

## Zweck
Standalone-Plugin-Repo für die macOS-App „Agent Screen": virtuelles Display
(CGVirtualDisplay-Fork von DeskPad, MIT) + MJPEG-Stream + Klick-Warp +
Hermes-Plugin (Desktop-Pane + Status-Chip + Backend plugin_api.py).
Install: `./install.sh` → `~/.hermes/plugins` + desktop-plugins + Skill.

## Aktueller Stand (17.08.2026)
- App läuft aus Bundle, signiert „Agent Screen Dev" (TCC-Grant überlebt
  Rebuilds); Drag-Portal fertig (Fenster per Drag auf virtuelles Display);
  Plugin Pane+Status-Chip (startet/stoppt via Backend); Dock-Icon V4.
- **Agent-Browser via CDP (LÖSUNG, live verifiziert 17.08):** Chrome for
  Testing (Playwright-Bundle, Chromium-1208) + eigenes Profil
  `~/.hermes/agent-browser` + `--remote-debugging-port=9224`; Hermes config
  `browser.cdp_url: http://127.0.0.1:9224` → ALLE browser_* steuern den
  sichtbaren Browser DOM-Level (kein AX-Fokus-Chaos, kein SCK-Problem, Enter
  funktioniert; Form-Submit verifiziert). Start-Skript idempotent:
  `~/.hermes/scripts/agent-browser.sh`. **Comet als Agent-Browser UNBRAUCHBAR**
  (Target.createTarget-Tabs unsichtbar, activateTarget/closeTarget ignoriert,
  Hermes-Supervisor hängt am frontmost-Tab, Telemetrie).
- **Display deterministisch 1080p** (1920×1080, scale 2, retina-scharf): App
  bietet nur noch den effektiven Modus an (vorher WindowServer nahm höchsten
  der 6 Whitelist-Modi → 3360×2100). Defaults Swift + `dashboard/config.py` +
  `.example` + Live-Config. Branch `fix/default-resolution-1080p`.
- **Stream-Refresh-Fix gemergt (main f3d199b):** CGVirtualDisplay liefert
  Frames nur bei Inhaltänderung → statische Seite frierte ein (0,07 fps).
  Fix: lastFrameCG cachen + 5-Hz-Timer. Era-Verifikation grün: 0,07→4,77 fps,
  CPU 4,2 %, Crash-Check sauber, pytest 21/21. Elon MERGE-READY (2 Punkte →
  GitHub-Issue: Timer-Encoding nur bei ≥1 Client + Stale-Suppression).
- **MJPEG-Robustheit + Kaltstart gemergt (17.08., FF 56e71cb..7ae224b):**
  Client-Gate, Stale-Suppression, Verbindungs-Race, Server-Start nach erstem
  Frame. Era-Messung: 0 Timeouts, fps 5,16, CPU 0 % ohne / ~1–2 % mit Client.
  Folge: pytest sammelt scripts/fps_test.py (parst -q als fps-Argument).
- Eich-01/02 erledigt: Display-Name/jpegEveryNthFrame/Auflösung/Modus-Liste
  aus `~/.hermes/agent-screen.json`; `kNativeWidth/Height` durch runtimeConfig
  ersetzt; expliziter `UInt(...)`-Cast (NSUInteger) — Bundle neu gebaut.

## Kernursache Input-Probleme (16.08., SEO-Abend)
Das per Drag-Portal verschobene Fremd-Fenster ist nie das „main window" — jede
Input-Aktion aktiviert die App, macOS holt das main window nach vorn → Capture
(app-weit) zeigt X/Twitch statt Ziel; Enter geht an Key-Fokus im Hauptfenster
(tot). Vollbild auf virtuellem Display = eigenes Space, SCK liefert dort keine
Frames → 19px-Capture. Workaround damals: `osascript set index of window 2 to
1`+`activate` (fokusklauend). **Fix-Optionen (für künftige Sessions):**
exakte (pid, window_id)-Bindung + element_token statt `app=`; px-Fokus-Klick
vor Tastatur; kein Vollbild auf Agent-Screen; für Web → Agent-Browser/CDP
(siehe Aktueller Stand). cua-driver erfasst Browser auf virtuellem Display per
exakter (pid, window_id)-Bindung — Gegenstück zur Main-Window-Falle.

## Verifikation 17.08. (Era, eigene Messung)
Era-Review (DeepSeek ≠ Builder-Flash) gegen Branch-Code ist der Beleg.
**Lektion: vom Coder gestartete Instanz lief mit ALTEM Code** (keine neuen
NSLogs, 2/5 Timeouts bei Erstmessung) — „15× 0 Timeouts" des Coders nicht
belastbar; eigene Messung gegen echten Branch-Code zählt. Diff-Reviews exakt
nach Plänen (`docs/plans/mjpeg-server-fix.md`, `stream-refresh-fix.md`).

## Tool-Lektionen (Klick-Tour + Benchmarks, 17.08.)
- Hit-Test `elementFromPoint` VOR jedem Klick (Footer-Links nach Scroll verdeckt).
- browser-exec: `agent_helpers.py` = Modul-Import, `js`/`cdp` dort unsichtbar →
  Helper inline pro Call definieren; `capture_screenshot()` explizit aufrufen
  (snap-Helper, der nur bekannte Datei kopiert, re-shippt still den alten Shot).
- Trusted Mausklick (CDP Input.dispatchMouseEvent) nötig bei Next.js-Links;
  DOM-dispatchEvent reicht nicht. Escape schließt Blog-Modal NICHT —
  `button[aria-label="Schließen"]`.
- Natives `<select>`: JS-Wert+change statt DOM-Klick (OS-Menü); Dropdown/
  Checkbox sind kleine Ziele — Retry muss NEU testen, nicht nur wiederholen.
- todomvc persistiert in localStorage (Alt-Items verfälschen Läufe) →
  vorher säubern.
- Stream-Frame-Curl timeoutet gelegentlich (3/5) → Retry; fps_test.py
  (urllib) zuverlässig.
- Klick-Tour-Befund Website: Nav-Link „These" (#blatt) ist tot.

## Benchmark (17.08., Baseline nach Stream-Fix)
- `scripts/benchmark_klicktour.py` (pure CDP): Blog 2,3 s; 5 Artikel je
  1,3–2,1 s, gesamt 11,4 s (Sleep-dominiert) → Optimierung Wait-on-Condition.
- Capture-Kosten (gleiche Seite): DOM 0 > CDP-Screenshot 146 KB >
  Stream ~150–250 KB (1280×720 JPEG) >> screencapture 3 MB.
- `scripts/benchmark_huerden.py` (17.08., 2× grün): dropdown 2 ms (JS-Weg),
  checkbox 310 ms, slider 315 ms, drag&drop 320 ms, keypress 610 ms,
  todomvc 3,15 s. Animation lokal 7,8 fps bei CPU 11,9 %.
- Weitere Kandidaten: demoqa.com, letcode.in/test, automationintesting.online
  (Restful Booker), demoblaze.com, parabank.parasoft.com. Down:
  uitestingplayground.com, automationpractice.pl, testpages.herokuapp.com (503).

## Laufende Tasks
- [x] MJPEG-Robustheit+Kaltstart gemergt (7ae224b)
      pytest-Collection-Fix für fps_test.py)
- [ ] Kleinkram-Sammlung des Users
- [ ] Optional: ⌘K-Command „Shift <App>" — Auslösemethode offen

## Entscheidungen
- **Kein First-Party-PR an Nous:** private SPI (CGVirtualDisplay) =
  Wartungsrisiko; dieses Repo ist kanonisch. PR #85518 im hermes-agent nur
  Pointer + DeskPad-Credit.
- Kein LaunchAgent-Autostart.
- Git-Workflow: Feature-Branch → Push → Merge, nie direkt auf main; Push nur
  mit x-access-token-URL.
- Zertifikat „Agent Screen Dev" / Bundle-ID ai.hermes.agent-screen — NIE
  ad-hoc signieren (TCC-Lektion).
- DeskPad-Fork (Stengo / Bastian Andelefski, MIT 2022) — NOTICE beachten.

## Fehlschläge & Korrekturen
- **Crash EXC_BAD_ACCESS (3× am 13.08.):** use-after-free im Drag-Portal-Timer
  (Fenster per X geschlossen, Timer lief weiter). Fix: isReleasedWhenClosed=false
  + Timer-Stopp bei willClose + applicationWillTerminate-Backstop → 0 weitere.
- **Drag-Portal, 3 Bugs:** (1) WindowServer schluckt Titelleisten-Drags →
  Polling; (2) Dock (Layer 20) verdeckt Fenster im Hit-Test → oberstes
  Layer-0-Fenster; (3) CGWindowBounds/NSEvent vs. CGEventPost → Umrechnung.
- **Dock-Icon-Cache:** `/var/folders`-Caches löschen, nicht nur ~/Library/Caches.

## Wichtige Pfade & Fakten
- App-Code: `native/` · Plugin: `desktop/` · Backend: `desktop/plugin_api.py`
- Stream: `http://127.0.0.1:8788/stream.mjpeg` · Ping: `/ping`
- Process-Match: `pgrep -x` / `pkill -x agent-screen-app` (nie `-f`)
- Skill: `computer-use` (Sektion „Agent Screen (macOS)")
