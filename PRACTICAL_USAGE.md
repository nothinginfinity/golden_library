# Practical Usage Guide: Compress Your Claude Code Conversations

This guide shows you how to **compress all your Claude Code conversations** and build a searchable library with 95%+ token savings.

## 🎯 Quick Start (5 Minutes)

### Step 1: Compress All Your Conversations

```bash
cd ~/ztgi/golden_library

# Find and compress all Claude Code conversations
python3 scripts/compress_all_conversations.py
```

**What this does:**
- Searches for Claude Code conversation files in common locations
- Compresses each with SLIM + Index extraction (30-70% reduction)
- Builds searchable index at `~/.claude/conversation_library/`
- Saves compressed versions for efficient search

**Output:**
```
🔍 Finding conversations...
✅ Found 47 conversation files

📦 Compressing: session_auth_feature.json
  ✅ 203,451 → 98,234 tokens (51.7% reduction)
  📄 Saved to: session_auth_feature.slim.indexed

📦 Compressing: bug_fix_session.json
  ✅ 156,789 → 82,345 tokens (47.5% reduction)
  📄 Saved to: bug_fix_session.slim.indexed

...

✅ COMPRESSION COMPLETE
Conversations compressed: 47/47
Library location: ~/.claude/conversation_library
```

### Step 2: Search Your Conversations (95% Token Savings!)

```bash
# Search for "authentication"
python3 scripts/search_library.py "authentication"
```

**Output:**
```
🔍 Searching 47 compressed conversations for 'authentication'...
   (This would cost 9,400,000 tokens if fully decompressed)

============================================================
Search Results: 'authentication'
============================================================

📊 Summary:
  Matches found: 12
  Conversations searched: 47
  Tokens used: 145,000
  Tokens saved: 9,255,000 (98.5%)

🎯 Matches by Conversation:

📄 JWT authentication implementation
   File: session_auth_feature.slim.indexed
   Project: myapp
   Tokens: 203,451 → 98,234 (51.7% reduction)
   Matches: 5

📄 Login flow bug fix
   File: bug_fix_session.slim.indexed
   Project: myapp
   Tokens: 156,789 → 82,345 (47.5% reduction)
   Matches: 3
```

**Cost Comparison:**
- **Without compression**: 9.4M tokens = $28.20
- **With selective search**: 145K tokens = $0.44
- **Savings**: 98.5% ($27.76 saved per search!)

### Step 3: Export Current Conversation

```bash
# Export and compress your current conversation
./scripts/export_current_conversation.sh myproject "Feature implementation"
```

This immediately compresses your current conversation and adds it to the searchable library.

---

## 📚 Detailed Usage

### Compress Specific Directory

```bash
# Compress conversations from custom location
python3 scripts/compress_all_conversations.py --session-dir ~/my/conversations
```

### Search with Filters

```bash
# Search specific project
python3 scripts/search_library.py "bug fix" --project myapp

# Search with more context
python3 scripts/search_library.py "error handling" --context 10

# Limit results
python3 scripts/search_library.py "optimization" --limit 10

# Detailed output
python3 scripts/search_library.py "authentication" --detailed
```

### List Projects

```bash
# See all projects in library
python3 scripts/search_library.py --list-projects
```

**Output:**
```
📁 Projects in Library
============================================================

• myapp
  Conversations: 23
  Tokens: 4,567,890 → 2,234,123 (51.1% reduction)

• debugging
  Conversations: 12
  Tokens: 2,345,678 → 1,123,456 (52.1% reduction)

• general
  Conversations: 12
  Tokens: 1,234,567 → 678,901 (45.0% reduction)
```

### Show Recent Conversations

```bash
# Show last 10 conversations
python3 scripts/search_library.py --recent

# Show last 20
python3 scripts/search_library.py --recent 20
```

### Get Library Statistics

```bash
# View overall stats
python3 scripts/compress_all_conversations.py --stats
```

**Output:**
```
📊 Library Statistics
============================================================
total_conversations: 47
total_original_tokens: 8,956,234
total_compressed_tokens: 4,234,567
total_tokens_saved: 4,721,667
average_reduction: 50.8%
library_dir: ~/.claude/conversation_library
```

---

## 🗂️ File Structure

After running compression:

```
~/.claude/conversation_library/
├── index.json                     # Searchable index
├── compressed/                    # Compressed conversations
│   ├── session_auth.slim.indexed
│   ├── bug_fix.slim.indexed
│   └── ...
└── raw/                          # Original exports (if using export script)
    ├── session_myproject_20260113.jsonl
    └── ...

~/.claude/indexes/                # Shared indexes for deduplication
├── global_cold.json              # Global patterns
├── sessions/                     # Session-specific indexes
│   ├── session_auth_hot.json
│   └── ...
└── projects/                     # Project-specific indexes
    ├── myapp_warm.json
    └── ...
```

---

## 💡 Use Cases

### Use Case 1: "What did I build last month?"

```bash
# Search all conversations from last month
python3 scripts/search_library.py "authentication" --detailed

# Review matches
# Load full conversation if needed
cat ~/.claude/conversation_library/compressed/session_auth.slim.indexed
```

**Token Cost:**
- Search 50 conversations: ~150K tokens ($0.45)
- vs loading all: 10M tokens ($30)
- **Savings: $29.55 per search**

### Use Case 2: "Find all bug fix discussions"

```bash
# Search for bug-related conversations
python3 scripts/search_library.py "bug" --project myapp --detailed

# Review matches and identify patterns
# Create compressed summary
```

### Use Case 3: "Build project knowledge base"

```bash
# Compress all project conversations
python3 scripts/compress_all_conversations.py --session-dir ~/projects/myapp/sessions

# Search across all
python3 scripts/search_library.py "architecture decision" --project myapp

# Export results for documentation
```

### Use Case 4: "Share context with another terminal"

Once QA.Stone integration is complete (see PRD), you'll be able to:

```bash
# Compress as QA.Stone
python3 src/qastone_cli.py compress session.jsonl \
    --author koda@wallet \
    --title "Auth implementation"

# Send to Cairn's inbox
python3 src/qastone_cli.py send {stone_hash} --target A

# Cairn searches with 95% savings
python3 src/qastone_cli.py search {stone_hash} "token refresh"
```

---

## 📊 Token Savings Analysis

### Real-World Scenario

**Your setup:**
- 50 Claude Code conversations
- Average: 200K tokens each
- Total: 10M tokens

**Current approach (searching manually):**
- Must load full conversation to search
- Cost per search: $30 (10M tokens × $3/M)
- 10 searches/month: $300

**With golden_library:**
- Compress once: 10M → 5M tokens (50% reduction)
- Search with selective decompression: 150K tokens/search
- Cost per search: $0.45 (150K tokens × $3/M)
- 10 searches/month: $4.50

**Monthly savings: $295.50**
**Annual savings: $3,546**

### Token Breakdown

| Operation | Full Load | Selective | Savings |
|-----------|-----------|-----------|---------|
| **Load 1 conversation** | 200K | 10K (compressed) | 95% |
| **Search 1 conversation** | 200K | 5K (selective) | 97.5% |
| **Search 50 conversations** | 10M | 150K | 98.5% |
| **Preview conversation** | 200K | 2K (first 100 lines) | 99% |

---

## 🔮 What's Next (After QA.Stone Integration)

Once you implement the [PRD](docs/PRD_QASTONE_COMPRESSION_INTEGRATION.md), you'll be able to:

### 1. **Progressive Loading**

```bash
# Load LOD5 (50 tokens) - just the summary
python3 src/qastone_cli.py get {stone_hash} --lod 5

# Interesting? Load LOD4 (200 tokens) - key points
python3 src/qastone_cli.py get {stone_hash} --lod 4

# Need details? Search compressed (5K tokens)
python3 src/qastone_cli.py search {stone_hash} "specific topic"
```

**Token cost progression:**
- LOD5: 50 tokens ($0.00015)
- LOD4: 200 tokens ($0.0006)
- Search: 5K tokens ($0.015)
- Full: 100K tokens ($0.30)

### 2. **Cross-Instance Sharing**

```bash
# Terminal K (Koda) compresses and sends
python3 src/qastone_cli.py compress session.jsonl --author koda@wallet
python3 src/qastone_cli.py send {hash} --target A

# Terminal A (Cairn) receives and searches
phi("check inbox")
python3 src/qastone_cli.py search {hash} "implementation details"
```

### 3. **Federated Access via MCP**

```python
# External user calls your MCP server
response = client.messages.create(
    tools=[{
        "name": "get_compressed_context",
        "description": "Search compressed conversations"
    }],
    messages=[{"role": "user", "content": "Find auth discussions"}]
)

# Claude searches your compressed library
# Returns matches with 95% token savings
```

### 4. **Conversation Chains**

```bash
# Create chain of related conversations
python3 src/qastone_cli.py compress session1.jsonl --chain null
# Returns: hash_a

python3 src/qastone_cli.py compress session2.jsonl --chain hash_a
# Returns: hash_b

python3 src/qastone_cli.py compress session3.jsonl --chain hash_b
# Returns: hash_c

# Trace evolution: C → B → A
python3 src/qastone_cli.py chain hash_c
```

---

## 🛠️ Maintenance

### Clean Old Conversations

```bash
# Delete conversations older than 90 days
find ~/.claude/conversation_library/compressed -mtime +90 -delete

# Rebuild index
python3 scripts/compress_all_conversations.py --stats
```

### Backup Library

```bash
# Backup compressed library
tar -czf conversation_library_backup.tar.gz ~/.claude/conversation_library

# Restore
tar -xzf conversation_library_backup.tar.gz -C ~/
```

### Monitor Storage

```bash
# Check library size
du -sh ~/.claude/conversation_library
du -sh ~/.claude/indexes

# Compare to original size
# Original: ~400MB
# Compressed: ~200MB (50% reduction)
```

---

## 🎓 Best Practices

1. **Compress Regularly**
   - Run compression weekly or after major sessions
   - Keep library up to date

2. **Use Descriptive Titles**
   - When exporting, provide meaningful titles
   - Makes search results more useful

3. **Organize by Project**
   - Use `--project` flag consistently
   - Enables project-specific searches

4. **Search Before Loading**
   - Always search first (95% token savings)
   - Only load full conversations when needed

5. **Clean Up Old Sessions**
   - Archive or delete old conversations
   - Keeps library focused and fast

---

## ❓ Troubleshooting

### "No conversations found"

**Problem:** Script can't find conversation files

**Solution:**
```bash
# Manually specify directory
python3 scripts/compress_all_conversations.py --session-dir ~/path/to/conversations

# Or export current conversation
./scripts/export_current_conversation.sh
```

### "Index not found"

**Problem:** Haven't run compression yet

**Solution:**
```bash
# Run compression first
python3 scripts/compress_all_conversations.py
```

### "Search returns no matches"

**Problem:** Query doesn't match compressed content

**Solution:**
- Try different search terms
- Use broader queries
- Check if conversation was compressed

### "Out of memory"

**Problem:** Processing very large conversations

**Solution:**
- Process in smaller batches
- Increase system memory
- Use `--limit` flag

---

## 📞 Support

- **Documentation**: See [docs/](docs/) folder
- **Examples**: See `examples/` folder
- **Issues**: https://github.com/nothinginfinity/golden_library/issues

---

**Start compressing your conversations now and save 95%+ on tokens!**

```bash
cd ~/ztgi/golden_library
python3 scripts/compress_all_conversations.py
python3 scripts/search_library.py "your first search"
```
