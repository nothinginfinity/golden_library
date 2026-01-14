#!/bin/bash
# Start Universal Watcher daemon

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$HOME/.claude/universal_watcher.pid"
LOG_FILE="$HOME/.claude/logs/universal_watcher.log"

# Create log directory
mkdir -p "$HOME/.claude/logs"

# Check if already running
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "⚠️  Universal Watcher already running (PID: $PID)"
        exit 1
    else
        echo "⚠️  Removing stale PID file"
        rm -f "$PID_FILE"
    fi
fi

# Start daemon
echo "🚀 Starting Universal Watcher..."
nohup python3 "$SCRIPT_DIR/daemons/universal_watcher.py" > "$LOG_FILE" 2>&1 &
PID=$!

# Save PID
echo "$PID" > "$PID_FILE"

echo "✅ Started (PID: $PID)"
echo "📋 Logs: $LOG_FILE"
echo ""
echo "To stop:"
echo "  ./stop_universal_watcher.sh"
echo ""
echo "To view logs:"
echo "  tail -f $LOG_FILE"
