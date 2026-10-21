"""The studio's local web server (standard library only).

Security for a page that can drive a projector:
  * listens on 127.0.0.1 only, and refuses a second server on the same port (no SO_REUSEADDR sharing);
  * every request must carry Host 127.0.0.1:<port> or localhost:<port> (blocks DNS-rebinding pages);
  * every /api/ call needs the per-launch token the page carries in a <meta> tag (other pages cannot read it),
    sent as the X-Holo-Token header; writes must be JSON from our own origin (cross-site forms and simple
    requests are refused, CORS preflights get no allow headers);
  * the page may not be framed (no clickjacking of the Play button) and loads only its own scripts and styles.
"""
from __future__ import annotations

import hmac
import json
import secrets
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from rig import config
from vol2 import volplay

from . import catalog, clips, engine

STATIC = Path(__file__).resolve().parent / "static"
STATIC_FILES = {"/static/app.js": ("app.js", "text/javascript; charset=utf-8"),
                "/static/app.css": ("app.css", "text/css; charset=utf-8")}
MAX_BODY = 64 * 1024
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; "
       "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")


class StudioServer(ThreadingHTTPServer):
    allow_reuse_address = False        # a second studio must fail to bind, not share the port
    daemon_threads = True

    def __init__(self, studio: engine.Studio, port: int = 8765):
        self.studio = studio
        self.token = secrets.token_urlsafe(24)
        super().__init__(("127.0.0.1", port), Handler)
        self.port = self.server_address[1]
        self.hosts = {f"127.0.0.1:{self.port}", f"localhost:{self.port}"}
        self.origins = {f"http://{h}" for h in self.hosts}

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}/"


class Handler(BaseHTTPRequestHandler):
    server: StudioServer
    server_version = "HoloStudio"
    sys_version = ""
    timeout = 15                       # an idle or half-sent connection cannot hold a server thread forever

    def log_message(self, fmt, *args):           # quiet: the studio logs what matters itself
        pass

    # ---------------------------------------------------------------- responses
    def _send(self, status, body: bytes, ctype, extra=None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", CSP)
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status, obj):
        self._send(status, json.dumps(obj).encode("utf-8"), "application/json; charset=utf-8")

    def _error(self, status, message):
        self._json(status, {"error": message})

    # ---------------------------------------------------------------- checks
    def _host_ok(self):
        if self.headers.get("Host", "") not in self.server.hosts:
            self._error(403, "wrong Host")
            return False
        return True

    def _token_ok(self):
        sent = self.headers.get("X-Holo-Token", "").encode("utf-8", "surrogateescape")
        if not hmac.compare_digest(sent, self.server.token.encode("ascii")):
            self._error(403, "missing or wrong token: reload the studio page")
            return False
        return True

    def _body(self):
        """The JSON body of a write, or None after an error response."""
        origin = self.headers.get("Origin")
        if origin is not None and origin not in self.server.origins:
            self._error(403, "cross-origin request refused")
            return None
        if not self.headers.get("Content-Type", "").lower().startswith("application/json"):
            self._error(415, "send JSON")
            return None
        try:
            n = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            n = -1
        if not 0 <= n <= MAX_BODY:
            self._error(413, "request too large")
            return None
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except (ValueError, RecursionError):
            self._error(400, "invalid JSON")
            return None
        if not isinstance(body, dict):
            self._error(400, "send a JSON object")
            return None
        return body

    # ---------------------------------------------------------------- routes
    def do_GET(self):
        self._guard(self._get)

    def do_POST(self):
        self._guard(self._post)

    def _guard(self, fn):
        """Any unexpected error becomes a 500 for this request; the server and the rig job carry on."""
        try:
            fn()
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            try:
                self._error(500, f"internal error ({type(e).__name__})")
            except Exception:  # noqa: BLE001 - headers may already be out
                pass

    def _get(self):
        if not self._host_ok():
            return
        url = urlsplit(self.path)
        path = url.path
        if path in ("/", "/index.html"):
            html = (STATIC / "index.html").read_text(encoding="utf-8").replace("{{TOKEN}}", self.server.token)
            return self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
        if path in STATIC_FILES:
            name, ctype = STATIC_FILES[path]
            return self._send(200, (STATIC / name).read_bytes(), ctype)
        if path.startswith("/figures/"):
            scene = path[len("/figures/"):]
            gif = catalog.camera_gif(scene) if scene in volplay.SCENES else None
            if gif is None:
                return self._error(404, "no camera capture for that scene")
            return self._send(200, gif.read_bytes(), "image/gif")
        if path == "/favicon.ico":
            return self._send(204, b"", "image/x-icon")
        if not path.startswith("/api/"):
            return self._error(404, "not found")
        if not self._token_ok():
            return
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        studio = self.server.studio
        if path == "/api/catalog":
            return self._json(200, {**catalog.as_json(), "limits": clips.LIMITS, "defaults": clips.DEFAULTS,
                                    "hardware": studio.hardware, "grid_seconds": engine.GRID_SECONDS,
                                    "duty_curve": clips.duty_lut()[2], "max_playlist_s": engine.MAX_PLAYLIST_S,
                                    "max_playlist_items": engine.MAX_PLAYLIST_ITEMS})
        if path == "/api/state":
            return self._json(200, studio.snapshot())
        if path in ("/api/preview", "/api/simulate"):
            try:
                s = clips.Settings.from_dict({"scene": q.get("scene"), "mode": q.get("mode", "ab"),
                                              **{k: float(q[k]) for k in ("brightness", "size", "L") if k in q}})
            except ValueError as e:
                return self._error(400, str(e))
            j = studio.previews.request("pattern" if path == "/api/preview" else "simulated", s)
            if j["state"] == "done":
                return self._json(200, {"state": "done", **j["result"]})
            if j["state"] == "error":
                return self._json(500, {"state": "error", "error": j["error"]})
            return self._json(202, {"state": j["state"], "progress": j["progress"]})
        return self._error(404, "not found")

    def _post(self):
        if not self._host_ok() or not self._token_ok():
            return
        body = self._body()
        if body is None:
            return
        studio = self.server.studio
        routes = {"/api/play": studio.submit_play, "/api/playlist": studio.submit_playlist,
                  "/api/grid": studio.submit_grid, "/api/stop": studio.stop,
                  "/api/check-rig": lambda b: studio.check_rig()}
        fn = routes.get(urlsplit(self.path).path)
        if fn is None:
            return self._error(404, "not found")
        try:
            return self._json(200, fn(body))
        except engine.Refused as e:
            return self._error(e.status, str(e))

    def do_HEAD(self):
        self.do_GET()

    def _refuse(self):
        self._error(405, "method not allowed")

    do_PUT = do_DELETE = do_PATCH = do_OPTIONS = _refuse


def stop_file_hint() -> str:
    return str(config.STOP)
