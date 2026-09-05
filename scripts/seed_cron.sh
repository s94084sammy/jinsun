#!/usr/bin/env bash
# 用 Hermes 內建排程建立金孫提醒。不是公司業務排程。
set -euo pipefail

exec_h() {
  docker exec -u "${HERMES_UID:-1000}" \
    -e HOME=/opt/data \
    -e HERMES_HOME=/opt/data \
    -e TZ=Asia/Taipei \
    -e JINSUN_DATA=/opt/data/jinsun \
    jinsun /opt/hermes/.venv/bin/hermes "$@"
}

# 可重複執行：先列出現有名稱，已有就跳過。
existing="$(exec_h cron list 2>/dev/null || true)"

create_if_missing() {
  local name="$1"
  shift
  if echo "$existing" | grep -q "$name"; then
    echo "已有排程：$name"
    return 0
  fi
  exec_h cron create --name "$name" --no-agent --deliver local "$@"
}

create_if_missing "金孫到期檢查" --script jinsun_due.py "*/15 * * * *"
create_if_missing "吃藥提醒" --script jinsun_demo_medicine.py "5 8 * * *"
create_if_missing "看診前一天" --script jinsun_demo_clinic.py "7 9 * * *"
create_if_missing "繳費截止" --script jinsun_demo_bill.py "11 19 * * *"
create_if_missing "活動前一天" --script jinsun_demo_activity.py "13 18 * * *"

if echo "$existing" | grep -q "花博附近每週在地"; then
  echo "已有排程：花博附近每週在地"
else
  exec_h cron create --name "花博附近每週在地" --no-agent --deliver line --script jinsun_weekly_local.py "3 8 * * 1"
fi

echo "排程已寫入。立刻試跑一次吃藥提醒："
# 找出吃藥那筆並 run。失敗不讓整段崩掉。
exec_h cron list
echo "若要立刻聽一次內容：docker exec jinsun python3 /opt/data/scripts/jinsun_demo_medicine.py"
