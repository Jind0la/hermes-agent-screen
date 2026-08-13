# Hermes Agent Screen — Projekt-Kontext

Standalone-Plugin-Repo: macOS-App „Agent Screen" (virtuelles Display für Hermes
Agenten) + MJPEG-Stream + Klick-Warp + Hermes-Plugin (Pane + Status-Chip).

## Agent-Zusammenarbeit (verbindlich)

- **Jede Session beginnt mit dem Lesen von `docs/WAR_ROOM.md`** und endet mit
  dessen Aktualisierung. Der War-Room ist der Einstiegspunkt, nicht der Chat.
- War-Room unter 150 Zeilen halten; bei Überschreitung verdichten.
- Commits mit `git commit -s` und Trailer `Co-authored-by: Era <era@hermes.agent>`
  (bzw. der jeweilige Agent).
- Git-Workflow: Feature-Branch → Push → Merge — NIE direkt auf main committen.
  Push nur mit `x-access-token`-URL (Bearer wird abgelehnt).
- **NIE ad-hoc signieren** — Zertifikat „Agent Screen Dev" verwenden, sonst
  verfällt der TCC-Grant.
- Install: `./install.sh` → `~/.hermes/plugins` + desktop-plugins + Skill.
