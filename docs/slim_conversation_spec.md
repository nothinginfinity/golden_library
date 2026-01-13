# SLIM Conversation Format Specification v1.0

## Purpose
Schema-once lossless format for Claude Code JSONL conversations.
Reduces file size by ~50% before applying additional compression.

## Problem
Claude Code JSONL files repeat keys on every line:
```json
{"type":"user","uuid":"abc","timestamp":"2025-12-31T08:58:02.855Z","sessionId":"d12906","message":{"role":"user","content":"hi"}}
{"type":"assistant","uuid":"def","timestamp":"2025-12-31T08:58:10.802Z","sessionId":"d12906","message":{"role":"assistant","content":"Hello"}}
```

Keys `type`, `uuid`, `timestamp`, `sessionId`, `message` are repeated every line.

## Solution: SLIM Format

### Structure
```
§SLIM§ v1
[SCHEMA]
field_names|field_types|nested_schemas
---
[DATA]
value1|value2|value3
value1|value2|value3
---
[META]
original_lines: N
compression: schema-once
format: JSONL→SLIM
§/SLIM§
```

### Example

**Original JSONL (365 chars)**:
```json
{"type":"queue-operation","operation":"dequeue","timestamp":"2025-12-31T08:58:02.463Z","sessionId":"d1290607"}
{"type":"user","uuid":"9417eaf4","parentUuid":null,"timestamp":"2025-12-31T08:58:02.855Z","sessionId":"d1290607","message":{"role":"user","content":"say hi"}}
{"type":"assistant","uuid":"8db04b1b","parentUuid":"9417eaf4","timestamp":"2025-12-31T08:58:10.802Z","sessionId":"d1290607","message":{"role":"assistant","content":"Hi!"}}
```

**SLIM Format (189 chars - 48% reduction)**:
```
§SLIM§ v1
[SCHEMA]
type|operation|timestamp|sessionId|uuid|parentUuid|message.role|message.content
str|str|iso|str|str|str|str|str
---
[DATA]
queue-operation|dequeue|2025-12-31T08:58:02.463Z|d1290607||||
user||2025-12-31T08:58:02.855Z|d1290607|9417eaf4|null|user|say hi
assistant||2025-12-31T08:58:10.802Z|d1290607|8db04b1b|9417eaf4|assistant|Hi!
---
[META]
lines:3
§/SLIM§
```

## Field Type Codes

| Code | Type | Example | Notes |
|------|------|---------|-------|
| `str` | String | "hello" | Default type |
| `int` | Integer | 42 | |
| `float` | Float | 3.14 | |
| `bool` | Boolean | true/false | |
| `iso` | ISO Timestamp | 2025-12-31T08:58:02.463Z | |
| `json` | JSON object | {...} | For complex nested data |
| `null` | Null value | null | |
| `arr` | Array | [...] | |

## Nested Object Handling

Nested objects use dot notation in schema:
```
message.role|message.content|message.usage.input_tokens
```

Complex nested objects that can't be flattened use `json` type:
```
message.usage|message.content
json|str
{"input_tokens":1,"output_tokens":119}|Hello world
```

## Empty/Null Values

- Empty string: `||` (two consecutive pipes)
- Null: `null`
- Missing field: Use empty between pipes

## Escaping

Values containing pipe `|` are JSON-escaped:
```
"Hello | World" → "Hello \| World"
```

Or use JSON encoding for complex strings:
```
message.content
json
"Complex text with\n|special\nchars"
```

## Compression Pipeline

```
JSONL (100%)
  ↓
SLIM (50%)         ← Structural deduplication (this spec)
  ↓
[Choose based on content]
  ├─→ V4Z (20%)    ← Mixed code/text
  ├─→ FSL (15%)    ← Prose-heavy
  └─→ ZTPCF (12%)  ← Tool/structured data heavy
```

## Decompression Algorithm

```python
def jsonl_to_slim(jsonl_path: str) -> str:
    # 1. Parse all lines
    # 2. Extract all unique keys (flattened)
    # 3. Build schema row
    # 4. Build data rows
    # 5. Return SLIM format
    pass

def slim_to_jsonl(slim_content: str) -> str:
    # 1. Parse SLIM sections
    # 2. Parse schema
    # 3. For each data row:
    #    - Zip with schema
    #    - Reconstruct nested objects
    #    - Emit JSON line
    pass
```

## Format Goals

- **Lossless**: Perfect reconstruction of original JSONL
- **Fast**: Simple pipe-delimited parsing
- **Readable**: Human can scan data rows
- **Compressible**: Further compression with V4/FSL/ZTPCF

## Implementation Files

1. `/Users/kanelawaccount/ztgi/phi_proxy/slim_converter.py` - Core converter
2. `/Users/kanelawaccount/ztgi/phi_proxy/handoff_slim.py` - Handoff integration
3. `/Users/kanelawaccount/ztgi/qastone-mcp-twin/static/compression_ui.html` - UI component

---

*Spec Version: 1.0*
*Author: Cairn*
*Date: 2026-01-13*
