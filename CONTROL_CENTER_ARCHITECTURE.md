# Claude Control & Generation Center - Architecture

**Vision:** Unified interface to manage multiple Claude configurations, daemons, and AI-assisted setup.

---

## 1. Config Arsenal System

### Storage Structure
```
~/.claude/arsenal/
├── profiles/
│   ├── koda.json              # Builder profile metadata
│   ├── cairn.json             # Architect profile metadata
│   ├── prax.json              # Strategist profile metadata
│   └── custom_*.json          # User-created profiles
├── library/
│   ├── claude_md/
│   │   ├── koda_builder.md
│   │   ├── cairn_architect.md
│   │   ├── prax_strategist.md
│   │   └── custom_*.md
│   ├── agents_md/
│   │   ├── default.md
│   │   ├── extended.md
│   │   └── custom_*.md
│   ├── hooks/
│   │   ├── basic/              # Hook set folder
│   │   │   ├── pre_tool.sh
│   │   │   └── post_tool.sh
│   │   ├── advanced/
│   │   │   ├── pre_tool.sh
│   │   │   ├── post_tool.sh
│   │   │   └── pre_tool_enforcer.py
│   │   └── custom_*/
│   └── settings/
│       ├── minimal.json
│       ├── full_featured.json
│       └── custom_*.json
└── active.json                # Currently active profile

Active configs (symlinked):
~/CLAUDE.md -> ~/.claude/arsenal/library/claude_md/koda_builder.md
~/agents.md -> ~/.claude/arsenal/library/agents_md/default.md
~/.claude/hooks/* -> ~/.claude/arsenal/library/hooks/basic/*
~/.claude/settings.json -> ~/.claude/arsenal/library/settings/minimal.json
```

### Profile Schema
```json
{
  "id": "koda",
  "name": "Koda Builder",
  "description": "Fast execution, practical solutions, results-oriented",
  "icon": "🔨",
  "created": "2026-01-13T23:00:00Z",
  "modified": "2026-01-13T23:00:00Z",
  "author": "system",
  "components": {
    "claude_md": "claude_md/koda_builder.md",
    "agents_md": "agents_md/default.md",
    "hooks": "hooks/basic",
    "settings": "settings/minimal.json"
  },
  "tags": ["builder", "fast", "coding"],
  "active": true
}
```

### Profile Operations
- **List Profiles** - Show all available profiles
- **Activate Profile** - Switch to profile (creates symlinks)
- **Create Profile** - New profile from scratch or clone existing
- **Edit Profile** - Modify profile components
- **Delete Profile** - Remove profile (keeps library files)
- **Export Profile** - Package as .tar.gz for sharing
- **Import Profile** - Load shared profile

---

## 2. Daemon Manager

### Daemon Registry
```
~/.claude/daemons/
├── registry.json              # All registered daemons
├── pids/                      # PID files
│   ├── auto_compress.pid
│   ├── phi_inbox.pid
│   └── custom_daemon.pid
└── logs/                      # Daemon logs
    ├── auto_compress.log
    ├── phi_inbox.log
    └── custom_daemon.log
```

### Daemon Schema
```json
{
  "id": "auto_compress",
  "name": "Auto-Compress Daemon",
  "description": "Automatically compresses Claude conversations",
  "type": "system",
  "command": "python3",
  "args": [
    "~/ztgi/golden_library/daemons/auto_compress_daemon.py"
  ],
  "working_dir": "~/ztgi/golden_library/daemons",
  "autostart": true,
  "restart_on_failure": true,
  "log_file": "~/.claude/daemons/logs/auto_compress.log",
  "pid_file": "~/.claude/daemons/pids/auto_compress.pid",
  "status": "running",
  "pid": 12345,
  "started_at": "2026-01-13T20:00:00Z",
  "uptime_seconds": 10800
}
```

### Daemon Operations
- **List Daemons** - Show all registered daemons
- **Start Daemon** - Launch daemon process
- **Stop Daemon** - Gracefully stop daemon
- **Restart Daemon** - Stop then start
- **Add Daemon** - Register new daemon
- **Remove Daemon** - Unregister daemon
- **View Logs** - Stream daemon logs
- **Configure** - Edit daemon settings

### System Daemons (Pre-configured)
1. **auto_compress_daemon** - Compression system
2. **phi_inbox_daemon** - Inbox message processor
3. **phi_process_monitor** - Process monitoring
4. **dashboard_server** - This control center

---

## 3. AI Chat Assistant

### Chat Interface
- **Query Input** - Ask questions about configs
- **AI Response** - Claude API integration
- **Context Awareness** - Knows your current setup
- **Recommendations** - Suggests configs for tasks

### Example Queries
```
User: "Which profile should I use for building a new feature?"
AI: "I recommend the Koda Builder profile. It's optimized for fast
     implementation with practical solutions. It includes minimal hooks
     for speed and focuses on getting working code quickly."

User: "What's the difference between basic and advanced hooks?"
AI: "Basic hooks include simple pre/post tool logging. Advanced hooks
     add enforcement, validation, and phi_proxy integration. Use advanced
     if you need ZTI indexing and cross-terminal coordination."

User: "Create a profile for debugging sessions"
AI: "I'll create a 'Debugger' profile with:
     - Extended logging in CLAUDE.md
     - Debug-focused agents.md
     - Verbose hooks with stack traces
     - Settings with increased timeout values
     Would you like me to generate this?"
```

### Chat Backend
```python
POST /api/chat
{
  "message": "Which profile for debugging?",
  "context": {
    "current_profile": "koda",
    "available_profiles": [...],
    "recent_tasks": [...]
  }
}

Response:
{
  "response": "I recommend creating a Debugger profile...",
  "suggestions": [
    {"action": "create_profile", "name": "debugger"},
    {"action": "activate_profile", "name": "debugger"}
  ]
}
```

---

## 4. Config Generation Tools

### Templates
```
~/.claude/arsenal/templates/
├── claude_md/
│   ├── minimal.md.template
│   ├── builder.md.template
│   ├── architect.md.template
│   └── custom.md.template
├── agents_md/
│   └── default.md.template
├── hooks/
│   ├── basic_set.tar.gz
│   └── advanced_set.tar.gz
└── profiles/
    ├── minimal_profile.json
    └── full_profile.json
```

### Generation Workflow
1. **Select Template** - Choose base template
2. **Customize** - AI-assisted customization
3. **Preview** - View generated config
4. **Test** - Dry-run with test prompts
5. **Save** - Add to library
6. **Activate** - Switch to new config

### AI-Assisted Generation
```
POST /api/generate/config
{
  "type": "claude_md",
  "requirements": [
    "Focus on code review",
    "Strict style enforcement",
    "No emoji use"
  ],
  "base_template": "architect"
}

Response:
{
  "generated_content": "# CLAUDE.md\n\n...",
  "explanation": "Created a code review focused config...",
  "filename": "code_reviewer.md"
}
```

---

## 5. Dashboard UI Updates

### New Navigation
```
┌─────────────────────────────────────────┐
│ Claude Control & Generation Center      │
├─────────────────────────────────────────┤
│ 📊 Dashboard │ 🔍 Search │ ⚙️ Config   │
│ 🎯 Arsenal │ 🤖 Daemons │ 💬 Chat      │
└─────────────────────────────────────────┘
```

### Arsenal Tab
```
┌─────────────────────────────────────────┐
│ Config Arsenal                           │
├─────────────────────────────────────────┤
│ Active Profile: Koda Builder 🔨         │
│ [Switch Profile ▼]                      │
├─────────────────────────────────────────┤
│ Available Profiles:                      │
│ ┌─────────────────┬─────────────────┐  │
│ │ 🔨 Koda Builder │ 🏗️ Cairn Arch   │  │
│ │ Active          │ [Activate]      │  │
│ │ [Edit] [Clone]  │ [Edit] [Clone]  │  │
│ └─────────────────┴─────────────────┘  │
│ ┌─────────────────┬─────────────────┐  │
│ │ 🎯 Prax Strat   │ 🐛 Debugger     │  │
│ │ [Activate]      │ [Activate]      │  │
│ │ [Edit] [Delete] │ [Edit] [Delete] │  │
│ └─────────────────┴─────────────────┘  │
│ [+ Create New Profile]                  │
├─────────────────────────────────────────┤
│ Config Library:                          │
│ [CLAUDE.md: 5] [agents.md: 3]          │
│ [Hooks: 4 sets] [Settings: 6]          │
│ [View Library →]                        │
└─────────────────────────────────────────┘
```

### Daemons Tab
```
┌─────────────────────────────────────────┐
│ Daemon Manager                           │
├─────────────────────────────────────────┤
│ Running: 3 │ Stopped: 1 │ Failed: 0    │
├─────────────────────────────────────────┤
│ ✅ auto_compress_daemon                 │
│    Uptime: 3h 24m │ CPU: 2% │ Mem: 45MB│
│    [Stop] [Restart] [Logs] [Config]    │
│                                          │
│ ✅ phi_inbox_daemon                     │
│    Uptime: 3h 24m │ CPU: 1% │ Mem: 32MB│
│    [Stop] [Restart] [Logs] [Config]    │
│                                          │
│ ✅ dashboard_server                     │
│    Uptime: 15m │ CPU: 0% │ Mem: 28MB   │
│    [Stop] [Restart] [Logs] [Config]    │
│                                          │
│ ⏸️ custom_daemon                        │
│    Status: Stopped                       │
│    [Start] [Remove] [Config]            │
├─────────────────────────────────────────┤
│ [+ Add New Daemon]                      │
└─────────────────────────────────────────┘
```

### Chat Tab
```
┌─────────────────────────────────────────┐
│ AI Assistant 💬                         │
├─────────────────────────────────────────┤
│ Chat History:                            │
│ ┌───────────────────────────────────┐  │
│ │ You: Which profile for debugging? │  │
│ │                                    │  │
│ │ AI: I recommend creating a        │  │
│ │ "Debugger" profile with extended  │  │
│ │ logging and verbose hooks...      │  │
│ │ [Create Profile] [View Details]   │  │
│ └───────────────────────────────────┘  │
│ ┌───────────────────────────────────┐  │
│ │ You: Compare Koda vs Cairn        │  │
│ │                                    │  │
│ │ AI: Koda focuses on fast          │  │
│ │ implementation, while Cairn...    │  │
│ └───────────────────────────────────┘  │
├─────────────────────────────────────────┤
│ [Type your question...]                 │
│ [Send] [Clear]                          │
├─────────────────────────────────────────┤
│ Quick Actions:                           │
│ • Recommend profile for task            │
│ • Compare two profiles                   │
│ • Generate new config                    │
│ • Explain config differences            │
└─────────────────────────────────────────┘
```

---

## 6. API Endpoints

### Arsenal API
```
GET    /api/arsenal/profiles              - List all profiles
GET    /api/arsenal/profile/:id           - Get profile details
POST   /api/arsenal/profile               - Create new profile
PUT    /api/arsenal/profile/:id           - Update profile
DELETE /api/arsenal/profile/:id           - Delete profile
POST   /api/arsenal/activate/:id          - Activate profile
GET    /api/arsenal/library               - List library files
POST   /api/arsenal/library/upload        - Upload file to library
DELETE /api/arsenal/library/:path         - Delete library file
GET    /api/arsenal/active                - Get active profile
```

### Daemon API
```
GET    /api/daemons                       - List all daemons
GET    /api/daemons/:id                   - Get daemon details
POST   /api/daemons/:id/start             - Start daemon
POST   /api/daemons/:id/stop              - Stop daemon
POST   /api/daemons/:id/restart           - Restart daemon
GET    /api/daemons/:id/logs              - Get daemon logs (stream)
GET    /api/daemons/:id/status            - Get daemon status
POST   /api/daemons                       - Register new daemon
PUT    /api/daemons/:id                   - Update daemon config
DELETE /api/daemons/:id                   - Unregister daemon
```

### Chat API
```
POST   /api/chat                          - Send chat message
GET    /api/chat/history                  - Get chat history
DELETE /api/chat/history                  - Clear chat history
POST   /api/chat/action/:action           - Execute suggested action
```

### Generation API
```
POST   /api/generate/config               - AI-generate config
GET    /api/generate/templates            - List available templates
POST   /api/generate/profile              - Generate full profile
POST   /api/generate/test                 - Test generated config
```

---

## 7. Implementation Phases

### Phase 1: Arsenal Backend (Week 1)
- ✅ Profile storage system
- ✅ Library management
- ✅ Profile activation (symlinks)
- ✅ CRUD operations
- ✅ Pre-populate with Koda/Cairn/Prax profiles

### Phase 2: Daemon Manager (Week 1-2)
- ✅ Daemon registry
- ✅ Start/stop/restart
- ✅ Status monitoring
- ✅ Log viewing
- ✅ Add/remove daemons

### Phase 3: Dashboard UI (Week 2)
- ✅ Arsenal tab
- ✅ Daemons tab
- ✅ Profile switcher
- ✅ Daemon controls
- ✅ Real-time status updates

### Phase 4: Chat Assistant (Week 3)
- ✅ Chat interface
- ✅ Claude API integration
- ✅ Context-aware responses
- ✅ Action suggestions
- ✅ Quick actions

### Phase 5: Config Generation (Week 3-4)
- ✅ Template system
- ✅ AI-assisted generation
- ✅ Config testing
- ✅ Profile export/import

---

## 8. Success Metrics

### User Experience
- Switch between profiles in <3 seconds
- Create new profile in <2 minutes (with AI)
- Manage daemons without terminal
- Get AI config recommendations in <10 seconds

### System Performance
- Profile activation: instant (symlinks)
- Daemon start/stop: <2 seconds
- Chat response: <5 seconds
- Config generation: <10 seconds

### Cost Efficiency
- Chat API calls: ~$0.01 per query (Haiku)
- Config generation: ~$0.05 per config (Sonnet)
- Estimated monthly: ~$5 for 100 queries

---

## 9. Security Considerations

### Profile Activation
- Backup current configs before switching
- Validate all symlink targets
- Prevent symlink outside ~/.claude/arsenal/

### Daemon Management
- Sandboxed daemon execution
- Resource limits (CPU, memory)
- Log rotation to prevent disk fill
- No arbitrary code execution

### Chat Assistant
- No direct file system access from chat
- All actions require user confirmation
- API key stored securely
- Rate limiting on API calls

---

## 10. Migration Path

### Existing Users
1. **Detect current config** on first run
2. **Create "Current" profile** from existing files
3. **Backup originals** to ~/.claude/arsenal/backups/
4. **Symlink to arsenal** (transparent migration)
5. **User can switch back** anytime

### Rollback
- Keep backups for 30 days
- "Restore Original Config" button
- Removes symlinks, restores files
- Zero data loss

---

## Summary

This transforms the dashboard from a **viewer** into a **control center**:

**Before:**
- View compressed data
- Search conversations
- Read config files

**After:**
- **Manage multiple configs** (Arsenal)
- **Control daemons** (Manager)
- **AI-assisted setup** (Chat)
- **Generate new configs** (Templates)
- **One-click profile switching**

**Result:** Complete control over Claude's behavior without editing files manually.

---

**Ready to implement?** Let me know which phase to start with, or if you want me to build it all at once!
