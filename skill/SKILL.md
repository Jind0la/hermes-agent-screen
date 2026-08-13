---
name: agent-screen
description: Drive a macOS virtual display for computer-use.
version: 1.1.0
author: Jind0la (Jind0la), Hermes Agent
license: MIT
platforms: [macos]
metadata:
  hermes:
    tags: [macos, display, computer-use, deskpad]
    related_skills: []
---

# Agent Screen

Standalone Hermes plugin: a real second macOS display (DeskPad fork)
plus a loopback MJPEG preview. Not part of hermes-agent. Private
`CGVirtualDisplay` SPI — experimental.

## When to Use

- The user is on the main display and you need to click/type in a native
  app without stealing their Space.
- `computer_use` returns `off_space_or_ax_unresolved` for a window that
  should be on the Agent Screen.
- The user asks to start, stop, or move a window onto Agent Screen.

Don't use for: Linux (Xvfb), Windows, or a remote Hermes backend.

## Prerequisites

- Plugin installed via `./install.sh` from
  https://github.com/Jind0la/hermes-agent-screen
- Native app built: `$HERMES_HOME/plugins/agent-screen/native/build-app.sh`
- Codesign identity `Agent Screen Dev` (never ad-hoc)
- Screen Recording granted; Accessibility for the drag portal
- Local macOS Hermes backend

## How to Run

```
terminal(command="~/.hermes/plugins/agent-screen/native/agent-screen.sh")
```

Health: `curl -s --max-time 1 http://127.0.0.1:8788/ping` → `ok`.

Stop: `pkill -x agent-screen-app` (never `pkill -f`).

## Procedure

1. Start the app if `/ping` is not `ok`. Wait until ping returns `ok`.
2. The display name is `Agent Screen Display` (3360×2100).
3. Move a window onto it with System Events, then drive it with
   `computer_use` (`action="capture"`, then click by element).
4. Do not raise the user's windows. Do not click TCC / password prompts.

## Pitfalls

- ScreenCaptureKit delivers no frames from virtual displays. The app
  uses `CGDisplayStream`.
- After `pkill -x`, wait ~3s before start — the virtual display lags.
- `pgrep -f agent-screen-app` matches editors. Always `-x`.
- A running `serve` process caches plugins at boot. New backend =
  Cmd+Q, not ⌘K reload.
- Preview binds loopback with no auth. Local processes can watch.

## Verification

- `pgrep -x agent-screen-app` is running
- `curl http://127.0.0.1:8788/ping` prints `ok`
- `computer_use` capture of a window on that display returns elements
