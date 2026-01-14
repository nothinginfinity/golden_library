#!/bin/bash
# Stop Auto-Compress Daemon

PID_FILE="${HOME}/.claude/auto_compress_daemon.pid"

if [ ! -f "${PID_FILE}" ]; then
    echo "❌ Daemon not running (no PID file)"
    exit 1
fi

PID=$(cat "${PID_FILE}")

if ! ps -p "${PID}" > /dev/null 2>&1; then
    echo "❌ Daemon not running (stale PID file)"
    rm "${PID_FILE}"
    exit 1
fi

echo "🛑 Stopping daemon (PID: ${PID})..."
kill "${PID}"

# Wait for process to stop
for i in {1..10}; do
    if ! ps -p "${PID}" > /dev/null 2>&1; then
        echo "✅ Daemon stopped"
        rm "${PID_FILE}"
        exit 0
    fi
    sleep 0.5
done

# Force kill if still running
if ps -p "${PID}" > /dev/null 2>&1; then
    echo "⚠️  Force killing daemon..."
    kill -9 "${PID}"
    rm "${PID_FILE}"
    echo "✅ Daemon stopped (forced)"
fi
