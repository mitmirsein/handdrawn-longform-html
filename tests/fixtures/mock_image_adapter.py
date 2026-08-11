#!/usr/bin/env python3
"""Offline adapter used to test the handdrawn-image/v1 contract."""

from __future__ import annotations

import json
import struct
import sys
import zlib
from pathlib import Path


def main() -> int:
    request = json.load(sys.stdin)
    protocol = request.get("protocol")
    if protocol != "handdrawn-image/v1":
        print(json.dumps({"protocol": "handdrawn-image/v1", "status": "error", "error": "protocol mismatch"}))
        return 0
    if request.get("operation") == "capabilities":
        print(
            json.dumps(
                {
                    "protocol": "handdrawn-image/v1",
                    "status": "ok",
                    "capabilities": {
                        "generate": True,
                        "reference_images": True,
                        "native_alpha": True,
                    },
                    "provider": "mock",
                    "model": "fixture",
                }
            )
        )
        return 0
    output = request.get("output", {}).get("path")
    if not isinstance(output, str):
        print(json.dumps({"protocol": "handdrawn-image/v1", "status": "error", "error": "missing output path"}))
        return 0
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Keep the fixture independent of the interpreter that launches an
    # external adapter.  This is a small valid 32x32 RGBA PNG.
    width = height = 32
    row = bytes([255, 254, 250, 255]) * width
    raw = b"".join(b"\x00" + row for _ in range(height))
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw))
    png += chunk(b"IEND", b"")
    path.write_bytes(png)
    print(
        json.dumps(
            {
                "protocol": "handdrawn-image/v1",
                "status": "ok",
                "provider": "mock",
                "model": "fixture",
                "request_id": request.get("job_id"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
