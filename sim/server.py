"""The fish pond simulator's web server: a camera picture and the equipment's switches.

    python sim/server.py [--port 8800] [--fps 5] [--day-minutes 6] [--seed 1]

  http://127.0.0.1:8800/              the control room: the camera picture, the equipment and demo buttons
  http://127.0.0.1:8800/video.mjpg    the camera as an MJPEG stream (Inspector: Sources › Stream › HTTP)
  http://127.0.0.1:8800/snapshot.jpg  one picture
  POST /api/command                   {"command": "aerator_on" | "aerator_off" | "pump_on" | "pump_off" | "feed" | "scare"}
                                      - exactly what an Inspector HTTP output sends ({"device", "command", "value", ...})
  GET  /api/command?command=feed      the same, for a quick try in a browser
  GET  /api/state                     the model's own numbers (for checking only: Inspector must judge from the picture)

Only 127.0.0.1 is served unless --host says otherwise."""
import argparse
import io
import json
import os
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pond import Pond  # noqa: E402

PAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "page.html")


class Camera:
    """Steps the pond and keeps the newest JPEG."""

    def __init__(self, pond, fps):
        self.pond, self.fps = pond, fps
        self.jpeg = b""
        self.seq = 0
        self.cond = threading.Condition()
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while True:
            t0 = time.time()
            self.pond.step()
            buf = io.BytesIO()
            self.pond.draw().save(buf, "JPEG", quality=85)
            with self.cond:
                self.jpeg = buf.getvalue()
                self.seq += 1
                self.cond.notify_all()
            time.sleep(max(0.0, 1.0 / self.fps - (time.time() - t0)))

    def wait_frame(self, seq, timeout=5):
        with self.cond:
            self.cond.wait_for(lambda: self.seq != seq, timeout)
            return self.seq, self.jpeg


def make_handler(pond, cam):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json"):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, ensure_ascii=False).encode("utf-8")
            elif isinstance(body, str):
                body = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _command(self, cmd, value=None):
            try:
                pond.command(cmd, value)
            except (ValueError, TypeError) as e:
                return self._send(400, {"ok": False, "error": str(e)})
            self._send(200, {"ok": True, "state": pond.state()})

        def do_GET(self):
            u = urllib.parse.urlparse(self.path)
            q = dict(urllib.parse.parse_qsl(u.query))
            if u.path == "/":
                with open(PAGE, encoding="utf-8") as f:
                    return self._send(200, f.read(), "text/html; charset=utf-8")
            if u.path == "/snapshot.jpg":
                _seq, jpg = cam.wait_frame(-1, 0)
                return self._send(200, jpg, "image/jpeg")
            if u.path == "/video.mjpg":
                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                seq = -1
                try:
                    while True:
                        seq, jpg = cam.wait_frame(seq)
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                                         + str(len(jpg)).encode() + b"\r\n\r\n" + jpg + b"\r\n")
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    return
            if u.path == "/api/state":
                return self._send(200, pond.state())
            if u.path == "/api/command":
                return self._command(q.get("command"), q.get("value"))
            self._send(404, {"error": "not found"})

        def do_POST(self):
            u = urllib.parse.urlparse(self.path)
            if u.path != "/api/command":
                return self._send(404, {"error": "not found"})
            n = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                return self._send(400, {"ok": False, "error": "the body must be JSON"})
            self._command(body.get("command"), body.get("value"))

    return Handler


def main():
    ap = argparse.ArgumentParser(description="A simulated fish pond with a camera, for trying Inspector")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8800)
    ap.add_argument("--fps", type=float, default=5)
    ap.add_argument("--day-minutes", type=float, default=6, help="real minutes for one simulated day")
    ap.add_argument("--seed", type=int, default=None)
    a = ap.parse_args()
    pond = Pond(seed=a.seed, day_minutes=a.day_minutes)
    cam = Camera(pond, a.fps)
    ThreadingHTTPServer.allow_reuse_address = os.name != "nt"     # on Windows it would let a second copy share the port
    try:
        srv = ThreadingHTTPServer((a.host, a.port), make_handler(pond, cam))
    except OSError as e:
        sys.exit(f"Port {a.port} is in use (is the simulator already running?): {e}")
    srv.daemon_threads = True
    print(f"Fish pond simulator: http://{a.host}:{a.port}/   camera: http://{a.host}:{a.port}/video.mjpg", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
