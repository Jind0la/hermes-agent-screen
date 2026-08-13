/**
 * Agent Screen — statusbar chip + snappable pane.
 * Runtime plugin ($HERMES_HOME/desktop-plugins/agent-screen/plugin.js).
 * Imports: @hermes/plugin-sdk + react only.
 *
 * Local macOS backend only. Preview always hits 127.0.0.1:8788 on this Mac.
 * Fork of DeskPad (Bastian Andelefski / Stengo, MIT 2022) — see NOTICE.
 */
import {
  cn,
  icons,
  PANES_AREA,
  Popover,
  PopoverContent,
  PopoverTrigger,
  StatusDot,
  useMutation,
  useQuery,
  useQueryClient
} from '@hermes/plugin-sdk'
import { jsx, jsxs } from 'react/jsx-runtime'
import { useRef, useState } from 'react'

const ID = 'agent-screen'
const STREAM_URL = 'http://127.0.0.1:8788/stream.mjpeg'
const PING_URL = 'http://127.0.0.1:8788/ping'
const GREEN = '#16A34A'
const GRAY = 'var(--ui-text-tertiary)'

let rest = null

async function pingLocalStream() {
  try {
    const r = await fetch(PING_URL, { signal: AbortSignal.timeout(800) })
    return r.ok && (await r.text()).trim() === 'ok'
  } catch {
    return false
  }
}

function useAgentStatus() {
  return useQuery({
    queryKey: [ID, 'status'],
    queryFn: async () => {
      if (!rest) throw new Error('agent-screen api not ready')
      const s = await rest('/status')
      const localStream = await pingLocalStream()
      return { ...s, localStream }
    },
    refetchInterval: 5000,
    staleTime: 2000
  })
}

function useToggle() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      if (!rest) throw new Error('agent-screen api not ready')
      const s = await rest('/status')
      if (s && s.supported === false) {
        throw new Error(s.error || 'Agent Screen requires a local macOS backend')
      }
      return rest(s && s.running ? '/stop' : '/start', { method: 'POST' })
    },
    onSettled: () => qc.invalidateQueries({ queryKey: [ID, 'status'] })
  })
}

function AgentScreenChip() {
  const { data } = useAgentStatus()
  const toggle = useToggle()
  const [hover, setHover] = useState(false)
  const openTimer = useRef(null)
  const closeTimer = useRef(null)

  const supported = !data || data.supported !== false
  const running = !!(data && data.running)
  const preview = !!(data && data.localStream)

  const onMouseEnter = () => {
    clearTimeout(closeTimer.current)
    openTimer.current = setTimeout(() => setHover(true), 150)
  }
  const onMouseLeave = () => {
    clearTimeout(openTimer.current)
    closeTimer.current = setTimeout(() => setHover(false), 120)
  }

  return jsx(Popover, {
    open: hover && running && preview,
    onOpenChange: setHover,
    children: [
      jsx(PopoverTrigger, {
        asChild: true,
        children: jsx('button', {
          type: 'button',
          disabled: !supported,
          className: cn(
            'inline-flex h-full items-center gap-1 px-1.5 transition-colors',
            'text-(--ui-text-tertiary) hover:bg-(--chrome-action-hover) hover:text-foreground',
            !supported && 'opacity-50'
          ),
          onClick: (e) => {
            e.preventDefault()
            if (!supported || toggle.isPending) return
            toggle.mutate()
          },
          onMouseEnter,
          onMouseLeave,
          'aria-label': supported
            ? (running ? 'Agent Screen: on — click to stop' : 'Agent Screen: off — click to start')
            : 'Agent Screen requires a local macOS backend',
          children: jsx(icons.Monitor, {
            size: 14,
            style: { color: running && supported ? GREEN : GRAY, transition: 'color 200ms' }
          })
        })
      }),
      running && preview
        ? jsx(PopoverContent, {
            side: 'top',
            align: 'end',
            sideOffset: 6,
            className: 'w-auto p-1.5',
            children: jsx('img', {
              src: STREAM_URL,
              alt: 'Agent Screen (live)',
              style: {
                width: 320,
                aspectRatio: '16 / 9',
                objectFit: 'contain',
                borderRadius: 6,
                background: '#000'
              }
            })
          })
        : null
    ]
  })
}

function AgentScreenPane() {
  const { data } = useAgentStatus()
  const toggle = useToggle()
  const supported = !data || data.supported !== false
  const running = !!(data && data.running)
  const streaming = !!(data && data.localStream)

  return jsxs('div', {
    className: 'flex h-full flex-col gap-1.5 p-2 text-sm',
    children: [
      jsxs('div', {
        className: 'flex items-center gap-2 px-1',
        children: [
          jsx(StatusDot, { tone: streaming ? 'good' : 'muted' }),
          jsx('span', { className: 'font-medium', children: 'Agent Screen' }),
          jsx('span', {
            className: 'text-(--ui-text-tertiary)',
            children: !supported
              ? 'local macOS only'
              : streaming ? 'live · :8788' : running ? 'starting…' : 'off'
          }),
          jsx('button', {
            type: 'button',
            disabled: !supported || toggle.isPending,
            className: cn(
              'ml-auto inline-flex items-center gap-1 rounded px-2 py-0.5 text-[0.6875rem] transition-colors',
              'text-(--ui-text-secondary) hover:bg-(--chrome-action-hover) hover:text-foreground',
              !supported && 'opacity-50'
            ),
            onClick: () => { if (supported && !toggle.isPending) toggle.mutate() },
            children: running ? 'Stop' : 'Start'
          })
        ]
      }),
      streaming
        ? jsx('img', {
            src: STREAM_URL,
            alt: 'Agent Screen (live)',
            style: {
              width: '100%',
              flex: 1,
              minHeight: 0,
              objectFit: 'contain',
              borderRadius: 6,
              background: '#000'
            }
          })
        : jsx('div', {
            className: 'flex flex-1 items-center justify-center text-(--ui-text-tertiary)',
            children: !supported
              ? 'Agent Screen only runs on a local macOS Hermes backend.'
              : running
                ? 'Stream is not up yet…'
                : 'Agent Screen is off. Click Start — the native window opens.'
          })
    ]
  })
}

export default {
  id: ID,
  name: 'Agent Screen',
  description: 'Virtual macOS display (DeskPad fork) — local backend only.',
  defaultEnabled: false,
  register(ctx) {
    rest = ctx.rest
    if (typeof ctx.onDispose === 'function') {
      ctx.onDispose(() => { rest = null })
    }

    ctx.register({
      id: 'chip',
      area: 'statusBar.right',
      order: 120,
      render: () => jsx(AgentScreenChip, {})
    })

    ctx.register({
      id: 'pane',
      area: PANES_AREA,
      title: 'Agent Screen',
      data: {
        placement: 'right',
        dock: { pane: 'workspace', pos: 'right' },
        width: '360px'
      },
      render: () => jsx(AgentScreenPane, {})
    })
  }
}
