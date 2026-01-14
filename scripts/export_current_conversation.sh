#!/bin/bash
# Export Current Claude Code Conversation
#
# This script exports your current Claude Code conversation to JSONL format
# so it can be compressed with the golden_library pipeline.
#
# Usage:
#   ./scripts/export_current_conversation.sh
#   ./scripts/export_current_conversation.sh myproject
#   ./scripts/export_current_conversation.sh myproject "Feature implementation"

set -e

PROJECT="${1:-general}"
TITLE="${2:-Claude Code Session}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_DIR="${HOME}/.claude/conversation_library/raw"
OUTPUT_FILE="${OUTPUT_DIR}/session_${PROJECT}_${TIMESTAMP}.jsonl"

echo "🔍 Exporting current Claude Code conversation..."
echo

# Create output directory
mkdir -p "${OUTPUT_DIR}"

# Try to find Claude Code conversation history
# Location varies by installation

# Option 1: Standard config location
CLAUDE_CONFIG="${HOME}/.config/Claude Code"

# Option 2: Cache location
CLAUDE_CACHE="${HOME}/.cache/claude-code"

# Option 3: Application support (macOS)
CLAUDE_APP_SUPPORT="${HOME}/Library/Application Support/Claude Code"

echo "📁 Checking for conversation history..."

# Function to find most recent conversation file
find_recent_conversation() {
    local search_dir="$1"
    if [ -d "$search_dir" ]; then
        find "$search_dir" -name "*.json" -o -name "*.jsonl" 2>/dev/null | \
            xargs ls -t 2>/dev/null | head -1
    fi
}

# Try to find the most recent conversation
CONVERSATION_FILE=""

for dir in "$CLAUDE_CONFIG" "$CLAUDE_CACHE" "$CLAUDE_APP_SUPPORT"; do
    FOUND=$(find_recent_conversation "$dir")
    if [ -n "$FOUND" ]; then
        CONVERSATION_FILE="$FOUND"
        echo "✅ Found: $CONVERSATION_FILE"
        break
    fi
done

if [ -z "$CONVERSATION_FILE" ]; then
    echo "❌ Could not find Claude Code conversation history"
    echo
    echo "💡 Manual export:"
    echo "   1. In Claude Code, save your conversation"
    echo "   2. Place the file in: ${OUTPUT_DIR}/"
    echo "   3. Run: python3 scripts/compress_all_conversations.py --session-dir ${OUTPUT_DIR}"
    exit 1
fi

# Copy to output location
cp "$CONVERSATION_FILE" "$OUTPUT_FILE"

echo "✅ Exported to: $OUTPUT_FILE"
echo

# Compress it immediately
echo "📦 Compressing conversation..."
echo

cd "$(dirname "$0")/.."

python3 scripts/compress_all_conversations.py --session-dir "${OUTPUT_DIR}"

echo
echo "✅ Done!"
echo
echo "💡 Next steps:"
echo "   1. Search: python3 scripts/search_library.py 'your query'"
echo "   2. View: cat ${OUTPUT_FILE}"
echo "   3. Stats: python3 scripts/compress_all_conversations.py --stats"
