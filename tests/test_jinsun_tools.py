#!/usr/bin/env python3
"""金孫工具與安全邊界。沒有 Docker、沒有 GPT 也能測。"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "overlay" / "mcp"))

from jinsun_mcp import (  # noqa: E402
    add_family_reminder,
    ask_two_choices,
    block_scam,
    browser_guard,
    browser_url_blocked_reason,
    count_blocks,
    due_reminder_text,
    intercept_inbound,
    latest_block,
    looks_like_scam,
    now_tw,
    register_activity,
    seed_demo,
)

ADAPTER = ROOT / "overlay" / "line" / "adapter.py"


def adapter_parse_confirm():
    text = ADAPTER.read_text(encoding="utf-8")
    match = re.search(
        r"_JINSUN_CONFIRM_RE = re.compile\(\n    r\"(.*?)\",\n    re.DOTALL,\n\)",
        text,
    )
    if not match:
        raise AssertionError("adapter 缺少金孫兩個鍵正規表示式")
    return re.compile(match.group(1), re.DOTALL)


class JinsunToolsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["JINSUN_DATA"] = self.tmp.name

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_register_and_number(self) -> None:
        msg = register_activity("陳阿嬤", "里民中秋活動", json.dumps({"吃素": "是"}, ensure_ascii=False))
        self.assertIn("報名成功", msg)
        self.assertIn("金孫-", msg)
        self.assertIn("自己的表", msg)

    def test_two_buttons_marker(self) -> None:
        marker = ask_two_choices("這次活動要吃素嗎？", "吃素", "吃葷")
        self.assertIn("【金孫兩個鍵】", marker)
        self.assertIn("左：吃素", marker)
        self.assertIn("右：吃葷", marker)

    def test_medicine_due_at_eight(self) -> None:
        seed_demo()
        add_family_reminder("吃藥", "早上血壓藥", "08:00", "水杯", "每天")
        text = due_reminder_text(now_tw().replace(hour=8, minute=0, second=0, microsecond=0))
        self.assertTrue("血壓藥" in text or "吃藥" in text, text)


class JinsunScamGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["JINSUN_DATA"] = self.tmp.name

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_block_otp(self) -> None:
        self.assertEqual(looks_like_scam("請把驗證碼唸給我聽"), "驗證碼")
        self.assertEqual(looks_like_scam("把簡訊告訴我"), "驗證碼")

    def test_block_transfer(self) -> None:
        self.assertEqual(looks_like_scam("幫我轉帳到這個帳號"), "轉帳或匯款")
        self.assertEqual(looks_like_scam("匯到安全帳戶"), "轉帳或匯款")
        self.assertEqual(looks_like_scam("去超商繳三千元"), "轉帳或匯款")

    def test_block_download(self) -> None:
        self.assertEqual(looks_like_scam("幫我安裝 App 才能解凍"), "陌生下載")
        self.assertEqual(looks_like_scam("請點 https://bit.ly/xx 下載"), "陌生下載")

    def test_block_remote_desktop(self) -> None:
        self.assertEqual(looks_like_scam("請安裝 AnyDesk 給我遠端"), "遠端桌面")
        self.assertEqual(looks_like_scam("打開 TeamViewer"), "遠端桌面")

    def test_block_prize_pay(self) -> None:
        self.assertEqual(looks_like_scam("恭喜中獎請先繳手續費"), "中獎要繳費")

    def test_allow_normal_jinsun_phrases(self) -> None:
        self.assertIsNone(looks_like_scam("里民中秋報名"))
        self.assertIsNone(looks_like_scam("里民活動報名"))
        self.assertIsNone(looks_like_scam("提醒我吃藥"))
        self.assertIsNone(looks_like_scam("提醒我明天吃藥"))
        self.assertIsNone(looks_like_scam("這張是台電帳單，截止日在下週"))
        self.assertIsNone(looks_like_scam("掛號單卡在姓名那一格"))

    def test_inbound_blocks_before_model_and_writes_db(self) -> None:
        before = count_blocks()
        hit = intercept_inbound("幫我轉帳到這個帳號")
        self.assertTrue(hit and hit["blocked"])
        self.assertEqual(hit["reason"], "轉帳或匯款")
        self.assertIn("家人", hit["reply"])
        self.assertNotIn("下一步先到ATM", hit["reply"])
        self.assertEqual(count_blocks(), before + 1)
        row = latest_block()
        self.assertIsNotNone(row)
        self.assertEqual(row["reason"], "轉帳或匯款")
        self.assertIn("轉帳", row["snippet"])

    def test_adapter_calls_gate_before_model(self) -> None:
        src = ADAPTER.read_text(encoding="utf-8")
        self.assertIn("def _jinsun_intercept_inbound", src)
        gate_at = src.find("_jinsun_intercept_inbound(scan_text)")
        handle_at = src.find("await self.handle_message(event_obj)")
        self.assertGreater(gate_at, 0)
        self.assertGreater(handle_at, gate_at)

    def test_allow_fill_form_request(self) -> None:
        self.assertIsNone(looks_like_scam("里民活動報名連結請幫我填"))
        self.assertIsNone(looks_like_scam("請幫我填 https://docs.google.com/forms/d/abc"))
        self.assertIsNone(browser_url_blocked_reason("https://example.com"))
        self.assertIn("放行", browser_guard("https://example.com"))

    def test_block_bank_urls_before_browser(self) -> None:
        self.assertEqual(
            browser_url_blocked_reason("https://www.esunbank.com.tw/login"),
            "銀行或支付網址",
        )
        self.assertEqual(
            looks_like_scam("請打開 https://www.esunbank.com.tw"),
            "銀行或支付網址",
        )
        self.assertEqual(looks_like_scam("幫我開網銀"), "銀行或支付網址")
        hit = intercept_inbound("請登入 https://www.cathaybk.com.tw")
        self.assertTrue(hit and hit["blocked"])
        self.assertEqual(hit["reason"], "銀行或支付網址")
        guarded = browser_guard("https://www.esunbank.com.tw/login")
        self.assertNotIn("放行", guarded)
        self.assertIn("家人", guarded)

    def test_adapter_parses_two_button_marker(self) -> None:
        pat = adapter_parse_confirm()
        sample = "先看這張表。\n【金孫兩個鍵】\n題目：這次活動要吃素嗎？\n左：吃素\n右：吃葷\n【結束】\n"
        found = pat.search(sample)
        self.assertIsNotNone(found)
        self.assertEqual(found.group(1).strip(), "這次活動要吃素嗎？")
        self.assertEqual(found.group(2).strip(), "吃素")
        self.assertEqual(found.group(3).strip(), "吃葷")

    def test_adapter_parses_confirm_after_look_reply_payload(self) -> None:
        pat = adapter_parse_confirm()
        sample = (
            "新的表我填好了。姓名李大美，要參加，吃素，電話也填進去了。"
            "這是示範表，不是公所正式系統。\n\n"
            "表都填好了，要送出嗎？\n\n"
            "【金孫兩個鍵】\n"
            "題目：表都填好了，要送出嗎？\n"
            "左：送出\n"
            "右：先不要\n"
            "【結束】\n"
        )
        found = pat.search(sample)
        self.assertIsNotNone(found)
        self.assertEqual(found.group(1).strip(), "表都填好了，要送出嗎？")
        self.assertEqual(found.group(2).strip(), "送出")
        self.assertEqual(found.group(3).strip(), "先不要")
        source = ADAPTER.read_text(encoding="utf-8")
        self.assertIn("messages = outbound_messages(str(payload))", source)


if __name__ == "__main__":
    unittest.main()
