#!/bin/bash
# Start Auto-Compress Daemon
#
# Starts the background daemon that auto-compresses Claude Code conversations.
# Runs continuously and restarts on failure.

set -e

DAEMON_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="${HOME}/.claude/logs"
PID_FILE="${HOME}/.claude/auto_compress_daemon.pid"

mkdir -p "${LOG_DIR}"

# Check if already running
if [ -f "${PID_FILE}" ]; then
    OLD_PID=$(cat "${PID_FILE}")
    if ps -p "${OLD_PID}" > /dev/null 2>&1; then
        echo "✅ Daemon already running (PID: ${OLD_PID})"
        echo "   To restart: kill ${OLD_PID} && $0"
        exit 0
    fi
fi

echo "🚀 Starting Auto-Compress Daemon..."

# Install watchdog if needed
if ! python3 -c "import watchdog" 2>/dev/null; then
    echo "📦 Installing watchdog..."
    pip3 install watchdog
fi

# Start daemon in background
nohup python3 "${DAEMON_DIR}/auto_compress_daemon.py" \
    > "${LOG_DIR}/auto_compress_daemon.log" 2>&1 &

DAEMON_PID=$!
echo "${DAEMON_PID}" > "${PID_FILE}"

echo "✅ Daemon started (PID: ${DAEMON_PID})"
echo "   Log: ${LOG_DIR}/auto_compress_daemon.log"
echo "   Status: tail -f ${LOG_DIR}/auto_compress_daemon.log"
echo "   Stop: kill ${DAEMON_PID}"
echo

# Show initial output
sleep 2
tail -20 "${LOG_DIR}/auto_compress_daemon.log"
