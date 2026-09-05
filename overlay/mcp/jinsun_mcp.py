#!/usr/bin/env python3
"""金孫家用工具。報名、提醒、擋詐騙，加上台灣在地查詢。"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import jinsun_tw

TZ = timezone(timedelta(hours=8))


def now_tw() -> datetime:
    return datetime.now(TZ)


def data_dir() -> Path:
    raw = os.environ.get("JINSUN_DATA") or os.environ.get("HERMES_HOME") or "/opt/data"
    path = Path(raw)
    if path.name != "jinsun":
        path = path / "jinsun"
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return data_dir() / "jinsun.db"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            elder_name TEXT NOT NULL,
            activity_name TEXT NOT NULL,
            answers_json TEXT NOT NULL DEFAULT '{}',
            note TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'confirmed'
        );
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            kind TEXT NOT NULL,
            fire_at TEXT NOT NULL,
            title TEXT NOT NULL,
            bring_what TEXT NOT NULL DEFAULT '',
            repeat_rule TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'scheduled',
            last_sent_at TEXT
        );
        CREATE TABLE IF NOT EXISTS blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            reason TEXT NOT NULL,
            snippet TEXT NOT NULL DEFAULT '',
            note TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            action TEXT NOT NULL,
            payload TEXT NOT NULL DEFAULT '{}'
        );
        """
    )
    conn.commit()


def audit(conn: sqlite3.Connection, action: str, payload: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO audit (created_at, action, payload) VALUES (?, ?, ?)",
        (now_tw().isoformat(timespec="seconds"), action, json.dumps(payload, ensure_ascii=False)),
    )
    conn.commit()


def registration_number(created_at: datetime, row_id: int) -> str:
    return f"金孫-{created_at.strftime('%Y%m%d')}-{int(row_id):04d}"


def register_activity(elder_name: str, activity_name: str, answers_json: str = "{}", note: str = "") -> str:
    elder_name = (elder_name or "").strip() or "長輩"
    activity_name = (activity_name or "").strip()
    if not activity_name:
        return "還沒寫活動名稱，請再問一次活動叫什麼。"
    try:
        answers = json.loads(answers_json) if answers_json else {}
        if not isinstance(answers, dict):
            answers = {"內容": str(answers_json)}
    except json.JSONDecodeError:
        answers = {"內容": answers_json}
    created = now_tw()
    conn = connect()
    try:
        init_db(conn)
        conn.execute(
            """
            INSERT INTO registrations (created_at, elder_name, activity_name, answers_json, note, status)
            VALUES (?, ?, ?, ?, ?, 'confirmed')
            """,
            (
                created.isoformat(timespec="seconds"),
                elder_name,
                activity_name,
                json.dumps(answers, ensure_ascii=False),
                note or "",
            ),
        )
        row_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        number = registration_number(created, row_id)
        audit(conn, "register_activity", {"number": number, "activity": activity_name, "elder": elder_name})
        conn.commit()
    finally:
        conn.close()
    extra = "、".join(f"{k}{v}" for k, v in answers.items()) if answers else "沒有額外欄位"
    return f"報名成功。編號是 {number}。活動：{activity_name}。姓名：{elder_name}。{extra}。這是家裡金孫自己的表，不是公所或醫院的正式系統。"


def add_family_reminder(
    kind: str,
    title: str,
    fire_at: str,
    bring_what: str = "",
    repeat_rule: str = "",
) -> str:
    kind = (kind or "").strip() or "其它"
    title = (title or "").strip()
    fire_at = (fire_at or "").strip()
    if not title or not fire_at:
        return "提醒要有名稱和時間。時間請用 2026-09-05 09:00 這種格式。"
    conn = connect()
    try:
        init_db(conn)
        conn.execute(
            """
            INSERT INTO reminders (created_at, kind, fire_at, title, bring_what, repeat_rule, status)
            VALUES (?, ?, ?, ?, ?, ?, 'scheduled')
            """,
            (
                now_tw().isoformat(timespec="seconds"),
                kind,
                fire_at,
                title,
                bring_what or "",
                repeat_rule or "",
            ),
        )
        row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        audit(conn, "add_reminder", {"id": row_id, "kind": kind, "fire_at": fire_at, "title": title})
        conn.commit()
    finally:
        conn.close()
    bring = f"要帶：{bring_what}。" if bring_what else ""
    repeat = f"重複：{repeat_rule}。" if repeat_rule else "只提醒這一次。"
    return f"已經記下提醒。編號是 提醒-{row_id}。{kind}：{title}。時間：{fire_at}。{bring}{repeat}"


def block_scam(reason: str, snippet: str = "", note: str = "") -> str:
    reason = (reason or "").strip() or "可疑要求"
    conn = connect()
    try:
        init_db(conn)
        conn.execute(
            "INSERT INTO blocks (created_at, reason, snippet, note) VALUES (?, ?, ?, ?)",
            (now_tw().isoformat(timespec="seconds"), reason, snippet or "", note or ""),
        )
        row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        audit(conn, "block_scam", {"id": row_id, "reason": reason})
        conn.commit()
    finally:
        conn.close()
    return (
        f"已經擋住，編號是 擋住-{row_id}。"
        "這件事我不能幫你做。請把手機拿給家人看。"
        "不要轉帳、不要把驗證碼唸出來、不要去按陌生下載。"
    )


def list_registrations(limit: int = 5) -> str:
    conn = connect()
    try:
        init_db(conn)
        rows = conn.execute(
            "SELECT id, created_at, elder_name, activity_name, answers_json FROM registrations ORDER BY id DESC LIMIT ?",
            (max(1, min(int(limit), 20)),),
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        return "目前沒有報名紀錄。"
    lines = []
    for row in rows:
        created = datetime.fromisoformat(row["created_at"])
        number = registration_number(created, int(row["id"]))
        lines.append(f"{number} {row['elder_name']} 報名 {row['activity_name']}")
    return "最近報名：\n" + "\n".join(lines)


def list_reminders(limit: int = 8) -> str:
    conn = connect()
    try:
        init_db(conn)
        rows = conn.execute(
            "SELECT id, kind, fire_at, title, bring_what, status FROM reminders ORDER BY id DESC LIMIT ?",
            (max(1, min(int(limit), 20)),),
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        return "目前沒有提醒。"
    lines = [
        f"提醒-{row['id']} {row['kind']} {row['fire_at']} {row['title']} {row['bring_what']}（{row['status']}）"
        for row in rows
    ]
    return "家庭提醒：\n" + "\n".join(lines)


def due_reminder_text(now: Optional[datetime] = None) -> str:
    """給排程腳本用：到期就印白話，沒到期就空白（Hermes --no-agent 空白＝不吵）。"""
    current = now or now_tw()
    conn = connect()
    try:
        init_db(conn)
        rows = conn.execute(
            "SELECT id, kind, fire_at, title, bring_what, repeat_rule, status, last_sent_at FROM reminders WHERE status = 'scheduled'"
        ).fetchall()
        due = []
        for row in rows:
            if _is_due(row, current):
                due.append(row)
                conn.execute(
                    "UPDATE reminders SET last_sent_at = ?, status = CASE WHEN repeat_rule = '' THEN 'sent' ELSE status END WHERE id = ?",
                    (current.isoformat(timespec="seconds"), row["id"]),
                )
        if due:
            audit(conn, "due_fire", {"ids": [int(r["id"]) for r in due]})
        conn.commit()
    finally:
        conn.close()
    if not due:
        return ""
    parts = []
    for row in due:
        bring = f"要記得帶：{row['bring_what']}。" if row["bring_what"] else ""
        parts.append(f"金孫提醒你。{row['kind']}：{row['title']}。{bring}時間是 {row['fire_at']}。")
    return "\n".join(parts)


def _is_due(row: sqlite3.Row, current: datetime) -> bool:
    kind = row["kind"]
    fire_at = row["fire_at"]
    repeat_rule = row["repeat_rule"] or ""
    try:
        target = datetime.fromisoformat(fire_at)
        if target.tzinfo is None:
            target = target.replace(tzinfo=TZ)
    except ValueError:
        target = None
    if repeat_rule == "每天" or kind == "吃藥":
        # 每天同一時段，前後 12 分鐘內視為到期一次
        try:
            hh, mm = [int(x) for x in fire_at.split()[-1].split(":")[:2]]
        except Exception:
            if target is None:
                return False
            hh, mm = target.hour, target.minute
        scheduled = current.replace(hour=hh, minute=mm, second=0, microsecond=0)
        delta = abs((current - scheduled).total_seconds())
        last = row["last_sent_at"]
        if last:
            last_dt = datetime.fromisoformat(last)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=TZ)
            if last_dt.date() == current.date():
                return False
        return delta <= 12 * 60
    if target is None:
        return False
    if kind in {"看診前一天", "活動前一天"}:
        window_start = target - timedelta(hours=24)
        window_end = target - timedelta(hours=12)
        return window_start <= current <= window_end + timedelta(hours=12)
    if kind == "繳費截止":
        return target - timedelta(hours=36) <= current <= target + timedelta(hours=2)
    return abs((current - target).total_seconds()) <= 15 * 60


def ask_two_choices(question: str, left: str, right: str) -> str:
    question = (question or "").strip() or "要不要繼續？"
    left = (left or "").strip() or "好"
    right = (right or "").strip() or "先不要"
    return (
        f"【金孫兩個鍵】\n題目：{question}\n左：{left}\n右：{right}\n【結束】\n"
        "請把上面這段原樣寫進回覆，不要改成星號或編號清單。"
    )


_OTP_RE = re.compile(
    r"(驗證碼|認證碼|(?<![A-Za-z])otp(?![A-Za-z])|一次性密碼|把簡訊告訴我|把簡訊唸|簡訊給我聽|把簡訊說|把簡訊念出來)",
    re.I,
)
_REMOTE_RE = re.compile(
    r"(anydesk|teamviewer|splashtop|向日葵|遠端桌面|遠端協助|遠端連線|遠端控制)",
    re.I,
)
_PRIZE_RE = re.compile(r"(恭喜.{0,8}中獎|你中獎|中獎)")
_PRIZE_PAY_RE = re.compile(r"(繳|手續費|稅|保證金|領獎|匯)")
_POLICE_RE = re.compile(r"(地檢署|檢警|刑警|我是警察|我是檢察官|警察局.{0,8}(匯|轉帳|驗證)|警察說要)")
_DOWNLOAD_RE = re.compile(
    r"(幫我安裝\s*app|下載這個\s*app|下載app|安裝檔|\.apk\b|陌生下載)",
    re.I,
)
_SHORTLINK_RE = re.compile(r"(bit\.ly|tinyurl|reurl\.cc|shorturl)", re.I)
_CLICK_RE = re.compile(r"(點|按|下載|安裝|開啟連結)")
_TRANSFER_RE = re.compile(
    r"(轉帳|匯款|匯到|安全帳戶|去超商繳|超商繳費代碼|ATM\s*轉)",
    re.I,
)
_BANK_INTENT_RE = re.compile(r"(網銀|網路銀行|銀行登入|銀行網站|信用卡驗證)")
_URL_RE = re.compile(r"https?://[^\s<>\"')\]]+|www\.[^\s<>\"')\]]+", re.I)
_BLOCKED_HOST_PARTS = (
    "esunbank",
    "ctbcbank",
    "cathaybk",
    "firstbank",
    "megabank",
    "taishinbank",
    "sinopac",
    "fubon.com",
    "hncb.com",
    "scsb.com",
    "chb.com.tw",
    "tcb-bank",
    "landbank",
    "bot.com.tw",
    "tbb.com.tw",
    "paypal.",
    "jkopay",
    "pluspay",
    "nhi.gov.tw",
    "ris.gov.tw",
    "moica",
    "ebank.",
    "netbank",
)


def urls_in_text(text: str) -> list[str]:
    return _URL_RE.findall(text or "")


def browser_url_blocked_reason(url: str) -> Optional[str]:
    """瀏覽器不准開銀行、健保、戶政、支付、驗證碼頁、遠端桌面下載。"""
    raw = (url or "").strip()
    if not raw:
        return None
    candidate = raw if "://" in raw else "https://" + raw
    try:
        from urllib.parse import urlparse

        parsed = urlparse(candidate)
        host = (parsed.hostname or "").lower()
        full = candidate.lower()
    except Exception:
        host, full = "", raw.lower()
    if _REMOTE_RE.search(full):
        return "遠端桌面"
    if re.search(r"(3dsecure|verifiedbyvisa|securecode|/otp\b|one-time)", full, re.I):
        return "驗證碼頁"
    if "line.me" in host and re.search(r"/pay|linepay", full):
        return "支付頁"
    for part in _BLOCKED_HOST_PARTS:
        if part in host or part in full:
            if any(p in host for p in ("nhi.gov", "ris.gov")) or "moica" in host:
                return "健保或戶政"
            if any(p in host or p in full for p in ("paypal", "jkopay", "pluspay")):
                return "支付頁"
            return "銀行或支付網址"
    return None


def looks_like_scam(text: str) -> Optional[str]:
    """進線硬閘門。命中就擋，不把轉帳步驟送進模型。正常報名／吃藥提醒不准擋。"""
    blob = text or ""
    if not blob.strip():
        return None
    for url in urls_in_text(blob):
        reason = browser_url_blocked_reason(url)
        if reason:
            return reason
    if _OTP_RE.search(blob):
        return "驗證碼"
    if _REMOTE_RE.search(blob):
        return "遠端桌面"
    if _PRIZE_RE.search(blob) and _PRIZE_PAY_RE.search(blob):
        return "中獎要繳費"
    if _POLICE_RE.search(blob):
        return "檢警"
    if _DOWNLOAD_RE.search(blob):
        return "陌生下載"
    if _SHORTLINK_RE.search(blob) and _CLICK_RE.search(blob):
        return "陌生下載"
    if _TRANSFER_RE.search(blob):
        return "轉帳或匯款"
    if _BANK_INTENT_RE.search(blob):
        return "銀行或支付網址"
    return None


def browser_guard(url: str) -> str:
    """填表前先問。放行或擋住。已開到禁站時也走這裡，立刻停。"""
    reason = browser_url_blocked_reason(url) or looks_like_scam(url)
    if not reason:
        return "放行。這不是銀行、健保、戶政或支付頁。可以在家裡這台電腦用瀏覽器打開。"
    hit = intercept_inbound(url, note="browser-guard")
    return hit["reply"] if hit else "這件事我不能幫你做。請把手機拿給家人看。"


def intercept_inbound(text: str, *, persist: bool = True, note: str = "inbound-gate") -> Optional[dict]:
    """模型之前的硬閘門。命中就寫 blocks、回擋話，回傳 dict；沒命中回 None。"""
    reason = looks_like_scam(text)
    if not reason:
        return None
    snippet = (text or "").strip()[:240]
    if persist:
        reply = block_scam(reason, snippet=snippet, note=note)
    else:
        reply = (
            "這件事我不能幫你做。請把手機拿給家人看。"
            "不要轉帳、不要把驗證碼唸出來、不要去按陌生下載。"
        )
    return {"blocked": True, "reason": reason, "reply": reply, "snippet": snippet}


def latest_block() -> Optional[dict]:
    conn = connect()
    try:
        init_db(conn)
        row = conn.execute(
            "SELECT id, created_at, reason, snippet, note FROM blocks ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return {k: row[k] for k in row.keys()}


def count_blocks() -> int:
    conn = connect()
    try:
        init_db(conn)
        return int(conn.execute("SELECT COUNT(*) AS n FROM blocks").fetchone()["n"])
    finally:
        conn.close()


def seed_demo() -> str:
    conn = connect()
    try:
        init_db(conn)
        if conn.execute("SELECT COUNT(*) AS n FROM reminders").fetchone()["n"] == 0:
            created = now_tw().isoformat(timespec="seconds")
            rows = [
                ("吃藥", "早上血壓藥", "08:00", "水杯", "每天"),
                ("看診前一天", "林診所回診", "2026-09-06 09:00", "健保卡與證件", ""),
                ("繳費截止", "台電帳單", "2026-09-10 23:59", "帳單紙本或手機截圖", ""),
                ("活動前一天", "里民中秋活動", "2026-09-06 09:00", "身分證與自己的杯子", ""),
            ]
            for kind, title, fire_at, bring, repeat in rows:
                conn.execute(
                    """
                    INSERT INTO reminders (created_at, kind, fire_at, title, bring_what, repeat_rule, status)
                    VALUES (?, ?, ?, ?, ?, ?, 'scheduled')
                    """,
                    (created, kind, fire_at, title, bring, repeat),
                )
        conn.commit()
    finally:
        conn.close()
    return "示範提醒已準備。"


def run_selftest() -> int:
    os.environ.setdefault("JINSUN_DATA", str(Path("/tmp/jinsun-selftest")))
    test_dir = data_dir()
    for leftover in test_dir.glob("*"):
        leftover.unlink()
    seed_demo()
    msg = register_activity("陳阿嬤", "里民中秋活動", json.dumps({"吃素": "是"}, ensure_ascii=False))
    assert "報名成功" in msg and "金孫-" in msg, msg
    rem = add_family_reminder("吃藥", "晚上胃藥", "20:00", "水杯", "每天")
    assert "已經記下提醒" in rem, rem
    blocked = block_scam("轉帳", "請把錢匯到這個帳號")
    assert "已經擋住" in blocked, blocked
    listed = list_registrations()
    assert "里民中秋活動" in listed, listed
    marker = ask_two_choices("這次活動要吃素嗎？", "吃素", "吃葷")
    assert "【金孫兩個鍵】" in marker and "吃素" in marker
    assert looks_like_scam("請把驗證碼唸給我聽") == "驗證碼"
    hit = intercept_inbound("幫我轉帳到這個帳號")
    assert hit and hit["blocked"] and hit["reason"] == "轉帳或匯款", hit
    assert latest_block() is not None
    assert looks_like_scam("里民中秋報名") is None
    assert looks_like_scam("提醒我明天吃藥") is None
    assert looks_like_scam("里民活動報名連結請幫我填") is None
    assert looks_like_scam("明天會下雨嗎") is None
    assert looks_like_scam("附近哪裡有診所") is None
    assert looks_like_scam("幫我轉帳到這個帳號") == "轉帳或匯款"
    assert browser_url_blocked_reason("https://example.com") is None
    assert browser_url_blocked_reason("https://docs.google.com/forms/d/abc") is None
    assert browser_url_blocked_reason("https://www.esunbank.com.tw/login") == "銀行或支付網址"
    assert looks_like_scam("請打開 https://www.esunbank.com.tw") == "銀行或支付網址"
    due = due_reminder_text(now_tw().replace(hour=8, minute=0, second=0, microsecond=0))
    assert "血壓藥" in due or "胃藥" in due or "吃藥" in due, due
    print("金孫工具自我測試通過")
    print(msg)
    print(rem)
    print(blocked)
    return 0


def build_server():
    from mcp.server import MCPServer

    server = MCPServer("jinsun")

    @server.tool()
    def jinsun_register_activity(elder_name: str, activity_name: str, answers_json: str = "{}", note: str = "") -> str:
        """寫入家裡自製活動報名表，回傳編號。不是公所或醫院正式系統。"""
        return register_activity(elder_name, activity_name, answers_json, note)

    @server.tool()
    def jinsun_add_reminder(kind: str, title: str, fire_at: str, bring_what: str = "", repeat_rule: str = "") -> str:
        """寫入家庭提醒。kind 用：吃藥、看診前一天、繳費截止、活動前一天。"""
        return add_family_reminder(kind, title, fire_at, bring_what, repeat_rule)

    @server.tool()
    def jinsun_block_scam(reason: str, snippet: str = "", note: str = "") -> str:
        """轉帳、驗證碼、陌生下載預設擋下來，請家人看。"""
        return block_scam(reason, snippet, note)

    @server.tool()
    def jinsun_ask_two_choices(question: str, left: str, right: str) -> str:
        """產生一次兩個鍵的標記。請把回傳文字原樣寫進給長輩的回覆。"""
        return ask_two_choices(question, left, right)

    @server.tool()
    def jinsun_list_registrations(limit: int = 5) -> str:
        """列出最近的自製報名編號。"""
        return list_registrations(limit)

    @server.tool()
    def jinsun_list_reminders(limit: int = 8) -> str:
        """列出家庭提醒。"""
        return list_reminders(limit)

    @server.tool()
    def jinsun_browser_guard(url: str) -> str:
        """瀏覽器打開網址前必問。銀行、健保、戶政、支付、驗證碼頁會擋。"""
        return browser_guard(url)

    @server.tool()
    def jinsun_weather(place: str = "") -> str:
        """查中央氣象署縣市天氣與警特報。沒有授權碼時會改講災害示警。place 用縣市或路名。"""
        return jinsun_tw.weather_text(place)

    @server.tool()
    def jinsun_earthquake(place: str = "") -> str:
        """查中央氣象署顯著有感地震。沒有授權碼時請改問災害示警。"""
        return jinsun_tw.earthquake_text(place)

    @server.tool()
    def jinsun_disaster(place: str = "") -> str:
        """查國家災害防救科技中心示警。長輩問我家這區有沒有警報時用。免金鑰。"""
        return jinsun_tw.disaster_text(place)

    @server.tool()
    def jinsun_air(place: str = "") -> str:
        """查環境部空氣品質指標。place 用縣市或測站名。"""
        return jinsun_tw.air_text(place)

    @server.tool()
    def jinsun_holiday(question: str = "") -> str:
        """查台灣明天放不放假、下次連假、某一天是不是國定假日。"""
        return jinsun_tw.holiday_text(question)

    @server.tool()
    def jinsun_clinic(place: str = "", keyword: str = "") -> str:
        """查健保特約診所名稱電話地址看診時段。不掛號、不登入健保。place 必填縣市或路名。"""
        return jinsun_tw.clinic_text(place, keyword)

    @server.tool()
    def jinsun_pharmacy(place: str = "", keyword: str = "") -> str:
        """查健保特約藥局名稱電話地址。不登入健保、不查藥歷。place 必填縣市或路名。"""
        return jinsun_tw.pharmacy_text(place, keyword)

    @server.tool()
    def jinsun_long_term_care(place: str = "") -> str:
        """查長照據點名稱地址電話，並提醒打 1966。不能假裝核准給付。"""
        return jinsun_tw.long_term_care_text(place)

    @server.tool()
    def jinsun_garbage(place: str = "") -> str:
        """查垃圾車今天有沒有收、大約幾點。台北只有表定，新北有表定與可能延遲的即時位置。"""
        return jinsun_tw.garbage_text(place)

    @server.tool()
    def jinsun_power_outage(place: str = "") -> str:
        """查台電計畫性工程停電白話。不是繳電費。不確定請打 1911。"""
        return jinsun_tw.power_outage_text(place)

    @server.tool()
    def jinsun_medicine(name: str = "") -> str:
        """查食藥署公開許可證與仿單重點。必須提醒以藥袋與藥師為準。不是看診。"""
        return jinsun_tw.medicine_text(name)

    @server.tool()
    def jinsun_transit(question: str = "") -> str:
        """公車捷運台鐵即時。沒有 TDX 金鑰就明白說還沒授權，不要卡住別的功能。"""
        return jinsun_tw.transit_text(question)

    @server.tool()
    def jinsun_weekly_local(question: str = "") -> str:
        """花博爭艷館示範：查證中山區公所里活動表，只講圓山、集英、大佳、成功里這週的旅遊、中秋、敬老、健行。沒查到就空白。"""
        return jinsun_tw.weekly_local_text()

    return server


def main() -> int:
    if "--selftest" in sys.argv:
        return run_selftest()
    if "--inbound" in sys.argv:
        idx = sys.argv.index("--inbound")
        text = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else ""
        hit = intercept_inbound(text)
        if not hit:
            print("放行")
            return 0
        print(hit["reply"])
        return 2
    if "--due" in sys.argv:
        seed_demo()
        text = due_reminder_text()
        if text:
            print(text)
        return 0
    if "--seed" in sys.argv:
        print(seed_demo())
        return 0
    server = build_server()
    return server.run_stdio_async()  # type: ignore[misc]


if __name__ == "__main__":
    result = main()
    if hasattr(result, "__await__"):
        import asyncio

        asyncio.run(result)
    else:
        raise SystemExit(result or 0)
