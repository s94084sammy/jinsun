#!/usr/bin/env python3
"""放入示範提醒：吃藥、看診前一天、繳費截止、活動前一天。"""

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

from jinsun_mcp import seed_demo  # noqa: E402

if __name__ == "__main__":
    print(seed_demo())
