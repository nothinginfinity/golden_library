#!/usr/bin/env python3
"""
Phase 4C.5: Live Demo Mode

Recording system for workspace sessions with:
- Real-time event capture
- Key moment highlights/bookmarks
- Custom branding
- Export to shareable formats (HTML, JSON)

Run with: python3 demo_recorder.py
"""

import os
import json
import asyncio
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
import uuid
import html
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EventType(Enum):
    """Types of recordable events."""
    MESSAGE = "message"
    AGENT_RESPONSE = "agent_response"
    CANVAS_UPDATE = "canvas_update"
    TOOL_USE = "tool_use"
    DELEGATION = "delegation"
    USER_JOIN = "user_join"
    USER_LEAVE = "user_leave"
    HIGHLIGHT = "highlight"
    SYSTEM = "system"


@dataclass
class RecordedEvent:
    """A single recorded event in the demo."""
    id: str
    timestamp: str
    event_type: EventType
    actor: str  # user_id or agent_id
    content: Dict[str, Any]
    is_highlight: bool = False
    highlight_label: Optional[str] = None
    duration_ms: Optional[int] = None  # For events with duration

    def to_dict(self) -> Dict:
        data = asdict(self)
        data['event_type'] = self.event_type.value
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> 'RecordedEvent':
        data['event_type'] = EventType(data['event_type'])
        return cls(**data)


@dataclass
class BrandingConfig:
    """Custom branding for demo exports."""
    company_name: str = "Demo"
    logo_url: Optional[str] = None
    primary_color: str = "#6366f1"  # Indigo
    secondary_color: str = "#818cf8"
    background_color: str = "#1a1a2e"
    text_color: str = "#e2e8f0"
    font_family: str = "'Inter', -apple-system, sans-serif"
    header_text: Optional[str] = None
    footer_text: Optional[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class DemoRecording:
    """Complete demo recording with metadata."""
    id: str
    session_id: str
    title: str
    description: str
    created_at: str
    started_at: str
    ended_at: Optional[str]
    duration_ms: int
    events: List[RecordedEvent]
    highlights: List[str]  # Event IDs of highlighted moments
    branding: BrandingConfig
    participants: List[Dict[str, str]]
    agents_used: List[str]
    tags: List[str]
    is_recording: bool = False

    def to_dict(self) -> Dict:
        data = {
            'id': self.id,
            'session_id': self.session_id,
            'title': self.title,
            'description': self.description,
            'created_at': self.created_at,
            'started_at': self.started_at,
            'ended_at': self.ended_at,
            'duration_ms': self.duration_ms,
            'events': [e.to_dict() for e in self.events],
            'highlights': self.highlights,
            'branding': self.branding.to_dict(),
            'participants': self.participants,
            'agents_used': self.agents_used,
            'tags': self.tags,
            'is_recording': self.is_recording
        }
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> 'DemoRecording':
        data['events'] = [RecordedEvent.from_dict(e) for e in data['events']]
        data['branding'] = BrandingConfig(**data['branding'])
        return cls(**data)


class DemoRecorder:
    """
    Records workspace sessions for demo/replay purposes.

    Features:
    - Start/stop recording
    - Add highlights at key moments
    - Custom branding
    - Export to HTML/JSON
    """

    def __init__(self, storage_dir: str = "~/.claude/demo_recordings"):
        """
        Initialize the demo recorder.

        Args:
            storage_dir: Directory to store recordings
        """
        self.storage_dir = os.path.expanduser(storage_dir)
        os.makedirs(self.storage_dir, exist_ok=True)

        self.active_recordings: Dict[str, DemoRecording] = {}
        self._event_callbacks: List[Callable] = []

    # ===== Recording Control =====

    def start_recording(
        self,
        session_id: str,
        title: str = "Demo Recording",
        description: str = "",
        branding: Optional[BrandingConfig] = None,
        tags: Optional[List[str]] = None
    ) -> DemoRecording:
        """
        Start recording a session.

        Args:
            session_id: Session to record
            title: Recording title
            description: Recording description
            branding: Custom branding config
            tags: Tags for categorization

        Returns:
            New DemoRecording instance
        """
        now = datetime.now(timezone.utc).isoformat()

        recording = DemoRecording(
            id=str(uuid.uuid4())[:8],
            session_id=session_id,
            title=title,
            description=description,
            created_at=now,
            started_at=now,
            ended_at=None,
            duration_ms=0,
            events=[],
            highlights=[],
            branding=branding or BrandingConfig(),
            participants=[],
            agents_used=[],
            tags=tags or [],
            is_recording=True
        )

        self.active_recordings[session_id] = recording
        logger.info(f"[DemoRecorder] Started recording {recording.id} for session {session_id}")

        # Record start event
        self.record_event(
            session_id=session_id,
            event_type=EventType.SYSTEM,
            actor="system",
            content={"action": "recording_started", "title": title}
        )

        return recording

    def stop_recording(self, session_id: str, save: bool = True) -> Optional[DemoRecording]:
        """
        Stop recording a session.

        Args:
            session_id: Session to stop recording
            save: Whether to save the recording

        Returns:
            Completed DemoRecording or None
        """
        recording = self.active_recordings.get(session_id)
        if not recording:
            logger.warning(f"[DemoRecorder] No active recording for session {session_id}")
            return None

        now = datetime.now(timezone.utc)
        started = datetime.fromisoformat(recording.started_at.replace('Z', '+00:00'))
        duration = int((now - started).total_seconds() * 1000)

        recording.ended_at = now.isoformat()
        recording.duration_ms = duration
        recording.is_recording = False

        # Record stop event
        self.record_event(
            session_id=session_id,
            event_type=EventType.SYSTEM,
            actor="system",
            content={"action": "recording_stopped", "duration_ms": duration}
        )

        if save:
            self._save_recording(recording)

        del self.active_recordings[session_id]
        logger.info(f"[DemoRecorder] Stopped recording {recording.id} ({duration}ms)")

        return recording

    def is_recording(self, session_id: str) -> bool:
        """Check if a session is being recorded."""
        return session_id in self.active_recordings

    def get_recording(self, session_id: str) -> Optional[DemoRecording]:
        """Get active recording for a session."""
        return self.active_recordings.get(session_id)

    # ===== Event Recording =====

    def record_event(
        self,
        session_id: str,
        event_type: EventType,
        actor: str,
        content: Dict[str, Any],
        is_highlight: bool = False,
        highlight_label: Optional[str] = None
    ) -> Optional[RecordedEvent]:
        """
        Record an event in the demo.

        Args:
            session_id: Session ID
            event_type: Type of event
            actor: Who triggered the event
            content: Event content
            is_highlight: Mark as key moment
            highlight_label: Label for the highlight

        Returns:
            Recorded event or None if not recording
        """
        recording = self.active_recordings.get(session_id)
        if not recording:
            return None

        event = RecordedEvent(
            id=str(uuid.uuid4())[:8],
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=event_type,
            actor=actor,
            content=content,
            is_highlight=is_highlight,
            highlight_label=highlight_label
        )

        recording.events.append(event)

        if is_highlight:
            recording.highlights.append(event.id)

        # Track participants and agents
        if event_type == EventType.USER_JOIN:
            participant = {"user_id": actor, "name": content.get("name", actor)}
            if participant not in recording.participants:
                recording.participants.append(participant)

        if event_type in [EventType.AGENT_RESPONSE, EventType.DELEGATION]:
            agent = content.get("agent_id") or actor
            if agent not in recording.agents_used:
                recording.agents_used.append(agent)

        # Notify callbacks
        for callback in self._event_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"[DemoRecorder] Callback error: {e}")

        return event

    def add_highlight(
        self,
        session_id: str,
        label: str,
        description: Optional[str] = None
    ) -> Optional[RecordedEvent]:
        """
        Add a highlight marker at the current moment.

        Args:
            session_id: Session ID
            label: Short label for the highlight
            description: Optional longer description

        Returns:
            Highlight event or None
        """
        return self.record_event(
            session_id=session_id,
            event_type=EventType.HIGHLIGHT,
            actor="system",
            content={"label": label, "description": description},
            is_highlight=True,
            highlight_label=label
        )

    def on_event(self, callback: Callable[[RecordedEvent], None]):
        """Register a callback for new events."""
        self._event_callbacks.append(callback)

    # ===== Branding =====

    def update_branding(
        self,
        session_id: str,
        **branding_updates
    ) -> bool:
        """
        Update branding for a recording.

        Args:
            session_id: Session ID
            **branding_updates: Branding fields to update

        Returns:
            True if updated
        """
        recording = self.active_recordings.get(session_id)
        if not recording:
            return False

        for key, value in branding_updates.items():
            if hasattr(recording.branding, key):
                setattr(recording.branding, key, value)

        return True

    # ===== Storage =====

    def _save_recording(self, recording: DemoRecording):
        """Save recording to disk."""
        filepath = os.path.join(self.storage_dir, f"{recording.id}.json")
        with open(filepath, 'w') as f:
            json.dump(recording.to_dict(), f, indent=2)
        logger.info(f"[DemoRecorder] Saved recording to {filepath}")

    def load_recording(self, recording_id: str) -> Optional[DemoRecording]:
        """Load a recording from disk."""
        filepath = os.path.join(self.storage_dir, f"{recording_id}.json")
        if not os.path.exists(filepath):
            return None

        with open(filepath, 'r') as f:
            data = json.load(f)
            return DemoRecording.from_dict(data)

    def list_recordings(self) -> List[Dict[str, Any]]:
        """List all saved recordings."""
        recordings = []
        for filename in os.listdir(self.storage_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(self.storage_dir, filename)
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                        recordings.append({
                            'id': data['id'],
                            'title': data['title'],
                            'created_at': data['created_at'],
                            'duration_ms': data['duration_ms'],
                            'event_count': len(data['events']),
                            'highlight_count': len(data['highlights'])
                        })
                except Exception as e:
                    logger.error(f"[DemoRecorder] Error loading {filename}: {e}")

        return sorted(recordings, key=lambda x: x['created_at'], reverse=True)

    def delete_recording(self, recording_id: str) -> bool:
        """Delete a recording."""
        filepath = os.path.join(self.storage_dir, f"{recording_id}.json")
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False

    # ===== Export =====

    def export_json(self, recording_id: str) -> Optional[str]:
        """Export recording as JSON string."""
        recording = self.load_recording(recording_id)
        if not recording:
            return None
        return json.dumps(recording.to_dict(), indent=2)

    def export_html(self, recording_id: str) -> Optional[str]:
        """
        Export recording as standalone HTML file.

        Creates a self-contained HTML file with embedded CSS/JS
        that can be shared and viewed in any browser.
        """
        recording = self.load_recording(recording_id)
        if not recording:
            return None

        b = recording.branding
        events_json = json.dumps([e.to_dict() for e in recording.events])

        # Format duration
        duration_sec = recording.duration_ms // 1000
        duration_str = f"{duration_sec // 60}:{duration_sec % 60:02d}"

        html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(recording.title)} - {html.escape(b.company_name)}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: {b.font_family};
            background: {b.background_color};
            color: {b.text_color};
            line-height: 1.6;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
            padding: 24px;
        }}
        header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 16px 24px;
            background: linear-gradient(135deg, {b.primary_color}, {b.secondary_color});
            border-radius: 12px;
            margin-bottom: 24px;
        }}
        .logo {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .logo img {{ height: 40px; }}
        .logo h1 {{ font-size: 1.5rem; color: white; }}
        .meta {{
            display: flex;
            gap: 24px;
            color: rgba(255,255,255,0.9);
            font-size: 0.875rem;
        }}
        .title-section {{
            margin-bottom: 24px;
        }}
        .title-section h2 {{
            font-size: 1.75rem;
            margin-bottom: 8px;
        }}
        .title-section p {{
            color: rgba(255,255,255,0.7);
        }}
        .stats {{
            display: flex;
            gap: 16px;
            margin-bottom: 24px;
        }}
        .stat {{
            background: rgba(255,255,255,0.1);
            padding: 12px 20px;
            border-radius: 8px;
        }}
        .stat-value {{ font-size: 1.5rem; font-weight: 600; color: {b.primary_color}; }}
        .stat-label {{ font-size: 0.75rem; color: rgba(255,255,255,0.6); }}
        .timeline {{
            position: relative;
            padding-left: 24px;
        }}
        .timeline::before {{
            content: '';
            position: absolute;
            left: 8px;
            top: 0;
            bottom: 0;
            width: 2px;
            background: {b.primary_color}33;
        }}
        .event {{
            position: relative;
            margin-bottom: 16px;
            padding: 16px;
            background: rgba(255,255,255,0.05);
            border-radius: 8px;
            border-left: 3px solid transparent;
        }}
        .event.highlight {{
            background: rgba(99, 102, 241, 0.15);
            border-left-color: {b.primary_color};
        }}
        .event::before {{
            content: '';
            position: absolute;
            left: -20px;
            top: 20px;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: {b.primary_color};
        }}
        .event.highlight::before {{
            width: 14px;
            height: 14px;
            left: -22px;
            top: 18px;
            box-shadow: 0 0 8px {b.primary_color};
        }}
        .event-header {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
        }}
        .event-actor {{
            font-weight: 600;
            color: {b.secondary_color};
        }}
        .event-time {{
            font-size: 0.75rem;
            color: rgba(255,255,255,0.5);
        }}
        .event-type {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.7rem;
            text-transform: uppercase;
            background: {b.primary_color}33;
            color: {b.secondary_color};
            margin-right: 8px;
        }}
        .event-content {{
            white-space: pre-wrap;
            font-size: 0.9rem;
        }}
        .highlight-label {{
            display: inline-block;
            padding: 4px 12px;
            background: {b.primary_color};
            color: white;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
            margin-bottom: 8px;
        }}
        .participants {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            margin-bottom: 24px;
        }}
        .participant {{
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 4px 12px;
            background: rgba(255,255,255,0.1);
            border-radius: 20px;
            font-size: 0.8rem;
        }}
        .participant-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }}
        .agent {{ background: {b.primary_color}; }}
        .user {{ background: #10b981; }}
        footer {{
            text-align: center;
            padding: 24px;
            color: rgba(255,255,255,0.5);
            font-size: 0.8rem;
        }}
        .controls {{
            display: flex;
            gap: 12px;
            margin-bottom: 24px;
        }}
        .btn {{
            padding: 10px 20px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.9rem;
            transition: all 0.2s;
        }}
        .btn-primary {{
            background: {b.primary_color};
            color: white;
        }}
        .btn-primary:hover {{ background: {b.secondary_color}; }}
        .btn-secondary {{
            background: rgba(255,255,255,0.1);
            color: white;
        }}
        .btn-secondary:hover {{ background: rgba(255,255,255,0.2); }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo">
                {f'<img src="{html.escape(b.logo_url)}" alt="Logo">' if b.logo_url else ''}
                <h1>{html.escape(b.company_name)}</h1>
            </div>
            <div class="meta">
                <span>📅 {recording.created_at[:10]}</span>
                <span>⏱️ {duration_str}</span>
            </div>
        </header>

        <div class="title-section">
            <h2>{html.escape(recording.title)}</h2>
            <p>{html.escape(recording.description) if recording.description else ''}</p>
        </div>

        <div class="stats">
            <div class="stat">
                <div class="stat-value">{len(recording.events)}</div>
                <div class="stat-label">Events</div>
            </div>
            <div class="stat">
                <div class="stat-value">{len(recording.highlights)}</div>
                <div class="stat-label">Highlights</div>
            </div>
            <div class="stat">
                <div class="stat-value">{len(recording.participants)}</div>
                <div class="stat-label">Participants</div>
            </div>
            <div class="stat">
                <div class="stat-value">{len(recording.agents_used)}</div>
                <div class="stat-label">Agents</div>
            </div>
        </div>

        <div class="participants">
            {' '.join([f'<span class="participant"><span class="participant-dot agent"></span>{a}</span>' for a in recording.agents_used])}
            {' '.join([f'<span class="participant"><span class="participant-dot user"></span>{p.get("name", p.get("user_id", "User"))}</span>' for p in recording.participants])}
        </div>

        <div class="controls">
            <button class="btn btn-primary" onclick="jumpToHighlight(-1)">⏮️ Prev Highlight</button>
            <button class="btn btn-primary" onclick="jumpToHighlight(1)">Next Highlight ⏭️</button>
            <button class="btn btn-secondary" onclick="toggleHighlightsOnly()">Show Highlights Only</button>
        </div>

        <div class="timeline" id="timeline">
            <!-- Events rendered by JS -->
        </div>

        <footer>
            {html.escape(b.footer_text) if b.footer_text else f'Recorded with {html.escape(b.company_name)} Demo Mode'}
        </footer>
    </div>

    <script>
        const events = {events_json};
        const highlights = {json.dumps(recording.highlights)};
        let highlightsOnly = false;
        let currentHighlight = -1;

        function formatTime(isoString) {{
            return new Date(isoString).toLocaleTimeString();
        }}

        function getEventContent(event) {{
            const c = event.content;
            if (event.event_type === 'message' || event.event_type === 'agent_response') {{
                return c.message || c.content || JSON.stringify(c);
            }}
            if (event.event_type === 'highlight') {{
                return c.description || c.label || 'Key moment';
            }}
            if (event.event_type === 'tool_use') {{
                return `Tool: ${{c.tool_name || 'unknown'}}`;
            }}
            if (event.event_type === 'delegation') {{
                return `Delegated to ${{c.to_agent || 'agent'}}: ${{c.task || ''}}`;
            }}
            return JSON.stringify(c);
        }}

        function renderEvents() {{
            const timeline = document.getElementById('timeline');
            timeline.innerHTML = '';

            const toRender = highlightsOnly
                ? events.filter(e => e.is_highlight)
                : events;

            toRender.forEach((event, idx) => {{
                const div = document.createElement('div');
                div.className = 'event' + (event.is_highlight ? ' highlight' : '');
                div.id = 'event-' + event.id;

                div.innerHTML = `
                    ${{event.highlight_label ? `<div class="highlight-label">⭐ ${{event.highlight_label}}</div>` : ''}}
                    <div class="event-header">
                        <span>
                            <span class="event-type">${{event.event_type}}</span>
                            <span class="event-actor">${{event.actor}}</span>
                        </span>
                        <span class="event-time">${{formatTime(event.timestamp)}}</span>
                    </div>
                    <div class="event-content">${{getEventContent(event)}}</div>
                `;

                timeline.appendChild(div);
            }});
        }}

        function jumpToHighlight(direction) {{
            if (highlights.length === 0) return;

            currentHighlight += direction;
            if (currentHighlight >= highlights.length) currentHighlight = 0;
            if (currentHighlight < 0) currentHighlight = highlights.length - 1;

            const eventId = highlights[currentHighlight];
            const el = document.getElementById('event-' + eventId);
            if (el) {{
                el.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                el.style.animation = 'none';
                el.offsetHeight; // Trigger reflow
                el.style.animation = 'pulse 0.5s';
            }}
        }}

        function toggleHighlightsOnly() {{
            highlightsOnly = !highlightsOnly;
            renderEvents();
        }}

        // Initial render
        renderEvents();
    </script>
</body>
</html>'''

        return html_content

    def save_html_export(self, recording_id: str, output_path: Optional[str] = None) -> Optional[str]:
        """Save HTML export to file."""
        html_content = self.export_html(recording_id)
        if not html_content:
            return None

        if not output_path:
            output_path = os.path.join(self.storage_dir, f"{recording_id}.html")

        with open(output_path, 'w') as f:
            f.write(html_content)

        logger.info(f"[DemoRecorder] Exported HTML to {output_path}")
        return output_path


# ===== Global Instance =====

_demo_recorder: Optional[DemoRecorder] = None


def get_demo_recorder() -> DemoRecorder:
    """Get or create global DemoRecorder instance."""
    global _demo_recorder
    if _demo_recorder is None:
        _demo_recorder = DemoRecorder()
    return _demo_recorder


# ===== CLI Testing =====

def test_demo_recorder():
    """Test demo recorder functionality."""
    import tempfile

    print("=" * 60)
    print("  DemoRecorder Test")
    print("=" * 60)

    # Create recorder with temp storage
    with tempfile.TemporaryDirectory() as tmpdir:
        recorder = DemoRecorder(storage_dir=tmpdir)

        # Test 1: Start recording
        print("\n[Test 1] Starting recording...")
        session_id = "test_session"
        recording = recorder.start_recording(
            session_id=session_id,
            title="Feature Demo: User Authentication",
            description="Demonstrating the new JWT-based auth flow",
            branding=BrandingConfig(
                company_name="Acme Corp",
                primary_color="#6366f1"
            ),
            tags=["auth", "demo", "jwt"]
        )
        assert recording is not None
        assert recording.is_recording
        print(f"  ✓ Recording started: {recording.id}")

        # Test 2: Record events
        print("\n[Test 2] Recording events...")
        recorder.record_event(
            session_id=session_id,
            event_type=EventType.USER_JOIN,
            actor="user1",
            content={"name": "Alice", "role": "developer"}
        )
        recorder.record_event(
            session_id=session_id,
            event_type=EventType.MESSAGE,
            actor="user1",
            content={"message": "Let's implement JWT authentication"}
        )
        recorder.record_event(
            session_id=session_id,
            event_type=EventType.AGENT_RESPONSE,
            actor="cairn",
            content={"agent_id": "cairn", "content": "I'll design the auth architecture"}
        )
        print(f"  ✓ Recorded {len(recording.events)} events")

        # Test 3: Add highlight
        print("\n[Test 3] Adding highlight...")
        highlight = recorder.add_highlight(
            session_id=session_id,
            label="Architecture Decision",
            description="Decided to use JWT with refresh tokens"
        )
        assert highlight is not None
        assert highlight.is_highlight
        print(f"  ✓ Added highlight: {highlight.highlight_label}")

        # Test 4: More events
        recorder.record_event(
            session_id=session_id,
            event_type=EventType.DELEGATION,
            actor="cairn",
            content={"to_agent": "koda", "task": "Implement JWT endpoint"}
        )
        recorder.record_event(
            session_id=session_id,
            event_type=EventType.TOOL_USE,
            actor="koda",
            content={"tool_name": "code_analysis", "status": "success"}
        )

        # Test 5: Stop recording
        print("\n[Test 4] Stopping recording...")
        completed = recorder.stop_recording(session_id)
        assert completed is not None
        assert not completed.is_recording
        assert completed.duration_ms >= 0
        print(f"  ✓ Recording stopped: {completed.duration_ms}ms")
        print(f"  ✓ Total events: {len(completed.events)}")
        print(f"  ✓ Highlights: {len(completed.highlights)}")
        print(f"  ✓ Agents used: {completed.agents_used}")

        # Test 6: List recordings
        print("\n[Test 5] Listing recordings...")
        recordings = recorder.list_recordings()
        assert len(recordings) == 1
        print(f"  ✓ Found {len(recordings)} recording(s)")

        # Test 7: Load recording
        print("\n[Test 6] Loading recording...")
        loaded = recorder.load_recording(completed.id)
        assert loaded is not None
        assert loaded.title == "Feature Demo: User Authentication"
        print(f"  ✓ Loaded recording: {loaded.title}")

        # Test 8: Export JSON
        print("\n[Test 7] Exporting JSON...")
        json_export = recorder.export_json(completed.id)
        assert json_export is not None
        assert "Feature Demo" in json_export
        print(f"  ✓ JSON export: {len(json_export)} chars")

        # Test 9: Export HTML
        print("\n[Test 8] Exporting HTML...")
        html_export = recorder.export_html(completed.id)
        assert html_export is not None
        assert "<!DOCTYPE html>" in html_export
        assert "Acme Corp" in html_export
        print(f"  ✓ HTML export: {len(html_export)} chars")

        # Test 10: Save HTML
        print("\n[Test 9] Saving HTML export...")
        html_path = recorder.save_html_export(completed.id)
        assert html_path is not None
        assert os.path.exists(html_path)
        print(f"  ✓ Saved to: {html_path}")

    print("\n" + "=" * 60)
    print("  All tests passed! ✅")
    print("=" * 60)


if __name__ == "__main__":
    test_demo_recorder()
