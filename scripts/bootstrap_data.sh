#!/usr/bin/env bash
# 把金孫的靈魂、設定、技能、排程腳本放進獨立 ./data。不碰 ~/.hermes。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA="$ROOT/data"
OVERLAY="$ROOT/overlay"

mkdir -p "$DATA/jinsun" "$DATA/skills" "$DATA/scripts" "$DATA/home" "$DATA/cron" "$DATA/.local/bin"

cp "$OVERLAY/SOUL.md" "$DATA/SOUL.md"
cp "$OVERLAY/config.yaml" "$DATA/config.yaml"

# 只放金孫技能。其它目錄（含 leftover autonomous-ai-agents）一律清掉。
mkdir -p "$DATA/skills"
find "$DATA/skills" -mindepth 1 -maxdepth 1 ! -name '.hub' -exec rm -rf {} +
cp -a "$OVERLAY/skills/." "$DATA/skills/"
cp "$OVERLAY/no-bundled-skills" "$DATA/.no-bundled-skills"
mkdir -p "$DATA/hooks"
rm -rf "$DATA/hooks/jinsun-inbound-gate"
cp -a "$OVERLAY/hooks/jinsun-inbound-gate" "$DATA/hooks/"

cp -a "$OVERLAY/scripts/." "$DATA/scripts/"
chmod +x "$DATA/scripts/"*.py "$DATA/scripts/"*.sh 2>/dev/null || true

if [[ ! -f "$ROOT/.env" ]]; then
  cp "$OVERLAY/env.example" "$ROOT/.env"
fi
if [[ ! -f "$DATA/.env" ]]; then
  cp "$OVERLAY/env.example" "$DATA/.env"
  chmod 600 "$DATA/.env"
fi

# 閘道本機控制面金鑰：沒有就產生，已有就保留。
if ! grep -q '^API_SERVER_KEY=..*' "$DATA/.env" 2>/dev/null; then
  key="$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  printf '\nAPI_SERVER_KEY=%s\n' "$key" >> "$DATA/.env"
fi

# 種子示範活動與提醒（本機 Python，容器起來後也會再補一次）
export JINSUN_DATA="$DATA/jinsun"
python3 "$OVERLAY/mcp/jinsun_mcp.py" --seed >/dev/null

echo "金孫資料目錄已準備：$DATA"
echo "下一步：docker compose up -d"
