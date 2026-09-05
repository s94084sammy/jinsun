#!/usr/bin/env python3
"""Hermes 排程用：花博爭艷館附近每週在地一則。空白＝這週不推。"""

from __future__ import annotations

import sys
from pathlib import Path

CANDIDATES = [
    Path("/opt/jinsun/mcp/jinsun_mcp.py"),
    Path(__file__).resolve().parents[1] / "mcp" / "jinsun_mcp.py",
]

for path in CANDIDATES:
    if path.is_file():
        sys.path.insert(0, str(path.parent))
        break

from jinsun_tw import weekly_local_text  # noqa: E402

if __name__ == "__main__":
    text = weekly_local_text()
    if text:
        print(text)
