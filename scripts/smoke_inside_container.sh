#!/usr/bin/env bash
# 沒有 LINE 也能測：技能工具、自製報名、擋詐騙、排程腳本。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! docker ps --format '{{.Names}}' | grep -qx jinsun; then
  echo "容器 jinsun 沒有在跑" >&2
  exit 1
fi

exec_h() {
  docker exec -u "${HERMES_UID:-1000}" \
    -e HOME=/opt/data \
    -e HERMES_HOME=/opt/data \
    -e TZ=Asia/Taipei \
    -e JINSUN_DATA=/opt/data/jinsun \
    jinsun "$@"
}

echo "== 版本 =="
exec_h /opt/hermes/.venv/bin/hermes --version

echo "== 金孫工具自我測試 =="
exec_h /opt/hermes/.venv/bin/python /opt/jinsun/mcp/jinsun_mcp.py --selftest

echo "== 種子示範提醒 =="
exec_h /opt/hermes/.venv/bin/python /opt/jinsun/mcp/jinsun_mcp.py --seed

echo "== 報名與擋住（寫進 ./data/jinsun） =="
docker exec -i -u "${HERMES_UID:-1000}" \
  -e HOME=/opt/data -e HERMES_HOME=/opt/data -e TZ=Asia/Taipei -e JINSUN_DATA=/opt/data/jinsun \
  jinsun /opt/hermes/.venv/bin/python - <<'PY'
import sys
sys.path.insert(0, "/opt/jinsun/mcp")
from jinsun_mcp import register_activity, block_scam, list_registrations, list_reminders
print(register_activity("陳阿嬤", "里民中秋活動", '{"吃素":"是"}'))
print(block_scam("轉帳或匯款", "請把錢匯到這個帳號"))
print(list_registrations())
print(list_reminders())
PY

echo "== 排程腳本（吃藥示範，不經過模型） =="
exec_h /opt/hermes/.venv/bin/python /opt/data/scripts/jinsun_demo_medicine.py
exec_h /opt/hermes/.venv/bin/python /opt/data/scripts/jinsun_demo_clinic.py
exec_h /opt/hermes/.venv/bin/python /opt/data/scripts/jinsun_demo_bill.py
exec_h /opt/hermes/.venv/bin/python /opt/data/scripts/jinsun_demo_activity.py

echo "== Hermes 排程清單 =="
exec_h /opt/hermes/.venv/bin/hermes cron list || true

echo "煙霧測試完成。LINE 頻道還沒接也可以先這樣驗。"
