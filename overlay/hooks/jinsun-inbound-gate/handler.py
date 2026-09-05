"""金孫 hook：agent:start 再掃一次。LINE adapter 已擋過就不會進到這裡。"""

from __future__ import annotations

import sys
from typing import Any, Dict, Optional


def handle(event_type: str, context: Optional[Dict[str, Any]] = None):
    if event_type != "agent:start":
        return None
    message = ((context or {}).get("message") or "")
    if "/opt/jinsun/mcp" not in sys.path:
        sys.path.insert(0, "/opt/jinsun/mcp")
    from jinsun_mcp import intercept_inbound

    return intercept_inbound(message, note="hook-agent-start")
