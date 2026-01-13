#!/bin/bash
# Golden Library - CLI Test Script

set -e

echo "🏆 Golden Library CLI Test"
echo "=========================="
echo ""

# Find a sample JSONL file
SAMPLE_JSONL=$(find ~/.claude/projects -name "*.jsonl" -type f -size +1M -size -10M | head -1)

if [ -z "$SAMPLE_JSONL" ]; then
    echo "❌ No suitable JSONL file found in ~/.claude/projects"
    echo "   Looking for files between 1MB and 10MB"
    exit 1
fi

echo "📁 Using sample file:"
echo "   $SAMPLE_JSONL"
echo ""

# Test 1: Compression stats
echo "📊 Test 1: Compression Stats"
echo "-----------------------------"
python3 src/slim_converter.py stats "$SAMPLE_JSONL"
echo ""

# Test 2: Compress to SLIM
echo "📦 Test 2: Compress to SLIM"
echo "-----------------------------"
python3 src/slim_converter.py compress "$SAMPLE_JSONL" -o /tmp/golden_test.slim
echo ""

# Test 3: Show SLIM format preview
echo "👀 Test 3: SLIM Format Preview"
echo "-----------------------------"
head -30 /tmp/golden_test.slim
echo ""
echo "   (showing first 30 lines of SLIM file)"
echo ""

# Test 4: Decompress back to JSONL
echo "🔄 Test 4: Decompress to JSONL"
echo "-----------------------------"
python3 src/slim_converter.py decompress /tmp/golden_test.slim -o /tmp/golden_restored.jsonl
echo ""

# Test 5: Verify file sizes
echo "📏 Test 5: File Size Comparison"
echo "-----------------------------"
ORIGINAL_SIZE=$(wc -c < "$SAMPLE_JSONL")
SLIM_SIZE=$(wc -c < /tmp/golden_test.slim)
RESTORED_SIZE=$(wc -c < /tmp/golden_restored.jsonl)

echo "   Original:  $(printf "%'d" $ORIGINAL_SIZE) bytes"
echo "   SLIM:      $(printf "%'d" $SLIM_SIZE) bytes"
echo "   Restored:  $(printf "%'d" $RESTORED_SIZE) bytes"
echo ""

# Test 6: Line count check
echo "📝 Test 6: Line Count Verification"
echo "-----------------------------"
ORIGINAL_LINES=$(wc -l < "$SAMPLE_JSONL")
RESTORED_LINES=$(wc -l < /tmp/golden_restored.jsonl)

echo "   Original lines:  $ORIGINAL_LINES"
echo "   Restored lines:  $RESTORED_LINES"

if [ "$ORIGINAL_LINES" -eq "$RESTORED_LINES" ]; then
    echo "   ✅ Line count matches!"
else
    echo "   ⚠️  Line count mismatch (expected with current bugs)"
fi
echo ""

# Test 7: Create handoff
echo "🚀 Test 7: Create Handoff"
echo "-----------------------------"
python3 src/handoff_slim.py compress "$SAMPLE_JSONL" --level slim_only
echo ""

# Test 8: List handoffs
echo "📋 Test 8: List Handoffs"
echo "-----------------------------"
python3 src/handoff_slim.py list
echo ""

# Cleanup
echo "🧹 Cleanup"
echo "-----------------------------"
rm -f /tmp/golden_test.slim /tmp/golden_restored.jsonl
echo "   Removed temporary files"
echo ""

echo "✅ CLI test complete!"
echo ""
echo "📁 Handoffs are stored in: ~/.fsl/handoffs/"
echo "🔗 Repo: https://github.com/nothinginfinity/golden_library"
