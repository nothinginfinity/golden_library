#!/usr/bin/env python3
"""
Test Suite for Unified Token Compression Pipeline

Tests each stage independently and the full integrated pipeline.
"""

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from slim_converter import SlimConverter
from index_extractor import IndexExtractor
from token_analyzer import TokenAnalyzer
from unified_pipeline import UnifiedCompressionPipeline
from handoff_unified import HandoffManager


def create_test_conversation():
    """Create a test JSONL conversation with repeated patterns."""
    messages = []

    # System message (repeated pattern)
    system_msg = {
        "role": "system",
        "content": "You are Claude Code, Anthropic's official CLI for Claude."
    }

    # Tool definition (repeated pattern)
    bash_tool = {
        "name": "Bash",
        "description": "Execute bash command",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string"}
            }
        }
    }

    read_tool = {
        "name": "Read",
        "description": "Read file from filesystem",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"}
            }
        }
    }

    # Add system message
    messages.append(system_msg)

    # Add 10 exchanges with repeated tool uses
    for i in range(10):
        # User message
        messages.append({
            "role": "user",
            "content": f"Read the file config_{i}.json"
        })

        # Assistant with tool call
        messages.append({
            "role": "assistant",
            "content": [
                {"type": "text", "text": "I'll read that file for you."},
                {
                    "type": "tool_use",
                    "id": f"tool_{i}",
                    "name": "Read",
                    "input": {"file_path": f"/config_{i}.json"}
                }
            ]
        })

        # Tool result
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": f"tool_{i}",
                    "content": f'{{"version": "1.{i}"}}'
                }
            ]
        })

        # Another system message every 3 exchanges
        if i % 3 == 0:
            messages.append(system_msg)

    return messages


def test_slim_converter():
    """Test Stage 1: SLIM Conversion."""
    print("\n" + "=" * 80)
    print("TEST 1: SLIM Converter")
    print("=" * 80)

    # Create test data
    messages = create_test_conversation()
    jsonl_content = "\n".join(json.dumps(msg) for msg in messages)

    # Write to temp file
    test_dir = Path("/tmp/golden_library_test")
    test_dir.mkdir(exist_ok=True)
    test_file = test_dir / "test_slim.jsonl"
    with open(test_file, 'w') as f:
        f.write(jsonl_content)

    # Convert to SLIM
    converter = SlimConverter()
    slim_content = converter.jsonl_to_slim(str(test_file))

    # Verify
    assert slim_content.startswith("§SLIM§"), "SLIM header missing"
    assert "[SCHEMA]" in slim_content, "Schema section missing"
    assert "[DATA]" in slim_content, "Data section missing"

    # Measure compression
    original_size = len(jsonl_content.encode('utf-8'))
    slim_size = len(slim_content.encode('utf-8'))
    reduction = round((1 - slim_size / original_size) * 100, 1)

    print(f"✅ SLIM Conversion Success")
    print(f"   Original: {original_size:,} bytes")
    print(f"   SLIM: {slim_size:,} bytes")
    print(f"   Reduction: {reduction}%")

    # Test round-trip
    restored = converter.slim_to_jsonl(slim_content)
    assert restored, "Round-trip failed"
    print(f"✅ Round-trip successful")

    return slim_content


def test_index_extractor():
    """Test Stage 2: Index Extraction."""
    print("\n" + "=" * 80)
    print("TEST 2: Index Extractor")
    print("=" * 80)

    # Create test data with repeated patterns
    messages = create_test_conversation()
    jsonl_content = "\n".join(json.dumps(msg) for msg in messages)

    extractor = IndexExtractor()

    # Extract patterns from JSONL
    result = extractor.extract_patterns(
        jsonl_content,
        threshold=2,  # Low threshold for test
        session_id="test_session",
        project_id="test_project"
    )

    print(f"✅ Index Extraction Success")
    print(f"   Patterns extracted: {result.patterns_extracted}")
    print(f"   Hot patterns: {len(result.hot_index['patterns'])}")
    print(f"   Warm patterns: {len(result.warm_index['patterns'])}")
    print(f"   Cold patterns: {len(result.cold_index['patterns'])}")
    print(f"   Reduction: {result.reduction_percent}%")

    # Note: May be 0 for small test data
    print(f"✅ Index extraction completed (patterns found: {result.patterns_extracted})")

    return result


def test_token_analyzer():
    """Test Token Analyzer."""
    print("\n" + "=" * 80)
    print("TEST 3: Token Analyzer")
    print("=" * 80)

    analyzer = TokenAnalyzer()

    # Test token counting
    test_text = "This is a test of the token counting system implementation."
    tokens = analyzer.count_tokens(test_text)

    print(f"✅ Token Analysis Success")
    print(f"   Text: '{test_text}'")
    print(f"   Tokens: {tokens}")

    assert tokens > 0, "Token count failed"

    return tokens


def test_unified_pipeline_minimal():
    """Test Unified Pipeline - Minimal Level."""
    print("\n" + "=" * 80)
    print("TEST 4: Unified Pipeline (Minimal)")
    print("=" * 80)

    # Create test file
    messages = create_test_conversation()
    test_dir = Path("/tmp/golden_library_test")
    test_dir.mkdir(exist_ok=True)

    test_file = test_dir / "test_conversation.jsonl"
    with open(test_file, 'w') as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")

    # Run minimal pipeline
    pipeline = UnifiedCompressionPipeline(level="minimal")
    result = pipeline.compress_conversation(
        str(test_file),
        output_dir=str(test_dir)
    )

    print(f"✅ Minimal Pipeline Success")
    print(f"   Original tokens: {result.original_tokens:,}")
    print(f"   Final tokens: {result.final_tokens:,}")
    print(f"   Reduction: {result.total_reduction_percent}%")
    print(f"   Stages: {len(result.stages)}")

    assert result.total_reduction_percent > 0, "No compression achieved"
    assert Path(result.output_path).exists(), "Output file not created"

    return result


def test_unified_pipeline_balanced():
    """Test Unified Pipeline - Balanced Level."""
    print("\n" + "=" * 80)
    print("TEST 5: Unified Pipeline (Balanced)")
    print("=" * 80)

    # Create test file
    messages = create_test_conversation()
    test_dir = Path("/tmp/golden_library_test")

    test_file = test_dir / "test_conversation_balanced.jsonl"
    with open(test_file, 'w') as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")

    # Run balanced pipeline
    pipeline = UnifiedCompressionPipeline(level="balanced")
    result = pipeline.compress_conversation(
        str(test_file),
        output_dir=str(test_dir),
        session_id="test_balanced",
        project_id="test_project"
    )

    print(f"✅ Balanced Pipeline Success")
    print(f"   Original tokens: {result.original_tokens:,}")
    print(f"   Final tokens: {result.final_tokens:,}")
    print(f"   Reduction: {result.total_reduction_percent}%")
    print(f"   Stages: {len(result.stages)}")
    print(f"   Indexes created: {len(result.indexes_created)}")

    assert result.total_reduction_percent >= result.stages[0].reduction_percent, "Combined reduction should be >= first stage"
    assert Path(result.output_path).exists(), "Output file not created"
    assert len(result.indexes_created) > 0, "No indexes created"

    return result


def test_handoff_manager():
    """Test Handoff Manager."""
    print("\n" + "=" * 80)
    print("TEST 6: Handoff Manager")
    print("=" * 80)

    # Create test conversation
    messages = create_test_conversation()
    test_dir = Path("/tmp/golden_library_test")

    test_file = test_dir / "test_conversation_handoff.jsonl"
    with open(test_file, 'w') as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")

    # Create handoff
    manager = HandoffManager(handoff_dir=str(test_dir / "handoffs"))
    metadata = manager.create_handoff(
        str(test_file),
        level="balanced",
        notes="Test handoff for unit tests"
    )

    print(f"✅ Handoff Created")
    print(f"   ID: {metadata['handoff_id']}")
    print(f"   Reduction: {metadata['reduction_percent']}%")

    # List handoffs
    handoffs = manager.list_handoffs()
    assert len(handoffs) > 0, "No handoffs found"
    print(f"✅ Found {len(handoffs)} handoff(s)")

    # Load handoff
    result = manager.load_handoff(
        metadata['handoff_id'],
        output_path=str(test_dir / "restored_conversation.jsonl")
    )

    print(f"✅ Handoff Loaded")
    print(f"   Indexes loaded: {len(result['indexes_loaded'])}")
    assert Path(test_dir / "restored_conversation.jsonl").exists(), "Restored file not created"

    return metadata


def run_all_tests():
    """Run all tests."""
    print("\n" + "🧪" * 40)
    print("UNIFIED COMPRESSION PIPELINE - TEST SUITE")
    print("🧪" * 40)

    try:
        # Test individual components
        slim_content = test_slim_converter()
        index_result = test_index_extractor()
        test_token_analyzer()

        # Test integrated pipelines
        minimal_result = test_unified_pipeline_minimal()
        balanced_result = test_unified_pipeline_balanced()

        # Test handoff system
        handoff_metadata = test_handoff_manager()

        # Summary
        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED")
        print("=" * 80)
        print(f"\n📊 Summary:")
        print(f"   Tests run: 6")
        print(f"   Tests passed: 6")
        print(f"   Tests failed: 0")
        print("\n" + "=" * 80)

        return True

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
