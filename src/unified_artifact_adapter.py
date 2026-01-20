#!/usr/bin/env python3
"""
Unified Artifact Adapter - Universal 3D Data Explorer Backend

Normalizes all collaborative data sources into a unified format:
- Workspace Sessions
- Canvas Documents
- Messages
- Tasks
- Calendar Events
- Todos
- Conversations (Claude history)
- Files (uploaded)
- Inbox Messages
- Handoffs

Each source is adapted to the UnifiedArtifact schema for consistent
visualization and search across the 3D explorer.
"""

import json
import os
import glob
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum


class ArtifactType(Enum):
    """Types of unified artifacts."""
    WORKSPACE_SESSION = "workspace_session"
    CANVAS = "canvas"
    MESSAGE = "message"
    TASK = "task"
    CALENDAR = "calendar"
    TODO = "todo"
    CONVERSATION = "conversation"
    FILE = "file"
    INBOX = "inbox"
    HANDOFF = "handoff"


# Color mapping for each type (hex colors)
ARTIFACT_COLORS = {
    ArtifactType.WORKSPACE_SESSION: "#f7b731",  # Gold
    ArtifactType.CANVAS: "#a855f7",              # Purple
    ArtifactType.MESSAGE: "#3b82f6",             # Blue
    ArtifactType.TASK: "#ef4444",                # Red
    ArtifactType.CALENDAR: "#10b981",            # Green
    ArtifactType.TODO: "#f59e0b",                # Amber
    ArtifactType.CONVERSATION: "#4facfe",        # Light blue
    ArtifactType.FILE: "#8b5cf6",                # Violet
    ArtifactType.INBOX: "#ec4899",               # Pink
    ArtifactType.HANDOFF: "#00C851",             # Green
}


@dataclass
class UnifiedArtifact:
    """
    Normalized representation of any collaborative data item.
    All data sources are converted to this format for unified display.
    """
    id: str                           # Unique identifier
    type: str                         # ArtifactType value
    title: str                        # Display text
    preview: str                      # Short preview (100-200 chars)
    color: str                        # Hex color for node
    created_at: str                   # ISO timestamp
    parent_id: Optional[str] = None   # Parent artifact ID
    related_ids: List[str] = field(default_factory=list)  # Related artifacts
    participants: List[str] = field(default_factory=list)  # prax, koda, cairn, user IDs
    source: str = ""                  # Origin system
    status: Optional[str] = None      # pending|in_progress|completed
    tags: List[str] = field(default_factory=list)  # Searchable tags
    metadata: Dict[str, Any] = field(default_factory=dict)  # Type-specific data

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "preview": self.preview,
            "color": self.color,
            "created_at": self.created_at,
            "parent_id": self.parent_id,
            "related_ids": self.related_ids,
            "participants": self.participants,
            "source": self.source,
            "status": self.status,
            "tags": self.tags,
            "metadata": self.metadata
        }


class UnifiedArtifactAdapter:
    """
    Adapts all data sources to UnifiedArtifact format.
    Provides unified access, search, and relationship discovery.
    """

    def __init__(self):
        """Initialize paths to data sources."""
        self.home = Path.home()

        # Data source paths
        self.workspace_sessions_dir = self.home / ".claude" / "workspace_sessions"
        self.fsl_collab_dir = self.home / ".fsl" / "collab"
        self.calendars_dir = self.fsl_collab_dir / "calendars"
        self.todos_dir = self.fsl_collab_dir / "todos"
        self.history_file = self.home / ".claude" / "history.jsonl"
        self.uploads_dir = self.home / "ztgi" / "uploads"
        self.uploads_index = self.uploads_dir / "index.json"
        self.golden_library_dir = self.home / "ztgi" / "golden_library" / ".golden_library"
        self.golden_index = self.golden_library_dir / "index.json"

        # Cache
        self._cache: Dict[str, UnifiedArtifact] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl = 60  # seconds

    def _generate_id(self, prefix: str, content: str) -> str:
        """Generate a deterministic ID from content."""
        hash_input = f"{prefix}:{content}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:12]

    def _truncate_preview(self, text: str, max_len: int = 200) -> str:
        """Truncate text to preview length."""
        if not text:
            return ""
        text = text.replace("\n", " ").strip()
        if len(text) <= max_len:
            return text
        return text[:max_len-3] + "..."

    # ========== WORKSPACE SESSIONS ==========

    def _load_workspace_sessions(self) -> List[UnifiedArtifact]:
        """Load workspace session files."""
        artifacts = []

        if not self.workspace_sessions_dir.exists():
            return artifacts

        for session_file in self.workspace_sessions_dir.glob("*.json"):
            try:
                with open(session_file, 'r') as f:
                    session = json.load(f)

                session_id = session.get("id", session_file.stem)
                participants = session.get("participants", [])
                if isinstance(participants, dict):
                    participants = list(participants.keys())

                messages = session.get("messages", [])
                preview = ""
                if messages:
                    last_msg = messages[-1] if isinstance(messages[-1], dict) else {}
                    preview = self._truncate_preview(last_msg.get("content", ""))

                artifact = UnifiedArtifact(
                    id=f"ws_{session_id}",
                    type=ArtifactType.WORKSPACE_SESSION.value,
                    title=session.get("name", f"Session {session_id[:8]}"),
                    preview=preview or f"{len(messages)} messages",
                    color=ARTIFACT_COLORS[ArtifactType.WORKSPACE_SESSION],
                    created_at=session.get("created_at", datetime.now().isoformat()),
                    participants=participants,
                    source="workspace_sessions",
                    status=session.get("status", "active"),
                    tags=["session", "workspace"],
                    metadata={
                        "message_count": len(messages),
                        "has_canvas": bool(session.get("canvas")),
                        "file_path": str(session_file)
                    }
                )
                artifacts.append(artifact)

                # Also extract messages from sessions
                for i, msg in enumerate(messages[:50]):  # Limit to 50 messages per session
                    if isinstance(msg, dict):
                        msg_artifact = self._message_to_artifact(msg, f"ws_{session_id}", i)
                        if msg_artifact:
                            artifacts.append(msg_artifact)

            except Exception as e:
                print(f"[UnifiedAdapter] Error loading session {session_file}: {e}")

        return artifacts

    def _message_to_artifact(self, msg: Dict, parent_id: str, index: int) -> Optional[UnifiedArtifact]:
        """Convert a message dict to UnifiedArtifact."""
        content = msg.get("content", "")
        if not content:
            return None

        sender = msg.get("from", msg.get("sender", msg.get("author", "unknown")))
        timestamp = msg.get("timestamp", msg.get("created_at", datetime.now().isoformat()))

        return UnifiedArtifact(
            id=f"msg_{parent_id}_{index}",
            type=ArtifactType.MESSAGE.value,
            title=f"Message from {sender}",
            preview=self._truncate_preview(content),
            color=ARTIFACT_COLORS[ArtifactType.MESSAGE],
            created_at=timestamp,
            parent_id=parent_id,
            participants=[sender] if sender else [],
            source="workspace_message",
            tags=["message"],
            metadata={
                "sender": sender,
                "full_content": content[:1000]  # Store more for detail view
            }
        )

    # ========== CANVAS DOCUMENTS ==========

    def _load_canvas_documents(self) -> List[UnifiedArtifact]:
        """Load canvas documents from workspace sessions."""
        artifacts = []

        if not self.workspace_sessions_dir.exists():
            return artifacts

        for session_file in self.workspace_sessions_dir.glob("*.json"):
            try:
                with open(session_file, 'r') as f:
                    session = json.load(f)

                canvas = session.get("canvas")
                if not canvas:
                    continue

                session_id = session.get("id", session_file.stem)
                sections = canvas.get("sections", {})

                artifact = UnifiedArtifact(
                    id=f"canvas_{session_id}",
                    type=ArtifactType.CANVAS.value,
                    title=canvas.get("title", f"Canvas for {session_id[:8]}"),
                    preview=f"{len(sections)} sections",
                    color=ARTIFACT_COLORS[ArtifactType.CANVAS],
                    created_at=canvas.get("created_at", session.get("created_at", datetime.now().isoformat())),
                    parent_id=f"ws_{session_id}",
                    participants=list(set(canvas.get("contributors", []))),
                    source="canvas",
                    tags=["canvas", "document"],
                    metadata={
                        "section_count": len(sections),
                        "version": canvas.get("version", 1),
                        "sections": list(sections.keys())[:10]
                    }
                )
                artifacts.append(artifact)

            except Exception as e:
                print(f"[UnifiedAdapter] Error loading canvas from {session_file}: {e}")

        return artifacts

    # ========== TASKS ==========

    def _load_tasks(self) -> List[UnifiedArtifact]:
        """Load delegated tasks from task delegation manager storage."""
        artifacts = []

        tasks_file = self.fsl_collab_dir / "tasks" / "tasks.json"
        if not tasks_file.exists():
            # Try alternate location
            tasks_file = self.home / ".claude" / "tasks.json"

        if not tasks_file.exists():
            return artifacts

        try:
            with open(tasks_file, 'r') as f:
                tasks = json.load(f)

            if isinstance(tasks, dict):
                tasks = tasks.get("tasks", [])

            for task in tasks:
                task_id = task.get("id", self._generate_id("task", str(task)))

                artifact = UnifiedArtifact(
                    id=f"task_{task_id}",
                    type=ArtifactType.TASK.value,
                    title=task.get("title", task.get("description", "Untitled Task")[:50]),
                    preview=self._truncate_preview(task.get("description", "")),
                    color=ARTIFACT_COLORS[ArtifactType.TASK],
                    created_at=task.get("created_at", datetime.now().isoformat()),
                    participants=[task.get("to_agent", ""), task.get("from_agent", "")],
                    source="task_delegation",
                    status=task.get("status", "pending"),
                    tags=["task", task.get("priority", "medium")],
                    metadata={
                        "to_agent": task.get("to_agent"),
                        "from_agent": task.get("from_agent"),
                        "priority": task.get("priority", "medium"),
                        "progress": task.get("progress", 0)
                    }
                )
                artifacts.append(artifact)

        except Exception as e:
            print(f"[UnifiedAdapter] Error loading tasks: {e}")

        return artifacts

    # ========== CALENDAR EVENTS ==========

    def _load_calendar_events(self) -> List[UnifiedArtifact]:
        """Load calendar events from FSL collab calendars."""
        artifacts = []

        if not self.calendars_dir.exists():
            return artifacts

        for cal_file in self.calendars_dir.glob("*.json"):
            try:
                with open(cal_file, 'r') as f:
                    calendar = json.load(f)

                agent = cal_file.stem  # filename is agent name
                events = calendar.get("events", [])

                for event in events:
                    event_id = event.get("id", self._generate_id("cal", str(event)))

                    artifact = UnifiedArtifact(
                        id=f"cal_{event_id}",
                        type=ArtifactType.CALENDAR.value,
                        title=event.get("title", "Untitled Event"),
                        preview=event.get("description", "")[:100],
                        color=ARTIFACT_COLORS[ArtifactType.CALENDAR],
                        created_at=event.get("start", datetime.now().isoformat()),
                        participants=[agent] + event.get("attendees", []),
                        source="calendar",
                        tags=["calendar", "event", agent],
                        metadata={
                            "start": event.get("start"),
                            "end": event.get("end"),
                            "location": event.get("location"),
                            "agent": agent
                        }
                    )
                    artifacts.append(artifact)

            except Exception as e:
                print(f"[UnifiedAdapter] Error loading calendar {cal_file}: {e}")

        return artifacts

    # ========== TODOS ==========

    def _load_todos(self) -> List[UnifiedArtifact]:
        """Load todos from FSL collab todos directory."""
        artifacts = []

        # Check multiple possible todo locations
        todo_locations = [
            self.todos_dir,
            self.fsl_collab_dir / "todos",
            self.home / ".claude" / "todos"
        ]

        for todos_dir in todo_locations:
            if not todos_dir.exists():
                continue

            for todo_file in todos_dir.glob("*.json"):
                try:
                    with open(todo_file, 'r') as f:
                        data = json.load(f)

                    agent = todo_file.stem
                    todos = data.get("todos", data) if isinstance(data, dict) else data

                    if not isinstance(todos, list):
                        todos = [todos]

                    for i, todo in enumerate(todos):
                        if isinstance(todo, str):
                            todo = {"content": todo}

                        todo_id = todo.get("id", f"{agent}_{i}")

                        artifact = UnifiedArtifact(
                            id=f"todo_{todo_id}",
                            type=ArtifactType.TODO.value,
                            title=todo.get("content", todo.get("title", "Untitled"))[:60],
                            preview=self._truncate_preview(todo.get("content", "")),
                            color=ARTIFACT_COLORS[ArtifactType.TODO],
                            created_at=todo.get("created_at", datetime.now().isoformat()),
                            participants=[agent],
                            source="todos",
                            status=todo.get("status", "pending"),
                            tags=["todo", agent, todo.get("priority", "medium")],
                            metadata={
                                "agent": agent,
                                "priority": todo.get("priority", "medium")
                            }
                        )
                        artifacts.append(artifact)

                except Exception as e:
                    print(f"[UnifiedAdapter] Error loading todos from {todo_file}: {e}")

        return artifacts

    # ========== CONVERSATIONS (Claude History) ==========

    def _load_conversations(self, limit: int = 100) -> List[UnifiedArtifact]:
        """Load conversation history from Claude history.jsonl."""
        artifacts = []

        if not self.history_file.exists():
            return artifacts

        try:
            with open(self.history_file, 'r') as f:
                lines = f.readlines()[-limit:]  # Read last N lines

            for line in lines:
                try:
                    conv = json.loads(line.strip())

                    session_id = conv.get("sessionId", self._generate_id("conv", line))
                    display = conv.get("display", "")
                    project = conv.get("project", "unknown")

                    artifact = UnifiedArtifact(
                        id=f"conv_{session_id[:12]}",
                        type=ArtifactType.CONVERSATION.value,
                        title=display[:60] if display else f"Conversation {session_id[:8]}",
                        preview=self._truncate_preview(display),
                        color=ARTIFACT_COLORS[ArtifactType.CONVERSATION],
                        created_at=conv.get("timestamp", datetime.now().isoformat()),
                        participants=["user", "claude"],
                        source="claude_history",
                        tags=["conversation", project],
                        metadata={
                            "session_id": session_id,
                            "project": project,
                            "path": conv.get("path", "")
                        }
                    )
                    artifacts.append(artifact)

                except json.JSONDecodeError:
                    continue

        except Exception as e:
            print(f"[UnifiedAdapter] Error loading conversations: {e}")

        return artifacts

    # ========== FILES ==========

    def _load_files(self) -> List[UnifiedArtifact]:
        """Load uploaded files from uploads index."""
        artifacts = []

        if not self.uploads_index.exists():
            return artifacts

        try:
            with open(self.uploads_index, 'r') as f:
                index = json.load(f)

            files = index.get("files", index) if isinstance(index, dict) else index

            for file_entry in files:
                if isinstance(file_entry, str):
                    file_entry = {"filename": file_entry}

                file_id = file_entry.get("id", self._generate_id("file", file_entry.get("filename", "")))

                artifact = UnifiedArtifact(
                    id=f"file_{file_id}",
                    type=ArtifactType.FILE.value,
                    title=file_entry.get("filename", "Unknown File"),
                    preview=self._truncate_preview(file_entry.get("extracted_text", "")),
                    color=ARTIFACT_COLORS[ArtifactType.FILE],
                    created_at=file_entry.get("uploaded_at", datetime.now().isoformat()),
                    participants=["user"],
                    source="uploads",
                    tags=["file", file_entry.get("type", "unknown")],
                    metadata={
                        "filename": file_entry.get("filename"),
                        "size": file_entry.get("size"),
                        "type": file_entry.get("type"),
                        "path": file_entry.get("path")
                    }
                )
                artifacts.append(artifact)

        except Exception as e:
            print(f"[UnifiedAdapter] Error loading files: {e}")

        return artifacts

    # ========== INBOX MESSAGES ==========

    def _load_inbox_messages(self) -> List[UnifiedArtifact]:
        """Load inbox messages from FSL collab inbox files."""
        artifacts = []

        if not self.fsl_collab_dir.exists():
            return artifacts

        for inbox_file in self.fsl_collab_dir.glob("inbox_*.fsl"):
            try:
                with open(inbox_file, 'r') as f:
                    content = f.read()

                # Parse FSL inbox format (simple line-based)
                agent = inbox_file.stem.replace("inbox_", "")
                lines = content.strip().split("\n")

                for i, line in enumerate(lines):
                    if not line.strip():
                        continue

                    msg_id = self._generate_id("inbox", f"{agent}_{i}_{line[:50]}")

                    # Try to extract from/to from FSL format
                    from_agent = "unknown"
                    if "from:" in line.lower():
                        parts = line.lower().split("from:")
                        if len(parts) > 1:
                            from_agent = parts[1].split()[0].strip("§")

                    artifact = UnifiedArtifact(
                        id=f"inbox_{msg_id}",
                        type=ArtifactType.INBOX.value,
                        title=f"Inbox: {agent}",
                        preview=self._truncate_preview(line),
                        color=ARTIFACT_COLORS[ArtifactType.INBOX],
                        created_at=datetime.now().isoformat(),  # FSL doesn't store timestamps
                        participants=[agent, from_agent],
                        source="inbox",
                        tags=["inbox", agent],
                        metadata={
                            "to_agent": agent,
                            "from_agent": from_agent,
                            "raw_content": line[:500]
                        }
                    )
                    artifacts.append(artifact)

            except Exception as e:
                print(f"[UnifiedAdapter] Error loading inbox {inbox_file}: {e}")

        return artifacts

    # ========== HANDOFFS ==========

    def _load_handoffs(self) -> List[UnifiedArtifact]:
        """Load handoffs from golden library index."""
        artifacts = []

        if not self.golden_index.exists():
            return artifacts

        try:
            with open(self.golden_index, 'r') as f:
                index = json.load(f)

            handoffs = index.get("handoffs", index) if isinstance(index, dict) else index

            if isinstance(handoffs, dict):
                handoffs = list(handoffs.values())

            for handoff in handoffs:
                if isinstance(handoff, str):
                    handoff = {"id": handoff}

                handoff_id = handoff.get("id", handoff.get("hash", self._generate_id("ho", str(handoff))))

                artifact = UnifiedArtifact(
                    id=f"handoff_{handoff_id[:12]}",
                    type=ArtifactType.HANDOFF.value,
                    title=handoff.get("title", handoff.get("project", f"Handoff {handoff_id[:8]}")),
                    preview=self._truncate_preview(handoff.get("summary", handoff.get("description", ""))),
                    color=ARTIFACT_COLORS[ArtifactType.HANDOFF],
                    created_at=handoff.get("created_at", handoff.get("timestamp", datetime.now().isoformat())),
                    participants=handoff.get("participants", ["user", "claude"]),
                    source="golden_library",
                    tags=["handoff", handoff.get("compression_format", "unknown")],
                    metadata={
                        "compression_format": handoff.get("compression_format"),
                        "reduction": handoff.get("reduction"),
                        "original_size": handoff.get("original_size"),
                        "compressed_size": handoff.get("compressed_size"),
                        "file_path": handoff.get("file_path")
                    }
                )
                artifacts.append(artifact)

        except Exception as e:
            print(f"[UnifiedAdapter] Error loading handoffs: {e}")

        return artifacts

    # ========== UNIFIED API ==========

    def get_all_artifacts(
        self,
        types: Optional[List[str]] = None,
        participants: Optional[List[str]] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 500
    ) -> List[Dict[str, Any]]:
        """
        Get all artifacts with optional filtering.

        Args:
            types: Filter by artifact types (e.g., ["workspace_session", "message"])
            participants: Filter by participants (e.g., ["prax", "koda"])
            date_from: ISO date string for start of range
            date_to: ISO date string for end of range
            limit: Maximum number of results

        Returns:
            List of artifact dictionaries
        """
        artifacts = []

        # Load all sources
        artifacts.extend(self._load_workspace_sessions())
        artifacts.extend(self._load_canvas_documents())
        artifacts.extend(self._load_tasks())
        artifacts.extend(self._load_calendar_events())
        artifacts.extend(self._load_todos())
        artifacts.extend(self._load_conversations(limit=100))
        artifacts.extend(self._load_files())
        artifacts.extend(self._load_inbox_messages())
        artifacts.extend(self._load_handoffs())

        # Apply filters
        if types:
            artifacts = [a for a in artifacts if a.type in types]

        if participants:
            participants_lower = [p.lower() for p in participants]
            artifacts = [a for a in artifacts
                        if any(p.lower() in participants_lower for p in a.participants)]

        if date_from:
            artifacts = [a for a in artifacts if a.created_at >= date_from]

        if date_to:
            artifacts = [a for a in artifacts if a.created_at <= date_to]

        # Sort by created_at descending (handle empty/None/numeric values)
        def safe_sort_key(a):
            ts = a.created_at
            if not ts:
                return "1970-01-01"
            if isinstance(ts, (int, float)):
                # Convert Unix timestamp to ISO format
                try:
                    from datetime import datetime
                    return datetime.fromtimestamp(ts).isoformat()
                except:
                    return "1970-01-01"
            return str(ts)

        artifacts.sort(key=safe_sort_key, reverse=True)

        # Apply limit
        artifacts = artifacts[:limit]

        return [a.to_dict() for a in artifacts]

    def get_relationships(self, artifact_id: str) -> Dict[str, Any]:
        """
        Get relationships for a specific artifact.

        Returns:
            Dictionary with parent, children, and related artifacts
        """
        all_artifacts = self.get_all_artifacts(limit=1000)

        # Find the artifact
        artifact = None
        for a in all_artifacts:
            if a["id"] == artifact_id:
                artifact = a
                break

        if not artifact:
            return {"error": "Artifact not found", "artifact_id": artifact_id}

        # Find parent
        parent = None
        if artifact.get("parent_id"):
            for a in all_artifacts:
                if a["id"] == artifact["parent_id"]:
                    parent = a
                    break

        # Find children (artifacts that have this as parent)
        children = [a for a in all_artifacts if a.get("parent_id") == artifact_id]

        # Find related (same participants, same tags, temporal proximity)
        related = []
        artifact_time = artifact.get("created_at", "")
        artifact_participants = set(artifact.get("participants", []))
        artifact_tags = set(artifact.get("tags", []))

        for a in all_artifacts:
            if a["id"] == artifact_id:
                continue

            # Check participant overlap
            a_participants = set(a.get("participants", []))
            if artifact_participants & a_participants:
                related.append({"artifact": a, "reason": "shared_participants"})
                continue

            # Check tag overlap
            a_tags = set(a.get("tags", []))
            if artifact_tags & a_tags:
                related.append({"artifact": a, "reason": "shared_tags"})

        return {
            "artifact": artifact,
            "parent": parent,
            "children": children[:20],
            "related": related[:20]
        }

    def search_artifacts(self, query: str, types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Search across all artifacts.

        Args:
            query: Search query string
            types: Optional filter by types

        Returns:
            List of matching artifact dictionaries
        """
        all_artifacts = self.get_all_artifacts(types=types, limit=1000)
        query_lower = query.lower()

        results = []
        for artifact in all_artifacts:
            # Search in title, preview, and tags
            if (query_lower in artifact.get("title", "").lower() or
                query_lower in artifact.get("preview", "").lower() or
                any(query_lower in tag.lower() for tag in artifact.get("tags", []))):
                results.append(artifact)

        return results[:100]

    def get_stats(self) -> Dict[str, Any]:
        """
        Get aggregate statistics across all artifacts.

        Returns:
            Dictionary with counts by type, participant, etc.
        """
        all_artifacts = self.get_all_artifacts(limit=10000)

        # Count by type
        by_type = {}
        for a in all_artifacts:
            t = a.get("type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1

        # Count by participant
        by_participant = {}
        for a in all_artifacts:
            for p in a.get("participants", []):
                if p:
                    by_participant[p] = by_participant.get(p, 0) + 1

        # Count by status
        by_status = {}
        for a in all_artifacts:
            s = a.get("status") or "none"
            by_status[s] = by_status.get(s, 0) + 1

        # Date range
        dates = [a.get("created_at", "") for a in all_artifacts if a.get("created_at")]
        date_from = min(dates) if dates else None
        date_to = max(dates) if dates else None

        return {
            "total": len(all_artifacts),
            "by_type": by_type,
            "by_participant": by_participant,
            "by_status": by_status,
            "date_range": {
                "from": date_from,
                "to": date_to
            }
        }

    def get_artifact_detail(self, artifact_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information for a single artifact.

        Args:
            artifact_id: The artifact ID

        Returns:
            Full artifact dictionary or None if not found
        """
        all_artifacts = self.get_all_artifacts(limit=10000)

        for artifact in all_artifacts:
            if artifact.get("id") == artifact_id:
                # Add relationships
                relationships = self.get_relationships(artifact_id)
                artifact["relationships"] = {
                    "parent": relationships.get("parent"),
                    "children_count": len(relationships.get("children", [])),
                    "related_count": len(relationships.get("related", []))
                }
                return artifact

        return None


# Singleton instance
_adapter_instance: Optional[UnifiedArtifactAdapter] = None

def get_unified_adapter() -> UnifiedArtifactAdapter:
    """Get or create the singleton adapter instance."""
    global _adapter_instance
    if _adapter_instance is None:
        _adapter_instance = UnifiedArtifactAdapter()
    return _adapter_instance


# CLI for testing
if __name__ == "__main__":
    import sys

    adapter = get_unified_adapter()

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "stats":
            stats = adapter.get_stats()
            print(json.dumps(stats, indent=2))

        elif cmd == "list":
            types = sys.argv[2].split(",") if len(sys.argv) > 2 else None
            artifacts = adapter.get_all_artifacts(types=types, limit=50)
            for a in artifacts:
                print(f"[{a['type']}] {a['title'][:50]} ({a['id']})")

        elif cmd == "search":
            query = sys.argv[2] if len(sys.argv) > 2 else ""
            results = adapter.search_artifacts(query)
            print(f"Found {len(results)} results for '{query}':")
            for a in results[:20]:
                print(f"  [{a['type']}] {a['title'][:40]}")

        else:
            print(f"Unknown command: {cmd}")
            print("Usage: python unified_artifact_adapter.py [stats|list|search] [args]")
    else:
        # Default: show stats
        stats = adapter.get_stats()
        print("=== Unified Artifact Stats ===")
        print(f"Total artifacts: {stats['total']}")
        print("\nBy type:")
        for t, count in sorted(stats['by_type'].items()):
            print(f"  {t}: {count}")
        print("\nBy participant:")
        for p, count in sorted(stats['by_participant'].items(), key=lambda x: -x[1])[:10]:
            print(f"  {p}: {count}")
