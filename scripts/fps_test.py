#!/usr/bin/env python3
"""fps_test.py — misst die echte Framerate des Agent-Screen-MJPEG-Streams.

Liest N Sekunden vom Stream auf 127.0.0.1:8788/stream.mjpeg, zählt JPEG-Frames
(SOI-Marker) und meldet fps + Durchsatz. Dient als Baseline/Verifikation für
Stream-Optimierungen (z.B. Refresh-Timer).

Usage:  python3 scripts/fps_test.py [sekunden]
Exit:   0 = ok (Stream liefert Frames), 2 = Stream nicht erreichbar/leer.
"""
import sys
import time
import urllib.request

URL = "http://127.0.0.1:8788/stream.mjpeg"
DURATION = float(sys.argv[1]) if len(sys.argv) > 1 else 12.0
TARGET_FPS = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0


def main() -> int:
    start = time.time()
    count = 0
    bytes_total = 0
    buf = b""
    samples: list[int] = []
    last_count = 0
    last_t = start
    try:
        with urllib.request.urlopen(URL, timeout=DURATION + 5) as r:
            while time.time() - start < DURATION:
                chunk = r.read(65536)
                if not chunk:
                    break
                bytes_total += len(chunk)
                buf += chunk
                idx = 0
                while True:
                    i = buf.find(b"\xff\xd8", idx)
                    if i == -1:
                        buf = buf[idx:]
                        break
                    count += 1
                    idx = i + 2
                now = time.time()
                if now - last_t >= 1.0:
                    samples.append(count - last_count)
                    last_count = count
                    last_t = now
    except Exception as exc:  # noqa: BLE001
        print(f"FEHLER: {exc}")
        return 2

    elapsed = time.time() - start
    fps = count / elapsed if elapsed > 0 else 0.0
    print(f"Frames gesamt: {count} in {elapsed:.1f}s")
    print(f"Durchschnitt: {fps:.2f} fps")
    print(f"Pro Sekunde: {samples}")
    print(f"Durchsatz: {bytes_total / elapsed / 1024:.0f} KB/s")
    if count == 0:
        return 2
    if TARGET_FPS > 0:
        ok = fps >= TARGET_FPS
        print(f"Ziel {TARGET_FPS:.1f} fps: {'ERREICHT' if ok else 'VERFEHLT'}")
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
