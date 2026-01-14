#!/bin/bash
# Check Auto-Compress Daemon Status

PID_FILE="${HOME}/.claude/auto_compress_daemon.pid"
LOG_FILE="${HOME}/.claude/logs/auto_compress_daemon.log"
LIBRARY_DIR="${HOME}/.claude/conversation_library"

echo "📊 Auto-Compress Daemon Status"
echo "================================"
echo

# Check if running
if [ -f "${PID_FILE}" ]; then
    PID=$(cat "${PID_FILE}")
    if ps -p "${PID}" > /dev/null 2>&1; then
        echo "✅ Status: Running (PID: ${PID})"

        # Get process info
        echo "   Started: $(ps -p ${PID} -o lstart=)"
        echo "   Memory: $(ps -p ${PID} -o rss= | awk '{printf "%.1f MB", $1/1024}')"
        echo
    else
        echo "❌ Status: Stopped (stale PID file)"
        echo
    fi
else
    echo "❌ Status: Not running"
    echo
fi

# Check library
if [ -d "${LIBRARY_DIR}" ]; then
    CONV_COUNT=$(find "${LIBRARY_DIR}/compressed" -name "*.slim.indexed" 2>/dev/null | wc -l | tr -d ' ')
    LIB_SIZE=$(du -sh "${LIBRARY_DIR}" 2>/dev/null | awk '{print $1}')

    echo "📚 Library:"
    echo "   Location: ${LIBRARY_DIR}"
    echo "   Conversations: ${CONV_COUNT}"
    echo "   Size: ${LIB_SIZE}"
    echo
fi

# Show recent log
if [ -f "${LOG_FILE}" ]; then
    echo "📋 Recent Activity:"
    echo "   Log: ${LOG_FILE}"
    echo
    tail -10 "${LOG_FILE}" | sed 's/^/   /'
    echo
fi

echo "Commands:"
echo "   Start:  ./start_daemon.sh"
echo "   Stop:   ./stop_daemon.sh"
echo "   Logs:   tail -f ${LOG_FILE}"
