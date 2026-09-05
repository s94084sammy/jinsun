#!/usr/bin/env python3
"""金孫 LINE：一次一則、不串流、不吃推播月額。"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT / "overlay" / "line"))

from quota import (  # noqa: E402
    allow_cron_push,
    allow_push,
    max_messages_per_call,
    merge_confirm_question,
    split_for_line,
    swallow_system_ack,
)

ADAPTER = ROOT / "overlay" / "line" / "adapter.py"
OVERLAY_CONFIG = ROOT / "overlay" / "config.yaml"
DATA_CONFIG = ROOT / "data" / "config.yaml"


class JinsunLineQuotaTest(unittest.TestCase):
    def setUp(self) -> None:
        self._old = {
            key: os.environ.get(key)
            for key in ("LINE_ALLOW_PUSH", "LINE_CRON_ALLOW_PUSH", "LINE_MAX_MESSAGES_PER_CALL")
        }
        os.environ.pop("LINE_ALLOW_PUSH", None)
        os.environ.pop("LINE_CRON_ALLOW_PUSH", None)
        os.environ.pop("LINE_MAX_MESSAGES_PER_CALL", None)

    def tearDown(self) -> None:
        for key, value in self._old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_default_forbids_push(self) -> None:
        self.assertFalse(allow_push())
        self.assertFalse(allow_cron_push())

    def test_cron_push_can_open_without_chat_push(self) -> None:
        os.environ["LINE_CRON_ALLOW_PUSH"] = "true"
        self.assertTrue(allow_cron_push())
        self.assertFalse(allow_push())

    def test_push_only_when_explicitly_on(self) -> None:
        os.environ["LINE_ALLOW_PUSH"] = "true"
        self.assertTrue(allow_push())
        os.environ["LINE_ALLOW_PUSH"] = "false"
        self.assertFalse(allow_push())

    def test_default_one_bubble(self) -> None:
        self.assertEqual(max_messages_per_call(), 1)

    def test_bubble_cap_clamped(self) -> None:
        os.environ["LINE_MAX_MESSAGES_PER_CALL"] = "9"
        self.assertEqual(max_messages_per_call(), 5)
        os.environ["LINE_MAX_MESSAGES_PER_CALL"] = "0"
        self.assertEqual(max_messages_per_call(), 1)

    def test_long_text_stays_one_bubble(self) -> None:
        text = ("台北今天下雨。" * 400)
        chunks = split_for_line(text, max_chars=80)
        self.assertEqual(len(chunks), 1)
        self.assertTrue(chunks[0].endswith("…"))

    def test_swallow_busy_acks(self) -> None:
        self.assertTrue(swallow_system_ack("⚡ Interrupting current run"))
        self.assertTrue(swallow_system_ack("⏳ Queued behind another job"))
        self.assertTrue(swallow_system_ack("⏩ Steered into current run"))
        self.assertFalse(swallow_system_ack("今天下雨，記得帶傘。"))

    def test_confirm_merges_leftover(self) -> None:
        merged = merge_confirm_question("要幫你填嗎？", "這是里民中秋活動。")
        self.assertIn("里民中秋活動", merged)
        self.assertIn("要幫你填嗎？", merged)

    def test_confirm_does_not_repeat_question(self) -> None:
        merged = merge_confirm_question(
            "你住哪邊？",
            "你住哪邊？我再幫你對一下那一區。",
        )
        self.assertEqual(merged.count("你住哪邊？"), 1)

    def test_adapter_uses_quota_helpers(self) -> None:
        source = ADAPTER.read_text(encoding="utf-8")
        self.assertIn("from .quota import", source)
        self.assertIn("allow_push", source)
        self.assertIn("swallow_system_ack", source)
        self.assertIn("skip metered push", source)

    def test_config_disables_streaming_and_interim(self) -> None:
        paths = [OVERLAY_CONFIG]
        if DATA_CONFIG.is_file():
            paths.append(DATA_CONFIG)
        for path in paths:
            text = path.read_text(encoding="utf-8")
            self.assertIn("interim_assistant_messages: false", text, path)
            self.assertIn("long_running_notifications: false", text, path)
            self.assertIn("tool_progress: off", text, path)
            self.assertRegex(text, r"streaming:\s*\n(?:[^\n]*\n)*?\s+enabled: false", path.name)
            self.assertIn("mode: off", text, path)


if __name__ == "__main__":
    unittest.main()
