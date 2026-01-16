# Multi-LLM API Key Management

## Overview

The Control Center now supports managing API keys for 10 different LLM providers:

1. 🟣 **Claude** (Anthropic) - `claude-sonnet-4`, `claude-opus-4`
2. 🟢 **OpenAI** - `gpt-4`, `gpt-4-turbo`, `o1`
3. 🔵 **Gemini** (Google) - `gemini-pro`, `gemini-ultra`
4. ⚫ **Grok** (X.AI) - `grok-beta`
5. 🟠 **Groq** - Ultra-fast inference for `llama`, `mixtral`
6. 🔴 **Mistral** - `mistral-large`, `mistral-medium`
7. 🟡 **DeepSeek** - `deepseek-coder`, `deepseek-chat`
8. 🟣 **Cerebras** - High-performance inference
9. 🟢 **SambaNova** - Fast inference platform
10. 🔵 **OpenRouter** - Access 100+ models via one API

## Setup Instructions

### 1. Navigate to Config Tab

1. Open Control Center: http://localhost:8080
2. Click **⚙️ Config** tab (third tab in navigation)
3. Scroll to **🔑 API Keys - Multi-LLM Provider** section

### 2. Add Your API Keys

For each provider you want to use:

1. Click the input field
2. Paste your API key
3. Click the 👁️ button to toggle visibility (verify it's correct)
4. Click **💾 Save API Keys** at the bottom

### 3. Get API Keys

Click the links under each provider to get keys:

| Provider | Get Key From |
|----------|-------------|
| Claude | [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys) |
| OpenAI | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| Gemini | [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) |
| Grok | [console.x.ai](https://console.x.ai/) |
| Groq | [console.groq.com/keys](https://console.groq.com/keys) |
| Mistral | [console.mistral.ai/api-keys/](https://console.mistral.ai/api-keys/) |
| DeepSeek | [platform.deepseek.com/api_keys](https://platform.deepseek.com/api_keys) |
| Cerebras | [cloud.cerebras.ai](https://cloud.cerebras.ai/) |
| SambaNova | [cloud.sambanova.ai](https://cloud.sambanova.ai/) |
| OpenRouter | [openrouter.ai/keys](https://openrouter.ai/keys) |

### 4. Storage & Security

API keys are stored securely at:
```
~/.claude/api_keys.json
```

**Security features:**
- File permissions set to `600` (owner read/write only)
- Not committed to git (add to `.gitignore`)
- Masked in UI (show as `******` by default)
- Toggle visibility with 👁️ button

## Using API Keys

### Workspace (Phase 1 - Claude Only)

The collaborative workspace currently uses Claude API:

1. Set your Claude API key in Config tab
2. Navigate to **🚀 Workspace** tab
3. Chat with agents - they'll use your saved Claude key

**API Key Priority:**
1. Saved in Config tab (`~/.claude/api_keys.json`)
2. Environment variable `ANTHROPIC_API_KEY`
3. Direct parameter (development only)

### Future: Multi-Provider Support (Phase 2+)

Coming soon:
- Model selector dropdown in Workspace
- Per-agent model selection
- Mix models: Agent A uses Claude, Agent B uses GPT-4
- Cost tracking per provider
- Automatic failover to cheaper models

## Reload Keys

If you update keys outside the dashboard:

1. Click **🔄 Reload** button
2. Keys will refresh from `~/.claude/api_keys.json`

## Example Workflow

```bash
# 1. Set Claude key via Config tab
# (Navigate to Config → API Keys → paste key → Save)

# 2. Test workspace
# Navigate to Workspace tab
# Send message to Agent A
# Agent responds using your Claude key

# 3. Add OpenAI key
# Config → OpenAI field → paste key → Save

# 4. (Future) Switch models in workspace
# Workspace → Model selector → choose GPT-4
```

## Troubleshooting

### Error: "ANTHROPIC_API_KEY not found"

**Solution:**
1. Go to Config tab
2. Add your Claude API key
3. Click Save
4. Refresh page

### Keys not loading

**Check file exists:**
```bash
ls -la ~/.claude/api_keys.json
```

**Check permissions:**
```bash
# Should be -rw------- (600)
chmod 600 ~/.claude/api_keys.json
```

**Check JSON format:**
```bash
cat ~/.claude/api_keys.json
# Should look like:
# {
#   "claude": "sk-ant-api03-...",
#   "openai": "sk-proj-..."
# }
```

### Save button doesn't work

Check browser console (F12 → Console) for errors.

**Common issues:**
- Server not running
- Port 8080 blocked
- CORS issues (shouldn't happen on localhost)

## API Cost Estimates

Approximate costs per 1M tokens (as of Jan 2026):

| Provider | Input | Output | Notes |
|----------|-------|--------|-------|
| Claude Sonnet 4 | $3 | $15 | Default for workspace |
| Claude Opus 4 | $15 | $75 | Most capable |
| GPT-4 Turbo | $10 | $30 | Fast & capable |
| Gemini Pro | $0.50 | $1.50 | Very cheap |
| Groq (Llama) | $0.05 | $0.08 | Ultra cheap, fast |
| DeepSeek | $0.14 | $0.28 | Cheap, good for code |
| OpenRouter | Varies | Varies | Access all models |

**Workspace Usage (typical):**
- 10 message conversation ≈ 20K input + 5K output tokens
- Claude Sonnet: ~$0.06 per conversation
- Budget: ~$5/month for moderate use

## Advanced: Direct File Editing

You can also manually edit `~/.claude/api_keys.json`:

```json
{
  "claude": "sk-ant-api03-YOUR-KEY-HERE",
  "openai": "sk-proj-YOUR-KEY-HERE",
  "gemini": "AIza-YOUR-KEY-HERE",
  "grok": "xai-YOUR-KEY-HERE",
  "groq": "gsk_YOUR-KEY-HERE",
  "mistral": "YOUR-KEY-HERE",
  "deepseek": "sk-YOUR-KEY-HERE",
  "cerebras": "YOUR-KEY-HERE",
  "sambanova": "YOUR-KEY-HERE",
  "openrouter": "sk-or-YOUR-KEY-HERE"
}
```

Then click **🔄 Reload** in Config tab.

## Next Steps

1. **Save your Claude key** - Required for workspace
2. **Try the workspace** - Test with Agent A, B, Moderator
3. **Add other providers** - Experiment with different models (Phase 2)
4. **Monitor costs** - Check provider dashboards for usage

## Support

- Workspace docs: `WORKSPACE_SETUP.md`
- Issues: https://github.com/anthropics/claude-code/issues
- Provider docs: Check provider URLs above
