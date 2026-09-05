#!/usr/bin/env python3
"""容器內最小驗證：真的開得起瀏覽器。只開不會惹事的頁。"""

from __future__ import annotations

import json
import os
import sys

os.environ.setdefault("HOME", "/opt/data")
os.environ.setdefault("HERMES_HOME", "/opt/data")
os.environ.setdefault("JINSUN_DATA", "/opt/data/jinsun")

if "/opt/jinsun/mcp" not in sys.path:
    sys.path.insert(0, "/opt/jinsun/mcp")
if "/opt/hermes" not in sys.path:
    sys.path.insert(0, "/opt/hermes")

from jinsun_mcp import browser_guard, browser_url_blocked_reason  # noqa: E402


SAFE_URL = "https://example.com"
BANK_URL = "https://www.esunbank.com.tw/login"


def main() -> int:
    if browser_url_blocked_reason(SAFE_URL) is not None:
        print("安全頁不該被擋", SAFE_URL)
        return 1
    if browser_url_blocked_reason(BANK_URL) is None:
        print("銀行頁應該被擋", BANK_URL)
        return 1
    blocked = browser_guard(BANK_URL)
    if "放行" in blocked:
        print("銀行 guard 不該放行")
        return 1

    from tools.browser_tool import browser_navigate, browser_snapshot

    nav = browser_navigate(SAFE_URL, task_id="jinsun-smoke")
    print("navigate:", nav[:800] if isinstance(nav, str) else nav)
    snap = browser_snapshot(task_id="jinsun-smoke")
    text = snap if isinstance(snap, str) else json.dumps(snap, ensure_ascii=False)
    print("snapshot:", text[:1200])
    lowered = text.lower()
    if "example" not in lowered and "domain" not in lowered and "example.com" not in lowered:
        # 有些快照只給標題 Example Domain
        if "success" in lowered and "false" in lowered:
            print("瀏覽器打開失敗")
            return 2
    print("金孫瀏覽器煙霧測試通過")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
