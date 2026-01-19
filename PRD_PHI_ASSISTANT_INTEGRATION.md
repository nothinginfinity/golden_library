# PRD: Phi Assistant Integration for Dashboard

**Status:** PLANNED
**Priority:** Medium
**Created:** 2026-01-17
**Location:** `ztgi/golden_library/`

---

## Overview

Add phi-proxy as a third assistant option in the Storage panel's AI Research Assistant, alongside Claude and DeepSeek. Phi provides **zero token cost** search using local LLM (Ollama) and has 1000+ commands with learning capabilities.

---

## Current Architecture

### Frontend (claude_dashboard.html)

```html
<!-- Line 3961-3963: Model selector dropdown -->
<select id="assistant-model" class="filter-btn">
  <option value="claude">Claude (Sonnet 4.5)</option>
  <option value="deepseek">DeepSeek</option>
  <!-- ADD: <option value="phi">Phi (Local - Free)</option> -->
</select>
```

### Backend (dashboard_server.py)

```python
# Line 4102-4108: Model routing in serve_assistant_chat()
if model == 'claude':
    self.call_claude_with_tools(message, conversation_history, tools, api_keys)
elif model == 'deepseek':
    self.call_deepseek_with_tools(message, conversation_history, tools, api_keys)
# ADD: elif model == 'phi':
#          self.call_phi_with_tools(message, conversation_history, tools)
else:
    self.wfile.write(f'data: {json.dumps({"error": "Unknown model"})}\n\n'.encode())
```

### Tools Available to Assistant

The assistant has 4 tools (defined in `serve_assistant_chat`, lines 4019-4100):

1. **search_history** - Search Claude history (conversations, projects, file edits, todos, plans)
2. **get_related_items** - Find items related to a specific history item
3. **get_timeline** - Get activity timeline grouped by time period
4. **create_artifact** - Create visual artifacts (chart, checklist, table)

---

## Phi Capabilities

### Location
`~/ztgi/phi_proxy/`

### Relevant Modules

| Module | Purpose | Use Case |
|--------|---------|----------|
| `deep_search_handler.py` | Search everywhere (files, iCloud, drives, Spotlight) | Extend search beyond Claude history |
| `llm_router.py` | Route to Ollama, DeepSeek, Grok, OpenAI | Use local LLM for zero cost |
| `tool_router.py` | Route natural language to 1000+ commands | Natural language interface |
| `shell_executor.py` | Execute shell commands safely | File operations |
| `learning.py` | Learn new commands | Improve over time |

### Local LLM Options (via Ollama)

```python
# From llm_router.py - costs $0
OLLAMA_MODELS = ["phi3:mini", "llama3", "mistral"]
```

### Search Locations (from deep_search_handler.py)

```python
SEARCH_LOCATIONS = {
    "documents": HOME / "Documents",
    "downloads": HOME / "Downloads",
    "desktop": HOME / "Desktop",
    "slop": HOME / "slop",
    "ztgi": HOME / "ztgi",
    "icloud_archive": HOME / "iCloud Drive (Archive)",
    "fsl_compressed": HOME / ".fsl" / "compressed_chunks",
}
```

---

## Implementation Plan

### Phase 1: Frontend (5 min)

**File:** `claude_dashboard.html`

1. Add phi option to dropdown (line ~3963):
```html
<option value="phi">Phi (Local - Free)</option>
```

### Phase 2: Backend Handler (30 min)

**File:** `dashboard_server.py`

1. Add import at top:
```python
# Add phi-proxy to path
sys.path.insert(0, str(Path.home() / 'ztgi' / 'phi_proxy'))
from deep_search_handler import handle_deep_search
from llm_router import MultiLLMRouter
```

2. Add routing in `serve_assistant_chat()` (after line 4106):
```python
elif model == 'phi':
    self.call_phi_with_tools(message, conversation_history, tools)
```

3. Add new method `call_phi_with_tools()`:
```python
def call_phi_with_tools(self, message, history, tools):
    """Call phi-proxy with local LLM for zero-cost search."""
    try:
        # Initialize phi's LLM router
        router = MultiLLMRouter()

        # Use Ollama (local, free)
        response = router.call_ollama(
            model="phi3:mini",
            messages=history + [{"role": "user", "content": message}],
            tools=tools
        )

        # Stream response
        for chunk in response:
            self.wfile.write(f'data: {json.dumps({"chunk": chunk})}\n\n'.encode())
            self.wfile.flush()

    except Exception as e:
        self.wfile.write(f'data: {json.dumps({"error": str(e)})}\n\n'.encode())
```

### Phase 3: Enhanced Search (Optional, 1 hr)

Add phi's deep search as an additional tool:

```python
{
    "name": "deep_search",
    "description": "Search across entire system: files, iCloud, external drives, voice memos",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "locations": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Locations to search: documents, downloads, icloud, ztgi, etc."
            }
        },
        "required": ["query"]
    }
}
```

---

## Dependencies

### Required
- Ollama installed and running (`ollama serve`)
- At least one model pulled (`ollama pull phi3:mini`)

### Optional
- DeepSeek API key (fallback if Ollama unavailable)

### Check Ollama Status
```bash
curl http://localhost:11434/api/tags
```

---

## Cost Comparison

| Model | Cost per 1M tokens | Speed | Quality |
|-------|-------------------|-------|---------|
| **Phi (Ollama)** | **$0** | Fast | Good for search |
| DeepSeek | $0.14 | Fast | Good |
| Claude | $3-15 | Medium | Excellent |

---

## Testing Checklist

- [ ] Ollama running locally
- [ ] Phi3:mini model available
- [ ] Dropdown shows "Phi (Local - Free)" option
- [ ] Selecting phi routes to `call_phi_with_tools()`
- [ ] Search queries return results
- [ ] Streaming response works
- [ ] Error handling for Ollama not running
- [ ] Fallback to DeepSeek if Ollama fails

---

## Files to Modify

| File | Changes |
|------|---------|
| `claude_dashboard.html` | Add dropdown option (1 line) |
| `dashboard_server.py` | Add imports, routing, and handler (~50 lines) |

---

## Rollback

If issues occur:
1. Remove `<option value="phi">` from HTML
2. Remove phi routing from `serve_assistant_chat()`
3. Remove `call_phi_with_tools()` method

No database or state changes required.

---

## Future Enhancements

1. **Mini-swarm mode** - Use phi's multi-instance for parallel search
2. **Learning integration** - Phi learns from search patterns
3. **Voice search** - Integrate phi's voice memo search
4. **External drive search** - Search Samsung archive via phi

---

## Notes

- Phi is already available as MCP server in Claude Code
- This integration brings phi's search to the web dashboard
- Zero token cost makes it ideal for frequent/exploratory searches
- Can always escalate to Claude for complex reasoning
