#!/usr/bin/env bash
# ChatGPT 或 Codex 訂閱登入（裝置碼）。不要 API 金鑰。不要複製公司 auth.json。
set -euo pipefail
docker exec -it -u "${HERMES_UID:-1000}" \
  -e HOME=/opt/data \
  -e HERMES_HOME=/opt/data \
  -e PYTHONUNBUFFERED=1 \
  jinsun /opt/hermes/.venv/bin/hermes auth add openai-codex --type oauth --no-browser --label jinsun
echo "完成後可再執行：docker exec -u 1000 -e HOME=/opt/data -e HERMES_HOME=/opt/data jinsun /opt/hermes/.venv/bin/hermes model"
echo "選 ChatGPT or Codex Subscription。"
