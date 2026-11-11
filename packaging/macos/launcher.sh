#!/bin/bash
set -u

APP_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND="$APP_ROOT/Contents/Resources/backend/AutohomeSpecExporter"
DATA_DIR="$HOME/Library/Application Support/AutohomeSpecExporter"
LOG_DIR="$DATA_DIR/logs"
PORT_FILE="$DATA_DIR/runtime_port.txt"
LOG_FILE="$LOG_DIR/launcher.log"
FALLBACK_PORT="8765"

mkdir -p "$LOG_DIR"

read_port() {
  if [ -f "$PORT_FILE" ]; then
    tr -dc '0-9' < "$PORT_FILE" 2>/dev/null
  fi
}

ready() {
  local port="$1"
  [ -n "$port" ] || return 1
  /usr/bin/curl -fsS --max-time 1 "http://127.0.0.1:${port}/api/health" >/dev/null 2>&1 || return 1
  /usr/bin/curl -fsS --max-time 1 "http://127.0.0.1:${port}/" >/dev/null 2>&1 || return 1
}

open_page() {
  /usr/bin/open "http://127.0.0.1:$1"
}

PORT="$(read_port)"
if ready "$PORT"; then
  open_page "$PORT"
  exit 0
fi

if ready "$FALLBACK_PORT"; then
  open_page "$FALLBACK_PORT"
  exit 0
fi

# Start the Python backend detached from this short-lived launcher.
nohup "$BACKEND" >> "$LOG_FILE" 2>&1 </dev/null &

for _ in $(seq 1 60); do
  PORT="$(read_port)"
  if ready "$PORT"; then
    open_page "$PORT"
    exit 0
  fi
  if ready "$FALLBACK_PORT"; then
    open_page "$FALLBACK_PORT"
    exit 0
  fi
  sleep 0.25
done

/usr/bin/osascript -e 'display alert "汽车之家配置采集器启动失败" message "请重新安装应用，或查看 ~/Library/Application Support/AutohomeSpecExporter/logs 中的日志。" as critical'
exit 1
