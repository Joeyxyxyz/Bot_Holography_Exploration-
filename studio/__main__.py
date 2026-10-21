"""python -m studio [--port 8765] [--no-browser]   (run from the repository root; see studio/__init__.py)"""
from __future__ import annotations

import argparse
import sys
import threading
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # repo root, also for tools.numgrid

from studio.engine import Studio  # noqa: E402
from studio.server import StudioServer, stop_file_hint  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m studio", description="Holo Studio: play the volumetric scenes.")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true", help="do not open the page in a browser")
    a = ap.parse_args(argv)
    studio = Studio()
    try:
        server = StudioServer(studio, a.port)
    except OSError as e:
        raise SystemExit(f"Port {a.port} is in use ({e}). Is the studio already running? Open "
                         f"http://127.0.0.1:{a.port}/ or start with --port <another>.") from None
    threading.Thread(target=server.serve_forever, name="studio-http", daemon=True).start()
    mode = "LIVE: Play drives the projector" if studio.hardware else "PREVIEW ONLY (DLP_NO_HARDWARE is set)"
    print(f"\nHolo Studio  {server.url}  [{mode}]\n"
          f"Stop anything playing: the STOP button, Esc on the page, Ctrl+C here, or create {stop_file_hint()}\n",
          flush=True)
    if not a.no_browser:
        webbrowser.open(server.url)
    try:
        studio.run_forever()                     # rig jobs on the main thread: Ctrl+C reaches the player
    except KeyboardInterrupt:
        print("\n[studio] Ctrl+C: stopped; the DMD is blank and the rig lock is released.", flush=True)
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
