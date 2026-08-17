# MJpegServer-Robustheit: Client-Gate + Stale-Suppression + Verbindungs-Race (Issues #1/#2)

**Status:** Bau-Auftrag an Coder (17.08.2026)
**Branch:** `fix/mjpeg-server-robustness`
**Datei:** `native/agent-screen-app.swift` (einzige Code-Änderung)

## Probleme (Era-Code-Review 17.08.)

### Issue #2 (Bug) — curl-Frame-Grab timeoutet beim Verbindungsaufbau
Befund: `curl -s --max-time 8` auf `/stream.mjpeg` timeoutet gelegentlich (3/5),
obwohl der Stream 4,77 fps liefert und `/ping` sofort antwortet. Verbindung steht
(kein 503 busy), aber keine Daten bis zum Timeout. Retry hilft sofort.
`fps_test.py` (urllib, 12s-Lesespanne) ist nie betroffen.

Code-Befunde (Era-Review, alle in `MJpegServer`):

1. **Registrierungs-Race (real):** Zeile ~213-215 — der Client wird erst in der
   `send`-Completion (`contentProcessed { _ in ... }`) per `queue.async` in
   `clients` aufgenommen. Broadcasts zwischen Header-Send und Append verliert
   der Client. Bei 5-Hz-Timer nur ~200 ms — erklärt den vollen 8-s-Timeout
   nicht allein, ist aber ein echter Race.
2. **send-Completion ignoriert Fehler:** `{ _ in self.clients.append(conn) }` —
   der Fehler-Parameter wird weggeworfen. Wenn der Header-Send hängt (Completion
   feuert nie) oder fehlschlägt, wird der Client nie / sinnlos registriert und
   wartet ggf. dauerhaft auf Frames, obwohl die Verbindung steht. **Das ist der
   Mechanismus, der einen anhaltenden Timeout erklären kann.**
3. **pruneClients unvollständig:** entfernt nur `.failed`/`.cancelled`.
   Halbtote Verbindungen (Client weg ohne sauberen TCP-Close) bleiben stehen und
   können die 8er-Liste zustellen → später dann 503 für neue Clients.

### Issue #1 (Enhancement) — Timer-Optimierung
1. **Client-Gate fehlt:** Der 5-Hz-Refresh-Timer (Z. ~354) enkodiert
   `lastFrameCG` alle 0,2 s — auch mit 0 verbundenen Clients (JPEG-Encoding ist
   der teure Teil, nicht der Send). Zusätzlich enkodiert `handleFrame` bei jedem
   `jpegEveryNthFrame`-ten Frame (Default 20 → ~3 fps) unabhängig von Clients.
2. **Stale-Suppression fehlt:** Liefert CGDisplayStream gerade frische Frames
   (Scroll/Video), enkodiert der Timer zusätzlich das alte gecachte Bild —
   Doppel-Kodierung.

## Fix-Design

### Teil C (Issue #2 Restfall — Kaltstart, Era-Befund 17.08. 11:00)
**Befund:** Nach App-Neustart kommt der erste CGDisplayStream-Frame erst nach
1–18 s (WindowServer-Hochfahren des virtuellen Displays, gemessen: 1 s / 18 s).
Verbindet ein Client in dieser Zeit, ist `lastFrameCG == nil` →
`onFirstClient` sendet nichts → curl timeoutet (--max-time 8). Mit Teil A+B
wurde der Race bei laufender App behoben (15/15 Grabs), der Kaltstart-Fall
bleibt.

**Fix:** `server.start()` aus `applicationDidFinishLaunching` entfernen.
Stattdessen im ERSTEN `handleFrame`-Aufruf (ganz oben, vor dem
`frameCounter`-Check) einmalig starten (Bool-Flag `serverStarted`).
Konsequenz: `/ping` antwortet erst, wenn der Stream wirklich bereit ist;
frühe Clients bekommen connection refused (sofortiger Fehler, Retry explizit)
statt eines Timeouts. `do-catch` + NSLog bleibt. Keine weiteren Änderungen.
`onFirstClient` bleibt (fallback für den Fall, dass ein Client nach dem ersten
Frame verbindet, während `lastFrameCG` veraltet ist).

### Teil A (Issue #2) — Server-Registrierung robust machen
- **A1:** Client **vor** dem Header-Send in `clients` aufnehmen — direkt im
  `self.queue.async`-Block von `handle` (serial queue; `broadcast` läuft auf
  derselben queue → atomar gegen Broadcasts, kein Frame verlierbar).
  Reihenfolge: `pruneClients()` → Limit-Check → `clients.append(conn)` →
  Header senden. Der 503-Pfad bleibt unverändert.
- **A2:** send-Completion-Fehler behandeln: `contentProcessed { error in
  if error != nil { self.queue.async { conn.cancel() } } }` (prune räumt dann
  beim nächsten Durchlauf). Der Client ist ja schon in der Liste (A1) — bei
  Header-Send-Fehler sofort wieder raus.
- **A3:** `pruneClients()` zusätzlich um send-Fehler erweitern: In `broadcast`
  bei `conn.send`-Completion mit `error != nil` → `conn.cancel()`
  (entfernt wird sie dann beim nächsten prune). Das räumt halbtote Clients,
  die nie sauber geschlossen haben.
- **A4 (Diagnose, bleibt im Code):** NSLog bei Connection-Events statt bei
  Frames: „client connected (n)", „client disconnected (n)", „send error →
  cancel". Kein Per-Frame-Logging (5-Hz-Spam). So ist ein Wiederauftreten
  sofort im `log stream` nachweisbar.

### Teil B (Issue #1) — Timer-Gate
- **B1:** `MJpegServer.clientCount: Int` — berechnet auf der eigenen queue
  (`queue.sync { clients.count }`; alle queue-Blöcke sind kurz und blockieren
  Main nie → kein Deadlock-Risiko).
- **B2 (Client-Gate):**
  - Timer-Tick: `guard self.server.clientCount > 0 else { return }` VOR dem
    Encode-Dispatch (spart das 5-Hz-Encoding ohne Zuschauer).
  - `handleFrame`: Encode-Pfad (inkl. `lastFrameCG`-Update) nur bei
    `server.clientCount > 0`. **Regression verhindern:** statischer Inhalt +
    erster Client → CGDisplayStream liefert keinen neuen Frame, der Timer hätte
    nichts Frisches. Deshalb: `MJpegServer` bekommt einen
    `onFirstClient: (() -> Void)?`-Callback (0→1-Übergang, auf queue gesetzt,
    Aufruf asynchron auf Main) → AppDelegate enkodiert `lastFrameCG` sofort
    (falls vorhanden) und sendet. Edge-Case: Client kommt vor dem ersten
    Display-Frame (`lastFrameCG == nil`) → nichts senden, der erste echte Frame
    kommt gleich darauf — Stream startet minimal verzögert, ok.
- **B3 (Stale-Suppression):** Neues Property `lastEncodeDate: Date?`, wird NUR
  in `handleFrame` gesetzt (nach dem Encode-Dispatch). Timer-Tick:
  `if let d = lastEncodeDate, Date().timeIntervalSince(d) <= kStreamRefreshInterval { return }`.
  Semantik: Tick überspringt, wenn der Display-Pfad im letzten Intervall
  bereits enkodiert hat. Der Timer setzt `lastEncodeDate` NICHT (kein
  Selbst-Skip → statischer Inhalt bleibt konstant 5 Hz).

## Explizit NICHT in diesem Schritt
- Kein Config-Key für das Client-Gate / die Suppression (Konstanten).
- Keine Änderung an `broadcastJPEG` (1280er-Skalierung, q0.55), an
  `jpegEveryNthFrame`, am Plugin (desktop/) oder Backend (plugin_api.py).
- Kein Umbau des 503/`kStreamMaxClients`-Verhaltens.

## Regeln (AGENTS.md)
- Feature-Branch `fix/mjpeg-server-robustness` von main, NIE direkt auf main.
- Commit `git commit -s` mit Trailer `Co-authored-by: Coder <coder@hermes.agent>`.
- Push nur mit x-access-token-URL (Token nie ausgeben).
- `./native/build-app.sh` ausführen dürfen (ersetzt das Bundle) — laufende App
  erst nach Freigabe von Era neu starten.
- Fertig/Blockiert an Era melden: `hermes -p default chat "..."`.

## Verifikation (macht Era, ausführlich — User-Auftrag)
1. Diff-Review (Era + Grok, anderes Modell als Builder)
2. `./native/build-app.sh` → Bundle + Signatur „Agent Screen Dev" OK
3. App-Neustart (pkill -x, ~3 s warten, start, `/ping` ok)
4. **curl-Grab-Repro:** 15× `curl -s --max-time 8 -o /dev/null` → 0 Timeouts
   (Vorher-Befund: 3/5 Timeouts)
5. `scripts/fps_test.py` bei statischem Inhalt → ≥ 4 fps (vorher 4,77)
6. CPU mit vs. ohne Client (`ps -o %cpu`): ohne Client deutlich niedriger
   (Client-Gate-Nachweis)
7. Stale-Suppression: `scripts/benchmark-animation.html`-Tour → fps/CPU nicht
   schlechter als Baseline (7,8 fps / 11,9 %)
8. Crash-Check: Fenster schließen → 0 Crashes; danach wieder startbar
9. `pytest tests/` grün (Config/Plugin unverändert)
