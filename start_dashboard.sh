#!/bin/bash
# Start Claude Control Center Dashboard

cd "$(dirname "$0")"

echo "🚀 Starting Claude Control Center Dashboard..."
echo ""

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is required but not found"
    exit 1
fi

# Start the dashboard server
python3 dashboard_server.py 8080 &
SERVER_PID=$!

# Wait a moment for server to start
sleep 2

# Check if server is running
if ps -p $SERVER_PID > /dev/null 2>&1; then
    echo "✅ Dashboard server started (PID: $SERVER_PID)"
    echo ""
    echo "📊 Dashboard available at: http://localhost:8080"
    echo ""
    echo "Opening in browser..."

    # Open in default browser
    if command -v open &> /dev/null; then
        open http://localhost:8080
    elif command -v xdg-open &> /dev/null; then
        xdg-open http://localhost:8080
    fi

    echo ""
    echo "Server PID saved to: ~/.claude/dashboard_server.pid"
    echo $SERVER_PID > ~/.claude/dashboard_server.pid

    echo ""
    echo "To stop the server, run: ./stop_dashboard.sh"
    echo "Or press Ctrl+C in the server terminal"
else
    echo "❌ Error: Failed to start dashboard server"
    exit 1
fi
