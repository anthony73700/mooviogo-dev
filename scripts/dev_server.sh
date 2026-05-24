#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$ROOT_DIR/.runserver.pid"
LOG_FILE="$ROOT_DIR/runserver.log"
PORT="8000"
PYTHON_BIN="/home/debian/.venv/bin/python"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python introuvable: $PYTHON_BIN"
  exit 1
fi

is_running() {
  if [[ -f "$PID_FILE" ]]; then
    local pid
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      return 0
    fi
  fi
  return 1
}

port_pid() {
  ss -ltnp 2>/dev/null | sed -nE "s/.*:${PORT} .*pid=([0-9]+).*/\1/p" | head -n1
}

stop_port_listener() {
  local pid
  pid="$(port_pid)"
  if [[ -z "$pid" ]]; then
    return 0
  fi

  kill "$pid" 2>/dev/null || true
  sleep 1
  if kill -0 "$pid" 2>/dev/null; then
    kill -9 "$pid" 2>/dev/null || true
  fi
}

start_server() {
  stop_port_listener

  if is_running; then
    echo "Serveur deja actif (pid $(cat "$PID_FILE"))."
    return 0
  fi

  cd "$ROOT_DIR"
  nohup "$PYTHON_BIN" manage.py runserver 0.0.0.0:${PORT} --noreload >"$LOG_FILE" 2>&1 < /dev/null &
  local pid=$!
  echo "$pid" > "$PID_FILE"

  sleep 1
  if kill -0 "$pid" 2>/dev/null; then
    echo "Serveur demarre: http://127.0.0.1:${PORT} (pid $pid)"
    return 0
  fi

  echo "Echec du demarrage. Consulte $LOG_FILE"
  rm -f "$PID_FILE"
  return 1
}

stop_server() {
  stop_port_listener

  if ! is_running; then
    echo "Aucun serveur actif."
    rm -f "$PID_FILE"
    return 0
  fi

  local pid
  pid="$(cat "$PID_FILE")"
  kill "$pid" 2>/dev/null || true
  sleep 1

  if kill -0 "$pid" 2>/dev/null; then
    kill -9 "$pid" 2>/dev/null || true
  fi

  rm -f "$PID_FILE"
  echo "Serveur arrete."
}

status_server() {
  if is_running; then
    echo "Actif (pid $(cat "$PID_FILE"))."
  else
    echo "Inactif."
  fi
}

case "${1:-}" in
  start)
    start_server
    ;;
  stop)
    stop_server
    ;;
  restart)
    stop_server
    start_server
    ;;
  status)
    status_server
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status}"
    exit 1
    ;;
esac
