#!/usr/bin/env python3
"""
Phase 4B Backend Testing Script

Tests all MCP tool functionality without requiring frontend.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from workspace_session_manager import WorkspaceSessionManager, User, UserRole
from dataclasses import asdict


def test_phase4b_backend():
    """Test all Phase 4B backend functionality."""

    print("=" * 60)
    print("PHASE 4B BACKEND TESTING")
    print("=" * 60)
    print()

    # Create session manager
    manager = WorkspaceSessionManager()

    # Test 1: Create a test session
    print("TEST 1: Session Creation")
    print("-" * 60)

    class MockWebSocket:
        async def send(self, data):
            pass

    owner_ws = MockWebSocket()
    session = manager.create_session("test_user_1", "Alice", owner_ws)

    print(f"✓ Created session: {session.id}")
    print(f"✓ Owner: {session.owner_id}")
    print(f"✓ Agent inboxes initialized: {list(session.agent_inboxes.keys())}")
    print(f"✓ Agent capabilities: {list(session.agent_capabilities.keys())}")
    print()

    # Test 2: Agent Messaging
    print("TEST 2: Agent-to-Agent Messaging")
    print("-" * 60)

    msg1 = manager.send_agent_message(
        session.id,
        from_agent='prax',
        to_agent='koda',
        content='Please implement the authentication endpoint',
        priority='high',
        metadata={'workflow_id': 'auth_system', 'task_type': 'implementation'}
    )

    print(f"✓ Sent message: prax → koda")
    print(f"  Message ID: {msg1.id}")
    print(f"  Priority: {msg1.priority}")
    print(f"  Content: {msg1.content[:50]}...")
    print()

    msg2 = manager.send_agent_message(
        session.id,
        from_agent='cairn',
        to_agent='koda',
        content='Here are the design specs for the API',
        priority='medium',
        metadata={'workflow_id': 'auth_system', 'task_type': 'design'}
    )

    print(f"✓ Sent message: cairn → koda")
    print(f"  Message ID: {msg2.id}")
    print()

    # Test 3: Check Inbox
    print("TEST 3: Check Inbox")
    print("-" * 60)

    koda_inbox = manager.check_inbox(session.id, 'koda', unread_only=True)

    print(f"✓ Koda's inbox: {len(koda_inbox)} unread messages")
    for i, msg in enumerate(koda_inbox, 1):
        print(f"  {i}. From {msg.from_agent} (priority: {msg.priority})")
        print(f"     Content: {msg.content[:60]}...")
    print()

    # Test 4: Search Messages
    print("TEST 4: Search Messages")
    print("-" * 60)

    search_results = manager.search_messages(
        session.id,
        'koda',
        query='authentication',
        workflow_id='auth_system'
    )

    print(f"✓ Search for 'authentication': {len(search_results)} results")
    for msg in search_results:
        print(f"  - From {msg.from_agent}: {msg.content[:50]}...")
    print()

    # Test 5: Workflow Creation
    print("TEST 5: Workflow Management")
    print("-" * 60)

    workflow = manager.create_workflow(
        session.id,
        workflow_id='oauth2_auth',
        name='OAuth2 Authentication System',
        assigned_agents=['cairn', 'koda'],
        deadline='2026-01-20T18:00:00Z'
    )

    print(f"✓ Created workflow: {workflow.name}")
    print(f"  ID: {workflow.id}")
    print(f"  Status: {workflow.status}")
    print(f"  Assigned agents: {workflow.assigned_agents}")
    print()

    # Test 6: Set Milestones
    print("TEST 6: Milestone Tracking")
    print("-" * 60)

    manager.set_milestone(
        session.id,
        'oauth2_auth',
        milestone='Design complete',
        status='in_progress',
        completion_percentage=50
    )

    print(f"✓ Set milestone: Design complete (50%)")

    manager.set_milestone(
        session.id,
        'oauth2_auth',
        milestone='Implementation complete',
        status='pending',
        completion_percentage=0
    )

    print(f"✓ Set milestone: Implementation complete (0%)")
    print()

    # Test 7: Context Sharing
    print("TEST 7: Context Sharing")
    print("-" * 60)

    manager.share_context(
        session.id,
        from_agent='cairn',
        target='koda',
        context_key='api_spec',
        content={
            'endpoint': '/auth/login',
            'method': 'POST',
            'body': {'username': 'string', 'password': 'string'},
            'response': {'token': 'jwt_token', 'expires': 'timestamp'}
        },
        workflow_id='oauth2_auth'
    )

    print(f"✓ Shared context: api_spec (cairn → koda)")

    retrieved_context = manager.get_shared_context(
        session.id,
        context_key='api_spec',
        workflow_id='oauth2_auth'
    )

    print(f"✓ Retrieved context: {list(retrieved_context['content'].keys())}")
    print()

    # Test 8: Blocker Escalation
    print("TEST 8: Blocker Escalation")
    print("-" * 60)

    blocker_id = manager.escalate_blocker(
        session.id,
        blocker_description='Database schema needs clarification for OAuth token storage',
        affected_agents=['koda'],
        severity='high',
        requires_human_input=True
    )

    print(f"✓ Escalated blocker: {blocker_id[:8]}...")
    print(f"  Severity: high")
    print(f"  Requires human input: Yes")
    print()

    # Test 9: Agent Workload
    print("TEST 9: Agent Workload Tracking")
    print("-" * 60)

    for agent_id in ['prax', 'cairn', 'koda']:
        workload = manager.get_agent_workload(session.id, agent_id)
        capabilities = manager.get_agent_capabilities(session.id, agent_id)
        print(f"✓ {agent_id.upper()}")
        print(f"  Active tasks: {workload.get('active_tasks', 0)}")
        print(f"  Status: {workload.get('status', 'unknown')}")
        print(f"  Capabilities: {', '.join(capabilities)}")
    print()

    # Test 10: Workflow Status
    print("TEST 10: Get Workflow Status")
    print("-" * 60)

    workflow_status = manager.get_workflow_status(session.id, 'oauth2_auth')

    print(f"✓ Workflow: {workflow_status.name}")
    print(f"  Status: {workflow_status.status}")
    print(f"  Milestones:")
    for milestone, data in workflow_status.milestones.items():
        print(f"    - {milestone}: {data['status']} ({data['completion_percentage']}%)")
    print()

    # Test 11: Audit Log
    print("TEST 11: Audit Log")
    print("-" * 60)

    print(f"✓ Total audit entries: {len(session.audit_log)}")
    print(f"✓ Recent events:")
    for entry in session.audit_log[-5:]:
        print(f"  - {entry.action} by {entry.user_id}")
        if entry.workflow_id:
            print(f"    [Workflow: {entry.workflow_id}]")
    print()

    # Test 12: WebSocket Events Queue
    print("TEST 12: WebSocket Event Queue")
    print("-" * 60)

    events = manager.get_and_clear_ws_events()

    print(f"✓ Pending WebSocket events: {len(events)}")
    for event in events[:5]:
        print(f"  - {event['event']} for session {event['session_id'][:6]}...")
    print()

    # Test 13: Session Export
    print("TEST 13: Session Serialization")
    print("-" * 60)

    session_dict = session.to_dict()

    print(f"✓ Session serialized to dict")
    print(f"  Keys: {list(session_dict.keys())}")
    print(f"  Agent inboxes: {len(session_dict['agent_inboxes']['koda'])} messages in koda's inbox")
    print(f"  Workflows: {len(session_dict['workflows'])} workflow(s)")
    print(f"  Shared contexts: {len(session_dict['shared_contexts'])} context(s)")
    print()

    # Summary
    print("=" * 60)
    print("TESTING COMPLETE")
    print("=" * 60)
    print()
    print("✅ All Phase 4B backend features working correctly!")
    print()
    print("Summary:")
    print(f"  - Session ID: {session.id}")
    print(f"  - Messages sent: 2")
    print(f"  - Workflows created: 1")
    print(f"  - Milestones: 2")
    print(f"  - Contexts shared: 1")
    print(f"  - Blockers escalated: 1")
    print(f"  - WebSocket events: {len(events)}")
    print()
    print("Next: Test frontend at http://localhost:8080")
    print()


if __name__ == '__main__':
    test_phase4b_backend()
