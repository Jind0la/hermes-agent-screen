# Agent Screen

> **A fork of [DeskPad](https://github.com/Stengo/DeskPad)** by
> [Bastian Andelefski](https://github.com/Stengo) (MIT, 2022).
> The virtual display, window chrome, click-to-warp, and titlebar
> highlight are DeskPad. This repo adds a loopback MJPEG preview, a
> drag-portal, and a Hermes chip/pane. See [`NOTICE`](./NOTICE) and
> [`LICENSE.deskpad`](./LICENSE.deskpad).
> `CGVirtualDisplayPrivate.h` originates from Khaos Tian's VirtualDisplayExp
> (2021).

A virtual display for macOS — the missing Xvfb equivalent — shipped as a
**standalone Hermes plugin**. It does **not** live in the hermes-agent
tree. Private `CGVirtualDisplay` SPI is a maintenance risk Nous should
not have to own; install this into `~/.hermes/` instead.

**Experimental.** Apple can break the private display API on any macOS
update. macOS 14+, Apple Silicon or Intel.

## What you get

- A real second display with its own Space (drag windows onto it, or
  drop a window onto the Agent Screen window to teleport it)
- A Hermes statusbar chip + snappable pane with a live preview
- Click the native window to warp the cursor onto the virtual display

**Local macOS Hermes backend only.** Start/stop hit the connected
gateway; the preview always reads `http://127.0.0.1:8788` on this Mac.

## Install

```bash
git clone https://github.com/Jind0la/hermes-agent-screen.git
cd hermes-agent-screen
./install.sh
cd native && ./build-app.sh
```

Then:

1. Create a codesigning certificate named **Agent Screen Dev**
   (Keychain Access → Certificate Assistant → Code Signing). Never
   ad-hoc — Screen Recording TCC is bound to the signing identity.
2. Grant **Screen Recording** (and **Accessibility** for the drag
   portal) in System Settings ▸ Privacy & Security.
3. Enable the plugin: add `agent-screen` to `plugins.enabled` in
   `~/.hermes/config.yaml` (YAML list, not a string).
4. Enable **Agent Screen** in Hermes Desktop ▸ Settings ▸ Plugins.
5. **Quit Hermes Desktop fully (Cmd+Q)** and reopen — a running
   `serve` process caches the plugin list at startup. ⌘K → Reload
   desktop plugins is not enough for the Python backend.

Start without the chip: `~/.hermes/plugins/agent-screen/native/agent-screen.sh`

## Layout

```
dashboard/     FastAPI router → /api/plugins/agent-screen/
desktop/       runtime plugin.js (chip + pane)
native/        Swift companion + build-app.sh
skill/         SKILL.md for computer-use on the virtual display
tests/         contract tests for the router
```

`install.sh` copies those into `$HERMES_HOME` (default `~/.hermes`):

- `plugins/agent-screen/`
- `desktop-plugins/agent-screen/plugin.js`
- `skills/agent-screen/SKILL.md`

The built `.app` lands in `~/.hermes/agent-screen/`.

## Threat model

- `/start` and `/stop` sit behind the dashboard session-token middleware.
- The MJPEG server binds **loopback only** and has **no auth**. Any local
  process can watch the virtual display. Documented trade-off for a
  cheap `<img src>` preview.
- Process control uses `pgrep -x` / `pkill -x agent-screen-app`.

## Why not hermes-agent?

AGENTS.md: capability that is niche, macOS-only, or someone else's
project belongs in `~/.hermes/plugins/`, not the first-party tree.
This is a DeskPad fork on private SPI. If Nous later wants it
first-party, vendor from here — the same path hermes-achievements took.

A companion PR against hermes-agent exists only as a pointer:
https://github.com/NousResearch/hermes-agent/pull/85518

## Attribution

Fork of [DeskPad](https://github.com/Stengo/DeskPad) by Bastian
Andelefski, MIT (c) 2022. Header from Khaos Tian, VirtualDisplayExp
(2021). Hermes-side glue is MIT, see `LICENSE`.
