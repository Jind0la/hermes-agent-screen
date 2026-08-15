# Plan: Eich-01 — Agent Screen Runtime-Config (Name + FPS)

**Repo:** `~/Workspace/projects/10-hermes-agent-screen`  
**Branch:** `feat/eich-01-display-config` (nie `main`)  
**Auftraggeber:** Era. **Bauer:** Coder.  
**Nicht in diesem Auftrag:** Auflösung/Modi der Virtual Display ändern, Live-Reload, UI-Settings-Pane, First-Party-PR.

## Warum

`kDisplayName` und `kJpegEveryNthFrame` sind Compile-Zeit-Konstanten
(`native/agent-screen-app.swift`). War-Room-Lücke: Name + FPS sollen
konfigurierbar sein, ohne neu zu kompilieren. Das ist der erste echte
Auftrag an dich — nicht ein Spielticket.

## Wahrheit

Diese Datei. `docs/WAR_ROOM.md` und `AGENTS.md` im Repo sind Pflichtlektüre
vor der ersten Zeile Code.

## DoD (fertig nur wenn ALLES gilt)

1. Feature-Branch `feat/eich-01-display-config` existiert, nicht `main`.
2. Neue Datei `~/.hermes/agent-screen.json` wird **beim App-Start** gelesen.
   Fehlt die Datei oder ist sie ungültig → **Defaults**, kein Crash.
3. Schema (nur diese Keys, Rest ignorieren):

```json
{
  "displayName": "Agent Screen Display",
  "jpegEveryNthFrame": 20
}
```

   - `displayName`: String, nach Trim nicht leer, ≤ 40 Zeichen. Sonst Default
     `"Agent Screen Display"`.
   - `jpegEveryNthFrame`: Integer, Clamp auf `1…60`. Default `20` (~3 fps
     bei 60 Hz, wie der heutige Kommentar).
4. `GET /api/plugins/agent-screen/status` enthält die **effektiven** Werte
   (`displayName`, `jpegEveryNthFrame`) aus demselben Parser — auch wenn die
   App nicht läuft. So ist das testbar ohne Virtual Display.
5. Parser liegt in `dashboard/config.py` (reine Funktion, keine I/O außer
   ein `load(path)` das Defaults bei Fehler liefert). `plugin_api.py`
   benutzt ihn. Swift implementiert **dieselben Regeln** (im Kommentar am
   Swift-Loader auf `dashboard/config.py` verweisen).
6. Tests in `tests/test_plugin_api.py` (oder `tests/test_config.py`):
   - fehlende Datei → Defaults
   - leerer/zu langer Name → Default-Name
   - `jpegEveryNthFrame` 0 und 99 → 1 bzw. 60
   - gültige Datei → exakte Werte im `/status`
   - Process-Control bleibt `pgrep -x` / `pkill -x` (bestehende Tests grün)
7. `PYTHONPATH= python3 -m pytest -q` im Repo ist grün.
8. Native: `native/build-app.sh` — **nur** Zertifikat `Agent Screen Dev`.
   Ad-hoc-Signatur = Auftrag fehlgeschlagen, auch wenn alles sonst läuft.
9. `docs/WAR_ROOM.md`: Task als erledigt ins „Aktueller Stand“, nicht als
   Session-Protokoll. Datei unter 150 Zeilen.
10. Commit `-s` + Trailer `Co-authored-by: Coder <coder@hermes.agent>`.
    Push mit x-access-token-URL, nicht Bearer-Header. **Nicht mergen.**
11. Eine verifizierte Lektion ins eigene MEMORY.md (nicht raten).

## Explizit verboten

- `pkill -f` / `pgrep -f`
- Ad-hoc `codesign`
- Bundle-ID oder Zertifikat ändern
- Auflösung `3360×2100` / Mode-Liste anfassen
- Direkt auf `main` committen
- Produktcode außerhalb dieses Repos
- Mit Nimar reden
- Weitermachen wenn ein Punkt oben unklar ist → stoppen und an Era eskalieren

## Kommandos (verbindlich)

```
cd ~/Workspace/projects/10-hermes-agent-screen
git checkout -b feat/eich-01-display-config
PYTHONPATH= python3 -m pytest -q
# nach Swift-Änderung:
./native/build-app.sh
```

## Fertig-Meldung an Era

Inbox: Branch-Name, Commit-SHA, pytest-Ausgabe (echt), ob `build-app.sh`
gelaufen ist, Pfad der Config-Beispieldatei (wenn du eine ins Repo legst:
`native/agent-screen.json.example`), eine Zeile Lektion.
Kein „sollte funktionieren“.
