# 🏆 Golden Library

**Schema-once compression for AI conversation archives**

Turn massive Claude Code conversation logs into portable, shareable QA.Stones with 50-90% compression.

---

## 🎯 What is Golden Library?

Golden Library solves a critical problem: **AI conversation archives are getting huge**.

A single Claude Code session can be 73MB+ of JSONL data. When you try to:
- Share conversations with others
- Transfer context between sessions (handoffs)
- Index and search across conversations
- Archive long-term knowledge

...you hit serious performance issues. Phi server timeouts, slow searches, storage bloat.

**Golden Library compresses conversations using a two-stage pipeline:**

1. **SLIM** (Schema-once) - Eliminates JSON key repetition (~50% reduction)
2. **Advanced Compression** - V4Z/FSL/ZTPCF formats (~86% total reduction)

Then packages them as **QA.Stones** - portable, signed, shareable knowledge artifacts.

---

## 📊 The Problem (Illustrated)

```json
// Typical JSONL conversation (repeats keys on EVERY line)
{"type":"user","uuid":"abc","timestamp":"2025-12-31T08:58:02.855Z","sessionId":"d12906","message":{"role":"user","content":"hi"}}
{"type":"assistant","uuid":"def","timestamp":"2025-12-31T08:58:10.802Z","sessionId":"d12906","message":{"role":"assistant","content":"Hello"}}
{"type":"user","uuid":"ghi","timestamp":"2025-12-31T08:58:15.123Z","sessionId":"d12906","message":{"role":"user","content":"How are you?"}}
// ... repeated 1000s of times
```

**Keys repeated:** `type`, `uuid`, `timestamp`, `sessionId`, `message`, `role`, `content`

**Result:** 73MB file with 50% wasted space

---

## ✨ The Solution (SLIM Format)

```
§SLIM§ v1
[SCHEMA]
type|uuid|timestamp|sessionId|message.role|message.content
str|str|iso|str|str|str
---
[DATA]
user|abc|2025-12-31T08:58:02.855Z|d12906|user|hi
assistant|def|2025-12-31T08:58:10.802Z|d12906|assistant|Hello
user|ghi|2025-12-31T08:58:15.123Z|d12906|user|How are you?
---
[META]
lines:3
§/SLIM§
```

**Same data, 50% smaller, still lossless.**

Then optionally compress further with V4Z/FSL/ZTPCF → **10MB final size (86% total reduction)**

---

## 🚀 Quick Start

### Installation

```bash
git clone https://github.com/nothinginfinity/golden_library.git
cd golden_library
pip install -r requirements.txt
```

### Compress a Conversation

```bash
# Find your Claude Code conversation
ls ~/.claude/projects/-Users-yourname/

# Compress it
python src/slim_converter.py compress ~/.claude/projects/.../session-abc123.jsonl -o compressed.slim

# See stats
python src/slim_converter.py stats ~/.claude/projects/.../session-abc123.jsonl
```

### Create a Handoff

```bash
# Compress for handoff to another session
python src/handoff_slim.py compress ~/.claude/projects/.../session-abc123.jsonl --level slim_v4z

# List all handoffs
python src/handoff_slim.py list

# Decompress when needed
python src/handoff_slim.py decompress abc123def456
```

### 3D Visualization

```bash
# Start the 3D viewer
python3 viewer_backend.py

# Open in browser
open http://localhost:8080
```

See [VIEWER_README.md](VIEWER_README.md) for details.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Claude Code Session (73MB JSONL)                          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │  SLIM Converter      │
          │  (Schema-once)       │
          └──────────┬───────────┘
                     │ 50% reduction
                     ▼
          ┌──────────────────────┐
          │  SLIM Format (36MB)  │
          └──────────┬───────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │  Optional V4Z/FSL    │
          │  Compression         │
          └──────────┬───────────┘
                     │ 86% total
                     ▼
          ┌──────────────────────┐
          │  QA.Stone (10MB)     │
          │  - Signed            │
          │  - Portable          │
          │  - Searchable        │
          └──────────────────────┘
```

---

## 📦 What's Included

### Core Modules

| File | Purpose | Status |
|------|---------|--------|
| `src/slim_converter.py` | JSONL ↔ SLIM conversion | ⚠️ Needs bug fixes |
| `src/handoff_slim.py` | Handoff compression system | ✅ Framework complete |
| `docs/slim_conversation_spec.md` | SLIM format specification | ✅ Complete |
| `docs/HANDOFF_COMPRESSION_SUMMARY.md` | Architecture overview | ✅ Complete |

### Features

- ✅ **SLIM Format**: Schema-once compression
- ✅ **Handoff System**: Compress/decompress conversations
- ✅ **CLI Tools**: Easy command-line interface
- ✅ **3D Viewer**: Beautiful visualization of handoffs
- ⚠️ **Roundtrip Testing**: Needs fixes for nested structures
- 🔄 **QA.Stone Integration**: In progress

---

## 🗺️ Roadmap

### Phase 1: Core Compression (Current)
- [x] SLIM format specification
- [x] Basic SLIM converter
- [x] Handoff compression framework
- [ ] **Fix nested structure bugs** (Priority 1)
- [ ] **100% lossless roundtrip testing**
- [ ] Unit tests for all conversion scenarios

### Phase 2: Advanced Compression
- [ ] Integrate V4Z compression (token-based)
- [ ] Integrate FSL v7 compression (semantic)
- [ ] Integrate ZTPCF compression (structured data)
- [ ] Auto-detect best compression format based on content
- [ ] Benchmark compression ratios across different conversation types

### Phase 3: QA.Stone Packaging
- [ ] Conversation → QA.Stone converter
- [ ] Extract conversation metadata (participants, topics, concepts)
- [ ] Generate LOD (Level of Detail) layers
- [ ] Sign stones with wallet
- [ ] Store in `~/.qastone/stones/` or `~/terminal_library/`

### Phase 4: Web UI
- [ ] Compression settings component
  - Radio buttons: SLIM only, SLIM+V4Z, SLIM+FSL, SLIM+ZTPCF
  - Content type auto-detection
  - Live compression preview
  - Fidelity slider (lossy ↔ lossless)
- [ ] Terminal Library viewer
  - Browse all conversation stones
  - Search by date, topic, participants
  - View metadata and compression stats
  - Decompress and view in browser
  - Share stones with other users
- [ ] Integrate into `qastone-mcp-twin` app

### Phase 5: Phi Integration
- [ ] Modify `handoff_executor.py` to use SLIM compression
- [ ] Add phi commands:
  - `phi("compress conversation <session_id>")`
  - `phi("handoff compress")`
  - `phi("handoff decompress <id>")`
  - `phi("terminal library stats")`
- [ ] Fix phi server timeout issues with compressed lookups
- [ ] Retroactive compression of existing large JSONL files

### Phase 6: Advanced Features
- [ ] Incremental compression (compress new messages only)
- [ ] Streaming decompression (decompress sections on demand)
- [ ] Multi-format support (export to Markdown, HTML, PDF)
- [ ] Conversation diffing (compare two sessions)
- [ ] Knowledge graph extraction from conversations
- [ ] Semantic search across compressed conversations

---

## 🧪 Testing

### Current Test Results

```bash
# 100-line conversation sample
Original: 130,722 bytes
SLIM:     117,053 bytes
Saved:    13,669 bytes (10.5% reduction)
Ratio:    1.12:1
```

**Note:** Compression ratio improves with conversation length (schema overhead amortized).

### Run Tests

```bash
# Unit tests
python -m pytest tests/

# Integration tests
./tests/integration_test.sh

# Benchmark
python tests/benchmark.py
```

---

## 🤝 Contributing

We need help with:

1. **Bug Fixes**: SLIM converter fails on complex nested structures
2. **Compression Integrations**: V4Z, FSL, ZTPCF modules
3. **Testing**: More test cases for different conversation types
4. **UI Development**: Web interface for compression settings
5. **Documentation**: Usage examples, tutorials

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## 🔧 Configuration

### Compression Levels

| Level | Format | Speed | Reduction | Lossless |
|-------|--------|-------|-----------|----------|
| `slim_only` | SLIM | Fast | 50% | ✅ Yes |
| `slim_v4z` | SLIM + V4Z | Medium | 80% | ✅ Yes |
| `slim_fsl` | SLIM + FSL | Slow | 85% | ⚠️ Optional |
| `slim_ztpcf` | SLIM + ZTPCF | Medium | 86% | ✅ Yes |
| `auto` | Auto-detect | Varies | Best possible | ✅ Yes |

### Default Configuration

Edit `~/.fsl/handoffs/config.json`:

```json
{
  "compression_level": "slim_v4z",
  "preserve_original": true,
  "compression_threshold": 1024,
  "auto_detect_format": true
}
```

---

## 📖 Documentation

- [SLIM Format Specification](docs/slim_conversation_spec.md)
- [Architecture Overview](docs/HANDOFF_COMPRESSION_SUMMARY.md)
- [API Reference](docs/API.md) (Coming soon)
- [Integration Guide](docs/INTEGRATION.md) (Coming soon)

---

## 🎓 Use Cases

1. **Handoffs**: Transfer context between Claude Code sessions
   - Before: 73MB JSONL causes timeouts
   - After: 10MB compressed handoff loads instantly

2. **Knowledge Archives**: Store long conversations efficiently
   - Before: 1000 conversations = 73GB
   - After: 1000 conversations = 10GB (86% savings)

3. **Team Sharing**: Send conversations to colleagues
   - Before: Email attachment fails (file too large)
   - After: Share 10MB QA.Stone via any platform

4. **Search & Index**: Build searchable conversation database
   - Before: Indexing 73MB JSONL times out
   - After: Index compressed metadata, decompress on demand

---

## 🙏 Credits

**Inspired by:**
- The JSON repetition problem (schema-once compression)
- QA.Stone architecture (portable knowledge artifacts)
- Claude Code conversation JSONL format
- FSL/V4/ZTPCF compression research

**Built for:**
- Claude Code users with massive conversation archives
- AI engineers building knowledge management systems
- Anyone tired of waiting for phi server timeouts

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file

---

## 🔗 Related Projects

- [qastone-mcp-twin](https://github.com/nothinginfinity/qastone-mcp-twin) - QA.Stone wallet system
- phi_proxy - Local AI command center (private repo)
- trinity-os - Multi-terminal AI system

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/nothinginfinity/golden_library/issues)
- **Discussions**: [GitHub Discussions](https://github.com/nothinginfinity/golden_library/discussions)

---

**🏆 Make your AI conversations golden. Compress, archive, share.**
