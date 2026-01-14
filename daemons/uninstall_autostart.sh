#!/bin/bash
# Uninstall Auto-Compress Daemon from Auto-Start

INSTALLED_PLIST="${HOME}/Library/LaunchAgents/com.claude.autocompress.plist"

if [ ! -f "${INSTALLED_PLIST}" ]; then
    echo "❌ Daemon not installed"
    exit 1
fi

echo "🗑️  Uninstalling Auto-Compress Daemon..."

# Unload
launchctl unload "${INSTALLED_PLIST}" 2>/dev/null || true

# Remove plist
rm "${INSTALLED_PLIST}"

echo "✅ Daemon uninstalled"
echo "   (You can reinstall with: ./install_autostart.sh)"
