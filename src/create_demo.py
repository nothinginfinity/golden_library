#!/usr/bin/env python3
"""
Create demo JSONL file showing index-based compression potential.

This generates a synthetic conversation with many repeated tool definitions,
system messages, and common patterns to demonstrate maximum compression.
"""

import json
from pathlib import Path

# Common tool definition (would appear in cold index)
BASH_TOOL = {
    "name": "Bash",
    "description": "Execute bash command",
    "parameters": {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The command to execute"},
            "timeout": {"type": "number", "description": "Optional timeout in ms"}
        },
        "required": ["command"]
    }
}

READ_TOOL = {
    "name": "Read",
    "description": "Read file from filesystem",
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Absolute path to file"},
            "offset": {"type": "number", "description": "Line offset"},
            "limit": {"type": "number", "description": "Number of lines"}
        },
        "required": ["file_path"]
    }
}

EDIT_TOOL = {
    "name": "Edit",
    "description": "Edit file with string replacement",
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {"type": "string"},
            "old_string": {"type": "string"},
            "new_string": {"type": "string"}
        },
        "required": ["file_path", "old_string", "new_string"]
    }
}

# System message template (would appear in warm index)
SYSTEM_MSG = {
    "role": "system",
    "content": "You are Claude Code, Anthropic's official CLI. You help with software engineering tasks."
}

def create_demo_conversation(output_path: str, num_exchanges: int = 10):
    """Create demo conversation with repeated structures."""

    messages = []

    # Initial system message
    messages.append({"role": "system", "content": SYSTEM_MSG["content"]})

    # Simulate multiple exchanges with tool use
    for i in range(num_exchanges):
        # User message
        messages.append({
            "role": "user",
            "content": f"Read the file config_{i}.json and update the version field"
        })

        # Assistant response with tool calls
        messages.append({
            "role": "assistant",
            "content": [
                {"type": "text", "text": f"I'll read the config file for you."},
                {
                    "type": "tool_use",
                    "id": f"tool_{i}_1",
                    "name": "Read",
                    "input": {
                        "file_path": f"/path/to/config_{i}.json"
                    }
                }
            ]
        })

        # Tool result
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": f"tool_{i}_1",
                    "content": f'{{"version": "1.{i}", "name": "app"}}'
                }
            ]
        })

        # Assistant edit
        messages.append({
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Now I'll update the version."},
                {
                    "type": "tool_use",
                    "id": f"tool_{i}_2",
                    "name": "Edit",
                    "input": {
                        "file_path": f"/path/to/config_{i}.json",
                        "old_string": f'"version": "1.{i}"',
                        "new_string": f'"version": "1.{i+1}"'
                    }
                }
            ]
        })

        # Another system reminder (repeated pattern)
        if i % 3 == 0:
            messages.append({
                "role": "system",
                "content": "Remember to follow best practices and test your changes."
            })

    # Also add tool definitions in a metadata section (as they'd appear in real conversations)
    conversation_data = {
        "metadata": {
            "tools": [BASH_TOOL, READ_TOOL, EDIT_TOOL]
        },
        "messages": messages
    }

    # Write as JSONL (one message per line for simulation)
    output = Path(output_path)
    with open(output, 'w') as f:
        # Write tool definitions multiple times (simulating how they appear in API calls)
        for _ in range(5):
            f.write(json.dumps({"type": "tool_definition", "tool": BASH_TOOL}) + "\n")
            f.write(json.dumps({"type": "tool_definition", "tool": READ_TOOL}) + "\n")
            f.write(json.dumps({"type": "tool_definition", "tool": EDIT_TOOL}) + "\n")

        # Write all messages
        for msg in messages:
            f.write(json.dumps(msg) + "\n")

    print(f"✅ Created demo conversation: {output}")
    print(f"   Messages: {len(messages)}")
    print(f"   Tool definitions: 15 (5 sets of 3 tools)")
    print(f"   File size: {output.stat().st_size:,} bytes")

if __name__ == "__main__":
    create_demo_conversation("/tmp/demo_conversation.jsonl", num_exchanges=20)
