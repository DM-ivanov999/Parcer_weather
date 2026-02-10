#!/usr/bin/env python3
"""Minimal UV HTTP API for banner integration testing.

Run:
    python uv_api.py --host 0.0.0.0 --port 8080

Example:
    curl "http://127.0.0.1:8080/banner/uv?city=Delhi&threshold=6&op=gte&fresh=1"
"""

from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from uv_india import DEFAULT_CITY, fetch_uv, get_uv, save

OPS = {
    "gte": lambda uv, threshold: uv >= threshold,
    "gt": lambda uv, threshold: uv > threshold,
    "lte": lambda uv, threshold: uv <= threshold,
    "lt": lambda uv, threshold: uv < threshold,
    "eq": lambda uv, threshold: uv == threshold,
}


class UVHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT.value)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/health":
            self._send_json({"ok": True})
            return

        if parsed.path != "/banner/uv":
            self._send_json({"ok": False, "error": "Not found"}, status=HTTPStatus.NOT_FOUND)
            return

        query = parse_qs(parsed.query)
        city = query.get("city", [DEFAULT_CITY])[0]
        op = query.get("op", ["gte"])[0].lower()
        fresh = query.get("fresh", ["0"])[0] in {"1", "true", "True", "yes"}

        try:
            threshold = float(query.get("threshold", ["6"])[0])
        except ValueError:
            self._send_json(
                {"ok": False, "error": "Invalid threshold. Use number, e.g. threshold=6"},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        if op not in OPS:
            self._send_json(
                {"ok": False, "error": "Invalid op. Use one of: gte, gt, lte, lt, eq"},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        try:
            if fresh:
                latest = fetch_uv(city)
                save(latest)
            else:
                latest = get_uv(city)
                if not latest:
                    latest = fetch_uv(city)
                    save(latest)
        except Exception as exc:  # pragma: no cover
            self._send_json(
                {"ok": False, "error": str(exc)},
                status=HTTPStatus.BAD_GATEWAY,
            )
            return

        uv_value = float(latest.get("uv_index", 0))
        is_triggered = OPS[op](uv_value, threshold)

        self._send_json(
            {
                "ok": True,
                "city": latest.get("city", city),
                "timestamp": latest.get("timestamp"),
                "uv_index": uv_value,
                "uv_desc": latest.get("uv_desc"),
                "trigger": {
                    "op": op,
                    "threshold": threshold,
                    "matched": is_triggered,
                },
                "banner_payload": {
                    "uv": uv_value,
                    "show_uv_creative": is_triggered,
                },
            }
        )

    def log_message(self, fmt: str, *args) -> None:
        # Keep console clean for local testing
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="UV API for banner trigger testing")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), UVHandler)
    print(f"UV API listening on http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
