#!/bin/bash
# Install Auto-Compress Daemon for Auto-Start
#
# This sets up the daemon to start automatically on boot (macOS launchd)

set -e

DAEMON_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_FILE="${DAEMON_DIR}/com.claude.autocompress.plist"
LAUNCHD_DIR="${HOME}/Library/LaunchAgents"
INSTALLED_PLIST="${LAUNCHD_DIR}/com.claude.autocompress.plist"

echo "🔧 Installing Auto-Compress Daemon for Auto-Start"
echo

# Create LaunchAgents directory
mkdir -p "${LAUNCHD_DIR}"

# Copy plist
cp "${PLIST_FILE}" "${INSTALLED_PLIST}"

echo "✅ Installed plist to: ${INSTALLED_PLIST}"

# Load the daemon
launchctl unload "${INSTALLED_PLIST}" 2>/dev/null || true
launchctl load "${INSTALLED_PLIST}"

echo "✅ Daemon loaded and will start on boot"
echo

# Check status
sleep 2
launchctl list | grep com.claude.autocompress && echo "✅ Daemon is running" || echo "⚠️  Daemon not running yet"

echo
echo "📋 Management Commands:"
echo "   Status:     launchctl list | grep com.claude.autocompress"
echo "   Stop:       launchctl unload ${INSTALLED_PLIST}"
echo "   Start:      launchctl load ${INSTALLED_PLIST}"
echo "   Logs:       tail -f ~/.claude/logs/auto_compress_daemon.log"
echo "   Uninstall:  ./uninstall_autostart.sh"
