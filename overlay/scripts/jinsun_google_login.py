#!/usr/bin/env python3
"""用金孫獨立瀏覽器登入一次 Google。密碼只從本機權限 600 檔讀，不准印出來。"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

DATA = Path(os.environ.get("JINSUN_DATA") or "/opt/data/jinsun")
PROFILE = DATA / "chrome-profile"
EMAIL_FILE = DATA / ".google-email"
PASS_FILE = DATA / ".google-pass"
BROWSER = Path.home() / ".local/bin/agent-browser"


def run(*args: str, timeout: int = 60) -> str:
    env = os.environ.copy()
    env["PATH"] = str(BROWSER.parent) + ":" + env.get("PATH", "")
    env["AGENT_BROWSER_PROFILE"] = str(PROFILE)
    cmd = [str(BROWSER), "--profile", str(PROFILE), *args]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return out


def main() -> int:
    if not EMAIL_FILE.is_file() or not PASS_FILE.is_file():
        print("沒有登入檔，不進行。")
        return 2
    email = EMAIL_FILE.read_text(encoding="utf-8").strip()
    password = PASS_FILE.read_text(encoding="utf-8").strip()
    if not email or not password or "@" not in email:
        print("登入檔不完整，不進行。")
        return 2
    PROFILE.mkdir(parents=True, exist_ok=True)
    run("close", "--all")
    time.sleep(1)
    print(
        run(
            "open",
            "https://accounts.google.com/ServiceLogin?hl=zh-TW&continue=https://docs.google.com/spreadsheets",
        )
    )
    time.sleep(2)
    snap = run("snapshot")
    print(snap[:2500])
    if "電子郵件" in snap or "email" in snap.lower() or "identifier" in snap.lower():
        print(run("fill", "e10", email))
        time.sleep(0.5)
        print(run("click", "e3"))
        time.sleep(3)
        snap = run("snapshot")
        print(snap[:2500])
    # password field refs change; find a password textbox
    if "密碼" in snap or "password" in snap.lower():
        # try common refs then fill by placeholder via eval-less fill of first password
        print(run("fill", 'textbox "輸入你的密碼"', password))
        time.sleep(0.4)
        print(run("press", "Enter"))
        time.sleep(4)
        snap = run("snapshot")
        print(snap[:3000])
    url = run("get", "url")
    title = run("get", "title")
    print("URL_OK" if "accounts.google.com" not in url or "challenge" in url else "STILL_LOGIN")
    print("title_line", title.strip()[:120])
    print("url_line", url.strip()[:180])
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.TimeoutExpired:
        print("登入逾時")
        raise SystemExit(1)
