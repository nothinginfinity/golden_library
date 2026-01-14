#!/bin/bash
# Stop Universal Watcher daemon

PID_FILE="$HOME/.claude/universal_watcher.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "⚠️  Universal Watcher not running (no PID file)"
    exit 1
fi

PID=$(cat "$PID_FILE")

if ! ps -p "$PID" > /dev/null 2>&1; then
    echo "⚠️  Process not running (stale PID file)"
    rm -f "$PID_FILE"
    exit 1
fi

echo "🛑 Stopping Universal Watcher (PID: $PID)..."
kill "$PID"

# Wait for process to stop (max 10 seconds)
for i in {1..10}; do
    if ! ps -p "$PID" > /dev/null 2>&1; then
        echo "✅ Stopped"
        rm -f "$PID_FILE"
        exit 0
    fi
    sleep 1
done

# Force kill if still running
echo "⚠️  Process didn't stop gracefully, forcing..."
kill -9 "$PID"
rm -f "$PID_FILE"
echo "✅ Stopped (forced)"
