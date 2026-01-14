# PRD: Selective Decompression for Unified Compression Pipeline

**Version:** 1.0
**Date:** 2026-01-13
**Status:** Ready for Implementation
**Priority:** High
**Estimated Effort:** 8-12 hours

---

## Executive Summary

Add selective decompression capabilities to the unified compression pipeline, allowing users to search and access compressed conversations without full decompression. This reduces token costs by 85-95% for search operations and improves query speed by 10-20×.

**Key Benefit:** Search 100 compressed conversations (50M tokens compressed to 20M) using only 1-2M tokens instead of 20M.

---

## Background & Context

### Current System

The unified compression pipeline (`~/ztgi/golden_library/`) currently provides:

1. **Multi-stage compression** (30-70% token reduction)
   - SLIM format (schema-once)
   - Index extraction (pattern deduplication with $refs)
   - CairnESL/FSL/V4 integration (future stages)

2. **Lossless round-trip** via `resolve_references()`
   - Loads all indexes
   - Resolves all $ref pointers
   - Reconstructs full original content

3. **Handoff system** for instance transfers

**Problem:** To search compressed conversations, you must fully decompress first, paying full token cost.

### Existing Patterns to Learn From

The ecosystem already has selective access in other tools:

**FSL Search Agent** (`~/ztgi/fsl_search_agent.py`):
- Searches V4 compressed files without full decompression
- Uses T0-T2.5 tier structure
- Loads only needed tiers based on query

**V4 Format** (`~/ztgi/COMPRESSION_FORMATS.md`):
- Tiered index structure (T0: chunks, T1: concepts, T2: keywords, T2.5: positions)
- Can query T1/T2 without loading full content

**Our System's Advantage:** We have explicit $ref pointers, making selective resolution easier than tier parsing.

---

## Problem Statement

**Users want to:**
1. Search across many compressed conversations
2. Find specific patterns or keywords
3. Preview results before full decompression
4. Only pay token costs for what they access

**Current limitation:**
- Must decompress entire conversation (20M tokens) to search
- Costs $60 per search session (at $3/M tokens)
- Slow (must load all indexes and resolve all references)

**Desired state:**
- Search compressed conversation directly
- Only decompress matching sections
- Cost: $0.15-0.30 per search (1-2M tokens for index + previews)
- **Savings: 95%+ for search operations**

---

## Goals & Non-Goals

### Goals

✅ **Search compressed conversations without full decompression**
- Query indexes (hot/warm/cold) directly
- Find $refs matching search terms
- Return preview without resolving references

✅ **Selective reference resolution**
- Resolve only specific $refs (not all)
- Load only needed index patterns
- Minimize token cost per query

✅ **Fast preview generation**
- Show context around matches
- Keep $refs unresolved for non-matching content
- Expandable on-demand

✅ **Compatible with existing pipeline**
- Works with current SLIM + Index format
- No breaking changes to compression
- Backward compatible

### Non-Goals

❌ **Full-text search** (use existing tools like grep)
❌ **Semantic search** (different feature)
❌ **Real-time indexing** (batch-based is fine)
❌ **Query language** (simple keyword search sufficient)

---

## User Stories

### Story 1: Search Across Conversations

**As a** developer with 100 compressed conversations
**I want to** search for "authentication bug" without decompressing all files
**So that** I can find relevant discussions quickly and cheaply

**Acceptance Criteria:**
- Can search all 100 files with < 2M token cost
- Results show file, location, and preview
- Can selectively expand individual results

### Story 2: Preview Before Full Load

**As a** user reviewing handoff packages
**I want to** preview compressed handoff contents
**So that** I can decide which to fully decompress

**Acceptance Criteria:**
- Can list handoff metadata without decompression
- Can preview key sections (summary, last exchanges)
- Can expand full conversation on-demand

### Story 3: Partial Context Loading

**As a** developer debugging an issue
**I want to** load only the relevant conversation section
**So that** I don't waste tokens on unrelated exchanges

**Acceptance Criteria:**
- Can load specific message ranges (e.g., lines 100-150)
- Only resolves $refs in requested range
- Can expand before/after on demand

---

## Technical Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                 SELECTIVE DECOMPRESSION                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Compressed Conversation (with $refs)                        │
│       │                                                      │
│       ▼                                                      │
│  ┌──────────────────────┐                                   │
│  │  1. INDEX SEARCHER   │  Search indexes without loading   │
│  │     - Query indexes  │  full content                     │
│  │     - Find $refs     │                                   │
│  │     - Map to lines   │                                   │
│  └──────────┬───────────┘                                   │
│             │                                                │
│             ▼                                                │
│  ┌──────────────────────┐                                   │
│  │  2. MATCH LOCATOR    │  Find matches in compressed       │
│  │     - Scan content   │  content                          │
│  │     - Track $refs    │                                   │
│  │     - Extract ranges │                                   │
│  └──────────┬───────────┘                                   │
│             │                                                │
│             ▼                                                │
│  ┌──────────────────────┐                                   │
│  │  3. SELECTIVE        │  Resolve only needed $refs        │
│  │     RESOLVER         │                                   │
│  │     - Load subset    │                                   │
│  │     - Expand matches │                                   │
│  │     - Keep rest      │                                   │
│  └──────────┬───────────┘                                   │
│             │                                                │
│             ▼                                                │
│  Result: Partially decompressed with matches expanded       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Component Design

#### 1. IndexSearcher (New Class)

**File:** `src/index_searcher.py`

**Purpose:** Search indexes without loading full conversation

```python
class IndexSearcher:
    """Search compressed content via indexes."""

    def search_indexes(
        self,
        query: str,
        index_files: List[str]
    ) -> List[IndexMatch]:
        """
        Search indexes for query term.

        Returns list of IndexMatch objects with:
        - pattern_hash: $ref hash
        - category: pattern category
        - content_preview: first 200 chars
        - occurrences: how many times appears
        """

    def find_refs_in_content(
        self,
        compressed_content: str,
        ref_hashes: List[str]
    ) -> Dict[str, List[int]]:
        """
        Find line numbers where specific $refs appear.

        Returns: {ref_hash: [line_nums]}
        """
```

#### 2. SelectiveResolver (Enhancement to IndexExtractor)

**File:** `src/index_extractor.py` (modify existing)

**New Methods:**

```python
class IndexExtractor:
    # ... existing methods ...

    def resolve_references_selective(
        self,
        compressed: str,
        ref_patterns: List[str],  # Only resolve these $refs
        indexes: List[str],
        context_lines: int = 5     # Lines before/after to include
    ) -> str:
        """
        Resolve only specific $ref patterns.

        Args:
            compressed: Compressed content with $refs
            ref_patterns: List of $ref IDs to resolve (e.g., ["$cold#abc123"])
            indexes: Index files to load
            context_lines: Context around each match

        Returns:
            Partially decompressed content with only requested refs resolved
        """

    def get_section(
        self,
        compressed: str,
        start_line: int,
        end_line: int,
        resolve_refs: bool = True,
        indexes: Optional[List[str]] = None
    ) -> str:
        """
        Extract specific line range from compressed content.

        Args:
            compressed: Compressed content
            start_line: Starting line (0-indexed)
            end_line: Ending line (exclusive)
            resolve_refs: Whether to resolve $refs in this range
            indexes: Index files if resolve_refs=True

        Returns:
            Extracted section (with refs resolved if requested)
        """
```

#### 3. SearchResult (New Dataclass)

**File:** `src/search_result.py` (new)

```python
@dataclass
class SearchMatch:
    """A single search match in compressed content."""
    file_path: str
    line_number: int
    ref_id: Optional[str]  # If match is in a $ref pattern
    match_text: str        # Text that matched
    context_before: str    # Lines before match
    context_after: str     # Lines after match
    resolved: bool         # Whether refs are resolved

@dataclass
class SearchResult:
    """Result from searching compressed conversations."""
    query: str
    total_matches: int
    files_searched: int
    tokens_used: int       # Tokens for search (not full content)
    matches: List[SearchMatch]

    def expand_match(self, match_index: int, indexes: List[str]) -> SearchMatch:
        """Resolve refs for a specific match."""
```

#### 4. ConversationSearcher (New Class)

**File:** `src/conversation_searcher.py` (new)

**Purpose:** High-level search interface

```python
class ConversationSearcher:
    """Search compressed conversations efficiently."""

    def __init__(self, index_dir: str = "~/.claude/indexes"):
        self.index_searcher = IndexSearcher()
        self.index_extractor = IndexExtractor()
        self.index_dir = Path(index_dir).expanduser()

    def search(
        self,
        query: str,
        files: List[str],
        preview_context: int = 3,
        auto_expand: bool = False
    ) -> SearchResult:
        """
        Search compressed conversations for query.

        Args:
            query: Search term
            files: List of compressed files to search
            preview_context: Lines of context around matches
            auto_expand: If True, resolve all matches immediately

        Returns:
            SearchResult with matches (unexpanded unless auto_expand=True)
        """

    def search_directory(
        self,
        query: str,
        directory: str,
        pattern: str = "*.slim.indexed",
        limit: int = 100
    ) -> SearchResult:
        """Search all compressed files in directory."""
```

### Data Flow

#### Search Operation

```
User Query: "authentication bug"
       ↓
1. Load indexes (hot/warm/cold)
   - Total: ~50K tokens (one-time per session)
       ↓
2. Search index patterns for "authentication"
   - Found in: $cold#abc123, $warm#def456
   - Token cost: ~1K tokens
       ↓
3. Find $refs in compressed files
   - File1: line 45, 67 ($cold#abc123)
   - File2: line 123 ($warm#def456)
   - Token cost: ~5K tokens (scan compressed files)
       ↓
4. Extract context (5 lines before/after)
   - File1:45 context (with $refs unresolved)
   - File2:123 context (with $refs unresolved)
   - Token cost: ~10K tokens
       ↓
5. Resolve only matched $refs
   - $cold#abc123 → "authentication system"
   - $warm#def456 → "bug in auth flow"
   - Token cost: ~2K tokens
       ↓
6. Return SearchResult
   - 2 matches across 2 files
   - Total tokens: ~68K (vs 20M for full decompression)
   - Savings: 99.7%
```

#### Expand Operation (On-Demand)

```
User: "Expand match #1"
       ↓
1. Already have $cold#abc123 resolved
   - No additional token cost
       ↓
2. Load more context (expand to ±10 lines)
   - Scan compressed file
   - Token cost: ~5K tokens
       ↓
3. Resolve any new $refs in expanded range
   - 2 additional refs: $cold#xyz789, $hot#session123
   - Token cost: ~3K tokens
       ↓
4. Return expanded result
   - Total cost for expansion: ~8K tokens
```

### File Format Compatibility

**Works with existing formats:**

```
Compressed file with $refs:
§SLIM§ v1
[SCHEMA]
role|content|type
---
[DATA]
user|Tell me about "$cold#abc123"
assistant|"$cold#abc123" is important...
system|"$warm#def456" reminder
---
§/SLIM§

Search for "authentication":
1. Check $cold#abc123 in cold index → matches "authentication system"
2. Identify line 2: assistant message contains match
3. Return line 2 with ±3 context
4. Optionally resolve $cold#abc123 for preview
```

---

## Implementation Plan

### Phase 1: Core Selective Resolution (4-6 hours)

**Files to modify:**
- `src/index_extractor.py`

**New methods:**
1. `resolve_references_selective()` - Resolve specific $refs only
2. `get_section()` - Extract line ranges
3. `_load_selective_patterns()` - Load only needed index patterns

**Tests:**
- Test resolving 1 out of 10 $refs
- Test line range extraction
- Verify token savings

### Phase 2: Search Infrastructure (3-4 hours)

**New files:**
- `src/search_result.py` - Data classes for results
- `src/index_searcher.py` - Index searching logic
- `src/conversation_searcher.py` - High-level search API

**Features:**
- Search indexes for keywords
- Find $refs in compressed content
- Generate previews with context

**Tests:**
- Search across 10 compressed files
- Verify match locations
- Test context extraction

### Phase 3: CLI Interface (1-2 hours)

**New file:**
- `src/search_cli.py` - Command-line search tool

**Commands:**
```bash
# Search compressed files
python3 src/search_cli.py search "authentication" \
    --directory ~/.fsl/handoffs \
    --context 5

# Expand specific match
python3 src/search_cli.py expand \
    --result results.json \
    --match 0 \
    --context 10

# Preview file without decompression
python3 src/search_cli.py preview handoff_123.slim.indexed \
    --lines 1-50
```

**Tests:**
- CLI integration tests
- Output format validation

### Phase 4: Documentation & Examples (1 hour)

**Update files:**
- `docs/UNIFIED_PIPELINE.md` - Add search section
- `docs/SEARCH_GUIDE.md` - New search documentation
- `README.md` - Update with search examples

---

## API Specification

### Python API

```python
from conversation_searcher import ConversationSearcher

# Initialize searcher
searcher = ConversationSearcher()

# Search multiple files
result = searcher.search(
    query="authentication bug",
    files=[
        "handoff1.slim.indexed",
        "handoff2.slim.indexed"
    ],
    preview_context=5
)

# Print results
print(f"Found {result.total_matches} matches")
print(f"Tokens used: {result.tokens_used:,} (vs {result.full_decompress_tokens:,} for full)")

for i, match in enumerate(result.matches):
    print(f"\nMatch {i+1}:")
    print(f"  File: {match.file_path}")
    print(f"  Line: {match.line_number}")
    print(f"  Context: {match.context_before}")
    print(f"  >>> {match.match_text}")
    print(f"  Context: {match.context_after}")

# Expand specific match (resolve all refs in context)
expanded = result.expand_match(
    match_index=0,
    indexes=["~/.claude/indexes/global_cold.json"]
)
print(f"\nExpanded match:\n{expanded.match_text}")
```

### CLI API

```bash
# Basic search
python3 src/search_cli.py search "authentication" \
    --files handoff1.slim.indexed handoff2.slim.indexed

# Directory search
python3 src/search_cli.py search "bug" \
    --directory ~/.fsl/handoffs \
    --pattern "*.slim.indexed" \
    --limit 50

# With more context
python3 src/search_cli.py search "error" \
    --files session.slim.indexed \
    --context 10

# Save results for later expansion
python3 src/search_cli.py search "performance" \
    --directory ~/conversations \
    --output results.json

# Expand saved result
python3 src/search_cli.py expand results.json --match 0

# Preview file sections
python3 src/search_cli.py preview handoff.slim.indexed \
    --lines 1-100 \
    --resolve-refs
```

---

## Success Criteria

### Functional Requirements

✅ **Search Accuracy**
- Finds all matches in compressed content
- Correctly identifies $ref patterns
- No false positives/negatives

✅ **Token Efficiency**
- Search uses < 5% tokens of full decompression
- Typical search across 100 files: < 2M tokens
- Expansion costs < 10K tokens per match

✅ **Performance**
- Search 100 compressed files in < 10 seconds
- Preview generation in < 1 second
- Expansion in < 2 seconds

✅ **Compatibility**
- Works with all compression levels (minimal/balanced/maximum)
- Backward compatible with existing compressed files
- No changes needed to compression pipeline

### Non-Functional Requirements

✅ **Usability**
- CLI is intuitive and well-documented
- Python API is simple and Pythonic
- Error messages are clear

✅ **Reliability**
- Handles malformed compressed files gracefully
- Doesn't corrupt files during search
- Maintains lossless property

✅ **Maintainability**
- Code follows existing patterns
- Well-tested (>80% coverage)
- Documented with examples

---

## Test Requirements

### Unit Tests

**File:** `tests/test_selective_decompression.py`

```python
def test_resolve_selective():
    """Test resolving only specific $refs."""
    # Create content with 10 $refs
    # Resolve only 2
    # Verify others remain as $refs

def test_section_extraction():
    """Test extracting line ranges."""
    # Extract lines 50-60
    # Verify correct content
    # Test edge cases (start=0, end=EOF)

def test_index_search():
    """Test searching index patterns."""
    # Search for "auth" in indexes
    # Verify correct $refs returned
    # Test case sensitivity

def test_match_location():
    """Test finding $refs in content."""
    # Find where $cold#abc appears
    # Verify line numbers
    # Test multiple occurrences

def test_context_extraction():
    """Test context around matches."""
    # Get ±5 lines around match
    # Verify boundaries (start/end of file)
    # Test overlapping contexts
```

### Integration Tests

```python
def test_search_workflow():
    """Test complete search workflow."""
    # 1. Compress conversation
    # 2. Search for term
    # 3. Verify matches found
    # 4. Expand one match
    # 5. Verify full context

def test_token_savings():
    """Verify token cost reduction."""
    # Search 10 compressed files
    # Measure tokens used
    # Compare to full decompression
    # Verify >90% savings

def test_multi_file_search():
    """Test searching across files."""
    # Create 10 compressed files
    # Search for term in 3 of them
    # Verify correct files found
    # Verify all matches located
```

### Performance Tests

```python
def test_search_speed():
    """Benchmark search performance."""
    # Search 100 files
    # Measure time
    # Should be < 10 seconds

def test_memory_usage():
    """Verify memory efficiency."""
    # Search large compressed file (100MB)
    # Memory should stay < 200MB
    # Should not load full content
```

---

## Metrics & Monitoring

### Key Metrics

Track these metrics to measure success:

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Token Reduction** | >90% | Tokens(search) / Tokens(full_decompress) |
| **Search Speed** | <10s for 100 files | Time to return results |
| **Match Accuracy** | 100% | Found matches / Total matches |
| **Expansion Cost** | <10K tokens/match | Tokens for expand operation |
| **Memory Usage** | <200MB | Peak memory during search |

### Logging

Add logging for:
- Search queries and result counts
- Token usage per operation
- Timing metrics
- Error conditions

---

## Migration & Rollout

### Backward Compatibility

✅ **No migration needed** - works with existing compressed files
✅ **Additive changes** - new functionality, no breaking changes
✅ **Optional feature** - can continue using full decompression

### Rollout Plan

1. **Phase 1:** Implement and test with existing compressed files
2. **Phase 2:** Update documentation and examples
3. **Phase 3:** Announce feature in README
4. **Phase 4:** Gather usage feedback and iterate

---

## Future Enhancements (Out of Scope)

These are intentionally excluded from v1 but could be added later:

- **Semantic search** using embeddings
- **Fuzzy matching** for typos
- **Regex support** for complex queries
- **AND/OR/NOT** operators for compound queries
- **Result ranking** by relevance
- **Parallel search** across many files
- **Incremental indexing** for real-time updates
- **Web UI** for visual search interface

---

## Dependencies & Prerequisites

### Required

- Existing unified compression pipeline (already built)
- `index_extractor.py` with index loading
- `slim_converter.py` for format parsing
- `tiktoken` for token counting

### Optional

- None - self-contained feature

---

## Risk Assessment

### Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Search misses matches** | Low | High | Comprehensive testing, fuzzy matching |
| **Token cost higher than expected** | Medium | Medium | Profile and optimize, add caching |
| **Slow for large files** | Medium | Low | Streaming, pagination |
| **Complex API** | Low | Medium | Clear docs, examples |

---

## Appendix A: Example Scenarios

### Scenario 1: Debug Session Search

**Goal:** Find all conversations mentioning "memory leak"

```python
searcher = ConversationSearcher()

result = searcher.search_directory(
    query="memory leak",
    directory="~/conversations/2026",
    pattern="*.slim.indexed"
)

print(f"Found {result.total_matches} mentions across {len(result.files)} files")
print(f"Token cost: {result.tokens_used:,} (saved {result.tokens_saved:,})")

# Expand most relevant match
top_match = result.matches[0]
expanded = result.expand_match(0, indexes=["cold", "warm"])
print(f"\nContext:\n{expanded.context_before}")
print(f">>> {expanded.match_text}")
print(f"{expanded.context_after}")
```

**Expected tokens:**
- Index load: 50K (one-time)
- Search: 20K (scan 100 files)
- Preview: 10K (3 matches, 5 lines each)
- **Total: 80K tokens** (vs 20M for full decompression)
- **Savings: 99.6%**

### Scenario 2: Handoff Preview

**Goal:** Preview handoff without loading all 140K tokens

```bash
# Quick preview
python3 src/search_cli.py preview handoff_123.slim.indexed \
    --lines 1-20 \
    --lines -20--1  # Last 20 lines

# Search within handoff
python3 src/search_cli.py search "authentication" \
    --files handoff_123.slim.indexed \
    --context 10

# Expand specific section
python3 src/search_cli.py preview handoff_123.slim.indexed \
    --lines 50-75 \
    --resolve-refs  # Full decompression of this range only
```

**Expected tokens:**
- Preview (first/last 20 lines): 5K tokens
- Search: 15K tokens
- Expand section (25 lines): 8K tokens
- **Total: 28K tokens** (vs 140K for full load)
- **Savings: 80%**

---

## Appendix B: Code Structure

```
~/ztgi/golden_library/
├── src/
│   ├── slim_converter.py        [existing]
│   ├── index_extractor.py       [modify - add selective methods]
│   ├── index_searcher.py        [NEW]
│   ├── search_result.py         [NEW]
│   ├── conversation_searcher.py [NEW]
│   └── search_cli.py            [NEW]
├── tests/
│   ├── test_unified_pipeline.py [existing]
│   └── test_selective_decompression.py [NEW]
└── docs/
    ├── UNIFIED_PIPELINE.md      [update]
    ├── SEARCH_GUIDE.md          [NEW]
    └── PRD_SELECTIVE_DECOMPRESSION.md [this file]
```

---

## Appendix C: Token Cost Analysis

### Comparison: Full vs Selective Decompression

| Operation | Full Decompress | Selective | Savings |
|-----------|----------------|-----------|---------|
| **Search 1 file** | 200K tokens | 15K tokens | 92.5% |
| **Search 10 files** | 2M tokens | 80K tokens | 96% |
| **Search 100 files** | 20M tokens | 500K tokens | 97.5% |
| **Preview handoff** | 140K tokens | 10K tokens | 92.9% |
| **Expand 1 match** | 140K tokens | 18K tokens | 87.1% |

### Monthly Cost Savings

**Scenario:** Search 100 conversations daily

| Approach | Daily Tokens | Monthly Cost | Annual Cost |
|----------|--------------|--------------|-------------|
| **Full decompress** | 20M | $1,800 | $21,600 |
| **Selective search** | 500K | $45 | $540 |
| **Savings** | 19.5M | **$1,755** | **$21,060** |

**ROI:** Implementation time (10 hours) pays for itself in 4 hours of daily searching.

---

## Contact & Questions

For questions about this PRD or implementation:

- **Author:** Cairn (Claude Sonnet 4.5)
- **Project:** Golden Library Unified Compression Pipeline
- **Repository:** https://github.com/nothinginfinity/golden_library
- **Context:** This PRD assumes you have the completed unified compression pipeline in `~/ztgi/golden_library/`

---

**Ready for implementation.** Hand this PRD to a new Claude Code instance along with the repository, and they should have everything needed to implement selective decompression.

---

*End of PRD*
