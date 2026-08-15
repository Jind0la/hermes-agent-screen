# Plan: Eich-02 — Agent Screen Runtime-Config (Auflösung + Modi)

**Repo:** `~/Workspace/projects/10-hermes-agent-screen`
**Branch:** `feat/eich-02-display-modes` (nie `main`; `main` steht auf `ef6d5a9`)
**Auftraggeber:** Era. **Bauer:** Coder.
**Vorgänger:** Eich-01 (`docs/plans/coder-eich-01-display-config.md`, gemergt
`ef6d5a9`). Dieselbe Datei `~/.hermes/agent-screen.json`, derselbe Parser.

**Nicht in diesem Auftrag:** Live-Reload, UI-Settings-Pane, First-Party-PR,
Display-Name oder JPEG-Cadence umbauen (die bleiben, nur erweitern).

## Warum

`kNativeWidth` / `kNativeHeight` (3360×2100) und die Mode-Liste in
`native/agent-screen-app.swift` sind Compile-Zeit-Konstanten. War-Room-Lücke
nach Eich-01: Auflösung/Modi sollen aus derselben Config kommen, ohne
neu zu kompilieren. Das ist die **zweite ähnliche Karte** — Lernen, nicht
Modell-Benchmark.

## Wahrheit

Diese Datei. `docs/WAR_ROOM.md` und `AGENTS.md` im Repo sind Pflichtlektüre
vor der ersten Zeile Code. Dein MEMORY: Lektion zu `plugin_api.py` standalone
lesen, **bevor** du `config.py` anfasst.

## Schema-Erweiterung (nur diese neuen Keys)

```json
{
  "displayName": "Agent Screen Display",
  "jpegEveryNthFrame": 20,
  "nativeWidth": 3360,
  "nativeHeight": 2100,
  "modes": [
    [3360, 2100],
    [3840, 2160],
    [2560, 1440],
    [1920, 1080],
    [1600, 900],
    [1280, 720]
  ]
}
```

Erlaubte Auflösungen (Whitelist, sonst Default):

| width | height |
|------:|-------:|
| 3360  | 2100   |
| 3840  | 2160   |
| 2560  | 1440   |
| 1920  | 1080   |
| 1600  | 900    |
| 1280  | 720    |

Regeln:

- `nativeWidth`/`nativeHeight` nur **gemeinsam** gültig: beide Integer (kein
  Bool, kein Float), Paar steht in der Whitelist. Sonst Default `3360×2100`.
- `modes`: Array von `[width, height]`-Paaren. Jedes Paar muss in der
  Whitelist stehen. Leere Liste, kein Array, oder kein gültiges Paar →
  Default-Liste (die sechs Zeilen oben, in dieser Reihenfolge).
- Unbekannte Keys weiterhin ignorieren.
- Fehlende Datei / ungültiges JSON / I/O-Fehler → **alle** Defaults
  (Name, JPEG, Native, Modes), kein Crash.
- Float-Parität (Lektion aus Review Eich-01): `3360.0` ist **kein** Integer
  → Default. Python und Swift müssen dasselbe tun.

## DoD (fertig nur wenn ALLES gilt)

1. Feature-Branch `feat/eich-02-display-modes` existiert, nicht `main`.
2. Parser in `dashboard/config.py` erweitert (reine Funktionen + `load`).
   `plugin_api.py` bleibt standalone — **kein** `from . import config`.
   Deine MEMORY-Lektion (`importlib.util.spec_from_file_location`) gilt.
3. `GET /api/plugins/agent-screen/status` enthält die effektiven Werte
   `nativeWidth`, `nativeHeight`, `modes` (Liste von `[w, h]`) aus demselben
   Parser — auch wenn die App nicht läuft.
4. Swift-Spiegel in `native/agent-screen-app.swift`:
   `RuntimeConfig` liest die neuen Keys mit **denselben Regeln**.
   Kommentar am Loader verweist weiter auf `dashboard/config.py`.
   `kNativeWidth` / `kNativeHeight` werden durch `runtimeConfig` ersetzt
   (Stream-Output, Aspect-Ratio, Frame-Skalierung). Mode-Liste kommt aus
   Config; Refresh bleibt 60. `descriptor.maxPixelsWide/High` bleiben 5120/2160.
5. Tests in `tests/test_config.py` + `tests/test_plugin_api.py`:
   - fehlende Datei → Defaults inkl. 3360×2100 + Default-Modi
   - ungültiges Paar (z. B. 1000×1000, nur width, Float 3360.0) → Default
   - gültige Datei `1920×1080` + Teilmenge der Modi → exakte Werte im `/status`
   - bestehende Eich-01-Tests bleiben grün
   - Process-Control bleibt `pgrep -x` / `pkill -x`
6. `PYTHONPATH= ~/.hermes/hermes-agent/venv/bin/python -m pytest -q` ist grün.
   System-Python hat kein pytest — dieses Binary.
7. Native: `./native/build-app.sh` — **nur** Zertifikat `Agent Screen Dev`.
   Ad-hoc-Signatur = Auftrag fehlgeschlagen.
8. `native/agent-screen.json.example` um die neuen Keys ergänzen.
9. `docs/WAR_ROOM.md`: Task „Auflösung/Modi“ als erledigt ins „Aktueller Stand“,
   Datei unter 150 Zeilen. Kein Session-Protokoll.
10. Commit `-s` + Trailer `Co-authored-by: Coder <coder@hermes.agent>`.
    Push mit x-access-token-URL, nicht Bearer-Header. **Nicht mergen.**
11. Eine verifizierte Lektion ins eigene MEMORY.md (nicht raten). On-disk
    lesen nach dem Write — `replace` frisst Nachbarzeilen.

## Explizit verboten

- `pkill -f` / `pgrep -f`
- Ad-hoc `codesign`
- Bundle-ID oder Zertifikat ändern
- `from . import config` in `plugin_api.py`
- Relativimport „schnell nochmal versuchen“
- Direkt auf `main` committen
- Produktcode außerhalb dieses Repos
- Mit Nimar reden
- Live-Reload, UI-Pane, Display-Name/JPEG-Regeln ändern
- Weitermachen wenn ein Punkt oben unklar ist → stoppen und an Era eskalieren

## Kommandos (verbindlich)

```
cd ~/Workspace/projects/10-hermes-agent-screen
git checkout main
git checkout -b feat/eich-02-display-modes
PYTHONPATH= ~/.hermes/hermes-agent/venv/bin/python -m pytest -q
# nach Swift-Änderung:
./native/build-app.sh
```

Push (Token nicht echoen):

```
TOKEN=$(grep '^GITHUB_TOKEN=' ~/.hermes/.env | head -1 | cut -d= -f2-)
git push "https://x-access-token:${TOKEN}@github.com/Jind0la/hermes-agent-screen.git" feat/eich-02-display-modes
```

## Fertig-Meldung an Era (Pflicht)

EIN Call, sonst gilt der Auftrag als nicht gemeldet. Karten-Kommentar allein zählt nicht.

```
hermes -p default chat -c "Agent Inbox" --cli -Q --yolo --max-turns 3 \
  -q "[Message from agent 'coder'] DONE: <Karte-ID>. feat/eich-02-display-modes <SHA>. pytest: <echt, Zeile mit N passed>. build-app.sh: <gelaufen ja/nein, Authority>. Lektion: <ein Satz>."
```

Kein „sollte funktionieren“.
