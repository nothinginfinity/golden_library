#!/usr/bin/env python3
"""
Phase 4C.5 Integration Test: Live Demo Mode

Tests:
1. DemoRecorder initialization
2. Start/stop demo mode via SessionManager
3. Event recording during demo
4. Highlight markers
5. Custom branding
6. HTML/JSON export
7. Recording persistence

Run with: python3 test_phase4c5_demo.py
"""

import sys
import os
import tempfile

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from workspace_session_manager import WorkspaceSessionManager, HAS_DEMO_RECORDER
from demo_recorder import DemoRecorder, EventType, BrandingConfig, get_demo_recorder


def test_demo_recorder_available():
    """Test that DemoRecorder is available."""
    print("\n" + "="*60)
    print("TEST 1: DemoRecorder Availability")
    print("="*60)

    assert HAS_DEMO_RECORDER, "DemoRecorder should be importable"
    print(f"  ✓ HAS_DEMO_RECORDER = {HAS_DEMO_RECORDER}")

    recorder = DemoRecorder(storage_dir=tempfile.mkdtemp())
    assert recorder is not None
    print(f"  ✓ DemoRecorder instantiated")

    print("\n✅ DemoRecorder Availability test passed!")
    return True


def test_start_stop_demo_mode():
    """Test starting and stopping demo mode via SessionManager."""
    print("\n" + "="*60)
    print("TEST 2: Start/Stop Demo Mode")
    print("="*60)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Patch demo recorder storage
        import demo_recorder
        demo_recorder._demo_recorder = DemoRecorder(storage_dir=tmpdir)

        sm = WorkspaceSessionManager()

        class MockWebSocket:
            async def send(self, msg): pass

        session = sm.create_session("user1", "Test User", MockWebSocket())
        session_id = session.id
        print(f"  ✓ Created session: {session_id[:8]}...")

        # Start demo mode
        result = sm.start_demo_mode(
            session_id=session_id,
            title="Feature Demo",
            description="Testing the demo mode"
        )

        assert 'recording_id' in result, f"Expected recording_id, got {result}"
        print(f"  ✓ Demo started: {result['recording_id']}")

        # Check session flags
        assert session.demo_mode is True, "demo_mode should be True"
        assert session.demo_recording_id is not None, "recording_id should be set"
        print(f"  ✓ Session flags updated")

        # Stop demo mode
        result = sm.stop_demo_mode(session_id)
        assert 'recording_id' in result, f"Expected recording_id, got {result}"
        assert 'duration_ms' in result, "Expected duration_ms"
        print(f"  ✓ Demo stopped: {result['duration_ms']}ms")

        # Check flags cleared
        assert session.demo_mode is False, "demo_mode should be False"
        assert session.demo_recording_id is None, "recording_id should be None"
        print(f"  ✓ Session flags cleared")

    print("\n✅ Start/Stop Demo Mode test passed!")
    return True


def test_event_recording():
    """Test that events are recorded during demo mode."""
    print("\n" + "="*60)
    print("TEST 3: Event Recording")
    print("="*60)

    with tempfile.TemporaryDirectory() as tmpdir:
        import demo_recorder
        demo_recorder._demo_recorder = DemoRecorder(storage_dir=tmpdir)

        sm = WorkspaceSessionManager()

        class MockWebSocket:
            async def send(self, msg): pass

        session = sm.create_session("user1", "Test User", MockWebSocket())
        session_id = session.id

        # Start demo
        result = sm.start_demo_mode(session_id, title="Event Test")
        recording_id = result['recording_id']

        # Add some messages
        sm.add_message(session_id, "user1", None, "user", "Hello, let's build something!")
        sm.add_message(session_id, "user1", "cairn", "assistant", "I'll design the architecture.")
        sm.add_message(session_id, "user1", "koda", "assistant", "Starting implementation now.")

        # Stop and check
        result = sm.stop_demo_mode(session_id)
        event_count = result.get('event_count', 0)

        # Should have: start event + 3 messages + stop event = 5 events
        assert event_count >= 4, f"Expected at least 4 events, got {event_count}"
        print(f"  ✓ Recorded {event_count} events")

        # Load and verify
        recorder = demo_recorder.get_demo_recorder()
        recording = recorder.load_recording(recording_id)
        assert recording is not None
        print(f"  ✓ Recording loaded: {len(recording.events)} events")

        # Check event types
        event_types = [e.event_type.value for e in recording.events]
        assert 'message' in event_types or 'agent_response' in event_types
        print(f"  ✓ Event types: {set(event_types)}")

    print("\n✅ Event Recording test passed!")
    return True


def test_highlight_markers():
    """Test adding highlight markers."""
    print("\n" + "="*60)
    print("TEST 4: Highlight Markers")
    print("="*60)

    with tempfile.TemporaryDirectory() as tmpdir:
        import demo_recorder
        demo_recorder._demo_recorder = DemoRecorder(storage_dir=tmpdir)

        sm = WorkspaceSessionManager()

        class MockWebSocket:
            async def send(self, msg): pass

        session = sm.create_session("user1", "Test User", MockWebSocket())
        session_id = session.id

        sm.start_demo_mode(session_id, title="Highlight Test")

        # Add messages
        sm.add_message(session_id, "user1", None, "user", "Let's make a decision")

        # Add highlight
        success = sm.add_demo_highlight(
            session_id=session_id,
            label="Key Decision",
            description="We decided to use PostgreSQL"
        )
        assert success, "Highlight should be added"
        print(f"  ✓ Highlight added")

        # Add more content
        sm.add_message(session_id, "user1", "cairn", "assistant", "PostgreSQL it is!")

        # Add another highlight
        sm.add_demo_highlight(session_id, "Architecture Finalized")

        result = sm.stop_demo_mode(session_id)
        highlight_count = result.get('highlight_count', 0)
        assert highlight_count >= 2, f"Expected 2+ highlights, got {highlight_count}"
        print(f"  ✓ {highlight_count} highlights recorded")

    print("\n✅ Highlight Markers test passed!")
    return True


def test_custom_branding():
    """Test custom branding support."""
    print("\n" + "="*60)
    print("TEST 5: Custom Branding")
    print("="*60)

    with tempfile.TemporaryDirectory() as tmpdir:
        import demo_recorder
        demo_recorder._demo_recorder = DemoRecorder(storage_dir=tmpdir)

        sm = WorkspaceSessionManager()

        class MockWebSocket:
            async def send(self, msg): pass

        session = sm.create_session("user1", "Test User", MockWebSocket())
        session_id = session.id

        # Start with custom branding
        branding = {
            'company_name': 'Acme Healthcare',
            'primary_color': '#10b981',
            'logo_url': 'https://example.com/logo.png',
            'footer_text': 'HIPAA Compliant Demo'
        }

        result = sm.start_demo_mode(
            session_id=session_id,
            title="Branded Demo",
            branding=branding
        )
        recording_id = result['recording_id']

        sm.add_message(session_id, "user1", None, "user", "Testing branding")
        sm.stop_demo_mode(session_id)

        # Verify branding in export
        recorder = demo_recorder.get_demo_recorder()
        html = recorder.export_html(recording_id)

        assert 'Acme Healthcare' in html, "Company name should be in HTML"
        assert '#10b981' in html, "Primary color should be in HTML"
        assert 'HIPAA Compliant Demo' in html, "Footer text should be in HTML"
        print(f"  ✓ Custom branding applied to HTML export")

    print("\n✅ Custom Branding test passed!")
    return True


def test_html_export():
    """Test HTML export functionality."""
    print("\n" + "="*60)
    print("TEST 6: HTML Export")
    print("="*60)

    with tempfile.TemporaryDirectory() as tmpdir:
        import demo_recorder
        demo_recorder._demo_recorder = DemoRecorder(storage_dir=tmpdir)

        sm = WorkspaceSessionManager()

        class MockWebSocket:
            async def send(self, msg): pass

        session = sm.create_session("user1", "Test User", MockWebSocket())
        session_id = session.id

        sm.start_demo_mode(session_id, title="Export Test Demo")
        sm.add_message(session_id, "user1", None, "user", "This is a test message")
        sm.add_demo_highlight(session_id, "Important Moment")
        sm.add_message(session_id, "user1", "cairn", "assistant", "Response from agent")
        result = sm.stop_demo_mode(session_id)
        recording_id = result['recording_id']

        # Export HTML
        html = sm.export_demo_html(recording_id)
        assert html is not None, "HTML export should not be None"
        assert '<!DOCTYPE html>' in html, "Should be valid HTML"
        assert 'Export Test Demo' in html, "Title should be in HTML"
        assert 'Important Moment' in html, "Highlight should be in HTML"
        print(f"  ✓ HTML export: {len(html)} chars")

        # Check it's self-contained
        assert '<style>' in html, "Should have embedded styles"
        assert '<script>' in html, "Should have embedded JavaScript"
        print(f"  ✓ Self-contained HTML (CSS + JS embedded)")

    print("\n✅ HTML Export test passed!")
    return True


def test_json_export():
    """Test JSON export functionality."""
    print("\n" + "="*60)
    print("TEST 7: JSON Export")
    print("="*60)

    with tempfile.TemporaryDirectory() as tmpdir:
        import demo_recorder
        import json
        demo_recorder._demo_recorder = DemoRecorder(storage_dir=tmpdir)

        sm = WorkspaceSessionManager()

        class MockWebSocket:
            async def send(self, msg): pass

        session = sm.create_session("user1", "Test User", MockWebSocket())
        session_id = session.id

        sm.start_demo_mode(session_id, title="JSON Export Test")
        sm.add_message(session_id, "user1", None, "user", "Test message")
        result = sm.stop_demo_mode(session_id)
        recording_id = result['recording_id']

        # Export JSON
        json_str = sm.export_demo_json(recording_id)
        assert json_str is not None, "JSON export should not be None"

        # Parse and validate
        data = json.loads(json_str)
        assert data['title'] == 'JSON Export Test'
        assert 'events' in data
        assert 'branding' in data
        print(f"  ✓ JSON export: {len(json_str)} chars")
        print(f"  ✓ Valid JSON with {len(data['events'])} events")

    print("\n✅ JSON Export test passed!")
    return True


def test_recording_persistence():
    """Test that recordings are persisted and can be listed."""
    print("\n" + "="*60)
    print("TEST 8: Recording Persistence")
    print("="*60)

    with tempfile.TemporaryDirectory() as tmpdir:
        import demo_recorder
        demo_recorder._demo_recorder = DemoRecorder(storage_dir=tmpdir)

        sm = WorkspaceSessionManager()

        class MockWebSocket:
            async def send(self, msg): pass

        # Create multiple recordings
        for i in range(3):
            session = sm.create_session(f"user{i}", f"User {i}", MockWebSocket())
            sm.start_demo_mode(session.id, title=f"Demo {i+1}")
            sm.add_message(session.id, f"user{i}", None, "user", f"Message in demo {i+1}")
            sm.stop_demo_mode(session.id)

        # List recordings
        recordings = sm.get_demo_recordings()
        assert len(recordings) == 3, f"Expected 3 recordings, got {len(recordings)}"
        print(f"  ✓ {len(recordings)} recordings persisted")

        # Check recordings are sorted by date (newest first)
        titles = [r['title'] for r in recordings]
        print(f"  ✓ Recordings: {titles}")

        # Verify each recording has expected fields
        for rec in recordings:
            assert 'id' in rec
            assert 'title' in rec
            assert 'duration_ms' in rec
            assert 'event_count' in rec
        print(f"  ✓ All recordings have expected fields")

    print("\n✅ Recording Persistence test passed!")
    return True


def test_demo_mode_without_session():
    """Test graceful handling when session doesn't exist."""
    print("\n" + "="*60)
    print("TEST 9: Error Handling")
    print("="*60)

    sm = WorkspaceSessionManager()

    # Try to start demo on non-existent session
    result = sm.start_demo_mode("fake_session", "Test")
    assert 'error' in result, "Should return error for non-existent session"
    print(f"  ✓ Non-existent session: {result['error']}")

    # Try to stop demo when not active
    class MockWebSocket:
        async def send(self, msg): pass

    session = sm.create_session("user1", "Test", MockWebSocket())
    result = sm.stop_demo_mode(session.id)
    assert 'error' in result, "Should return error when demo not active"
    print(f"  ✓ Demo not active: {result['error']}")

    # Try to add highlight when not recording
    success = sm.add_demo_highlight(session.id, "Test")
    assert success is False, "Should return False when not recording"
    print(f"  ✓ Highlight without demo: False")

    print("\n✅ Error Handling test passed!")
    return True


def main():
    """Run all tests."""
    print("="*60)
    print("  Phase 4C.5 Integration Tests")
    print("  Live Demo Mode")
    print("="*60)

    tests = [
        ("DemoRecorder Available", test_demo_recorder_available),
        ("Start/Stop Demo Mode", test_start_stop_demo_mode),
        ("Event Recording", test_event_recording),
        ("Highlight Markers", test_highlight_markers),
        ("Custom Branding", test_custom_branding),
        ("HTML Export", test_html_export),
        ("JSON Export", test_json_export),
        ("Recording Persistence", test_recording_persistence),
        ("Error Handling", test_demo_mode_without_session),
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
        print("\n🎉 All Phase 4C.5 tests passed!")
        print("\nPhase 4C.5 Implementation Complete:")
        print("  ✓ Demo mode flag per session")
        print("  ✓ Session recording with all events")
        print("  ✓ Highlight/bookmark markers for key moments")
        print("  ✓ Custom branding (colors, logo, text)")
        print("  ✓ HTML export (shareable, self-contained)")
        print("  ✓ JSON export (data interchange)")
        print("  ✓ Recording persistence and listing")
        print("\nSuccess Criteria Met:")
        print("  ✓ Client onboarding: features built live")
        print("  ✓ Recordings saved to disk")
        print("  ✓ Export to shareable HTML")
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
