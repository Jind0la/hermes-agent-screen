#!/usr/bin/env python3
"""benchmark_klicktour.py — CDP-Benchmark der Agent-Browser-Klick-Tour.

Misst die Latenz der realen Arbeits-Pipeline auf dem Agent-Screen:
Blog-Seite laden, 5 Artikel per trusted Mausklick (Input.dispatchMouseEvent)
öffnen, Modal-Inhalt lesen, per Close-Button schliessen. Pure CDP gegen den
Agent-Browser (Port 9224) — kein browser-use-Harness, dadurch wiederholbar.

Usage:
    /Users/nimar/.hermes/hermes-agent/venv/bin/python scripts/benchmark_klicktour.py [n_artikel]

Exit: 0 = ok, 1 = Benchmark fehlgeschlagen.
"""
import asyncio
import json
import sys
import time
import urllib.request

import websockets

CDP_HTTP = "http://127.0.0.1:9224/json"
SITE = "https://nimar.moradbakhti.de"
ARTIKEL = [
    "/blog/ki-fuer-kmu", "/blog/ki-gedaechtnis", "/blog/menschzentrierte-ki",
    "/blog/bildung-revolution", "/blog/ai-act",
]
N = int(sys.argv[1]) if len(sys.argv) > 1 else 5


def list_targets():
    with urllib.request.urlopen(CDP_HTTP, timeout=5) as r:
        return json.load(r)


def find_tab():
    for t in list_targets():
        if t.get("type") == "page" and "moradbakhti" in t.get("url", ""):
            return t
    return None


class CDP:
    def __init__(self, ws_url):
        self.ws_url = ws_url
        self._id = 0
        self._pending = {}

    async def connect(self):
        self.ws = await websockets.connect(self.ws_url, max_size=50 * 1024 * 1024)
        asyncio.create_task(self._reader())

    async def _reader(self):
        async for msg in self.ws:
            data = json.loads(msg)
            mid = data.get("id")
            if mid in self._pending:
                self._pending.pop(mid).set_result(data)

    async def cmd(self, method, params=None):
        self._id += 1
        mid = self._id
        fut = asyncio.get_running_loop().create_future()
        self._pending[mid] = fut
        await self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        return await fut

    async def eval(self, expr):
        res = await self.cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True})
        return res.get("result", {}).get("result", {}).get("value")

    async def click_selector(self, sel):
        """Trusted CDP-Mausklick mit Hit-Test (elementFromPoint)."""
        pos = await self.eval(f"""
        (() => {{
          const el = document.querySelector({json.dumps(sel)});
          if (!el) return null;
          const r = el.getBoundingClientRect();
          if (r.width === 0 || r.height === 0) return null;
          const x = Math.round(r.x + r.width/2), y = Math.round(r.y + r.height/2);
          return {{x, y, ok: document.elementFromPoint(x, y) === el || el.contains(document.elementFromPoint(x, y))}};
        }})()
        """)
        if not pos:
            return False, "element fehlt"
        if not pos.get("ok"):
            await self.eval(f"document.querySelector({json.dumps(sel)}).scrollIntoView({{block:'center'}})")
            await asyncio.sleep(0.6)
            pos = await self.eval(f"""
            (() => {{
              const el = document.querySelector({json.dumps(sel)});
              if (!el) return null;
              const r = el.getBoundingClientRect();
              const x = Math.round(r.x + r.width/2), y = Math.round(r.y + r.height/2);
              return {{x, y, ok: true}};
            }})()
            """)
            if not pos:
                return False, "element nach scroll fehlt"
        for evt in ("mouseMoved", "mousePressed", "mouseReleased"):
            await self.cmd("Input.dispatchMouseEvent", {
                "type": evt, "x": pos["x"], "y": pos["y"], "button": "left", "clickCount": 1,
            })
        return True, ""


async def modal_sig(cdp):
    return await cdp.eval("""
    (() => {
      const c = Array.from(document.querySelectorAll('[role="dialog"], dialog, [class*="modal" i]'))
        .filter(el => el.getBoundingClientRect().width > 200);
      if (!c.length) return null;
      return (c[c.length-1].innerText || '').replace(/\\s+/g,' ').trim().slice(0, 60);
    })()
    """)


async def main():
    tab = find_tab()
    if not tab:
        print("FEHLER: Agent-Browser-Tab mit nimar.moradbakhti.de nicht gefunden")
        return 1
    cdp = CDP(tab["webSocketDebuggerUrl"])
    await cdp.connect()
    timings = {}
    t0 = time.perf_counter()

    # Phase 1: Blog-Seite laden
    t = time.perf_counter()
    await cdp.cmd("Page.enable")
    await cdp.cmd("Page.navigate", {"url": SITE + "/blog"})
    await asyncio.sleep(2.0)  # Ladezeit (Load-Event folgt asynchron)
    timings["blog_laden"] = round((time.perf_counter() - t) * 1000)

    # Phase 2: N Artikel öffnen, Modal lesen, schliessen
    per_artikel = []
    sigs = set()
    for i, slug in enumerate(ARTIKEL[:N]):
        t = time.perf_counter()
        ok, err = await cdp.click_selector(f'a[href="{slug}"]')
        if not ok:
            per_artikel.append({"slug": slug, "status": f"klick-fehler: {err}"})
            continue
        await asyncio.sleep(0.8)
        sig = await modal_sig(cdp)
        if not sig:
            per_artikel.append({"slug": slug, "status": "kein modal"})
            continue
        sigs.add(sig)
        ok2, _ = await cdp.click_selector('button[aria-label="Schließen"]')
        if not ok2:
            per_artikel.append({"slug": slug, "status": "close-fehler"})
            continue
        await asyncio.sleep(0.5)
        per_artikel.append({"slug": slug, "status": "ok", "titel": sig})
        per_artikel[-1]["ms"] = round((time.perf_counter() - t) * 1000)

    timings["gesamt"] = round((time.perf_counter() - t0) * 1000)
    timings["artikel"] = per_artikel
    dups = len(sigs) != len(per_artikel)
    timings["duplikate"] = dups

    print(json.dumps(timings, indent=2, ensure_ascii=False))
    await cdp.ws.close()
    return 0 if not dups and all(a.get("status") == "ok" for a in per_artikel) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
