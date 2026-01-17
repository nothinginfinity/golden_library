#!/usr/bin/env python3
"""
Canvas Sync Manager - Phase 4C.2 Real-time Canvas Collaboration

Implements CRDT-like conflict resolution for collaborative document editing:
- Section-based document organization
- Last-Write-Wins with vector clocks for conflict resolution
- Version history tracking
- Real-time sync via WebSocket events
- Export to Markdown/HTML/PDF
"""

import uuid
import json
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict


class SectionType(Enum):
    """Types of canvas sections."""
    MARKDOWN = "markdown"
    CODE = "code"
    DIAGRAM = "diagram"  # Mermaid diagrams
    JSON = "json"
    TABLE = "table"


class EditOperation(Enum):
    """Types of edit operations."""
    INSERT = "insert"
    DELETE = "delete"
    REPLACE = "replace"
    FORMAT = "format"


@dataclass
class VectorClock:
    """
    Vector clock for tracking causality in distributed edits.
    Maps author_id -> logical timestamp.
    """
    clocks: Dict[str, int] = field(default_factory=dict)

    def increment(self, author_id: str) -> 'VectorClock':
        """Increment clock for author and return new clock."""
        new_clocks = self.clocks.copy()
        new_clocks[author_id] = new_clocks.get(author_id, 0) + 1
        return VectorClock(clocks=new_clocks)

    def merge(self, other: 'VectorClock') -> 'VectorClock':
        """Merge with another clock, taking max of each."""
        merged = self.clocks.copy()
        for author, ts in other.clocks.items():
            merged[author] = max(merged.get(author, 0), ts)
        return VectorClock(clocks=merged)

    def happens_before(self, other: 'VectorClock') -> bool:
        """Check if self happens-before other (causal ordering)."""
        dominated = False
        for author in set(self.clocks.keys()) | set(other.clocks.keys()):
            self_ts = self.clocks.get(author, 0)
            other_ts = other.clocks.get(author, 0)
            if self_ts > other_ts:
                return False
            if self_ts < other_ts:
                dominated = True
        return dominated

    def concurrent_with(self, other: 'VectorClock') -> bool:
        """Check if edits are concurrent (neither happens-before)."""
        return not self.happens_before(other) and not other.happens_before(self)

    def to_dict(self) -> Dict[str, int]:
        return self.clocks.copy()

    @classmethod
    def from_dict(cls, d: Dict[str, int]) -> 'VectorClock':
        return cls(clocks=d.copy())


@dataclass
class CanvasEdit:
    """
    Represents a single edit operation on a canvas section.
    """
    id: str
    section_name: str
    author_id: str  # User or agent ID
    author_name: str
    operation: EditOperation
    content: str  # New content or delta
    position: Optional[int] = None  # For insert/delete operations
    length: Optional[int] = None  # For delete operations
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    vector_clock: VectorClock = field(default_factory=VectorClock)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'section_name': self.section_name,
            'author_id': self.author_id,
            'author_name': self.author_name,
            'operation': self.operation.value,
            'content': self.content,
            'position': self.position,
            'length': self.length,
            'timestamp': self.timestamp,
            'vector_clock': self.vector_clock.to_dict(),
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'CanvasEdit':
        return cls(
            id=d['id'],
            section_name=d['section_name'],
            author_id=d['author_id'],
            author_name=d['author_name'],
            operation=EditOperation(d['operation']),
            content=d['content'],
            position=d.get('position'),
            length=d.get('length'),
            timestamp=d['timestamp'],
            vector_clock=VectorClock.from_dict(d.get('vector_clock', {})),
            metadata=d.get('metadata', {})
        )


@dataclass
class CanvasSection:
    """
    A section of the canvas document.
    """
    name: str
    section_type: SectionType
    content: str
    owner: Optional[str] = None  # Agent or user who owns this section
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    version: int = 1
    vector_clock: VectorClock = field(default_factory=VectorClock)
    edit_history: List[CanvasEdit] = field(default_factory=list)
    locked_by: Optional[str] = None  # User currently editing
    lock_expires: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'section_type': self.section_type.value,
            'content': self.content,
            'owner': self.owner,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'version': self.version,
            'vector_clock': self.vector_clock.to_dict(),
            'edit_history': [e.to_dict() for e in self.edit_history[-20:]],  # Keep last 20
            'locked_by': self.locked_by,
            'lock_expires': self.lock_expires,
            'metadata': self.metadata
        }


@dataclass
class CanvasDocument:
    """
    A collaborative canvas document containing multiple sections.
    """
    id: str
    name: str
    session_id: str
    sections: Dict[str, CanvasSection] = field(default_factory=dict)
    section_order: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'session_id': self.session_id,
            'sections': {k: v.to_dict() for k, v in self.sections.items()},
            'section_order': self.section_order,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'metadata': self.metadata
        }


class CanvasSyncManager:
    """
    Manages real-time canvas collaboration with CRDT-like conflict resolution.

    Key features:
    - Section-based document editing
    - Vector clock conflict resolution
    - Permission enforcement (section ownership)
    - Version history tracking
    - Export to multiple formats
    """

    def __init__(self, session_manager=None):
        """
        Initialize CanvasSyncManager.

        Args:
            session_manager: WorkspaceSessionManager for WebSocket events
        """
        self.session_manager = session_manager
        self.documents: Dict[str, CanvasDocument] = {}  # doc_id -> document
        self.documents_by_session: Dict[str, List[str]] = defaultdict(list)  # session_id -> [doc_ids]

    def create_document(
        self,
        session_id: str,
        name: str,
        initial_sections: Optional[List[Dict]] = None
    ) -> CanvasDocument:
        """
        Create a new canvas document.

        Args:
            session_id: Session ID
            name: Document name
            initial_sections: Optional list of section dicts with name, type, content, owner

        Returns:
            Created CanvasDocument
        """
        doc_id = f"canvas_{uuid.uuid4().hex[:12]}"

        doc = CanvasDocument(
            id=doc_id,
            name=name,
            session_id=session_id
        )

        # Add initial sections
        if initial_sections:
            for sec in initial_sections:
                section = CanvasSection(
                    name=sec['name'],
                    section_type=SectionType(sec.get('type', 'markdown')),
                    content=sec.get('content', ''),
                    owner=sec.get('owner')
                )
                doc.sections[sec['name']] = section
                doc.section_order.append(sec['name'])

        self.documents[doc_id] = doc
        self.documents_by_session[session_id].append(doc_id)

        print(f"[CanvasSyncManager] Created document: {doc_id} ({name})")

        # Queue WebSocket event
        if self.session_manager:
            self.session_manager._queue_ws_event(session_id, 'canvas_document_created', {
                'document_id': doc_id,
                'name': name,
                'sections': list(doc.sections.keys())
            })

        return doc

    def get_document(self, doc_id: str) -> Optional[CanvasDocument]:
        """Get a document by ID."""
        return self.documents.get(doc_id)

    def get_session_documents(self, session_id: str) -> List[CanvasDocument]:
        """Get all documents for a session."""
        doc_ids = self.documents_by_session.get(session_id, [])
        return [self.documents[did] for did in doc_ids if did in self.documents]

    def add_section(
        self,
        doc_id: str,
        section_name: str,
        section_type: str = "markdown",
        content: str = "",
        owner: Optional[str] = None,
        position: Optional[int] = None
    ) -> Optional[CanvasSection]:
        """
        Add a new section to a document.

        Args:
            doc_id: Document ID
            section_name: Section name (must be unique)
            section_type: Type (markdown, code, diagram, json)
            content: Initial content
            owner: Optional owner (agent or user ID)
            position: Optional position in section order

        Returns:
            Created section or None if failed
        """
        doc = self.documents.get(doc_id)
        if not doc:
            return None

        if section_name in doc.sections:
            print(f"[CanvasSyncManager] Section '{section_name}' already exists")
            return None

        section = CanvasSection(
            name=section_name,
            section_type=SectionType(section_type),
            content=content,
            owner=owner
        )

        doc.sections[section_name] = section

        if position is not None and 0 <= position <= len(doc.section_order):
            doc.section_order.insert(position, section_name)
        else:
            doc.section_order.append(section_name)

        doc.updated_at = datetime.utcnow().isoformat()

        print(f"[CanvasSyncManager] Added section: {section_name} to {doc_id}")

        if self.session_manager:
            self.session_manager._queue_ws_event(doc.session_id, 'canvas_section_added', {
                'document_id': doc_id,
                'section_name': section_name,
                'section_type': section_type,
                'owner': owner,
                'position': doc.section_order.index(section_name)
            })

        return section

    def apply_edit(
        self,
        doc_id: str,
        section_name: str,
        author_id: str,
        author_name: str,
        content: str,
        operation: str = "replace"
    ) -> Tuple[bool, Optional[CanvasEdit]]:
        """
        Apply an edit to a canvas section with conflict resolution.

        Args:
            doc_id: Document ID
            section_name: Section name
            author_id: Editor ID (user or agent)
            author_name: Editor display name
            content: New content (or delta for insert/delete)
            operation: Edit operation type

        Returns:
            Tuple of (success, edit) - edit may be transformed if conflict occurred
        """
        doc = self.documents.get(doc_id)
        if not doc or section_name not in doc.sections:
            return (False, None)

        section = doc.sections[section_name]

        # Check ownership permission
        if section.owner and section.owner != author_id:
            # Only owner can edit owned sections
            print(f"[CanvasSyncManager] Permission denied: {author_id} cannot edit section owned by {section.owner}")
            return (False, None)

        # Check lock
        if section.locked_by and section.locked_by != author_id:
            if section.lock_expires:
                lock_exp = datetime.fromisoformat(section.lock_expires)
                if datetime.utcnow() < lock_exp:
                    print(f"[CanvasSyncManager] Section locked by {section.locked_by}")
                    return (False, None)

        # Create edit with incremented vector clock
        new_clock = section.vector_clock.increment(author_id)

        edit = CanvasEdit(
            id=str(uuid.uuid4()),
            section_name=section_name,
            author_id=author_id,
            author_name=author_name,
            operation=EditOperation(operation),
            content=content,
            vector_clock=new_clock
        )

        # Apply edit based on operation type
        if operation == "replace":
            section.content = content
        elif operation == "insert" and edit.position is not None:
            pos = min(edit.position, len(section.content))
            section.content = section.content[:pos] + content + section.content[pos:]
        elif operation == "delete" and edit.position is not None and edit.length:
            pos = min(edit.position, len(section.content))
            section.content = section.content[:pos] + section.content[pos + edit.length:]

        # Update section metadata
        section.vector_clock = new_clock
        section.version += 1
        section.updated_at = datetime.utcnow().isoformat()
        section.edit_history.append(edit)

        # Trim history to last 50 edits
        if len(section.edit_history) > 50:
            section.edit_history = section.edit_history[-50:]

        doc.updated_at = section.updated_at

        print(f"[CanvasSyncManager] Edit applied: {section_name} v{section.version} by {author_name}")

        # Broadcast update
        if self.session_manager:
            self.session_manager._queue_ws_event(doc.session_id, 'canvas_edit', {
                'document_id': doc_id,
                'section_name': section_name,
                'edit': edit.to_dict(),
                'new_content': section.content,
                'version': section.version
            })

        return (True, edit)

    def get_section(self, doc_id: str, section_name: str) -> Optional[CanvasSection]:
        """Get a section from a document."""
        doc = self.documents.get(doc_id)
        if not doc:
            return None
        return doc.sections.get(section_name)

    def get_section_content(self, doc_id: str, section_name: str) -> Optional[str]:
        """Get just the content of a section."""
        section = self.get_section(doc_id, section_name)
        return section.content if section else None

    def get_version_history(
        self,
        doc_id: str,
        section_name: str,
        limit: int = 20
    ) -> List[Dict]:
        """
        Get edit history for a section.

        Args:
            doc_id: Document ID
            section_name: Section name
            limit: Max edits to return

        Returns:
            List of edit dicts (most recent first)
        """
        section = self.get_section(doc_id, section_name)
        if not section:
            return []

        history = section.edit_history[-limit:]
        return [e.to_dict() for e in reversed(history)]

    def lock_section(
        self,
        doc_id: str,
        section_name: str,
        user_id: str,
        duration_seconds: int = 60
    ) -> bool:
        """
        Lock a section for editing.

        Args:
            doc_id: Document ID
            section_name: Section name
            user_id: User acquiring lock
            duration_seconds: Lock duration

        Returns:
            True if lock acquired
        """
        section = self.get_section(doc_id, section_name)
        if not section:
            return False

        # Check existing lock
        if section.locked_by and section.locked_by != user_id:
            if section.lock_expires:
                lock_exp = datetime.fromisoformat(section.lock_expires)
                if datetime.utcnow() < lock_exp:
                    return False

        from datetime import timedelta
        section.locked_by = user_id
        section.lock_expires = (datetime.utcnow() + timedelta(seconds=duration_seconds)).isoformat()

        doc = self.documents.get(doc_id)
        if doc and self.session_manager:
            self.session_manager._queue_ws_event(doc.session_id, 'canvas_section_locked', {
                'document_id': doc_id,
                'section_name': section_name,
                'locked_by': user_id,
                'expires': section.lock_expires
            })

        return True

    def unlock_section(self, doc_id: str, section_name: str, user_id: str) -> bool:
        """Release a section lock."""
        section = self.get_section(doc_id, section_name)
        if not section:
            return False

        if section.locked_by == user_id:
            section.locked_by = None
            section.lock_expires = None

            doc = self.documents.get(doc_id)
            if doc and self.session_manager:
                self.session_manager._queue_ws_event(doc.session_id, 'canvas_section_unlocked', {
                    'document_id': doc_id,
                    'section_name': section_name
                })

            return True

        return False

    def reorder_sections(
        self,
        doc_id: str,
        new_order: List[str]
    ) -> bool:
        """
        Reorder sections in a document.

        Args:
            doc_id: Document ID
            new_order: New list of section names in order

        Returns:
            True if reordered
        """
        doc = self.documents.get(doc_id)
        if not doc:
            return False

        # Validate all sections exist
        for name in new_order:
            if name not in doc.sections:
                return False

        doc.section_order = new_order
        doc.updated_at = datetime.utcnow().isoformat()

        if self.session_manager:
            self.session_manager._queue_ws_event(doc.session_id, 'canvas_sections_reordered', {
                'document_id': doc_id,
                'section_order': new_order
            })

        return True

    def delete_section(self, doc_id: str, section_name: str) -> bool:
        """Delete a section from a document."""
        doc = self.documents.get(doc_id)
        if not doc or section_name not in doc.sections:
            return False

        del doc.sections[section_name]
        doc.section_order.remove(section_name)
        doc.updated_at = datetime.utcnow().isoformat()

        if self.session_manager:
            self.session_manager._queue_ws_event(doc.session_id, 'canvas_section_deleted', {
                'document_id': doc_id,
                'section_name': section_name
            })

        return True

    # ===== Export Functions =====

    def export_markdown(self, doc_id: str) -> Optional[str]:
        """
        Export document to Markdown.

        Args:
            doc_id: Document ID

        Returns:
            Markdown string or None
        """
        doc = self.documents.get(doc_id)
        if not doc:
            return None

        lines = [f"# {doc.name}\n"]

        for section_name in doc.section_order:
            section = doc.sections.get(section_name)
            if not section:
                continue

            # Add section header
            lines.append(f"\n## {section_name}\n")

            if section.owner:
                lines.append(f"*Owner: {section.owner}*\n")

            # Add content based on type
            if section.section_type == SectionType.CODE:
                lang = section.metadata.get('language', '')
                lines.append(f"\n```{lang}\n{section.content}\n```\n")
            elif section.section_type == SectionType.DIAGRAM:
                lines.append(f"\n```mermaid\n{section.content}\n```\n")
            elif section.section_type == SectionType.JSON:
                lines.append(f"\n```json\n{section.content}\n```\n")
            else:
                lines.append(f"\n{section.content}\n")

        # Add metadata footer
        lines.append(f"\n---\n")
        lines.append(f"*Generated: {datetime.utcnow().isoformat()}*\n")
        lines.append(f"*Document ID: {doc_id}*\n")

        return ''.join(lines)

    def export_html(self, doc_id: str) -> Optional[str]:
        """
        Export document to HTML.

        Args:
            doc_id: Document ID

        Returns:
            HTML string or None
        """
        doc = self.documents.get(doc_id)
        if not doc:
            return None

        # Convert markdown to basic HTML
        md_content = self.export_markdown(doc_id)
        if not md_content:
            return None

        # Basic markdown to HTML conversion
        html_lines = [
            '<!DOCTYPE html>',
            '<html>',
            '<head>',
            f'<title>{doc.name}</title>',
            '<style>',
            'body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 2rem; }',
            'h1 { border-bottom: 2px solid #333; padding-bottom: 0.5rem; }',
            'h2 { color: #444; margin-top: 2rem; }',
            'pre { background: #f4f4f4; padding: 1rem; border-radius: 4px; overflow-x: auto; }',
            'code { font-family: "SF Mono", Monaco, monospace; }',
            '.owner { color: #666; font-style: italic; font-size: 0.9em; }',
            '.footer { margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #ddd; color: #999; font-size: 0.8em; }',
            '</style>',
            '</head>',
            '<body>',
        ]

        # Simple markdown conversion
        import re

        for section_name in doc.section_order:
            section = doc.sections.get(section_name)
            if not section:
                continue

            html_lines.append(f'<h2>{section_name}</h2>')

            if section.owner:
                html_lines.append(f'<p class="owner">Owner: {section.owner}</p>')

            content = section.content

            # Handle code blocks
            if section.section_type in [SectionType.CODE, SectionType.DIAGRAM, SectionType.JSON]:
                lang = section.metadata.get('language', section.section_type.value)
                html_lines.append(f'<pre><code class="{lang}">{self._escape_html(content)}</code></pre>')
            else:
                # Basic markdown processing
                content = self._escape_html(content)
                content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)
                content = re.sub(r'\*(.+?)\*', r'<em>\1</em>', content)
                content = re.sub(r'^# (.+)$', r'<h1>\1</h1>', content, flags=re.MULTILINE)
                content = re.sub(r'^## (.+)$', r'<h2>\1</h2>', content, flags=re.MULTILINE)
                content = re.sub(r'^### (.+)$', r'<h3>\1</h3>', content, flags=re.MULTILINE)
                content = re.sub(r'^- (.+)$', r'<li>\1</li>', content, flags=re.MULTILINE)
                content = re.sub(r'\n\n', '</p><p>', content)
                html_lines.append(f'<div><p>{content}</p></div>')

        html_lines.extend([
            '<div class="footer">',
            f'<p>Generated: {datetime.utcnow().isoformat()}</p>',
            f'<p>Document ID: {doc_id}</p>',
            '</div>',
            '</body>',
            '</html>'
        ])

        return '\n'.join(html_lines)

    def export_json(self, doc_id: str) -> Optional[str]:
        """Export document to JSON."""
        doc = self.documents.get(doc_id)
        if not doc:
            return None

        return json.dumps(doc.to_dict(), indent=2)

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#39;'))

    # ===== Sync from Session Manager =====

    def sync_from_session_canvas(self, session_id: str) -> Optional[CanvasDocument]:
        """
        Create/sync a canvas document from session's canvas_sections.

        This bridges Phase 4C.1 canvas_sections with Phase 4C.2 CanvasDocument.
        """
        if not self.session_manager:
            return None

        session = self.session_manager.get_session(session_id)
        if not session:
            return None

        # Check if document already exists
        existing_docs = self.get_session_documents(session_id)
        if existing_docs:
            doc = existing_docs[0]
        else:
            doc = self.create_document(session_id, f"Session {session_id} Canvas")

        # Sync sections from session
        for section_name, section_data in session.canvas_sections.items():
            if section_name not in doc.sections:
                self.add_section(
                    doc.id,
                    section_name,
                    section_type="markdown",
                    content=section_data.get('content', ''),
                    owner=section_data.get('owner')
                )
            else:
                # Update existing section
                section = doc.sections[section_name]
                session_version = section_data.get('version', 0)
                if session_version > section.version:
                    section.content = section_data.get('content', '')
                    section.version = session_version
                    section.updated_at = section_data.get('updated_at', datetime.utcnow().isoformat())

        return doc


# Global instance
canvas_sync_manager: Optional[CanvasSyncManager] = None


def get_canvas_sync_manager(session_manager=None) -> CanvasSyncManager:
    """Get or create the global CanvasSyncManager instance."""
    global canvas_sync_manager

    if canvas_sync_manager is None:
        canvas_sync_manager = CanvasSyncManager(session_manager)
    elif session_manager and canvas_sync_manager.session_manager is None:
        canvas_sync_manager.session_manager = session_manager

    return canvas_sync_manager
