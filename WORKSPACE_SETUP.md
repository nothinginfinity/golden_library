# Collaborative Workspace Setup

## Quick Start

The collaborative workspace requires an Anthropic API key to power the 3 AI agents.

### 1. Get an API Key

Get your API key from: https://console.anthropic.com/settings/keys

### 2. Set the Environment Variable

**Option A: Terminal Session (Temporary)**
```bash
export ANTHROPIC_API_KEY="sk-ant-api03-your-key-here"
```

**Option B: Create .env File (Recommended)**
```bash
# Copy the example file
cp .env.example .env

# Edit .env and add your API key
# ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
```

Then load it before starting the server:
```bash
set -a; source .env; set +a
python3 dashboard_server.py
```

**Option C: Shell Profile (Permanent)**

Add to `~/.zshrc` or `~/.bashrc`:
```bash
export ANTHROPIC_API_KEY="sk-ant-api03-your-key-here"
```

Then reload:
```bash
source ~/.zshrc  # or source ~/.bashrc
```

### 3. Start the Server

```bash
cd ~/ztgi/golden_library
python3 dashboard_server.py
```

### 4. Open the Workspace

Navigate to: http://localhost:8080

Click the **🚀 Workspace** tab (second tab in navigation)

## Using the Workspace

### Three Agents

1. **🅰️ Agent A (Koda)** - Builder/Implementation agent
   - Focus: Coding, building, practical solutions
   - Use for: Writing code, implementing features, debugging

2. **🅱️ Agent B (Cairn)** - Architect/Design agent
   - Focus: Architecture, design, specifications
   - Use for: System design, code review, planning

3. **🎭 Moderator (Prax)** - Orchestrator/Coordinator
   - Focus: Coordination, strategy, synthesis
   - Use for: Coordinating A & B, strategic decisions

### Example Usage

**Agent A (Koda):**
```
Write a Python function to validate email addresses
```

**Agent B (Cairn):**
```
Design the architecture for a user authentication system
```

**Moderator (Prax):**
```
Agent A: Implement the login endpoint.
Agent B: Review the implementation for security issues.
Then synthesize the feedback.
```

## Troubleshooting

### Error: "ANTHROPIC_API_KEY not found in environment"

The API key is not set. Follow setup steps above.

### Server won't start

Check if another process is using port 8080:
```bash
lsof -i :8080
```

Kill it if needed:
```bash
kill -9 <PID>
```

### No streaming responses

1. Check browser console for errors (F12 → Console)
2. Verify API key is valid
3. Check server logs for errors

## Phase 1 MVP Features

✅ Single-user controlling 3 agents
✅ Real-time streaming responses
✅ Independent agent contexts
✅ Status indicators
✅ Chat history
✅ Clear chat function

## Coming Soon (Phase 2+)

⏳ WebSocket multiplayer support
⏳ Document loading UI
⏳ Moderator coordination logic
⏳ Workflow presets
⏳ Session export/import

## API Costs

Agents use Claude Sonnet 4 (default model). Approximate costs:
- ~$3 per million input tokens
- ~$15 per million output tokens

A typical conversation (10 exchanges) costs ~$0.05-0.20

Monitor usage at: https://console.anthropic.com/settings/usage
