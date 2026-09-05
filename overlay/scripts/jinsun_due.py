#!/usr/bin/env python3
"""Hermes 排程用：到期提醒印白話。空白輸出＝這輪不吵長輩。"""

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

from jinsun_mcp import due_reminder_text, seed_demo  # noqa: E402

if __name__ == "__main__":
    seed_demo()
    text = due_reminder_text()
    if text:
        print(text)
