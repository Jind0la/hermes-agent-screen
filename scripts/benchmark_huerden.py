#!/usr/bin/env python3
"""benchmark_huerden.py — Hürden-Benchmark der Klick-Pipeline auf Testseiten.

Deckt die Fälle ab, die einfache Seiten (One-Pager) nicht testen:
  - natives <select>-Dropdown  -> JS-Wert + change-Event (DOM-Klicks sind bei
    OS-Menüs wirkungslos; Keyboard-Fokus-Weg als Alternative dokumentiert)
  - kleine Checkbox-Ziele      -> Hit-Test mit RE-CHECK nach scrollIntoView
    (Retry ohne neuen Hit-Test klickt daneben — Befund 17.08.)
  - Slider-Drag, HTML5-Drag&Drop, KeyPress (Enter)
  - todomvc: Tippen (insertText) + Enter + Toggle + Filter

Pure CDP gegen den Agent-Browser (Port 9224). Wiederholbar:
    python3 scripts/benchmark_huerden.py

Exit: 0 = alle Fälle grün, 1 = mindestens ein Fall fehlgeschlagen.
"""
import asyncio
import json
import sys
import time
import urllib.request

import websockets

from benchmark_klicktour import CDP  # gleiche CDP-Klasse (scripts/ im sys.path)

CDP_HTTP = "http://127.0.0.1:9224/json"
THE_INTERNET = "https://the-internet.herokuapp.com"
TODOMVC = "https://demo.playwright.dev/todomvc/"


def find_tab():
    with urllib.request.urlopen(CDP_HTTP, timeout=5) as r:
        targets = json.load(r)
    for t in targets:
        if t.get("type") == "page" and t.get("url") and "about:blank" not in t.get("url", ""):
            return t
    return None


async def click_selector_fixed(cdp, sel):
    """Trusted CDP-Klick mit Hit-Test; der Retry nach scrollIntoView führt den
    Hit-Test NEU aus (Re-Check-Pflicht) und klickt sonst nicht."""
    async def probe():
        return await cdp.eval(f"""
        (() => {{
          const el = document.querySelector({json.dumps(sel)});
          if (!el) return null;
          const r = el.getBoundingClientRect();
          if (r.width === 0 || r.height === 0) return null;
          const x = Math.round(r.x + r.width/2), y = Math.round(r.y + r.height/2);
          const hit = document.elementFromPoint(x, y);
          return {{x, y, ok: hit === el || el.contains(hit)}};
        }})()
        """)

    pos = await probe()
    if not pos:
        return False, "element fehlt"
    if not pos["ok"]:
        await cdp.eval(f"document.querySelector({json.dumps(sel)}).scrollIntoView({{block:'center'}})")
        await asyncio.sleep(0.6)
        pos = await probe()  # Re-Check: Hit-Test nach dem Scroll ERNEUT
        if not pos or not pos["ok"]:
            return False, "verdeckt auch nach scroll"
    for evt in ("mouseMoved", "mousePressed", "mouseReleased"):
        await cdp.cmd("Input.dispatchMouseEvent", {
            "type": evt, "x": pos["x"], "y": pos["y"], "button": "left", "clickCount": 1,
        })
    return True, ""


async def navigate(cdp, url, settle=1.2):
    await cdp.cmd("Page.navigate", {"url": url})
    await asyncio.sleep(settle)


async def run_case(cdp, name, fn):
    t = time.perf_counter()
    ok, detail = await fn()
    ms = round((time.perf_counter() - t) * 1000)
    status = "OK" if ok else "FAIL"
    print(f"{status:4s} {name:22s} {ms:6d} ms  {detail}")
    return ok


async def main():
    tab = find_tab()
    if not tab:
        print("FEHLER: kein Page-Tab im Agent-Browser (Port 9224?)")
        return 1
    cdp = CDP(tab["webSocketDebuggerUrl"])
    await cdp.connect()
    await cdp.cmd("Page.enable")
    results = []

    # --- the-internet: Dropdown (natives <select>) ---
    await navigate(cdp, THE_INTERNET + "/dropdown")
    async def case_dropdown():
        await cdp.eval(
            "document.querySelector('#dropdown').value = '2';"
            "document.querySelector('#dropdown').dispatchEvent(new Event('change', {bubbles: true}));"
            "document.querySelector('#dropdown').value"
        )
        val = await cdp.eval("document.querySelector('#dropdown').value")
        return val == "2", f"value={val} (JS-Weg; DOM-Klick wirkungslos bei OS-Menü)"
    results.append(await run_case(cdp, "dropdown (JS-Weg)", case_dropdown))

    # --- the-internet: Checkbox (kleines Ziel, Re-Check-Hit-Test) ---
    await navigate(cdp, THE_INTERNET + "/checkboxes")
    async def case_checkbox():
        pre = await cdp.eval("document.querySelectorAll('input[type=checkbox]')[0].checked")
        ok, err = await click_selector_fixed(cdp, 'input[type=checkbox]:nth-of-type(1)')
        if not ok:
            return False, err
        await asyncio.sleep(0.3)
        post = await cdp.eval("document.querySelectorAll('input[type=checkbox]')[0].checked")
        # Inversions-Check: der Klick MUSS den Zustand kippen (unabhängig vom
        # Ausgangszustand — Checkbox 1 startet unchecked, 2 checked).
        return pre != post, f"pre={pre} post={post}"
    results.append(await run_case(cdp, "checkbox (Re-Check)", case_checkbox))

    # --- the-internet: Slider per Drag ---
    await navigate(cdp, THE_INTERNET + "/horizontal_slider")
    async def case_slider():
        pos = await cdp.eval("""
        (() => { const r = document.querySelector('input[type=range]').getBoundingClientRect();
                 return {x: Math.round(r.x + r.width*0.3), y: Math.round(r.y + r.height/2)}; })()
        """)
        await cdp.cmd("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": pos["x"], "y": pos["y"]})
        await cdp.cmd("Input.dispatchMouseEvent", {"type": "mousePressed", "x": pos["x"], "y": pos["y"], "button": "left", "clickCount": 1})
        await cdp.cmd("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": pos["x"] + 80, "y": pos["y"], "button": "left"})
        await cdp.cmd("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": pos["x"] + 80, "y": pos["y"], "button": "left", "clickCount": 1})
        await asyncio.sleep(0.3)
        val = await cdp.eval("document.querySelector('input[type=range]').value")
        return float(val) > 2.5, f"value={val}"
    results.append(await run_case(cdp, "slider (Drag)", case_slider))

    # --- the-internet: HTML5-Drag&Drop ---
    await navigate(cdp, THE_INTERNET + "/drag_and_drop")
    async def case_dragdrop():
        a = await cdp.eval("(() => { const r = document.querySelector('#column-a').getBoundingClientRect(); return {x: Math.round(r.x+r.width/2), y: Math.round(r.y+r.height/2)}; })()")
        b = await cdp.eval("(() => { const r = document.querySelector('#column-b').getBoundingClientRect(); return {x: Math.round(r.x+r.width/2), y: Math.round(r.y+r.height/2)}; })()")
        await cdp.cmd("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": a["x"], "y": a["y"]})
        await cdp.cmd("Input.dispatchMouseEvent", {"type": "mousePressed", "x": a["x"], "y": a["y"], "button": "left", "clickCount": 1})
        for step in range(1, 11):
            await cdp.cmd("Input.dispatchMouseEvent", {
                "type": "mouseMoved",
                "x": round(a["x"] + (b["x"] - a["x"]) * step / 10),
                "y": round(a["y"] + (b["y"] - a["y"]) * step / 10),
                "button": "left",
            })
        await cdp.cmd("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": b["x"], "y": b["y"], "button": "left", "clickCount": 1})
        await asyncio.sleep(0.3)
        head_a = await cdp.eval("document.querySelector('#column-a header').textContent")
        return head_a.strip() == "B", f"column-a={head_a.strip()}"
    results.append(await run_case(cdp, "drag&drop", case_dragdrop))

    # --- the-internet: KeyPress (Enter) ---
    await navigate(cdp, THE_INTERNET + "/key_presses")
    async def case_keypress():
        ok, _ = await click_selector_fixed(cdp, "#target")
        if not ok:
            return False, "target nicht klickbar"
        await asyncio.sleep(0.3)
        for evt in ("keyDown", "keyUp"):
            await cdp.cmd("Input.dispatchKeyEvent", {"type": evt, "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
        await asyncio.sleep(0.3)
        res = await cdp.eval("document.querySelector('#result').textContent")
        return "ENTER" in res, res
    results.append(await run_case(cdp, "keypress (Enter)", case_keypress))

    # --- todomvc: Tippen + Enter + Toggle + Filter ---
    await navigate(cdp, TODOMVC, settle=1.5)
    async def case_todomvc():
        # Zustand säubern: todomvc persistiert in localStorage — wiederholte
        # Läufe treffen sonst Alt-Items (Befund 17.08.: der Toggle-Klick
        # traf ein bereits completed-Item und machte es UNcompleted).
        await cdp.eval("localStorage.clear()")
        await cdp.cmd("Page.reload")
        await asyncio.sleep(1.5)
        await cdp.eval("document.querySelector('.new-todo').focus()")
        await cdp.cmd("Input.insertText", {"text": "Hürden-Test von Era"})
        for evt in ("keyDown", "keyUp"):
            await cdp.cmd("Input.dispatchKeyEvent", {"type": evt, "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
        await asyncio.sleep(0.8)
        items = await cdp.eval("Array.from(document.querySelectorAll('.todo-list li label')).map(l => l.textContent)")
        if "Hürden-Test von Era" not in (items or []):
            return False, f"item fehlt: {items}"
        pre = await cdp.eval("document.querySelectorAll('.todo-list li .toggle')[0].checked")
        ok, _ = await click_selector_fixed(cdp, ".todo-list li .toggle")
        if not ok:
            return False, "toggle nicht klickbar"
        await asyncio.sleep(0.5)
        post = await cdp.eval("document.querySelectorAll('.todo-list li .toggle')[0].checked")
        if pre == post:
            return False, f"toggle wirkungslos (pre={pre} post={post})"
        completed = await cdp.eval("document.querySelectorAll('.todo-list li.completed').length")
        await cdp.eval("document.querySelector('a[href=\\\"#/completed\\\"]').click()")
        await asyncio.sleep(0.3)
        shown = await cdp.eval("document.querySelectorAll('.todo-list li').length")
        return completed == 1 and shown == 1, f"completed={completed}, filter-zeigt={shown}"
    results.append(await run_case(cdp, "todomvc (Tipp+Toggle)", case_todomvc))

    await cdp.ws.close()
    ok_all = all(results)
    print(f"\nERGEBNIS: {'ALLE GRÜN' if ok_all else 'FEHLER BEI ' + str(sum(1 for r in results if not r)) + ' FÄLLEN'}")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
