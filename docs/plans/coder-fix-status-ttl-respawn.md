# Coder-Auftrag: Status-TTL + Respawn-Guard (Review-Funde #85518)

Quelle: AI-Review auf PR NousResearch/hermes-agent#85518 (16.08.2026, Punkte 3+4),
von Era geprüft — beide Stellen existieren 1:1 in diesem Repo
(`dashboard/plugin_api.py`).

## Kontext

Der Desktop-Chip pollt `/status` alle 5s (`refetchInterval: 5000`), Panes/Clients
multiplizieren den Churn. Jeder Status-Call spawnt `pgrep` + `curl`. Zusätzlich
kann `start()` bei einem hängenden Prozess eine zweite Instanz neben der ersten
laufen lassen (beide versuchen Port 8788, `allowLocalEndpointReuse`).

## Auftrag

**Branch:** `fix/status-ttl-respawn-guard` (von main; NIE direkt auf main committen)
**Repo:** dieses (`~/Workspace/projects/10-hermes-agent-screen`)
**AGENTS.md im Repo lesen** (Commit-Regeln: `-s` + Trailer
`Co-authored-by: Coder <coder@hermes.agent>`; Push via x-access-token-URL).

### Fix 1 — TTL-Cache für Status-Proben (`_state()` / `/status`)

- Konstante `_STATUS_TTL_S = 2.0`.
- Module-Level-Cache `_probe_cache: dict[str, tuple[float, bool]]`
  (Key → (Zeitstempel, Wert)).
- Helper `_probe_cached(key, fn, ttl=_STATUS_TTL_S) -> bool`: Cache-Hit nur
  wenn `time.time() - ts < ttl`, sonst `fn()` ausführen und eintragen.
- `_app_running()` und `_stream_ok()` werden zu cached Wrappern; die bisherige
  Logik wandert UNVERÄNDERT in `_app_running_uncached()` bzw.
  `_stream_ok_uncached()` (inkl. Docstrings und exakter
  `pgrep -x`/`pkill -x`-Listen — der Quelltext-Test bleibt gültig).
- `_invalidate_probes()`: leert den Cache.
- `_state()` ruft weiterhin `_app_running()`/`_stream_ok()` (cached).
- **In `start()`/`stop()`:**
  - Alle `_wait_until(...)`-Prädikate auf die `_uncached`-Varianten (sonst
    friert der Zustand während des Wartens ein).
  - Nach jeder Mutation (`_spawn()`, `pkill`) → `_invalidate_probes()`.
  - Direkt vor dem finalen `return _state()` → `_invalidate_probes()`,
    damit die Antwort frische Werte enthält.

### Fix 2 — Respawn-Guard in `start()` (nie zwei Prozesse)

- Helper `_kill()`: `subprocess.run(["pkill", "-x", PROC_NAME], ...)`
  (capture_output, timeout=5) + `_wait_until(lambda: not _app_running_uncached())`.
- `stop()` nutzt `_kill()` (Logik bleibt gleich: pkill → warten → grace).
- `start()` neu:

  1. `_require_macos()`; `_launcher_ok()`-Check (unverändert).
  2. Healthy (`_app_running()` and `_stream_ok()`) → `return _state()`.
  3. `if _app_running():` warte max 6s auf natürlichen Tod
     (`_wait_until(lambda: not _app_running_uncached())`).
     Läuft die App danach IMMER NOCH → `_kill()` (hängende Instanz darf den
     Respawn nicht blockieren). Danach `_invalidate_probes()` +
     `time.sleep(_DISPLAY_GRACE_S)`.
  4. `if not _app_running_uncached(): _spawn(); _invalidate_probes()`
  5. `if not _wait_until(_stream_ok_uncached, timeout=6.0):`
     → grace-Sleep; läuft die App noch (kaputte Instanz, Stream nie hoch)
     → `_kill()` + grace-Sleep; dann `_spawn()`;
     `_wait_until(_stream_ok_uncached, timeout=6.0)`.
  6. `_invalidate_probes()`; `return _state()`.

### Tests (`tests/test_plugin_api.py`)

1. **TTL:** `_app_running_uncached`/`_stream_ok_uncached` mit Zählern
   monkeypatchen, zweimal `/status` → Zähler je 1; nach `_invalidate_probes()`
   erneut `/status` → Zähler je 2.
2. **Respawn-Guard:** App „hängt“: `_app_running_uncached`-Sequenz
   [True, True, False] (stirbt nicht von selbst), `_stream_ok_uncached`
   [False, True], `_kill` und `_spawn` als Aufzeichner. Assert: `_kill`
   genau 1× gerufen, `_spawn` genau 1×, Antwort `stream` True.
3. Bestehende Tests bleiben unverändert grün (die monkeypatchten Namen
   `_app_running`/`_stream_ok` existieren weiter als cached Wrapper).

## DoD

- [ ] `pytest tests/` komplett grün (bestehende + neue Tests)
- [ ] Branch `fix/status-ttl-respawn-guard` auf origin gepusht
      (x-access-token-URL)
- [ ] **KEIN Merge** — Merge macht Era nach Review
- [ ] Diese Plan-Datei im Feature-Branch mitcommittet
- [ ] `docs/WAR_ROOM.md`: unter „Laufende Tasks“ eine Zeile
      `- [ ] Review-Fixes #85518 (Status-TTL + Respawn-Guard) — Branch ...` ergänzen
- [ ] Meldung an Era (Pflicht):
      `hermes -p default chat -c "Agent Inbox" -q "[Message from agent 'coder'] Fix-Ergebnis: Commit-Hash, pytest-Zeile, Branch-Name, offene Punkte"`

Bei Blockade: stoppen und melden, nicht weiterwursteln.
