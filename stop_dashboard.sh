#!/bin/bash
# Stop Claude Control Center Dashboard

PID_FILE="$HOME/.claude/dashboard_server.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "⚠️  Dashboard server PID file not found"
    echo "Server may not be running, or was started manually"
    exit 1
fi

PID=$(cat "$PID_FILE")

if ps -p $PID > /dev/null 2>&1; then
    echo "🛑 Stopping dashboard server (PID: $PID)..."
    kill $PID

    # Wait for process to stop
    sleep 1

    if ps -p $PID > /dev/null 2>&1; then
        echo "⚠️  Process didn't stop gracefully, forcing..."
        kill -9 $PID
    fi

    rm "$PID_FILE"
    echo "✅ Dashboard server stopped"
else
    echo "⚠️  Dashboard server (PID: $PID) not running"
    rm "$PID_FILE"
fi
