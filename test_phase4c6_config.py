#!/usr/bin/env python3
"""
Phase 4C.6 Integration Test: Configuration & Polish

Tests:
1. WorkspaceConfig availability
2. CLAUDE.md configuration loading
3. User preferences storage
4. Hooks system
5. SessionManager integration
6. Agent configuration
7. Config reload

Run with: python3 test_phase4c6_config.py
"""

import sys
import os
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from workspace_session_manager import WorkspaceSessionManager, HAS_WORKSPACE_CONFIG
from workspace_config import WorkspaceConfig, HookEvent, get_workspace_config


def test_workspace_config_available():
    """Test that WorkspaceConfig is available."""
    print("\n" + "="*60)
    print("TEST 1: WorkspaceConfig Availability")
    print("="*60)

    assert HAS_WORKSPACE_CONFIG, "WorkspaceConfig should be importable"
    print(f"  ✓ HAS_WORKSPACE_CONFIG = {HAS_WORKSPACE_CONFIG}")

    config = WorkspaceConfig()
    assert config is not None
    print(f"  ✓ WorkspaceConfig instantiated")

    print("\n✅ WorkspaceConfig Availability test passed!")
    return True


def test_claude_md_loading():
    """Test loading configuration from CLAUDE.md."""
    print("\n" + "="*60)
    print("TEST 2: CLAUDE.md Loading")
    print("="*60)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create CLAUDE.md
        claude_md = Path(tmpdir) / "CLAUDE.md"
        claude_md.write_text('''# Test Workspace

## Configuration

```workspace-config
{
    "workspace_name": "Test Project",
    "max_users": 6,
    "default_agent": "koda",
    "enable_canvas": true
}
```

## Custom Instructions

- Follow TDD practices
- Document all functions
- Use type hints

## System Prompt

You are a test assistant.
''')

        config = WorkspaceConfig(workspace_dir=tmpdir)

        assert config.settings.workspace_name == "Test Project"
        print(f"  ✓ Workspace name: {config.settings.workspace_name}")

        assert config.settings.max_users == 6
        print(f"  ✓ Max users: {config.settings.max_users}")

        assert config.settings.default_agent == "koda"
        print(f"  ✓ Default agent: {config.settings.default_agent}")

        assert config.settings.enable_canvas is True
        print(f"  ✓ Canvas enabled: {config.settings.enable_canvas}")

        assert len(config.settings.custom_instructions) >= 2
        print(f"  ✓ Custom instructions: {len(config.settings.custom_instructions)}")

        assert config.settings.custom_system_prompt is not None
        print(f"  ✓ System prompt loaded")

    print("\n✅ CLAUDE.md Loading test passed!")
    return True


def test_user_preferences():
    """Test user preferences storage and retrieval."""
    print("\n" + "="*60)
    print("TEST 3: User Preferences")
    print("="*60)

    with tempfile.TemporaryDirectory() as tmpdir:
        config = WorkspaceConfig(workspace_dir=tmpdir)

        # Get default preferences
        prefs = config.get_user_preferences("user1")
        assert prefs.user_id == "user1"
        assert prefs.theme == "dark"  # Default
        print(f"  ✓ Default theme: {prefs.theme}")

        # Update preferences
        config.update_user_preferences("user1", theme="light", code_font_size=18)
        prefs = config.get_user_preferences("user1")
        assert prefs.theme == "light"
        assert prefs.code_font_size == 18
        print(f"  ✓ Updated theme: {prefs.theme}, font: {prefs.code_font_size}")

        # Reset preferences
        prefs = config.reset_user_preferences("user1")
        assert prefs.theme == "dark"
        print(f"  ✓ Reset to defaults: theme={prefs.theme}")

        # Multiple users
        config.update_user_preferences("user2", compact_messages=True)
        config.update_user_preferences("user3", preferred_agent="cairn")

        assert config.get_user_preferences("user2").compact_messages is True
        assert config.get_user_preferences("user3").preferred_agent == "cairn"
        print(f"  ✓ Multiple user preferences work")

    print("\n✅ User Preferences test passed!")
    return True


def test_hooks_system():
    """Test the hooks system."""
    print("\n" + "="*60)
    print("TEST 4: Hooks System")
    print("="*60)

    config = WorkspaceConfig()
    results = []

    # Register hooks
    def on_session_start(data):
        results.append(f"Session started: {data.get('session_id')}")
        return True

    def on_message(data):
        results.append(f"Message from {data.get('actor')}")
        return True

    hook1 = config.register_hook(HookEvent.SESSION_START, on_session_start, description="Log session")
    hook2 = config.register_hook(HookEvent.MESSAGE_SENT, on_message, description="Log messages")

    assert hook1 is not None
    assert hook2 is not None
    print(f"  ✓ Registered hooks: {hook1}, {hook2}")

    # Fire hooks
    config.fire_hook_sync(HookEvent.SESSION_START, {'session_id': 'abc123'})
    assert len(results) == 1
    print(f"  ✓ SESSION_START hook fired: {results[-1]}")

    config.fire_hook_sync(HookEvent.MESSAGE_SENT, {'actor': 'user1'})
    assert len(results) == 2
    print(f"  ✓ MESSAGE_SENT hook fired: {results[-1]}")

    # Disable hook
    config.enable_hook(hook2, enabled=False)
    config.fire_hook_sync(HookEvent.MESSAGE_SENT, {'actor': 'user2'})
    assert len(results) == 2  # Should not increase
    print(f"  ✓ Disabled hook not fired")

    # Unregister hook
    config.unregister_hook(hook1)
    results.clear()
    config.fire_hook_sync(HookEvent.SESSION_START, {'session_id': 'xyz'})
    assert len(results) == 0
    print(f"  ✓ Unregistered hook not fired")

    print("\n✅ Hooks System test passed!")
    return True


def test_hook_priority():
    """Test hook priority ordering."""
    print("\n" + "="*60)
    print("TEST 5: Hook Priority")
    print("="*60)

    config = WorkspaceConfig()
    order = []

    config.register_hook(HookEvent.SESSION_START, lambda d: order.append('low'), priority=1)
    config.register_hook(HookEvent.SESSION_START, lambda d: order.append('high'), priority=100)
    config.register_hook(HookEvent.SESSION_START, lambda d: order.append('mid'), priority=50)

    config.fire_hook_sync(HookEvent.SESSION_START, {})

    assert order == ['high', 'mid', 'low'], f"Expected priority order, got {order}"
    print(f"  ✓ Hooks fired in priority order: {order}")

    print("\n✅ Hook Priority test passed!")
    return True


def test_session_manager_integration():
    """Test WorkspaceConfig integration with SessionManager."""
    print("\n" + "="*60)
    print("TEST 6: SessionManager Integration")
    print("="*60)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create CLAUDE.md
        claude_md = Path(tmpdir) / "CLAUDE.md"
        claude_md.write_text('''# Integration Test

```workspace-config
{
    "workspace_name": "Integration Workspace",
    "max_users": 10,
    "default_agent": "cairn"
}
```
''')

        sm = WorkspaceSessionManager(workspace_dir=tmpdir)

        # Get settings
        settings = sm.get_workspace_settings()
        assert settings.get('workspace_name') == "Integration Workspace"
        print(f"  ✓ Workspace name via SM: {settings.get('workspace_name')}")

        # Get user preferences
        class MockWebSocket:
            async def send(self, msg): pass

        session = sm.create_session("user1", "Test User", MockWebSocket())

        prefs = sm.get_user_preferences("user1")
        assert prefs.get('user_id') == "user1"
        print(f"  ✓ User preferences via SM")

        # Update preferences
        prefs = sm.update_user_preferences("user1", theme="light")
        assert prefs.get('theme') == "light"
        print(f"  ✓ Updated preferences via SM: theme={prefs.get('theme')}")

        # Agent config
        agent_config = sm.get_agent_config("cairn")
        assert 'temperature' in agent_config
        assert 'personality' in agent_config
        print(f"  ✓ Agent config: temp={agent_config['temperature']}")

    print("\n✅ SessionManager Integration test passed!")
    return True


def test_config_reload():
    """Test configuration reload."""
    print("\n" + "="*60)
    print("TEST 7: Config Reload")
    print("="*60)

    with tempfile.TemporaryDirectory() as tmpdir:
        claude_md = Path(tmpdir) / "CLAUDE.md"

        # Initial config
        claude_md.write_text('''# Initial

```workspace-config
{"workspace_name": "Initial", "max_users": 5}
```
''')

        config = WorkspaceConfig(workspace_dir=tmpdir)
        assert config.settings.workspace_name == "Initial"
        print(f"  ✓ Initial config: {config.settings.workspace_name}")

        # Update file
        claude_md.write_text('''# Updated

```workspace-config
{"workspace_name": "Updated", "max_users": 20}
```
''')

        # Reload
        config.reload()
        assert config.settings.workspace_name == "Updated"
        assert config.settings.max_users == 20
        print(f"  ✓ Reloaded config: {config.settings.workspace_name}, users={config.settings.max_users}")

    print("\n✅ Config Reload test passed!")
    return True


def test_agent_configuration():
    """Test per-agent configuration."""
    print("\n" + "="*60)
    print("TEST 8: Agent Configuration")
    print("="*60)

    config = WorkspaceConfig()

    # Check default agent configs
    cairn_config = config.get_agent_config("cairn")
    assert cairn_config['personality'] == 'analytical'
    assert cairn_config['temperature'] == 0.5
    print(f"  ✓ Cairn: personality={cairn_config['personality']}, temp={cairn_config['temperature']}")

    koda_config = config.get_agent_config("koda")
    assert koda_config['personality'] == 'practical'
    assert koda_config['temperature'] == 0.3
    print(f"  ✓ Koda: personality={koda_config['personality']}, temp={koda_config['temperature']}")

    prax_config = config.get_agent_config("prax")
    assert prax_config['personality'] == 'strategic'
    assert prax_config['temperature'] == 0.7
    print(f"  ✓ Prax: personality={prax_config['personality']}, temp={prax_config['temperature']}")

    print("\n✅ Agent Configuration test passed!")
    return True


def test_export_config():
    """Test configuration export."""
    print("\n" + "="*60)
    print("TEST 9: Export Configuration")
    print("="*60)

    import json

    with tempfile.TemporaryDirectory() as tmpdir:
        claude_md = Path(tmpdir) / "CLAUDE.md"
        claude_md.write_text('''# Export Test

```workspace-config
{"workspace_name": "Export Test", "max_users": 8}
```
''')

        config = WorkspaceConfig(workspace_dir=tmpdir)
        config.update_user_preferences("user1", theme="light")
        config.register_hook(HookEvent.SESSION_START, lambda d: None, description="Test hook")

        export = config.export_config()
        data = json.loads(export)

        assert 'settings' in data
        assert data['settings']['workspace_name'] == "Export Test"
        print(f"  ✓ Settings exported")

        assert 'user_preferences' in data
        assert 'user1' in data['user_preferences']
        print(f"  ✓ User preferences exported")

        assert 'hooks' in data
        assert len(data['hooks']) >= 1
        print(f"  ✓ Hooks exported: {len(data['hooks'])}")

    print("\n✅ Export Configuration test passed!")
    return True


def main():
    """Run all tests."""
    print("="*60)
    print("  Phase 4C.6 Integration Tests")
    print("  Configuration & Polish")
    print("="*60)

    tests = [
        ("WorkspaceConfig Available", test_workspace_config_available),
        ("CLAUDE.md Loading", test_claude_md_loading),
        ("User Preferences", test_user_preferences),
        ("Hooks System", test_hooks_system),
        ("Hook Priority", test_hook_priority),
        ("SessionManager Integration", test_session_manager_integration),
        ("Config Reload", test_config_reload),
        ("Agent Configuration", test_agent_configuration),
        ("Export Configuration", test_export_config),
    ]

    passed = 0
    failed = 0

    for name, test_fn in tests:
        try:
            if test_fn():
                passed += 1
            else:
                failed += 1
                print(f"\n❌ {name} FAILED")
        except Exception as e:
            failed += 1
            print(f"\n❌ {name} FAILED with exception: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*60)
    print(f"  RESULTS: {passed} passed, {failed} failed")
    print("="*60)

    if failed == 0:
        print("\n🎉 All Phase 4C.6 tests passed!")
        print("\nPhase 4C.6 Implementation Complete:")
        print("  ✓ Workspace CLAUDE.md configuration loading")
        print("  ✓ Hooks system for all workspace events")
        print("  ✓ User preferences with persistence")
        print("  ✓ Per-agent configuration")
        print("  ✓ Configuration reload support")
        print("  ✓ Export configuration as JSON")
        print("\nSuccess Criteria Met:")
        print("  ✓ Workspace config loaded and applied")
        print("  ✓ Hooks fire on correct events")
        print("  ✓ Users can customize experience")
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
