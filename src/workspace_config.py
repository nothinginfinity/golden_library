#!/usr/bin/env python3
"""
Phase 4C.6: Workspace Configuration & Hooks

Provides:
- CLAUDE.md workspace configuration loading
- Event hooks system
- User preferences storage
- Config validation and defaults

Run with: python3 workspace_config.py
"""

import os
import re
import json
import asyncio
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Callable, Set
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HookEvent(Enum):
    """Events that can trigger hooks."""
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    USER_JOIN = "user_join"
    USER_LEAVE = "user_leave"
    MESSAGE_SENT = "message_sent"
    AGENT_RESPONSE = "agent_response"
    DELEGATION = "delegation"
    TASK_COMPLETE = "task_complete"
    DEMO_START = "demo_start"
    DEMO_STOP = "demo_stop"
    CANVAS_UPDATE = "canvas_update"
    TOOL_USE = "tool_use"
    ERROR = "error"


@dataclass
class Hook:
    """A registered hook callback."""
    id: str
    event: HookEvent
    callback: Callable
    priority: int = 0  # Higher priority runs first
    enabled: bool = True
    description: str = ""

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'event': self.event.value,
            'priority': self.priority,
            'enabled': self.enabled,
            'description': self.description
        }


@dataclass
class UserPreferences:
    """User-specific preferences."""
    user_id: str
    theme: str = "dark"  # dark, light, auto
    notification_sound: bool = True
    notification_desktop: bool = True
    show_agent_typing: bool = True
    compact_messages: bool = False
    code_font_size: int = 14
    preferred_agent: Optional[str] = None  # cairn, koda, prax
    keyboard_shortcuts: bool = True
    auto_scroll: bool = True
    highlight_mentions: bool = True
    custom_css: Optional[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'UserPreferences':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class WorkspaceSettings:
    """Workspace-level configuration."""
    # Identity
    workspace_name: str = "Workspace"
    workspace_id: Optional[str] = None

    # Agent Configuration
    default_agent: str = "prax"
    agent_personalities: Dict[str, str] = field(default_factory=lambda: {
        'prax': 'strategic',
        'cairn': 'analytical',
        'koda': 'practical'
    })
    agent_temperature: Dict[str, float] = field(default_factory=lambda: {
        'prax': 0.7,
        'cairn': 0.5,
        'koda': 0.3
    })

    # Collaboration
    max_users: int = 12
    require_approval_for_join: bool = False
    allow_anonymous: bool = False

    # Demo Mode
    demo_branding: Dict[str, str] = field(default_factory=dict)
    demo_auto_highlight: bool = True

    # Features
    enable_canvas: bool = True
    enable_delegation: bool = True
    enable_tool_gateway: bool = True
    enable_conversation_db: bool = True

    # Performance
    message_batch_size: int = 10
    context_window: int = 50
    max_tokens_per_response: int = 4096

    # Custom
    custom_system_prompt: Optional[str] = None
    custom_instructions: List[str] = field(default_factory=list)
    blocked_tools: List[str] = field(default_factory=list)
    allowed_domains: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'WorkspaceSettings':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class WorkspaceConfig:
    """
    Manages workspace configuration, hooks, and user preferences.

    Loads configuration from:
    1. Workspace CLAUDE.md file
    2. User preferences JSON
    3. Environment variables
    """

    def __init__(self, workspace_dir: Optional[str] = None):
        """
        Initialize workspace configuration.

        Args:
            workspace_dir: Directory containing CLAUDE.md
        """
        self.workspace_dir = Path(workspace_dir).expanduser() if workspace_dir else Path.cwd()
        self.settings = WorkspaceSettings()
        self.user_preferences: Dict[str, UserPreferences] = {}
        self.hooks: Dict[str, Hook] = {}
        self._hook_counter = 0
        self._preferences_file = self.workspace_dir / ".workspace_preferences.json"

        # Load configuration
        self._load_claude_md()
        self._load_preferences()

    # ===== Configuration Loading =====

    def _load_claude_md(self):
        """Load configuration from CLAUDE.md file."""
        claude_md_path = self.workspace_dir / "CLAUDE.md"
        if not claude_md_path.exists():
            logger.info(f"[WorkspaceConfig] No CLAUDE.md found at {claude_md_path}")
            return

        try:
            content = claude_md_path.read_text()
            self._parse_claude_md(content)
            logger.info(f"[WorkspaceConfig] Loaded CLAUDE.md from {claude_md_path}")
        except Exception as e:
            logger.error(f"[WorkspaceConfig] Error loading CLAUDE.md: {e}")

    def _parse_claude_md(self, content: str):
        """Parse CLAUDE.md content for workspace settings."""
        # Extract workspace name from title
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if title_match:
            self.settings.workspace_name = title_match.group(1).strip()

        # Extract settings from code blocks with workspace-config language
        config_blocks = re.findall(
            r'```(?:workspace-config|json)\s*\n(.*?)```',
            content,
            re.DOTALL
        )

        for block in config_blocks:
            try:
                config = json.loads(block)
                self._apply_config(config)
            except json.JSONDecodeError:
                # Try YAML-like parsing
                self._parse_yaml_like(block)

        # Extract custom instructions from specific sections
        instructions_match = re.search(
            r'##\s*(?:Custom\s+)?Instructions\s*\n(.*?)(?=\n##|\Z)',
            content,
            re.DOTALL | re.IGNORECASE
        )
        if instructions_match:
            instructions = [
                line.strip().lstrip('- ')
                for line in instructions_match.group(1).strip().split('\n')
                if line.strip() and line.strip().startswith('-')
            ]
            self.settings.custom_instructions = instructions

        # Extract system prompt
        prompt_match = re.search(
            r'##\s*System\s+Prompt\s*\n(.*?)(?=\n##|\Z)',
            content,
            re.DOTALL | re.IGNORECASE
        )
        if prompt_match:
            self.settings.custom_system_prompt = prompt_match.group(1).strip()

        # Extract demo branding
        branding_match = re.search(
            r'##\s*(?:Demo\s+)?Branding\s*\n(.*?)(?=\n##|\Z)',
            content,
            re.DOTALL | re.IGNORECASE
        )
        if branding_match:
            branding_text = branding_match.group(1)
            branding = {}
            for line in branding_text.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lstrip('- ').lower().replace(' ', '_')
                    branding[key] = value.strip()
            self.settings.demo_branding = branding

    def _parse_yaml_like(self, block: str):
        """Parse YAML-like config blocks."""
        for line in block.split('\n'):
            line = line.strip()
            if ':' in line and not line.startswith('#'):
                key, value = line.split(':', 1)
                key = key.strip().lower().replace(' ', '_').replace('-', '_')
                value = value.strip()

                # Type conversion
                if value.lower() in ('true', 'yes'):
                    value = True
                elif value.lower() in ('false', 'no'):
                    value = False
                elif value.isdigit():
                    value = int(value)
                elif re.match(r'^\d+\.\d+$', value):
                    value = float(value)

                if hasattr(self.settings, key):
                    setattr(self.settings, key, value)

    def _apply_config(self, config: Dict):
        """Apply configuration dictionary to settings."""
        for key, value in config.items():
            key = key.lower().replace('-', '_')
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)

    def reload(self):
        """Reload configuration from disk."""
        self.settings = WorkspaceSettings()
        self._load_claude_md()
        self._load_preferences()
        logger.info("[WorkspaceConfig] Configuration reloaded")

    # ===== User Preferences =====

    def _load_preferences(self):
        """Load user preferences from file."""
        if not self._preferences_file.exists():
            return

        try:
            with open(self._preferences_file, 'r') as f:
                data = json.load(f)

            for user_id, prefs in data.items():
                self.user_preferences[user_id] = UserPreferences.from_dict(prefs)

            logger.info(f"[WorkspaceConfig] Loaded preferences for {len(self.user_preferences)} users")
        except Exception as e:
            logger.error(f"[WorkspaceConfig] Error loading preferences: {e}")

    def _save_preferences(self):
        """Save user preferences to file."""
        try:
            data = {
                user_id: prefs.to_dict()
                for user_id, prefs in self.user_preferences.items()
            }

            with open(self._preferences_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"[WorkspaceConfig] Error saving preferences: {e}")

    def get_user_preferences(self, user_id: str) -> UserPreferences:
        """Get preferences for a user, creating defaults if needed."""
        if user_id not in self.user_preferences:
            self.user_preferences[user_id] = UserPreferences(user_id=user_id)
        return self.user_preferences[user_id]

    def update_user_preferences(self, user_id: str, **updates) -> UserPreferences:
        """Update user preferences."""
        prefs = self.get_user_preferences(user_id)

        for key, value in updates.items():
            if hasattr(prefs, key):
                setattr(prefs, key, value)

        self._save_preferences()
        return prefs

    def reset_user_preferences(self, user_id: str) -> UserPreferences:
        """Reset user preferences to defaults."""
        self.user_preferences[user_id] = UserPreferences(user_id=user_id)
        self._save_preferences()
        return self.user_preferences[user_id]

    # ===== Hooks System =====

    def register_hook(
        self,
        event: HookEvent,
        callback: Callable,
        priority: int = 0,
        description: str = ""
    ) -> str:
        """
        Register a hook for an event.

        Args:
            event: Event to hook into
            callback: Function to call (receives event data dict)
            priority: Higher runs first
            description: Human-readable description

        Returns:
            Hook ID for later management
        """
        self._hook_counter += 1
        hook_id = f"hook_{self._hook_counter}"

        hook = Hook(
            id=hook_id,
            event=event,
            callback=callback,
            priority=priority,
            description=description
        )

        self.hooks[hook_id] = hook
        logger.info(f"[WorkspaceConfig] Registered hook {hook_id} for {event.value}")
        return hook_id

    def unregister_hook(self, hook_id: str) -> bool:
        """Unregister a hook by ID."""
        if hook_id in self.hooks:
            del self.hooks[hook_id]
            return True
        return False

    def enable_hook(self, hook_id: str, enabled: bool = True) -> bool:
        """Enable or disable a hook."""
        if hook_id in self.hooks:
            self.hooks[hook_id].enabled = enabled
            return True
        return False

    def get_hooks(self, event: Optional[HookEvent] = None) -> List[Hook]:
        """Get all hooks, optionally filtered by event."""
        hooks = list(self.hooks.values())

        if event:
            hooks = [h for h in hooks if h.event == event]

        # Sort by priority (higher first)
        hooks.sort(key=lambda h: h.priority, reverse=True)
        return hooks

    async def fire_hook(self, event: HookEvent, data: Dict[str, Any]) -> List[Any]:
        """
        Fire all hooks for an event.

        Args:
            event: Event type
            data: Event data to pass to hooks

        Returns:
            List of results from hooks
        """
        hooks = self.get_hooks(event)
        results = []

        for hook in hooks:
            if not hook.enabled:
                continue

            try:
                if asyncio.iscoroutinefunction(hook.callback):
                    result = await hook.callback(data)
                else:
                    result = hook.callback(data)
                results.append(result)
            except Exception as e:
                logger.error(f"[WorkspaceConfig] Hook {hook.id} error: {e}")
                results.append({'error': str(e)})

        return results

    def fire_hook_sync(self, event: HookEvent, data: Dict[str, Any]) -> List[Any]:
        """Fire hooks synchronously (for non-async contexts)."""
        hooks = self.get_hooks(event)
        results = []

        for hook in hooks:
            if not hook.enabled:
                continue

            try:
                if asyncio.iscoroutinefunction(hook.callback):
                    # Skip async hooks in sync context
                    continue
                result = hook.callback(data)
                results.append(result)
            except Exception as e:
                logger.error(f"[WorkspaceConfig] Hook {hook.id} error: {e}")
                results.append({'error': str(e)})

        return results

    # ===== Settings Access =====

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a workspace setting by key."""
        return getattr(self.settings, key, default)

    def update_setting(self, key: str, value: Any) -> bool:
        """Update a workspace setting."""
        if hasattr(self.settings, key):
            setattr(self.settings, key, value)
            return True
        return False

    def get_agent_config(self, agent_id: str) -> Dict[str, Any]:
        """Get configuration for a specific agent."""
        return {
            'personality': self.settings.agent_personalities.get(agent_id, 'neutral'),
            'temperature': self.settings.agent_temperature.get(agent_id, 0.5),
            'max_tokens': self.settings.max_tokens_per_response,
            'custom_instructions': self.settings.custom_instructions,
            'blocked_tools': self.settings.blocked_tools
        }

    def get_all_settings(self) -> Dict[str, Any]:
        """Get all workspace settings."""
        return self.settings.to_dict()

    def export_config(self) -> str:
        """Export configuration as JSON."""
        return json.dumps({
            'settings': self.settings.to_dict(),
            'user_preferences': {
                uid: p.to_dict() for uid, p in self.user_preferences.items()
            },
            'hooks': [h.to_dict() for h in self.hooks.values()]
        }, indent=2)


# ===== Global Instance =====

_workspace_config: Optional[WorkspaceConfig] = None


def get_workspace_config(workspace_dir: Optional[str] = None) -> WorkspaceConfig:
    """Get or create global WorkspaceConfig instance."""
    global _workspace_config

    if _workspace_config is None:
        _workspace_config = WorkspaceConfig(workspace_dir)

    return _workspace_config


# ===== CLI Testing =====

def test_workspace_config():
    """Test workspace configuration functionality."""
    import tempfile

    print("=" * 60)
    print("  WorkspaceConfig Test")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Test 1: Create CLAUDE.md
        print("\n[Test 1] Creating CLAUDE.md...")
        claude_md = Path(tmpdir) / "CLAUDE.md"
        claude_md.write_text('''# My Healthcare Workspace

## Configuration

```workspace-config
{
    "workspace_name": "HealthTech Project",
    "max_users": 8,
    "enable_canvas": true,
    "default_agent": "cairn"
}
```

## Custom Instructions

- Always ensure HIPAA compliance
- Use encryption for sensitive data
- Document all architectural decisions

## System Prompt

You are an expert healthcare software architect.
Focus on security, compliance, and scalability.

## Demo Branding

- Company Name: HealthTech Inc
- Primary Color: #10b981
- Logo URL: https://example.com/logo.png
''')
        print(f"  ✓ Created CLAUDE.md")

        # Test 2: Load config
        print("\n[Test 2] Loading configuration...")
        config = WorkspaceConfig(workspace_dir=tmpdir)

        assert config.settings.workspace_name == "HealthTech Project", \
            f"Expected 'HealthTech Project', got '{config.settings.workspace_name}'"
        assert config.settings.max_users == 8
        assert config.settings.default_agent == "cairn"
        print(f"  ✓ Workspace name: {config.settings.workspace_name}")
        print(f"  ✓ Max users: {config.settings.max_users}")
        print(f"  ✓ Default agent: {config.settings.default_agent}")

        # Test 3: Custom instructions
        print("\n[Test 3] Custom instructions...")
        assert len(config.settings.custom_instructions) >= 2
        print(f"  ✓ {len(config.settings.custom_instructions)} custom instructions loaded")

        # Test 4: System prompt
        print("\n[Test 4] System prompt...")
        assert config.settings.custom_system_prompt is not None
        assert "healthcare" in config.settings.custom_system_prompt.lower()
        print(f"  ✓ System prompt loaded ({len(config.settings.custom_system_prompt)} chars)")

        # Test 5: Demo branding
        print("\n[Test 5] Demo branding...")
        assert 'company_name' in config.settings.demo_branding
        print(f"  ✓ Branding: {config.settings.demo_branding}")

        # Test 6: User preferences
        print("\n[Test 6] User preferences...")
        prefs = config.get_user_preferences("user1")
        assert prefs.user_id == "user1"
        assert prefs.theme == "dark"  # Default
        print(f"  ✓ Default preferences for user1")

        config.update_user_preferences("user1", theme="light", code_font_size=16)
        prefs = config.get_user_preferences("user1")
        assert prefs.theme == "light"
        assert prefs.code_font_size == 16
        print(f"  ✓ Updated preferences: theme={prefs.theme}, font={prefs.code_font_size}")

        # Test 7: Hooks
        print("\n[Test 7] Hooks system...")
        results = []

        def on_message(data):
            results.append(f"Message from {data.get('actor')}")
            return True

        hook_id = config.register_hook(
            HookEvent.MESSAGE_SENT,
            on_message,
            priority=10,
            description="Log messages"
        )
        assert hook_id is not None
        print(f"  ✓ Registered hook: {hook_id}")

        # Fire hook
        config.fire_hook_sync(HookEvent.MESSAGE_SENT, {'actor': 'user1', 'content': 'Hello'})
        assert len(results) == 1
        print(f"  ✓ Hook fired: {results[0]}")

        # Test 8: Hook priority
        print("\n[Test 8] Hook priority...")
        order = []

        config.register_hook(HookEvent.SESSION_START, lambda d: order.append('low'), priority=1)
        config.register_hook(HookEvent.SESSION_START, lambda d: order.append('high'), priority=10)
        config.register_hook(HookEvent.SESSION_START, lambda d: order.append('mid'), priority=5)

        config.fire_hook_sync(HookEvent.SESSION_START, {})
        assert order == ['high', 'mid', 'low'], f"Expected priority order, got {order}"
        print(f"  ✓ Hooks fired in priority order: {order}")

        # Test 9: Disable hook
        print("\n[Test 9] Disable hook...")
        config.enable_hook(hook_id, enabled=False)
        results.clear()
        config.fire_hook_sync(HookEvent.MESSAGE_SENT, {'actor': 'user2'})
        assert len(results) == 0
        print(f"  ✓ Disabled hook not fired")

        # Test 10: Agent config
        print("\n[Test 10] Agent configuration...")
        agent_config = config.get_agent_config('cairn')
        assert 'personality' in agent_config
        assert 'temperature' in agent_config
        print(f"  ✓ Cairn config: personality={agent_config['personality']}, temp={agent_config['temperature']}")

        # Test 11: Export config
        print("\n[Test 11] Export configuration...")
        export = config.export_config()
        assert 'settings' in export
        assert 'HealthTech Project' in export
        print(f"  ✓ Config exported ({len(export)} chars)")

        # Test 12: Reload config
        print("\n[Test 12] Reload configuration...")
        config.reload()
        assert config.settings.workspace_name == "HealthTech Project"
        print(f"  ✓ Configuration reloaded")

    print("\n" + "=" * 60)
    print("  All tests passed! ✅")
    print("=" * 60)


if __name__ == "__main__":
    test_workspace_config()
