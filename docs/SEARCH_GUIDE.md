# Search Guide: Selective Decompression

Complete guide to searching compressed conversations without full decompression.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [CLI Usage](#cli-usage)
- [Python API](#python-api)
- [Search Strategies](#search-strategies)
- [Performance Optimization](#performance-optimization)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)

## Overview

### What is Selective Decompression?

Selective decompression allows you to search and access compressed conversations without loading the entire content into memory. This dramatically reduces token costs for search operations.

**Traditional approach:**
```
Compressed File (20M tokens compressed to 10M)
    ↓
Full Decompression (load all indexes, resolve all $refs)
    ↓
Search (10M tokens processed)
    ↓
Cost: $30 @ $3/M tokens
```

**Selective approach:**
```
Compressed File (20M tokens compressed to 10M)
    ↓
Search Indexes (50K tokens for index patterns)
    ↓
Find Matches (scan file, 100K tokens)
    ↓
Preview Matches (extract context, 200K tokens)
    ↓
Cost: $1.05 @ $3/M tokens (96.5% savings!)
```

### Key Concepts

**$refs**: References to patterns stored in index files
- Format: `"$tier#hash"` (e.g., `"$cold#abc123"`)
- Tiers: hot (session), warm (project), cold (global)

**Indexes**: Files containing reusable patterns
- Location: `~/.claude/indexes/`
- Structure: `{patterns: {$ref_id: {content, category, occurrences}}}`

**Selective Resolution**: Resolving only specific $refs, leaving others as-is
- Load only needed patterns
- Replace only requested $refs
- Keep rest compressed

## Quick Start

### Installation

```bash
cd ~/ztgi/golden_library

# Verify dependencies
python3 -c "import tiktoken; print('✅ Ready')"

# Run tests
python3 tests/test_selective_decompression.py
```

### Your First Search

```bash
# Search for "authentication" in handoff files
python3 src/search_cli.py search "authentication" \
    --directory ~/.fsl/handoffs \
    --context 5
```

Expected output:
```
🔍 Searching for 'authentication'...

============================================================
Search Results: 'authentication'
============================================================

📊 Summary:
  Total matches: 3
  Files searched: 10
  Tokens used: 75,000
  Full decompress: 2,000,000 tokens
  Tokens saved: 1,925,000 (96.3%)
  Search time: 234.5ms

🎯 Matches:

[0] handoff_abc123.slim.indexed:45
    Ref: $cold#auth001
    >>> User: How does authentication work?

[1] handoff_def456.slim.indexed:123
    >>> System: Authentication system initialized
...
```

## CLI Usage

### Search Command

```bash
python3 src/search_cli.py search QUERY [options]
```

**Required:**
- `QUERY`: Search term (case-insensitive by default)

**File Selection (pick one):**
- `--files FILE [FILE ...]`: Specific files to search
- `--directory DIR`: Search all files in directory

**Options:**
- `--pattern PATTERN`: File pattern for directory search (default: `*.slim.indexed`)
- `--limit N`: Max files to search (default: 100)
- `--context N`: Context lines around matches (default: 3)
- `--expand`: Auto-resolve all matches immediately
- `--indexes INDEX [...]`: Index files to use (default: `cold warm`)
- `--output FILE`: Save results to JSON
- `--format {text,json}`: Output format (default: text)

**Examples:**

```bash
# Search specific files
python3 src/search_cli.py search "error" \
    --files session1.slim.indexed session2.slim.indexed

# Search directory with more context
python3 src/search_cli.py search "memory leak" \
    --directory ~/conversations \
    --context 10

# Search and save results
python3 src/search_cli.py search "bug" \
    --directory ~/.fsl/handoffs \
    --output bug_results.json

# Search with auto-expand
python3 src/search_cli.py search "optimization" \
    --files handoff.slim.indexed \
    --expand  # Resolves all $refs immediately
```

### Preview Command

```bash
python3 src/search_cli.py preview FILE [options]
```

**Required:**
- `FILE`: Compressed file to preview

**Options:**
- `--start N`: Start line (default: 0)
- `--lines N`: Number of lines (default: 20)
- `--resolve`: Resolve $refs in preview
- `--indexes INDEX [...]`: Indexes to use if --resolve

**Examples:**

```bash
# Preview first 20 lines
python3 src/search_cli.py preview handoff.slim.indexed

# Preview middle section
python3 src/search_cli.py preview handoff.slim.indexed \
    --start 100 --lines 50

# Preview with refs resolved
python3 src/search_cli.py preview handoff.slim.indexed \
    --start 50 --lines 30 --resolve
```

### Expand Command

```bash
python3 src/search_cli.py expand RESULTS.json --match INDEX [options]
```

**Required:**
- `RESULTS.json`: JSON file from previous search
- `--match INDEX`: Match number to expand

**Options:**
- `--indexes INDEX [...]`: Indexes to use (default: `cold warm`)
- `--save`: Update result file with expanded match

**Examples:**

```bash
# Expand first match
python3 src/search_cli.py expand results.json --match 0

# Expand and save
python3 src/search_cli.py expand results.json --match 0 --save
```

### List Indexes Command

```bash
python3 src/search_cli.py list-indexes
```

Shows all available index files with metadata.

## Python API

### ConversationSearcher

The high-level API for searching compressed conversations.

#### Initialization

```python
from conversation_searcher import ConversationSearcher

# Default index directory
searcher = ConversationSearcher()

# Custom index directory
searcher = ConversationSearcher(index_dir="~/custom/indexes")
```

#### search()

Search specific files for a query.

```python
result = searcher.search(
    query="authentication",
    files=["file1.slim.indexed", "file2.slim.indexed"],
    preview_context=5,        # Lines of context
    auto_expand=False,        # Don't resolve refs yet
    case_sensitive=False,     # Case-insensitive
    indexes=["cold", "warm"]  # Indexes to search
)

# Result attributes
print(result.query)                    # "authentication"
print(result.total_matches)            # 5
print(result.files_searched)           # 2
print(result.tokens_used)              # 75,000
print(result.full_decompress_tokens)   # 2,000,000
print(result.tokens_saved)             # 1,925,000
print(result.savings_percent)          # 96.3
print(result.search_time_ms)           # 234.5
print(result.indexes_loaded)           # ["cold", "warm"]

# Iterate matches
for i, match in enumerate(result.matches):
    print(f"[{i}] {match.file_path}:{match.line_number}")
    print(f"    {match.match_text}")
    if match.ref_id:
        print(f"    Ref: {match.ref_id}")
```

#### search_directory()

Search all files in a directory.

```python
result = searcher.search_directory(
    query="memory leak",
    directory="~/conversations/2026",
    pattern="*.slim.indexed",  # File pattern
    limit=100,                  # Max files
    preview_context=5,
    auto_expand=False,
    indexes=["cold", "warm"]
)
```

#### preview_file()

Preview a compressed file without full decompression.

```python
# Preview without resolving refs
preview = searcher.preview_file(
    "handoff.slim.indexed",
    start_line=0,
    num_lines=20,
    resolve_refs=False
)
print(preview)

# Preview with refs resolved
preview = searcher.preview_file(
    "handoff.slim.indexed",
    start_line=50,
    num_lines=30,
    resolve_refs=True,
    indexes=["cold", "warm"]
)
```

### SearchResult

Result object from search operations.

```python
result = searcher.search(...)

# Properties
result.query                    # Search query
result.total_matches           # Number of matches
result.files_searched          # Files searched
result.tokens_used             # Tokens consumed
result.full_decompress_tokens  # Tokens if fully decompressed
result.tokens_saved            # Calculated savings
result.savings_percent         # Savings percentage
result.search_time_ms          # Time in milliseconds
result.matches                 # List of SearchMatch objects

# Methods
expanded = result.expand_match(
    match_index=0,
    indexes=["cold", "warm"],
    context_lines=10  # Additional context
)
```

### SearchMatch

Individual match result.

```python
match = result.matches[0]

# Attributes
match.file_path       # Path to file
match.line_number     # Line number (0-indexed)
match.ref_id          # $ref ID if match is in a pattern
match.match_text      # Matched line
match.context_before  # Lines before match
match.context_after   # Lines after match
match.resolved        # Whether refs are resolved
match.category        # Pattern category (if applicable)

# String representation
print(match)  # Pretty-printed match
```

### IndexExtractor (Low-Level API)

Direct control over selective decompression.

```python
from index_extractor import IndexExtractor

extractor = IndexExtractor()

# Load compressed content
with open("session.slim.indexed", "r") as f:
    compressed = f.read()
```

#### resolve_references_selective()

Resolve only specific $refs.

```python
# Resolve only these refs
partially = extractor.resolve_references_selective(
    compressed,
    ref_patterns=["$cold#abc123", "$warm#def456"],
    indexes=["cold", "warm"],
    index_dir="~/.claude/indexes"
)

# Result: only specified refs are resolved,
# others remain as "$tier#hash"
```

#### get_section()

Extract specific line range.

```python
# Get lines 100-150 without resolving
section = extractor.get_section(
    compressed,
    start_line=100,
    end_line=150,
    resolve_refs=False
)

# Get lines 100-150 with refs resolved
section = extractor.get_section(
    compressed,
    start_line=100,
    end_line=150,
    resolve_refs=True,
    indexes=["cold", "warm"]
)
```

### IndexSearcher

Search index files directly.

```python
from index_searcher import IndexSearcher

searcher = IndexSearcher(index_dir="~/.claude/indexes")

# Search indexes for patterns containing query
matches = searcher.search_indexes(
    query="authentication",
    index_files=["cold", "warm"],
    case_sensitive=False
)

for match in matches:
    print(f"{match.ref_id}: {match.content_preview}")
    print(f"  Category: {match.category}")
    print(f"  Occurrences: {match.occurrences}")

# Find where $refs appear in content
with open("file.slim.indexed", "r") as f:
    content = f.read()

locations = searcher.find_refs_in_content(
    content,
    ref_hashes=["$cold#abc123", "$warm#def456"]
)

# locations = {
#     "$cold#abc123": [10, 45, 67],  # Line numbers
#     "$warm#def456": [123]
# }
```

## Search Strategies

### Strategy 1: Broad Search, Narrow Down

Start with minimal context, expand as needed.

```python
# 1. Quick search across many files
result = searcher.search_directory(
    "authentication",
    "~/conversations",
    preview_context=1,  # Minimal context
    limit=100
)

print(f"Found {result.total_matches} matches")

# 2. Review matches, identify interesting ones
for i, match in enumerate(result.matches[:10]):
    print(f"[{i}] {match.file_path}:{match.line_number}")
    print(f"    {match.match_text}")

# 3. Expand specific match for full context
expanded = result.expand_match(
    match_index=3,  # The interesting one
    context_lines=20  # More context
)
print(expanded)
```

### Strategy 2: Two-Phase Search

Search indexes first, then locate in files.

```python
from index_searcher import IndexSearcher

# Phase 1: Find patterns in indexes
index_searcher = IndexSearcher()
index_matches = index_searcher.search_indexes(
    "authentication",
    ["cold", "warm"]
)

print(f"Found {len(index_matches)} patterns")

# Extract ref IDs
ref_ids = [m.ref_id for m in index_matches]

# Phase 2: Find where these refs appear
for file_path in my_files:
    with open(file_path, "r") as f:
        content = f.read()

    locations = index_searcher.find_refs_in_content(
        content,
        ref_ids
    )

    if locations:
        print(f"{file_path}: {sum(len(v) for v in locations.values())} occurrences")
```

### Strategy 3: Progressive Decompression

Decompress incrementally as needed.

```python
# 1. Preview metadata (minimal tokens)
preview = searcher.preview_file(
    "handoff.slim.indexed",
    start_line=0,
    num_lines=10,
    resolve_refs=False
)

# 2. If interesting, search within file
result = searcher.search(
    "specific term",
    ["handoff.slim.indexed"],
    preview_context=3
)

# 3. If matches found, expand them
if result.total_matches > 0:
    expanded = result.expand_match(0)
    # Now have full context for match

# 4. If still need more, decompress entire file
if need_full_context:
    full = extractor.resolve_references(
        compressed,
        indexes=["cold", "warm", "hot"]
    )
```

## Performance Optimization

### 1. Minimize Index Loading

Indexes are loaded once per search. Batch searches to amortize cost.

```python
# ❌ Bad: Load indexes 10 times
for file in files:
    result = searcher.search("query", [file])

# ✅ Good: Load indexes once
result = searcher.search("query", files)
```

### 2. Use Appropriate Context

More context = more tokens. Start small.

```python
# Quick scan
result = searcher.search(..., preview_context=1)

# Detailed view
result = searcher.search(..., preview_context=5)

# Full context (expensive)
result = searcher.search(..., preview_context=20)
```

### 3. Limit File Count

```python
# Search recent files first
result = searcher.search_directory(
    "error",
    "~/conversations",
    limit=50,  # Only 50 most recent
    pattern="*.slim.indexed"
)
```

### 4. Save and Reuse Results

```python
# Search once
result = searcher.search(...)

# Save for later
import json
with open("results.json", "w") as f:
    json.dump({
        "query": result.query,
        "matches": [
            {
                "file": m.file_path,
                "line": m.line_number,
                "text": m.match_text
            }
            for m in result.matches
        ]
    }, f)

# Reuse later without re-searching
with open("results.json", "r") as f:
    saved = json.load(f)
```

### 5. Choose Right Indexes

```python
# Searching recent session: use hot
result = searcher.search(..., indexes=["hot", "warm", "cold"])

# Searching old conversations: skip hot
result = searcher.search(..., indexes=["warm", "cold"])

# Searching for common patterns: cold only
result = searcher.search(..., indexes=["cold"])
```

## Examples

### Example 1: Find Debugging Sessions

```python
# Find all conversations about a specific bug
result = searcher.search_directory(
    "NullPointerException in UserService",
    "~/conversations/2026",
    preview_context=5
)

# Group by file
from collections import defaultdict
by_file = defaultdict(list)

for match in result.matches:
    by_file[match.file_path].append(match)

# Show summary
for file, matches in by_file.items():
    print(f"\n{file}: {len(matches)} mentions")
    for match in matches[:3]:  # First 3
        print(f"  Line {match.line_number}: {match.match_text[:80]}")
```

### Example 2: Track Decision Evolution

```python
# Search for a decision across time
queries = ["authentication approach", "auth strategy", "login flow"]
all_matches = []

for query in queries:
    result = searcher.search_directory(
        query,
        "~/projects/myapp/conversations",
        limit=50
    )
    all_matches.extend(result.matches)

# Sort by file (usually chronological)
all_matches.sort(key=lambda m: m.file_path)

# Show timeline
print("Timeline of authentication decisions:")
for match in all_matches:
    print(f"{match.file_path}: {match.match_text}")
```

### Example 3: Code Review Preparation

```python
# Find all discussions about a module before reviewing
module_name = "payment_processor"

result = searcher.search_directory(
    module_name,
    "~/conversations",
    preview_context=10,
    auto_expand=True  # Get full context
)

# Export for review
with open(f"{module_name}_discussions.txt", "w") as f:
    f.write(f"Discussions about {module_name}\n")
    f.write("=" * 60 + "\n\n")

    for i, match in enumerate(result.matches):
        f.write(f"[{i+1}] {match.file_path}:{match.line_number}\n")
        f.write(match.context_before + "\n")
        f.write(f">>> {match.match_text}\n")
        f.write(match.context_after + "\n")
        f.write("\n" + "-" * 60 + "\n\n")

print(f"Exported {len(result.matches)} discussions")
```

### Example 4: Multi-Project Search

```python
# Search across multiple projects
projects = {
    "web_app": "~/projects/web_app/conversations",
    "mobile_app": "~/projects/mobile_app/conversations",
    "api_server": "~/projects/api_server/conversations"
}

query = "caching strategy"
all_results = {}

for project, directory in projects.items():
    result = searcher.search_directory(
        query,
        directory,
        limit=30
    )
    all_results[project] = result
    print(f"{project}: {result.total_matches} matches")

# Compare approaches
print(f"\nCaching strategies by project:")
for project, result in all_results.items():
    print(f"\n{project}:")
    for match in result.matches[:5]:
        print(f"  {match.match_text}")
```

## Troubleshooting

### No matches found

**Possible causes:**
1. Content is in a $ref pattern
2. Different terminology used
3. Case sensitivity issue

**Solutions:**

```bash
# 1. Search indexes directly
python3 src/index_searcher.py search "term" --indexes cold warm

# 2. Try synonyms
python3 src/search_cli.py search "auth|login|credential" ...

# 3. Check file content directly
python3 src/search_cli.py preview file.slim.indexed --lines 50
```

### Search is slow

**Causes:**
- Too many files
- Large index files
- Unnecessary index loading

**Solutions:**

```python
# Limit files
result = searcher.search_directory(..., limit=50)

# Use specific indexes
result = searcher.search(..., indexes=["cold"])  # Skip warm, hot

# Search smaller directory
result = searcher.search_directory(
    query,
    "~/conversations/2026/january",  # More specific
    limit=30
)
```

### High token usage

**Causes:**
- Too much context
- Auto-expand enabled
- Searching too many files

**Solutions:**

```python
# Reduce context
result = searcher.search(..., preview_context=2)  # Instead of 10

# Don't auto-expand
result = searcher.search(..., auto_expand=False)

# Expand selectively
expanded = result.expand_match(0)  # Only the one you need
```

### Index not found

**Error:** `FileNotFoundError: Index file not found`

**Solution:**

```bash
# Check available indexes
python3 src/search_cli.py list-indexes

# Create indexes by compressing content
python3 src/index_extractor.py conversation.jsonl \
    --session-id my_session \
    --project-id my_project
```

### $refs not resolving

**Cause:** Wrong indexes specified or indexes don't exist

**Solution:**

```python
# Check which indexes contain the $ref
from index_searcher import IndexSearcher
searcher = IndexSearcher()

# Get all available indexes
available = searcher.get_available_indexes()
print(available)

# Try resolving with all indexes
result = searcher.search(..., indexes=["cold", "warm", "hot"])
```

## See Also

- [PRD_SELECTIVE_DECOMPRESSION.md](PRD_SELECTIVE_DECOMPRESSION.md) - Feature specification
- [UNIFIED_PIPELINE.md](UNIFIED_PIPELINE.md) - Complete pipeline documentation
- [slim_conversation_spec.md](slim_conversation_spec.md) - SLIM format specification
