# V4Z Migration Plan: Replace SLIM JSONL Format

## Problem Statement

**Current Issue:** Conversation library uses SLIM format (`.slim.indexed`) which has broken pipe delimiter parsing. When content contains pipes (even escaped), the parser fails with type mismatches.

**Error Examples:**
```
invalid literal for int() with base 10: ' data.winner_by_judges...'
JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

**Impact:**
- Comparison mode only works with golden library (907 handoffs)
- Cannot compare conversation library handoffs (~1000+ sessions)
- SLIM parser breaks on complex JSON/code content

## Solution: Migrate to V4Z Format

**Why V4Z:**
- Already proven in golden library (works perfectly)
- Better compression than SLIM (75-85% vs 30-40%)
- No delimiter issues (uses Zstandard binary compression)
- Existing decompressor works (`v4z_compressor.py`)

**Current V4Z Stack:**
1. SLIM vocabulary (6-10% reduction on markdown)
2. Zstandard with dictionary training (70-80% additional)
3. Base64 encoding for safe storage
4. Total: 75-85% reduction

## Migration Steps

### Phase 1: Update Compression Pipeline (1 hour)

**File:** `src/unified_pipeline.py`

**Changes:**
```python
# Current
def _stage_slim(self, content: str, current_tokens: int):
    slim_content = self.slim_converter.jsonl_to_slim(content)
    # Returns SLIM format with pipe delimiters

# New
def _stage_v4z(self, content: str, current_tokens: int):
    from v4z_compressor import V4ZCompressor
    compressor = V4ZCompressor()
    result = compressor.compress(content)
    # Returns V4Z base64 encoded
```

**Update compression levels:**
- "minimal": V4Z only (~75% reduction)
- "balanced": V4Z + Index (~80% reduction) [OPTIONAL]
- "maximum": V4Z + Index + CairnESL (~85% reduction) [OPTIONAL]

**Note:** V4Z alone provides better compression than SLIM + Index, so we can simplify to just V4Z.

### Phase 2: Update Auto-Compress Daemon (30 min)

**File:** `daemons/auto_compress_daemon.py`

**Changes:**
```python
# Current
output_file = self.compressed_dir / f"{file_path.stem}.slim.indexed"

# New
output_file = self.compressed_dir / f"{file_path.stem}.v4z"
```

**Pipeline initialization:**
```python
# Use V4Z-based pipeline
self.pipeline = UnifiedCompressionPipeline(level="minimal")  # Just V4Z
```

### Phase 3: Update Backend Decompression (30 min)

**File:** `dashboard_server.py`

**Already implemented!** The `_decompress_handoff()` function already handles V4Z:

```python
# Try new format first (V4Z with compressed_file field)
if compressed_file:
    full_path = GOLDEN_LIBRARY_DIR.parent / compressed_file
    if full_path.exists():
        from v4z_compressor import V4ZCompressor
        compressor = V4ZCompressor()
        decompressed_content = compressor.decompress(compressed_content)
        return decompressed_content
```

**Only need to add:** Check for `.v4z` extension in conversation library search:

```python
# Update extensions list
for ext in ['', '.v4z', '.indexed', '.slim', '.slim.indexed']:
    test_path = conv_dir / f'{handoff_id}{ext}'
    if test_path.exists():
        # If .v4z, use V4ZCompressor
        if ext == '.v4z':
            from v4z_compressor import V4ZCompressor
            compressor = V4ZCompressor()
            with open(test_path, 'r') as f:
                return compressor.decompress(f.read())
```

### Phase 4: Migrate Existing Files (1-2 hours)

**Create migration script:** `scripts/migrate_slim_to_v4z.py`

```python
#!/usr/bin/env python3
"""
Migrate existing SLIM files to V4Z format.

1. Read all .slim.indexed files
2. Decompress using SlimConverter
3. Recompress using V4ZCompressor
4. Save as .v4z files
5. Update index.json entries
6. Optionally delete old .slim.indexed files
"""

def migrate_conversation_library():
    conv_dirs = [
        Path.home() / ".claude/conversation_library/compressed/projects",
        Path.home() / ".claude/conversation_library/compressed/todos"
    ]

    for conv_dir in conv_dirs:
        for slim_file in conv_dir.glob("*.slim.indexed"):
            try:
                # Decompress SLIM
                converter = SlimConverter()
                with open(slim_file, 'r') as f:
                    slim_content = f.read()
                jsonl_content = converter.slim_to_jsonl(slim_content)

                # Compress with V4Z
                compressor = V4ZCompressor()
                result = compressor.compress(jsonl_content)

                # Save V4Z
                v4z_file = slim_file.with_suffix('.v4z')
                with open(v4z_file, 'w') as f:
                    f.write(result.compressed_base64)

                print(f"✓ Migrated: {slim_file.name}")

                # Optional: Delete old file
                # slim_file.unlink()

            except Exception as e:
                print(f"✗ Failed: {slim_file.name} - {e}")
                # Keep old file on error
```

**Run migration:**
```bash
cd ~/ztgi/golden_library
python3 scripts/migrate_slim_to_v4z.py
```

### Phase 5: Update Frontend (15 min)

**File:** `claude_dashboard.html`

**Change:**
```javascript
// Current
const response = await fetch('/api/golden/handoffs');

// New - support both libraries
const response = await fetch('/api/3d/handoffs');  // All handoffs now work
```

**Remove comment:**
```javascript
// Remove: "golden library only - SLIM JSONL format is broken"
```

### Phase 6: Testing (30 min)

**Test Plan:**
1. Stop auto-compress daemon
2. Manually compress a test conversation with new pipeline
3. Verify decompression works
4. Test comparison in UI
5. Run migration script on small batch
6. Verify existing handoffs still work
7. Full migration
8. Restart daemon

## Timeline

**Total Estimate:** 3-4 hours

- Phase 1: Update pipeline (1h)
- Phase 2: Update daemon (30m)
- Phase 3: Update backend (30m)
- Phase 4: Migration script (1h)
- Phase 5: Update frontend (15m)
- Phase 6: Testing (30m)

## Benefits

**Immediate:**
- Comparison works with all handoffs (not just golden library)
- Better compression (75-85% vs 30-40%)
- No more pipe delimiter bugs
- Simpler codebase (remove SLIM parser complexity)

**Long-term:**
- More reliable decompression
- Better token savings
- Easier to maintain (binary format, no parsing)
- Foundation for future improvements

## Risks & Mitigation

**Risk:** Migration script fails on some files
**Mitigation:** Keep old .slim.indexed files until verified

**Risk:** V4Z decompressor has issues
**Mitigation:** Already proven in golden library (907 handoffs)

**Risk:** Breaking changes to existing tools
**Mitigation:** Backend already supports both formats

## Rollback Plan

If V4Z migration fails:
1. Revert pipeline changes
2. Keep .slim.indexed files
3. Frontend stays on golden library only
4. No data loss (old files remain)

## Success Criteria

✅ All conversation library handoffs decompress correctly
✅ Comparison mode works with full library (2000+ handoffs)
✅ New compressions use V4Z format
✅ Auto-compress daemon creates .v4z files
✅ No SLIM parser errors in logs
✅ Better compression ratios than before

## Next Steps

1. Review this plan
2. Approve migration
3. Start with Phase 1 (pipeline update)
4. Test thoroughly before full migration
5. Document changes in commit message

---

**Status:** Ready for implementation
**Priority:** Medium (workaround exists - golden library only)
**Complexity:** Low (V4Z already proven + working)
**Impact:** High (enables full comparison functionality)
