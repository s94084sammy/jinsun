#!/usr/bin/env bash
# 金孫專用真實 Chrome：已登入的 Google 工作階段。CDP 只從本機與 Docker 橋接進來。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROF="${JINSUN_CHROME_PROFILE:-$ROOT/data/jinsun/chrome-real}"
mkdir -p "$PROF"
chmod 700 "$PROF"

if ! curl -sf http://127.0.0.1:9224/json/version >/dev/null; then
  DISPLAY="${DISPLAY:-:0}" nohup /usr/bin/google-chrome-stable \
    --user-data-dir="$PROF" \
    --remote-debugging-port=9224 \
    --remote-debugging-address=127.0.0.1 \
    --no-first-run \
    --no-default-browser-check \
    --disable-features=Translate \
    --lang=zh-TW \
    "https://docs.google.com/spreadsheets" \
    >/tmp/jinsun-chrome.log 2>&1 &
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    curl -sf http://127.0.0.1:9224/json/version >/dev/null && break
    sleep 1
  done
fi

BRIDGE_IP="${JINSUN_DOCKER_BRIDGE:-172.25.0.1}"
if ! ss -ltn | grep -q "${BRIDGE_IP}:19224"; then
  nohup socat TCP-LISTEN:19224,bind="${BRIDGE_IP}",fork,reuseaddr TCP:127.0.0.1:9224 \
    >/tmp/jinsun-cdp-socat.log 2>&1 &
fi

echo "金孫 Chrome CDP 127.0.0.1:9224 ，Docker 走 ${BRIDGE_IP}:19224"
