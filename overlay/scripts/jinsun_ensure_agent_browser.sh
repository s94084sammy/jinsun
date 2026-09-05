#!/bin/sh
# 把 agent-browser 與 Chrome 放到金孫獨立資料目錄。不准關宿主瀏覽器個人資料。
set -eu
ROOT="${HERMES_HOME:-/opt/data}"
BIN_DIR="$ROOT/.local/bin"
DEST="$BIN_DIR/agent-browser"
CACHE="$ROOT/.agent-browser/browsers"
HOME_CACHE="$ROOT/home/.agent-browser"
mkdir -p "$BIN_DIR" "$ROOT/home"

if [ ! -x "$DEST" ]; then
  found="$(find "$ROOT/home/.npm" "$ROOT/browser-cli" -name 'agent-browser-linux-x64' 2>/dev/null | head -n 1 || true)"
  if [ -n "${found:-}" ] && [ -f "$found" ]; then
    cp "$found" "$DEST"
    chmod +x "$DEST"
  else
    mkdir -p "$ROOT/browser-cli"
    cd "$ROOT/browser-cli"
    npm install --no-fund --no-audit agent-browser >/tmp/jinsun-npm-agent-browser.log 2>&1
    linux="$(find "$ROOT/browser-cli" -name 'agent-browser-linux-x64' | head -n 1)"
    cp "$linux" "$DEST"
    chmod +x "$DEST"
  fi
fi

if [ ! -d "$CACHE/chrome-"* ] 2>/dev/null && ! ls "$CACHE"/chrome-* >/dev/null 2>&1; then
  HOME="$ROOT" "$DEST" install
fi

mkdir -p "$HOME_CACHE"
if [ -d "$CACHE" ] && [ ! -e "$HOME_CACHE/browsers" ]; then
  ln -s "$CACHE" "$HOME_CACHE/browsers"
fi
