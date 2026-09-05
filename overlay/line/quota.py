"""金孫 LINE 額度守門。

官方規則（Messaging API）：用回覆權杖的 Reply 不計月額。
Push、Multicast、Broadcast、Narrowcast 才計月額。
一次請求裡多則物件，仍依「送到幾個人」計，不依物件數加計。
但後續批次、中途狀態、串流、權杖過期後的推播後援，都會另外打 Push，吃免費月額。

金孫預設：
1. 一次只送一則完整話。
2. 不准推播後援。
3. 系統忙碌回條不發出去，避免搶走免費回覆權杖。
"""

from __future__ import annotations

import os
from typing import List

LINE_SAFE_BUBBLE_CHARS = 4500
_SYSTEM_ACK_PREFIXES = (
    "⚡ Interrupting",
    "⏳ Queued",
    "⏩ Steered",
    "💾",
)


def _truthy(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def max_messages_per_call() -> int:
    """一次 API 呼叫最多幾則。金孫預設 1，官方上限 5。"""
    raw = os.getenv("LINE_MAX_MESSAGES_PER_CALL", "1")
    try:
        count = int(str(raw).strip())
    except (TypeError, ValueError):
        count = 1
    return max(1, min(5, count))


def allow_push() -> bool:
    """是否允許計月額的 Push。金孫預設關閉。"""
    return _truthy("LINE_ALLOW_PUSH", False)


def allow_cron_push() -> bool:
    """是否允許排程推播。對話仍不准推播後援。"""
    return _truthy("LINE_CRON_ALLOW_PUSH", False) or allow_push()


def swallow_system_ack(content: str) -> bool:
    """閘道忙碌回條不該送到 LINE，否則會用掉免費回覆權杖。"""
    if not content:
        return False
    return any(content.startswith(prefix) for prefix in _SYSTEM_ACK_PREFIXES)


def merge_confirm_question(question: str, leftover: str) -> str:
    """兩個鍵與說明併成一則，不要先傳文字再傳按鍵。"""
    question = (question or "").strip() or "請選一個"
    leftover = (leftover or "").strip()
    if not leftover:
        return question
    if question in leftover:
        return leftover
    return f"{leftover}\n{question}".strip()


def split_for_line(text: str, max_chars: int = LINE_SAFE_BUBBLE_CHARS) -> List[str]:
    """切成 LINE 氣泡。金孫預設只留一則，超長在最後加省略。"""
    if not text:
        return []
    budget = max_messages_per_call()
    if len(text) <= max_chars:
        return [text]

    chunks: List[str] = []
    remaining = text
    while remaining and len(chunks) < budget:
        if len(remaining) <= max_chars:
            chunks.append(remaining)
            remaining = ""
            break
        cut = remaining.rfind("\n\n", 0, max_chars)
        if cut < int(max_chars * 0.5):
            cut = remaining.rfind("\n", 0, max_chars)
        if cut < int(max_chars * 0.5):
            cut = remaining.rfind(" ", 0, max_chars)
        if cut <= 0:
            cut = max_chars
        chunks.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip()

    if remaining:
        if chunks:
            tail = chunks[-1]
            if len(tail) > max_chars - 1:
                tail = tail[: max_chars - 1]
            chunks[-1] = tail.rstrip() + "…"
        else:
            chunks.append(remaining[: max_chars - 1] + "…")
    return chunks
