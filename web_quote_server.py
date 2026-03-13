#!/usr/bin/env python3
"""Simple local web UI server for quote comparison.

Run:
  python web_quote_server.py
Open:
  http://127.0.0.1:8000
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from moonpay_usdt_quote import collect_quotes

ROOT = Path(__file__).parent
WEB_DIR = ROOT / "web"


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/quotes":
            self._send_json(404, {"error": "Not found"})
            return

        try:
            raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            data = json.loads(raw.decode("utf-8"))
            rows = collect_quotes(
                providers=[p.lower() for p in data.get("providers", [])],
                fiat=str(data.get("fiat", "USD")).upper(),
                asset=str(data.get("asset", "USDT")).upper(),
                network=str(data.get("network", "ethereum")).lower(),
                payment_methods=[m.lower() for m in data.get("payment_methods", ["visa"])],
                amounts=[float(x) for x in data.get("amounts", [50, 100, 200])],
                timeout_ms=45000,
                allow_failures=bool(data.get("allow_failures", True)),
            )
            out = [r.__dict__ for r in rows]
            self._send_json(200, {"rows": out})
        except Exception as exc:  # noqa: BLE001
            self._send_json(400, {"error": str(exc)})

    def do_GET(self) -> None:  # noqa: N802
        if self.path in {"/", "/index.html"}:
            return self._serve_file(WEB_DIR / "index.html", "text/html; charset=utf-8")
        if self.path == "/web/app.js":
            return self._serve_file(WEB_DIR / "app.js", "application/javascript; charset=utf-8")
        if self.path == "/web/styles.css":
            return self._serve_file(WEB_DIR / "styles.css", "text/css; charset=utf-8")
        self.send_error(404, "Not found")

    def _serve_file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self.send_error(404, "Not found")
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", 8000), Handler)
    print("Serving at http://0.0.0.0:8000")
    server.serve_forever()


if __name__ == "__main__":
    main()
