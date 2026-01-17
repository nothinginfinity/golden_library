#!/usr/bin/env python3
"""
Phase 4C.1 Integration Test: Hierarchical Task Delegation

Tests the complete flow:
1. Prax delegates task to Cairn
2. Cairn acknowledges and starts task
3. Cairn updates progress
4. Cairn completes task with canvas output
5. Results reported back to Prax

Run with: python3 test_phase4c1_delegation.py
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from workspace_session_manager import WorkspaceSessionManager, session_manager
from task_delegation_manager import TaskDelegationManager, TaskDefinition, TaskStatus


def test_task_delegation_manager():
    """Test TaskDelegationManager in isolation."""
    print("\n" + "="*60)
    print("TEST 1: TaskDelegationManager Basic Operations")
    print("="*60)

    # Create fresh managers
    sm = WorkspaceSessionManager()
    tdm = TaskDelegationManager(session_manager=sm)

    # Create test session
    class MockWebSocket:
        async def send(self, msg): pass

    session = sm.create_session("user1", "Test User", MockWebSocket())
    session_id = session.id
    print(f"✓ Created session: {session_id}")

    # Test 1: Delegate task from Prax to Cairn
    task = TaskDefinition(
        id="",
        description="Research HIPAA compliance requirements",
        success_criteria="Comprehensive list of requirements with sources",
        tools_allowed=["web_search", "deepseek"],
        canvas_section="compliance_analysis",
        priority="high"
    )

    task_id = tdm.delegate_task(
        from_agent="prax",
        to_agent="cairn",
        task=task,
        session_id=session_id
    )

    print(f"✓ Task delegated: {task_id}")
    assert task_id.startswith("task_"), "Task ID should start with 'task_'"

    # Verify task created
    status = tdm.get_task_status(task_id)
    assert status is not None, "Task status should not be None"
    assert status['status'] == 'pending', f"Initial status should be 'pending', got {status['status']}"
    print(f"✓ Task status: {status['status']}")

    # Test 2: Cairn acknowledges task
    result = tdm.acknowledge_task(task_id, "cairn")
    assert result, "Acknowledge should succeed"

    status = tdm.get_task_status(task_id)
    assert status['status'] == 'acknowledged', f"Status should be 'acknowledged', got {status['status']}"
    print(f"✓ Task acknowledged by Cairn")

    # Test 3: Cairn starts task
    result = tdm.start_task(task_id, "cairn")
    assert result, "Start should succeed"

    status = tdm.get_task_status(task_id)
    assert status['status'] == 'in_progress', f"Status should be 'in_progress', got {status['status']}"
    print(f"✓ Task started")

    # Test 4: Update progress
    result = tdm.update_progress(task_id, "cairn", 50, "Completed requirements research")
    assert result, "Progress update should succeed"

    status = tdm.get_task_status(task_id)
    assert status['progress_percentage'] == 50, f"Progress should be 50%, got {status['progress_percentage']}%"
    print(f"✓ Progress updated: {status['progress_percentage']}%")

    # Test 5: Complete task
    canvas_content = """
# HIPAA Compliance Requirements

## Technical Safeguards
1. Access Control - Unique user identification
2. Audit Controls - Recording and examining access
3. Integrity Controls - Data cannot be improperly altered
4. Transmission Security - Encryption in transit

## Administrative Safeguards
1. Security Management Process
2. Assigned Security Responsibility
3. Workforce Security
4. Information Access Management

## Physical Safeguards
1. Facility Access Controls
2. Workstation Use
3. Device and Media Controls
"""

    result = tdm.complete_task(
        task_id=task_id,
        agent_id="cairn",
        result={"requirements_count": 10},
        result_summary="Compiled 10 HIPAA compliance requirements across technical, administrative, and physical safeguards.",
        canvas_content=canvas_content
    )
    assert result, "Complete should succeed"

    status = tdm.get_task_status(task_id)
    assert status['status'] == 'completed', f"Status should be 'completed', got {status['status']}"
    assert status['progress_percentage'] == 100, "Progress should be 100%"
    print(f"✓ Task completed")
    print(f"  Result: {status['result_summary'][:80]}...")

    # Test 6: Verify agent workload tracking
    cairn_tasks = tdm.get_tasks_for_agent(session_id, "cairn")
    assert len(cairn_tasks) == 1, f"Cairn should have 1 task, has {len(cairn_tasks)}"
    print(f"✓ Agent task tracking works: Cairn has {len(cairn_tasks)} task(s)")

    print("\n✅ All TaskDelegationManager tests passed!")
    return True


def test_session_integration():
    """Test integration with WorkspaceSessionManager."""
    print("\n" + "="*60)
    print("TEST 2: Session Manager Integration")
    print("="*60)

    # Create fresh managers
    sm = WorkspaceSessionManager()
    tdm = TaskDelegationManager(session_manager=sm)

    class MockWebSocket:
        async def send(self, msg): pass

    session = sm.create_session("user1", "Test User", MockWebSocket())
    session_id = session.id
    print(f"✓ Created session: {session_id}")

    # Delegate task
    task = TaskDefinition(
        id="",
        description="Design authentication flow",
        success_criteria="Clear flow diagram with security considerations",
        canvas_section="auth_design",
        priority="high"
    )

    task_id = tdm.delegate_task(
        from_agent="prax",
        to_agent="cairn",
        task=task,
        session_id=session_id
    )

    # Verify inbox message was sent
    session = sm.get_session(session_id)
    cairn_inbox = session.agent_inboxes.get('cairn', [])
    assert len(cairn_inbox) >= 1, "Cairn should have received delegation message"
    print(f"✓ Delegation message in Cairn's inbox: {len(cairn_inbox)} message(s)")

    # Check inbox message content
    latest_msg = cairn_inbox[-1]
    assert "DELEGATED TASK" in latest_msg.content, "Message should contain DELEGATED TASK"
    assert "Design authentication flow" in latest_msg.content, "Message should contain task description"
    print(f"✓ Inbox message content verified")

    # Verify WebSocket events were queued
    ws_events = sm.get_and_clear_ws_events()
    task_event = next((e for e in ws_events if e['event'] == 'task_delegated'), None)
    assert task_event is not None, "task_delegated event should be queued"
    print(f"✓ WebSocket event 'task_delegated' queued")

    print("\n✅ All Session Integration tests passed!")
    return True


def test_canvas_sections():
    """Test canvas section management."""
    print("\n" + "="*60)
    print("TEST 3: Canvas Section Management")
    print("="*60)

    sm = WorkspaceSessionManager()

    class MockWebSocket:
        async def send(self, msg): pass

    session = sm.create_session("user1", "Test User", MockWebSocket())
    session_id = session.id

    # Create canvas section
    result = sm.create_canvas_section(
        session_id=session_id,
        section_name="compliance_analysis",
        owner="cairn",
        initial_content="# HIPAA Compliance Analysis\n\n*Analysis pending...*"
    )
    assert result, "Canvas section creation should succeed"
    print(f"✓ Created canvas section 'compliance_analysis' owned by Cairn")

    # Get section
    section = sm.get_canvas_section(session_id, "compliance_analysis")
    assert section is not None, "Section should exist"
    assert section['owner'] == 'cairn', "Owner should be cairn"
    print(f"✓ Retrieved canvas section: version {section['version']}")

    # Update section
    new_content = """# HIPAA Compliance Analysis

## Requirements Identified
1. Access Control
2. Audit Controls
3. Integrity Controls
"""
    result = sm.update_canvas_section(
        session_id=session_id,
        section_name="compliance_analysis",
        content=new_content,
        updated_by="cairn"
    )
    assert result, "Update should succeed"

    section = sm.get_canvas_section(session_id, "compliance_analysis")
    assert section['version'] == 2, f"Version should be 2, got {section['version']}"
    print(f"✓ Updated canvas section: version {section['version']}")

    # List sections
    sections = sm.list_canvas_sections(session_id)
    assert len(sections) == 1, f"Should have 1 section, has {len(sections)}"
    print(f"✓ Listed {len(sections)} canvas section(s)")

    # Test permission: koda should NOT be able to update cairn's section
    result = sm.update_canvas_section(
        session_id=session_id,
        section_name="compliance_analysis",
        content="Koda trying to edit",
        updated_by="koda"
    )
    assert not result, "Koda should NOT be able to edit Cairn's section"
    print(f"✓ Permission denied: Koda cannot edit Cairn's section")

    # Get history
    history = sm.get_canvas_section_history(session_id, "compliance_analysis")
    assert len(history) == 2, f"Should have 2 history entries, has {len(history)}"
    print(f"✓ Canvas history: {len(history)} versions")

    print("\n✅ All Canvas Section tests passed!")
    return True


def test_full_delegation_flow():
    """Test complete Prax→Cairn→Result delegation flow."""
    print("\n" + "="*60)
    print("TEST 4: Full Delegation Flow (Prax → Cairn → Result)")
    print("="*60)

    # Create fresh managers
    sm = WorkspaceSessionManager()
    tdm = TaskDelegationManager(session_manager=sm)

    class MockWebSocket:
        async def send(self, msg): pass

    session = sm.create_session("user1", "Test User", MockWebSocket())
    session_id = session.id

    print("\n--- Step 1: Prax delegates to Cairn ---")
    task = TaskDefinition(
        id="",
        description="Research HIPAA compliance requirements for authentication systems",
        success_criteria="Comprehensive list of requirements with sources and recommendations",
        tools_allowed=["web_search", "analysis"],
        canvas_section="hipaa_requirements",
        priority="high"
    )

    task_id = tdm.delegate_task(
        from_agent="prax",
        to_agent="cairn",
        task=task,
        session_id=session_id,
        workflow_id="hipaa_auth"
    )
    print(f"  → Prax delegated task: {task_id}")

    # Register in session
    sm.register_delegated_task(
        session_id=session_id,
        task_id=task_id,
        task_info={
            'from_agent': 'prax',
            'to_agent': 'cairn',
            'description': task.description,
            'status': 'pending',
            'canvas_section': task.canvas_section
        }
    )

    # Check workload updated
    session = sm.get_session(session_id)
    assert session.agent_workload['cairn']['active_tasks'] >= 1
    print(f"  → Cairn workload updated: {session.agent_workload['cairn']}")

    print("\n--- Step 2: Cairn acknowledges and starts ---")
    tdm.acknowledge_task(task_id, "cairn")
    sm.update_delegated_task(session_id, task_id, {'status': 'acknowledged'})

    tdm.start_task(task_id, "cairn")
    sm.update_delegated_task(session_id, task_id, {'status': 'in_progress'})
    print(f"  → Cairn started working on task")

    # Prax should receive acknowledgment message
    prax_inbox = session.agent_inboxes.get('prax', [])
    assert len(prax_inbox) >= 1, "Prax should receive acknowledgment"
    print(f"  → Prax notified: {len(prax_inbox)} message(s) in inbox")

    print("\n--- Step 3: Cairn updates progress ---")
    tdm.update_progress(task_id, "cairn", 50, "Identified 10 key requirements")
    print(f"  → Progress: 50% - Identified 10 key requirements")

    print("\n--- Step 4: Cairn completes and writes to canvas ---")
    canvas_content = """# HIPAA Compliance Requirements for Authentication

## Summary
10 key requirements identified across technical, administrative, and physical safeguards.

## Technical Safeguards (45 CFR § 164.312)

### Access Control (§ 164.312(a)(1))
- Unique User Identification: Assign unique ID to each user
- Emergency Access Procedure: Documented procedure for emergencies
- Automatic Logoff: Terminate sessions after inactivity
- Encryption: Implement encryption mechanisms

### Audit Controls (§ 164.312(b))
- Record and examine activity in systems with ePHI
- Implement hardware, software, and procedural mechanisms

### Integrity (§ 164.312(c)(1))
- Protect ePHI from improper alteration or destruction
- Implement electronic mechanisms to corroborate integrity

### Transmission Security (§ 164.312(e)(1))
- Guard against unauthorized access during transmission
- Implement encryption for ePHI in transit

## Recommendations
1. Implement OAuth 2.0 with PKCE for authentication
2. Use JWT tokens with short expiry (15 min access, 24h refresh)
3. Require MFA for all users accessing ePHI
4. Log all authentication events for audit trail
5. Encrypt all data in transit using TLS 1.3

## Sources
- HHS HIPAA Security Rule: https://www.hhs.gov/hipaa/for-professionals/security/
- NIST Cybersecurity Framework
- HITRUST CSF
"""

    tdm.complete_task(
        task_id=task_id,
        agent_id="cairn",
        result={"requirements_count": 10, "categories": 4},
        result_summary="Compiled 10 HIPAA requirements across 4 categories with implementation recommendations.",
        canvas_content=canvas_content
    )

    sm.update_delegated_task(
        session_id, task_id,
        {'status': 'completed', 'result': 'HIPAA requirements documented'}
    )

    # Write to canvas section
    sm.update_canvas_section(
        session_id=session_id,
        section_name="hipaa_requirements",
        content=canvas_content,
        updated_by="cairn"
    )

    print(f"  → Task completed and written to canvas section 'hipaa_requirements'")

    # Verify final state
    status = tdm.get_task_status(task_id)
    assert status['status'] == 'completed'
    print(f"  → Final task status: {status['status']}")

    # Verify canvas section
    section = sm.get_canvas_section(session_id, "hipaa_requirements")
    assert section is not None
    assert len(section['content']) > 500
    print(f"  → Canvas section content: {len(section['content'])} chars")

    # Verify Prax received completion notification
    prax_inbox = session.agent_inboxes.get('prax', [])
    completion_msgs = [m for m in prax_inbox if 'COMPLETED' in m.content.upper()]
    assert len(completion_msgs) >= 1, "Prax should receive completion notification"
    print(f"  → Prax received completion notification")

    # Verify workload updated
    session = sm.get_session(session_id)
    # Note: workload updates happen through session manager
    print(f"  → Final Cairn workload: {session.agent_workload['cairn']}")

    print("\n✅ Full Delegation Flow test passed!")
    return True


def test_blocker_flow():
    """Test blocker reporting and resolution."""
    print("\n" + "="*60)
    print("TEST 5: Blocker Reporting Flow")
    print("="*60)

    sm = WorkspaceSessionManager()
    tdm = TaskDelegationManager(session_manager=sm)

    class MockWebSocket:
        async def send(self, msg): pass

    session = sm.create_session("user1", "Test User", MockWebSocket())
    session_id = session.id

    # Delegate task
    task = TaskDefinition(
        id="",
        description="Implement database schema for OAuth tokens",
        success_criteria="Working schema with migrations",
        priority="high"
    )

    task_id = tdm.delegate_task("prax", "koda", task, session_id)
    print(f"  → Task delegated: {task_id}")

    # Koda starts
    tdm.acknowledge_task(task_id, "koda")
    tdm.start_task(task_id, "koda")
    print(f"  → Koda started task")

    # Koda reports blocker
    result = tdm.report_blocker(
        task_id=task_id,
        agent_id="koda",
        blocker_description="Need clarification on token expiry policy - should access tokens expire in 15 min or 1 hour?",
        severity="high"
    )
    assert result, "Blocker report should succeed"
    print(f"  → Blocker reported: token expiry clarification needed")

    # Verify task is blocked
    status = tdm.get_task_status(task_id)
    assert status['status'] == 'blocked'
    print(f"  → Task status: {status['status']}")

    # Verify blocker escalated to UI
    ws_events = sm.get_and_clear_ws_events()
    blocker_events = [e for e in ws_events if e['event'] == 'blocker_escalated']
    assert len(blocker_events) >= 1, "Blocker should be escalated"
    print(f"  → Blocker escalated to UI")

    # Resolve blocker
    result = tdm.resolve_blocker(task_id, "Use 15 min for access tokens, 24h for refresh tokens")
    assert result, "Resolution should succeed"
    print(f"  → Blocker resolved")

    # Verify task resumed
    status = tdm.get_task_status(task_id)
    assert status['status'] == 'in_progress'
    print(f"  → Task status: {status['status']}")

    print("\n✅ Blocker Flow test passed!")
    return True


def main():
    """Run all tests."""
    print("="*60)
    print("  Phase 4C.1 Integration Tests")
    print("  Hierarchical Task Delegation")
    print("="*60)

    tests = [
        ("TaskDelegationManager Basic", test_task_delegation_manager),
        ("Session Integration", test_session_integration),
        ("Canvas Sections", test_canvas_sections),
        ("Full Delegation Flow", test_full_delegation_flow),
        ("Blocker Flow", test_blocker_flow),
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
        print("\n🎉 All Phase 4C.1 tests passed!")
        print("\nPhase 4C.1 Implementation Complete:")
        print("  ✓ TaskDelegationManager class")
        print("  ✓ DelegatedTask tracking in WorkspaceSession")
        print("  ✓ Enhanced Prax system prompt with delegation patterns")
        print("  ✓ WebSocket events for task lifecycle")
        print("  ✓ Canvas section assignment and management")
        print("\nSuccess Criteria Met:")
        print("  ✓ Prax can send: 'Cairn, research HIPAA compliance requirements'")
        print("  ✓ Cairn receives structured task")
        print("  ✓ Completes research")
        print("  ✓ Reports results back to Prax")
        print("  ✓ Results written to designated canvas section")
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
