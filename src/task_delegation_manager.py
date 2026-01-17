#!/usr/bin/env python3
"""
Task Delegation Manager - Phase 4C.1 Hierarchical Delegation Foundation

Handles:
- Task delegation from Prax to Cairn/Koda
- Task lifecycle tracking (pending, in_progress, completed, blocked)
- Canvas section assignment for task results
- Task status reporting back to Prax
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum


class TaskStatus(Enum):
    """Status of a delegated task."""
    PENDING = "pending"           # Task created, not yet started
    ACKNOWLEDGED = "acknowledged"  # Agent received and acknowledged task
    IN_PROGRESS = "in_progress"   # Agent actively working
    BLOCKED = "blocked"           # Task blocked, waiting for resolution
    COMPLETED = "completed"       # Task finished successfully
    FAILED = "failed"             # Task failed
    CANCELLED = "cancelled"       # Task cancelled


class TaskPriority(Enum):
    """Priority levels for tasks."""
    CRITICAL = "critical"  # Immediate attention required
    HIGH = "high"          # Urgent, complete soon
    MEDIUM = "medium"      # Standard priority
    LOW = "low"            # Can wait


@dataclass
class TaskDefinition:
    """
    Definition of a delegated task.

    Matches the delegation message format from PRD:
    {
      "type": "task_delegation",
      "from": "prax",
      "to": "cairn",
      "task": {
        "id": "task_123",
        "description": "Research HIPAA compliance requirements",
        "success_criteria": "Comprehensive list of requirements with sources",
        "tools_allowed": ["web_search", "deepseek"],
        "canvas_section": "compliance_analysis",
        "deadline": "2026-01-17T18:00:00Z",
        "priority": "high"
      }
    }
    """
    id: str
    description: str
    success_criteria: str
    tools_allowed: List[str] = field(default_factory=list)
    canvas_section: Optional[str] = None
    deadline: Optional[str] = None
    priority: str = "medium"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return asdict(self)


@dataclass
class DelegatedTask:
    """
    A task that has been delegated from one agent to another.

    Tracks full lifecycle from delegation to completion.
    """
    # Core identifiers
    id: str
    session_id: str
    workflow_id: Optional[str] = None

    # Delegation info
    from_agent: str = "prax"  # Always prax in hierarchical model
    to_agent: str = ""        # cairn or koda

    # Task definition
    task_definition: Optional[TaskDefinition] = None

    # Status tracking
    status: TaskStatus = TaskStatus.PENDING
    status_history: List[Dict] = field(default_factory=list)

    # Progress tracking
    progress_percentage: int = 0
    progress_notes: str = ""

    # Result tracking
    result: Optional[Any] = None
    result_summary: str = ""
    canvas_content: str = ""

    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    acknowledged_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    # Blocking info
    blocker_description: Optional[str] = None
    blocker_severity: str = "medium"

    def __post_init__(self):
        """Initialize status history with creation event."""
        if not self.status_history:
            self.status_history.append({
                'status': self.status.value,
                'timestamp': self.created_at,
                'note': 'Task created'
            })

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'workflow_id': self.workflow_id,
            'from_agent': self.from_agent,
            'to_agent': self.to_agent,
            'task_definition': self.task_definition.to_dict() if self.task_definition else None,
            'status': self.status.value,
            'status_history': self.status_history,
            'progress_percentage': self.progress_percentage,
            'progress_notes': self.progress_notes,
            'result': self.result,
            'result_summary': self.result_summary,
            'canvas_content': self.canvas_content,
            'created_at': self.created_at,
            'acknowledged_at': self.acknowledged_at,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'blocker_description': self.blocker_description,
            'blocker_severity': self.blocker_severity
        }


class TaskDelegationManager:
    """
    Manages hierarchical task delegation from Prax to Cairn/Koda.

    Key responsibilities:
    - Create and track delegated tasks
    - Monitor task status and progress
    - Handle task completion and result reporting
    - Manage canvas section assignments
    - Coordinate with WorkspaceSessionManager for messaging
    """

    def __init__(self, session_manager=None):
        """
        Initialize TaskDelegationManager.

        Args:
            session_manager: WorkspaceSessionManager instance for messaging/events
        """
        self.session_manager = session_manager
        self.tasks: Dict[str, DelegatedTask] = {}  # task_id -> DelegatedTask
        self.tasks_by_session: Dict[str, List[str]] = {}  # session_id -> [task_ids]
        self.tasks_by_agent: Dict[str, Dict[str, List[str]]] = {}  # session_id -> agent -> [task_ids]

    def delegate_task(
        self,
        from_agent: str,
        to_agent: str,
        task: TaskDefinition,
        session_id: str,
        workflow_id: Optional[str] = None
    ) -> str:
        """
        Delegate a task from orchestrator (Prax) to execution agent (Cairn/Koda).

        Args:
            from_agent: Source agent (should be 'prax')
            to_agent: Target agent ('cairn' or 'koda')
            task: TaskDefinition with all task details
            session_id: Session ID for this delegation
            workflow_id: Optional workflow ID to associate

        Returns:
            task_id: Unique task ID for tracking

        Raises:
            ValueError: If invalid agent IDs provided
        """
        # Validate agents
        valid_orchestrators = ['prax']
        valid_executors = ['cairn', 'koda']

        if from_agent not in valid_orchestrators:
            raise ValueError(f"Invalid from_agent: {from_agent}. Must be one of {valid_orchestrators}")
        if to_agent not in valid_executors:
            raise ValueError(f"Invalid to_agent: {to_agent}. Must be one of {valid_executors}")

        # Generate task ID if not provided
        task_id = task.id if task.id else f"task_{uuid.uuid4().hex[:12]}"
        task.id = task_id

        # Create DelegatedTask
        delegated_task = DelegatedTask(
            id=task_id,
            session_id=session_id,
            workflow_id=workflow_id,
            from_agent=from_agent,
            to_agent=to_agent,
            task_definition=task,
            status=TaskStatus.PENDING
        )

        # Store task
        self.tasks[task_id] = delegated_task

        # Index by session
        if session_id not in self.tasks_by_session:
            self.tasks_by_session[session_id] = []
        self.tasks_by_session[session_id].append(task_id)

        # Index by agent
        if session_id not in self.tasks_by_agent:
            self.tasks_by_agent[session_id] = {'prax': [], 'cairn': [], 'koda': []}
        self.tasks_by_agent[session_id][to_agent].append(task_id)

        # Send delegation message to target agent via session manager
        if self.session_manager:
            self.session_manager.send_agent_message(
                session_id=session_id,
                from_agent=from_agent,
                to_agent=to_agent,
                content=self._format_delegation_message(task),
                priority='high' if task.priority in ['critical', 'high'] else 'medium',
                metadata={
                    'task_type': 'task_delegation',
                    'task_id': task_id,
                    'workflow_id': workflow_id,
                    'success_criteria': task.success_criteria,
                    'tools_allowed': task.tools_allowed,
                    'canvas_section': task.canvas_section,
                    'deadline': task.deadline
                }
            )

            # Queue WebSocket event
            self.session_manager._queue_ws_event(session_id, 'task_delegated', {
                'task_id': task_id,
                'from_agent': from_agent,
                'to_agent': to_agent,
                'description': task.description,
                'priority': task.priority,
                'canvas_section': task.canvas_section,
                'deadline': task.deadline,
                'workflow_id': workflow_id
            })

        print(f"[TaskDelegationManager] Task delegated: {task_id} ({from_agent} → {to_agent})")

        return task_id

    def _format_delegation_message(self, task: TaskDefinition) -> str:
        """Format task definition as message content."""
        msg_parts = [
            f"**DELEGATED TASK**",
            f"",
            f"**Description:** {task.description}",
            f"",
            f"**Success Criteria:** {task.success_criteria}",
        ]

        if task.tools_allowed:
            msg_parts.append(f"**Tools Allowed:** {', '.join(task.tools_allowed)}")

        if task.canvas_section:
            msg_parts.append(f"**Write Results To:** Canvas section '{task.canvas_section}'")

        if task.deadline:
            msg_parts.append(f"**Deadline:** {task.deadline}")

        msg_parts.append(f"**Priority:** {task.priority.upper()}")
        msg_parts.append(f"")
        msg_parts.append(f"Please acknowledge receipt and begin work.")

        return "\n".join(msg_parts)

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """
        Get current status of a delegated task.

        Args:
            task_id: Task ID to query

        Returns:
            Dict with status info, or None if task not found
        """
        task = self.tasks.get(task_id)
        if not task:
            return None

        return {
            'task_id': task_id,
            'status': task.status.value,
            'progress_percentage': task.progress_percentage,
            'progress_notes': task.progress_notes,
            'to_agent': task.to_agent,
            'created_at': task.created_at,
            'acknowledged_at': task.acknowledged_at,
            'started_at': task.started_at,
            'completed_at': task.completed_at,
            'blocker_description': task.blocker_description,
            'result_summary': task.result_summary
        }

    def acknowledge_task(self, task_id: str, agent_id: str) -> bool:
        """
        Agent acknowledges receipt of delegated task.

        Args:
            task_id: Task ID being acknowledged
            agent_id: Agent acknowledging (must match to_agent)

        Returns:
            True if acknowledged, False if task not found or wrong agent
        """
        task = self.tasks.get(task_id)
        if not task or task.to_agent != agent_id:
            return False

        if task.status == TaskStatus.PENDING:
            task.status = TaskStatus.ACKNOWLEDGED
            task.acknowledged_at = datetime.utcnow().isoformat()
            task.status_history.append({
                'status': TaskStatus.ACKNOWLEDGED.value,
                'timestamp': task.acknowledged_at,
                'note': f'Task acknowledged by {agent_id}'
            })

            # Notify Prax
            if self.session_manager:
                self.session_manager.send_agent_message(
                    session_id=task.session_id,
                    from_agent=agent_id,
                    to_agent='prax',
                    content=f"Task {task_id} acknowledged. Will begin work shortly.",
                    priority='medium',
                    metadata={
                        'task_type': 'task_acknowledgement',
                        'task_id': task_id,
                        'workflow_id': task.workflow_id
                    }
                )

                self.session_manager._queue_ws_event(task.session_id, 'task_acknowledged', {
                    'task_id': task_id,
                    'agent': agent_id
                })

            print(f"[TaskDelegationManager] Task acknowledged: {task_id} by {agent_id}")
            return True

        return False

    def start_task(self, task_id: str, agent_id: str) -> bool:
        """
        Agent signals they are starting work on task.

        Args:
            task_id: Task ID being started
            agent_id: Agent starting work

        Returns:
            True if started, False otherwise
        """
        task = self.tasks.get(task_id)
        if not task or task.to_agent != agent_id:
            return False

        if task.status in [TaskStatus.PENDING, TaskStatus.ACKNOWLEDGED]:
            task.status = TaskStatus.IN_PROGRESS
            task.started_at = datetime.utcnow().isoformat()
            task.status_history.append({
                'status': TaskStatus.IN_PROGRESS.value,
                'timestamp': task.started_at,
                'note': f'Work started by {agent_id}'
            })

            if self.session_manager:
                self.session_manager._queue_ws_event(task.session_id, 'task_started', {
                    'task_id': task_id,
                    'agent': agent_id
                })

            print(f"[TaskDelegationManager] Task started: {task_id} by {agent_id}")
            return True

        return False

    def update_progress(
        self,
        task_id: str,
        agent_id: str,
        progress_percentage: int,
        notes: str = ""
    ) -> bool:
        """
        Update task progress.

        Args:
            task_id: Task ID
            agent_id: Agent updating (must match to_agent)
            progress_percentage: 0-100
            notes: Optional progress notes

        Returns:
            True if updated, False otherwise
        """
        task = self.tasks.get(task_id)
        if not task or task.to_agent != agent_id:
            return False

        if task.status == TaskStatus.IN_PROGRESS:
            task.progress_percentage = max(0, min(100, progress_percentage))
            task.progress_notes = notes
            task.status_history.append({
                'status': TaskStatus.IN_PROGRESS.value,
                'timestamp': datetime.utcnow().isoformat(),
                'note': f'Progress: {progress_percentage}% - {notes}'
            })

            if self.session_manager:
                self.session_manager._queue_ws_event(task.session_id, 'task_progress', {
                    'task_id': task_id,
                    'agent': agent_id,
                    'progress_percentage': progress_percentage,
                    'notes': notes
                })

            print(f"[TaskDelegationManager] Task progress: {task_id} at {progress_percentage}%")
            return True

        return False

    def report_blocker(
        self,
        task_id: str,
        agent_id: str,
        blocker_description: str,
        severity: str = "medium"
    ) -> bool:
        """
        Agent reports a blocker on their task.

        Args:
            task_id: Task ID that is blocked
            agent_id: Agent reporting blocker
            blocker_description: Description of the blocker
            severity: 'critical', 'high', 'medium', 'low'

        Returns:
            True if blocker reported, False otherwise
        """
        task = self.tasks.get(task_id)
        if not task or task.to_agent != agent_id:
            return False

        if task.status == TaskStatus.IN_PROGRESS:
            task.status = TaskStatus.BLOCKED
            task.blocker_description = blocker_description
            task.blocker_severity = severity
            task.status_history.append({
                'status': TaskStatus.BLOCKED.value,
                'timestamp': datetime.utcnow().isoformat(),
                'note': f'Blocked: {blocker_description}'
            })

            # Notify Prax of blocker
            if self.session_manager:
                self.session_manager.send_agent_message(
                    session_id=task.session_id,
                    from_agent=agent_id,
                    to_agent='prax',
                    content=f"**BLOCKER** on task {task_id}:\n\n{blocker_description}\n\nSeverity: {severity.upper()}",
                    priority='high',
                    metadata={
                        'task_type': 'task_blocker',
                        'task_id': task_id,
                        'workflow_id': task.workflow_id,
                        'severity': severity
                    }
                )

                # Escalate blocker to UI
                self.session_manager.escalate_blocker(
                    session_id=task.session_id,
                    blocker_description=f"Task {task_id}: {blocker_description}",
                    affected_agents=[agent_id, 'prax'],
                    severity=severity,
                    requires_human_input=severity in ['critical', 'high']
                )

                self.session_manager._queue_ws_event(task.session_id, 'task_blocked', {
                    'task_id': task_id,
                    'agent': agent_id,
                    'blocker_description': blocker_description,
                    'severity': severity
                })

            print(f"[TaskDelegationManager] Task blocked: {task_id} - {blocker_description}")
            return True

        return False

    def resolve_blocker(self, task_id: str, resolution: str = "") -> bool:
        """
        Resolve blocker and resume task.

        Args:
            task_id: Task ID to unblock
            resolution: Optional resolution description

        Returns:
            True if resolved, False otherwise
        """
        task = self.tasks.get(task_id)
        if not task:
            return False

        if task.status == TaskStatus.BLOCKED:
            task.status = TaskStatus.IN_PROGRESS
            task.blocker_description = None
            task.status_history.append({
                'status': TaskStatus.IN_PROGRESS.value,
                'timestamp': datetime.utcnow().isoformat(),
                'note': f'Blocker resolved: {resolution}'
            })

            if self.session_manager:
                self.session_manager._queue_ws_event(task.session_id, 'task_resumed', {
                    'task_id': task_id,
                    'agent': task.to_agent,
                    'resolution': resolution
                })

            print(f"[TaskDelegationManager] Task resumed: {task_id}")
            return True

        return False

    def complete_task(
        self,
        task_id: str,
        agent_id: str,
        result: Any,
        result_summary: str,
        canvas_content: str = ""
    ) -> bool:
        """
        Mark task as complete with results.

        Args:
            task_id: Task ID being completed
            agent_id: Agent completing (must match to_agent)
            result: Full result data
            result_summary: Brief summary for Prax
            canvas_content: Content to write to canvas section

        Returns:
            True if completed, False otherwise
        """
        task = self.tasks.get(task_id)
        if not task or task.to_agent != agent_id:
            return False

        if task.status in [TaskStatus.IN_PROGRESS, TaskStatus.ACKNOWLEDGED]:
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.utcnow().isoformat()
            task.progress_percentage = 100
            task.result = result
            task.result_summary = result_summary
            task.canvas_content = canvas_content
            task.status_history.append({
                'status': TaskStatus.COMPLETED.value,
                'timestamp': task.completed_at,
                'note': f'Completed: {result_summary}'
            })

            # Report back to Prax
            if self.session_manager:
                # Send completion message
                self.session_manager.send_agent_message(
                    session_id=task.session_id,
                    from_agent=agent_id,
                    to_agent='prax',
                    content=self._format_completion_message(task, result_summary),
                    priority='high',
                    metadata={
                        'task_type': 'task_completion',
                        'task_id': task_id,
                        'workflow_id': task.workflow_id,
                        'canvas_section': task.task_definition.canvas_section if task.task_definition else None
                    }
                )

                # If canvas section specified, share result as context
                if task.task_definition and task.task_definition.canvas_section and canvas_content:
                    self.session_manager.share_context(
                        session_id=task.session_id,
                        from_agent=agent_id,
                        target='all',
                        context_key=f"canvas:{task.task_definition.canvas_section}",
                        content=canvas_content,
                        workflow_id=task.workflow_id or 'default'
                    )

                self.session_manager._queue_ws_event(task.session_id, 'task_completed', {
                    'task_id': task_id,
                    'agent': agent_id,
                    'result_summary': result_summary,
                    'canvas_section': task.task_definition.canvas_section if task.task_definition else None,
                    'has_canvas_content': bool(canvas_content)
                })

            print(f"[TaskDelegationManager] Task completed: {task_id} by {agent_id}")
            return True

        return False

    def _format_completion_message(self, task: DelegatedTask, result_summary: str) -> str:
        """Format task completion message for Prax."""
        msg_parts = [
            f"**TASK COMPLETED**",
            f"",
            f"**Task ID:** {task.id}",
            f"**Description:** {task.task_definition.description if task.task_definition else 'N/A'}",
            f"",
            f"**Result Summary:**",
            result_summary,
        ]

        if task.task_definition and task.task_definition.canvas_section and task.canvas_content:
            msg_parts.append(f"")
            msg_parts.append(f"**Canvas Section:** '{task.task_definition.canvas_section}' has been updated.")

        return "\n".join(msg_parts)

    def fail_task(
        self,
        task_id: str,
        agent_id: str,
        reason: str
    ) -> bool:
        """
        Mark task as failed.

        Args:
            task_id: Task ID that failed
            agent_id: Agent reporting failure
            reason: Reason for failure

        Returns:
            True if marked failed, False otherwise
        """
        task = self.tasks.get(task_id)
        if not task or task.to_agent != agent_id:
            return False

        task.status = TaskStatus.FAILED
        task.completed_at = datetime.utcnow().isoformat()
        task.result_summary = f"FAILED: {reason}"
        task.status_history.append({
            'status': TaskStatus.FAILED.value,
            'timestamp': task.completed_at,
            'note': f'Failed: {reason}'
        })

        if self.session_manager:
            self.session_manager.send_agent_message(
                session_id=task.session_id,
                from_agent=agent_id,
                to_agent='prax',
                content=f"**TASK FAILED**\n\nTask ID: {task_id}\nReason: {reason}",
                priority='high',
                metadata={
                    'task_type': 'task_failure',
                    'task_id': task_id,
                    'workflow_id': task.workflow_id
                }
            )

            self.session_manager._queue_ws_event(task.session_id, 'task_failed', {
                'task_id': task_id,
                'agent': agent_id,
                'reason': reason
            })

        print(f"[TaskDelegationManager] Task failed: {task_id} - {reason}")
        return True

    def cancel_task(self, task_id: str, reason: str = "") -> bool:
        """
        Cancel a delegated task.

        Args:
            task_id: Task ID to cancel
            reason: Optional cancellation reason

        Returns:
            True if cancelled, False otherwise
        """
        task = self.tasks.get(task_id)
        if not task:
            return False

        if task.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.utcnow().isoformat()
            task.status_history.append({
                'status': TaskStatus.CANCELLED.value,
                'timestamp': task.completed_at,
                'note': f'Cancelled: {reason}'
            })

            if self.session_manager:
                self.session_manager.send_agent_message(
                    session_id=task.session_id,
                    from_agent='prax',
                    to_agent=task.to_agent,
                    content=f"**TASK CANCELLED**\n\nTask ID: {task_id}\nReason: {reason}",
                    priority='high',
                    metadata={
                        'task_type': 'task_cancellation',
                        'task_id': task_id
                    }
                )

                self.session_manager._queue_ws_event(task.session_id, 'task_cancelled', {
                    'task_id': task_id,
                    'reason': reason
                })

            print(f"[TaskDelegationManager] Task cancelled: {task_id}")
            return True

        return False

    def get_tasks_for_agent(
        self,
        session_id: str,
        agent_id: str,
        status_filter: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Get all tasks assigned to an agent.

        Args:
            session_id: Session ID
            agent_id: Agent ID ('cairn' or 'koda')
            status_filter: Optional list of statuses to filter by

        Returns:
            List of task status dicts
        """
        if session_id not in self.tasks_by_agent:
            return []

        task_ids = self.tasks_by_agent[session_id].get(agent_id, [])
        tasks = []

        for task_id in task_ids:
            task = self.tasks.get(task_id)
            if task:
                if status_filter is None or task.status.value in status_filter:
                    tasks.append(self.get_task_status(task_id))

        return tasks

    def get_all_session_tasks(
        self,
        session_id: str,
        status_filter: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Get all tasks for a session.

        Args:
            session_id: Session ID
            status_filter: Optional list of statuses to filter by

        Returns:
            List of task dicts
        """
        if session_id not in self.tasks_by_session:
            return []

        tasks = []
        for task_id in self.tasks_by_session[session_id]:
            task = self.tasks.get(task_id)
            if task:
                if status_filter is None or task.status.value in status_filter:
                    tasks.append(task.to_dict())

        return tasks

    def get_active_task_count(self, session_id: str, agent_id: str) -> int:
        """
        Get count of active (non-completed) tasks for an agent.

        Args:
            session_id: Session ID
            agent_id: Agent ID

        Returns:
            Count of active tasks
        """
        active_statuses = [
            TaskStatus.PENDING.value,
            TaskStatus.ACKNOWLEDGED.value,
            TaskStatus.IN_PROGRESS.value,
            TaskStatus.BLOCKED.value
        ]

        tasks = self.get_tasks_for_agent(session_id, agent_id, active_statuses)
        return len(tasks)


# Global task delegation manager instance (will be initialized with session_manager)
task_delegation_manager: Optional[TaskDelegationManager] = None


def get_task_delegation_manager(session_manager=None) -> TaskDelegationManager:
    """
    Get or create the global TaskDelegationManager instance.

    Args:
        session_manager: WorkspaceSessionManager to use for messaging

    Returns:
        TaskDelegationManager instance
    """
    global task_delegation_manager

    if task_delegation_manager is None:
        task_delegation_manager = TaskDelegationManager(session_manager)
    elif session_manager and task_delegation_manager.session_manager is None:
        task_delegation_manager.session_manager = session_manager

    return task_delegation_manager
