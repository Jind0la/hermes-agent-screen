#!/bin/bash
# install.sh — copy Agent Screen into $HERMES_HOME (default ~/.hermes).
# Does not build the native app and does not mutate config.yaml.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"

PLUGIN_DST="$HERMES_HOME/plugins/agent-screen"
DESKTOP_DST="$HERMES_HOME/desktop-plugins/agent-screen"
SKILL_DST="$HERMES_HOME/skills/agent-screen"

say() { printf '\033[1;36m[install]\033[0m %s\n' "$*"; }

mkdir -p "$PLUGIN_DST/dashboard" "$PLUGIN_DST/native/icon" "$DESKTOP_DST" "$SKILL_DST"

cp "$ROOT/dashboard/manifest.json" "$PLUGIN_DST/dashboard/"
cp "$ROOT/dashboard/plugin_api.py" "$PLUGIN_DST/dashboard/"
cp "$ROOT/NOTICE" "$ROOT/LICENSE.deskpad" "$ROOT/LICENSE" "$PLUGIN_DST/"
cp "$ROOT/native/agent-screen-app.swift" "$PLUGIN_DST/native/"
cp "$ROOT/native/CGVirtualDisplayPrivate.h" "$PLUGIN_DST/native/"
cp "$ROOT/native/build-app.sh" "$PLUGIN_DST/native/"
cp "$ROOT/native/agent-screen.sh" "$PLUGIN_DST/native/"
cp "$ROOT/native/.gitignore" "$PLUGIN_DST/native/"
cp "$ROOT/native/icon/agent-screen-icon-final.png" "$PLUGIN_DST/native/icon/"
chmod +x "$PLUGIN_DST/native/build-app.sh" "$PLUGIN_DST/native/agent-screen.sh"

cp "$ROOT/desktop/plugin.js" "$DESKTOP_DST/plugin.js"
cp "$ROOT/skill/SKILL.md" "$SKILL_DST/SKILL.md"

say "copied dashboard  → $PLUGIN_DST"
say "copied desktop    → $DESKTOP_DST"
say "copied skill      → $SKILL_DST"
echo
cat <<EOF
Next:

  1. Build the native app (needs the "Agent Screen Dev" codesign cert):
       $PLUGIN_DST/native/build-app.sh

  2. Add agent-screen to plugins.enabled in $HERMES_HOME/config.yaml
     as a YAML list item (not a quoted string).

  3. Enable "Agent Screen" in Hermes Desktop ▸ Settings ▸ Plugins.

  4. Quit Hermes Desktop fully (Cmd+Q) and reopen so serve rediscovers
     the Python backend. ⌘K → Reload desktop plugins is not enough.

  5. Grant Screen Recording (+ Accessibility for the drag portal).

Start by hand: $PLUGIN_DST/native/agent-screen.sh
EOF
