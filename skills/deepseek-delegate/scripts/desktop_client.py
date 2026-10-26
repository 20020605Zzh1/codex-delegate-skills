"""Use the Desktop's documented local authentication and Remote RPC carrier."""
from __future__ import annotations

import http.cookiejar
import json
import re
import uuid
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener


class DesktopClient:
    def __init__(self, launch_log: Path):
        log = launch_log.read_text(encoding="utf-8-sig")
        matches = re.findall(r"dsh web: (http://127\.0\.0\.1:\d+/\?token=\S+)", log)
        if not matches:
            raise RuntimeError("No local Desktop launch URL is available")
        parts = urlsplit(matches[-1])
        self.origin = f"{parts.scheme}://{parts.netloc}"
        self.cookies = http.cookiejar.CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cookies))
        with self.opener.open(matches[-1], timeout=12) as response:
            if response.status != 200 or not self.cookies:
                raise RuntimeError("Desktop authentication did not complete")

    def call(self, namespace: str, method: str, args: dict) -> object:
        endpoint = f"{namespace}/{method}"
        request = Request(self.origin + "/api/" + endpoint, method="POST", data=json.dumps({
            "type": "client-request", "rpcId": str(uuid.uuid4()), "method": endpoint,
            "payload": {"args": args},
        }).encode(), headers={"content-type": "application/json", "origin": self.origin})
        with self.opener.open(request, timeout=30) as response:
            result = json.loads(response.read())["result"]
        if not result["ok"]:
            raise RuntimeError(f"{endpoint}: {result['error']['message']}")
        return result.get("value")
