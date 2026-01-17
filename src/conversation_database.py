#!/usr/bin/env python3
"""
Phase 4C.4: Conversation Database

Persistent storage for all workspace conversations with:
- PostgreSQL primary storage (SQLite fallback for development)
- Auto-save all messages
- Query interface for agents
- Context recovery for new Prax instances
- Full-text search support

Run with: python3 conversation_database.py
"""

import os
import json
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging

# Try PostgreSQL, fall back to SQLite
try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False

import aiosqlite

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseType(Enum):
    POSTGRESQL = "postgresql"
    SQLITE = "sqlite"


@dataclass
class StoredMessage:
    """Message as stored in database."""
    id: str
    session_id: str
    user_id: str
    agent_id: Optional[str]
    role: str
    content: str
    timestamp: str
    mentions: List[str]
    # Additional metadata
    workspace_id: Optional[str] = None
    parent_message_id: Optional[str] = None
    embedding_vector: Optional[List[float]] = None  # For semantic search

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'StoredMessage':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class SessionSummary:
    """Summary of a session for context recovery."""
    session_id: str
    workspace_id: Optional[str]
    created_at: str
    last_activity: str
    message_count: int
    participants: List[str]
    agents_used: List[str]
    key_topics: List[str]
    decisions: List[str]

    def to_dict(self) -> Dict:
        return asdict(self)


class ConversationDatabase:
    """
    Persistent storage for workspace conversations.

    Supports PostgreSQL (production) and SQLite (development/testing).
    """

    def __init__(
        self,
        database_url: Optional[str] = None,
        db_type: Optional[DatabaseType] = None,
        sqlite_path: str = "conversations.db"
    ):
        """
        Initialize database connection.

        Args:
            database_url: PostgreSQL connection URL (or None for SQLite)
            db_type: Force specific database type
            sqlite_path: Path for SQLite database file
        """
        self.database_url = database_url or os.getenv("DATABASE_URL")
        self.sqlite_path = sqlite_path
        self._pool = None
        self._sqlite_conn = None

        # Determine database type
        if db_type:
            self.db_type = db_type
        elif self.database_url and HAS_ASYNCPG:
            self.db_type = DatabaseType.POSTGRESQL
        else:
            self.db_type = DatabaseType.SQLITE

        logger.info(f"[ConversationDB] Using {self.db_type.value} backend")

    async def initialize(self):
        """Initialize database connection and create tables."""
        if self.db_type == DatabaseType.POSTGRESQL:
            await self._init_postgresql()
        else:
            await self._init_sqlite()

    async def _init_postgresql(self):
        """Initialize PostgreSQL connection pool and schema."""
        self._pool = await asyncpg.create_pool(
            self.database_url,
            min_size=2,
            max_size=10
        )

        async with self._pool.acquire() as conn:
            # Create messages table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    workspace_id TEXT,
                    user_id TEXT NOT NULL,
                    agent_id TEXT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    mentions JSONB DEFAULT '[]',
                    parent_message_id TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            ''')

            # Create indexes
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_messages_session
                ON messages(session_id)
            ''')
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_messages_timestamp
                ON messages(timestamp DESC)
            ''')
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_messages_agent
                ON messages(agent_id)
            ''')

            # Full-text search index
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_messages_content_fts
                ON messages USING gin(to_tsvector('english', content))
            ''')

            # Sessions summary table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS session_summaries (
                    session_id TEXT PRIMARY KEY,
                    workspace_id TEXT,
                    created_at TIMESTAMPTZ NOT NULL,
                    last_activity TIMESTAMPTZ NOT NULL,
                    message_count INTEGER DEFAULT 0,
                    participants JSONB DEFAULT '[]',
                    agents_used JSONB DEFAULT '[]',
                    key_topics JSONB DEFAULT '[]',
                    decisions JSONB DEFAULT '[]',
                    context_snapshot TEXT,
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            ''')

            logger.info("[ConversationDB] PostgreSQL schema initialized")

    async def _init_sqlite(self):
        """Initialize SQLite database and schema."""
        self._sqlite_conn = await aiosqlite.connect(self.sqlite_path)

        # Enable WAL mode for better concurrency
        await self._sqlite_conn.execute("PRAGMA journal_mode=WAL")

        # Create messages table
        await self._sqlite_conn.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                workspace_id TEXT,
                user_id TEXT NOT NULL,
                agent_id TEXT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                mentions TEXT DEFAULT '[]',
                parent_message_id TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create indexes
        await self._sqlite_conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_messages_session
            ON messages(session_id)
        ''')
        await self._sqlite_conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_messages_timestamp
            ON messages(timestamp DESC)
        ''')

        # Sessions summary table
        await self._sqlite_conn.execute('''
            CREATE TABLE IF NOT EXISTS session_summaries (
                session_id TEXT PRIMARY KEY,
                workspace_id TEXT,
                created_at TEXT NOT NULL,
                last_activity TEXT NOT NULL,
                message_count INTEGER DEFAULT 0,
                participants TEXT DEFAULT '[]',
                agents_used TEXT DEFAULT '[]',
                key_topics TEXT DEFAULT '[]',
                decisions TEXT DEFAULT '[]',
                context_snapshot TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        await self._sqlite_conn.commit()
        logger.info(f"[ConversationDB] SQLite schema initialized at {self.sqlite_path}")

    async def close(self):
        """Close database connections."""
        if self._pool:
            await self._pool.close()
        if self._sqlite_conn:
            await self._sqlite_conn.close()

    # ===== Message Operations =====

    async def save_message(self, message: StoredMessage) -> bool:
        """
        Save a message to the database.

        Args:
            message: Message to save

        Returns:
            True if saved successfully
        """
        try:
            if self.db_type == DatabaseType.POSTGRESQL:
                async with self._pool.acquire() as conn:
                    await conn.execute('''
                        INSERT INTO messages (id, session_id, workspace_id, user_id,
                            agent_id, role, content, timestamp, mentions, parent_message_id)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        ON CONFLICT (id) DO UPDATE SET
                            content = EXCLUDED.content,
                            mentions = EXCLUDED.mentions
                    ''', message.id, message.session_id, message.workspace_id,
                        message.user_id, message.agent_id, message.role,
                        message.content, message.timestamp,
                        json.dumps(message.mentions), message.parent_message_id)
            else:
                await self._sqlite_conn.execute('''
                    INSERT OR REPLACE INTO messages
                    (id, session_id, workspace_id, user_id, agent_id, role,
                     content, timestamp, mentions, parent_message_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (message.id, message.session_id, message.workspace_id,
                      message.user_id, message.agent_id, message.role,
                      message.content, message.timestamp,
                      json.dumps(message.mentions), message.parent_message_id))
                await self._sqlite_conn.commit()

            return True
        except Exception as e:
            logger.error(f"[ConversationDB] Error saving message: {e}")
            return False

    async def save_messages_batch(self, messages: List[StoredMessage]) -> int:
        """
        Save multiple messages in a batch.

        Args:
            messages: List of messages to save

        Returns:
            Number of messages saved
        """
        saved = 0
        for msg in messages:
            if await self.save_message(msg):
                saved += 1
        return saved

    async def get_session_messages(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0,
        agent_id: Optional[str] = None,
        since: Optional[str] = None
    ) -> List[StoredMessage]:
        """
        Get messages from a session.

        Args:
            session_id: Session to get messages from
            limit: Max messages to return
            offset: Messages to skip
            agent_id: Filter by agent
            since: Only messages after this timestamp

        Returns:
            List of messages
        """
        messages = []

        try:
            if self.db_type == DatabaseType.POSTGRESQL:
                async with self._pool.acquire() as conn:
                    query = '''
                        SELECT id, session_id, workspace_id, user_id, agent_id,
                               role, content, timestamp, mentions, parent_message_id
                        FROM messages
                        WHERE session_id = $1
                    '''
                    params = [session_id]
                    param_idx = 2

                    if agent_id:
                        query += f" AND agent_id = ${param_idx}"
                        params.append(agent_id)
                        param_idx += 1

                    if since:
                        query += f" AND timestamp > ${param_idx}"
                        params.append(since)
                        param_idx += 1

                    query += f" ORDER BY timestamp DESC LIMIT ${param_idx} OFFSET ${param_idx + 1}"
                    params.extend([limit, offset])

                    rows = await conn.fetch(query, *params)

                    for row in rows:
                        messages.append(StoredMessage(
                            id=row['id'],
                            session_id=row['session_id'],
                            workspace_id=row['workspace_id'],
                            user_id=row['user_id'],
                            agent_id=row['agent_id'],
                            role=row['role'],
                            content=row['content'],
                            timestamp=row['timestamp'].isoformat() if hasattr(row['timestamp'], 'isoformat') else row['timestamp'],
                            mentions=json.loads(row['mentions']) if isinstance(row['mentions'], str) else row['mentions'],
                            parent_message_id=row['parent_message_id']
                        ))
            else:
                query = '''
                    SELECT id, session_id, workspace_id, user_id, agent_id,
                           role, content, timestamp, mentions, parent_message_id
                    FROM messages
                    WHERE session_id = ?
                '''
                params = [session_id]

                if agent_id:
                    query += " AND agent_id = ?"
                    params.append(agent_id)

                if since:
                    query += " AND timestamp > ?"
                    params.append(since)

                query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])

                async with self._sqlite_conn.execute(query, params) as cursor:
                    rows = await cursor.fetchall()

                    for row in rows:
                        messages.append(StoredMessage(
                            id=row[0],
                            session_id=row[1],
                            workspace_id=row[2],
                            user_id=row[3],
                            agent_id=row[4],
                            role=row[5],
                            content=row[6],
                            timestamp=row[7],
                            mentions=json.loads(row[8]) if row[8] else [],
                            parent_message_id=row[9]
                        ))
        except Exception as e:
            logger.error(f"[ConversationDB] Error getting messages: {e}")

        return messages

    # ===== Search Operations =====

    async def search_messages(
        self,
        query: str,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        limit: int = 20,
        since: Optional[str] = None
    ) -> List[Tuple[StoredMessage, float]]:
        """
        Full-text search across messages.

        Args:
            query: Search query
            session_id: Limit to specific session
            agent_id: Limit to specific agent
            limit: Max results
            since: Only search messages after this timestamp

        Returns:
            List of (message, relevance_score) tuples
        """
        results = []

        try:
            if self.db_type == DatabaseType.POSTGRESQL:
                async with self._pool.acquire() as conn:
                    # PostgreSQL full-text search
                    base_query = '''
                        SELECT id, session_id, workspace_id, user_id, agent_id,
                               role, content, timestamp, mentions, parent_message_id,
                               ts_rank(to_tsvector('english', content),
                                       plainto_tsquery('english', $1)) as rank
                        FROM messages
                        WHERE to_tsvector('english', content) @@ plainto_tsquery('english', $1)
                    '''
                    params = [query]
                    param_idx = 2

                    if session_id:
                        base_query += f" AND session_id = ${param_idx}"
                        params.append(session_id)
                        param_idx += 1

                    if agent_id:
                        base_query += f" AND agent_id = ${param_idx}"
                        params.append(agent_id)
                        param_idx += 1

                    if since:
                        base_query += f" AND timestamp > ${param_idx}"
                        params.append(since)
                        param_idx += 1

                    base_query += f" ORDER BY rank DESC LIMIT ${param_idx}"
                    params.append(limit)

                    rows = await conn.fetch(base_query, *params)

                    for row in rows:
                        msg = StoredMessage(
                            id=row['id'],
                            session_id=row['session_id'],
                            workspace_id=row['workspace_id'],
                            user_id=row['user_id'],
                            agent_id=row['agent_id'],
                            role=row['role'],
                            content=row['content'],
                            timestamp=row['timestamp'].isoformat() if hasattr(row['timestamp'], 'isoformat') else row['timestamp'],
                            mentions=json.loads(row['mentions']) if isinstance(row['mentions'], str) else row['mentions'],
                            parent_message_id=row['parent_message_id']
                        )
                        results.append((msg, float(row['rank'])))
            else:
                # SQLite LIKE-based search (simpler but less powerful)
                base_query = '''
                    SELECT id, session_id, workspace_id, user_id, agent_id,
                           role, content, timestamp, mentions, parent_message_id
                    FROM messages
                    WHERE content LIKE ?
                '''
                params = [f"%{query}%"]

                if session_id:
                    base_query += " AND session_id = ?"
                    params.append(session_id)

                if agent_id:
                    base_query += " AND agent_id = ?"
                    params.append(agent_id)

                if since:
                    base_query += " AND timestamp > ?"
                    params.append(since)

                base_query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)

                async with self._sqlite_conn.execute(base_query, params) as cursor:
                    rows = await cursor.fetchall()

                    for row in rows:
                        msg = StoredMessage(
                            id=row[0],
                            session_id=row[1],
                            workspace_id=row[2],
                            user_id=row[3],
                            agent_id=row[4],
                            role=row[5],
                            content=row[6],
                            timestamp=row[7],
                            mentions=json.loads(row[8]) if row[8] else [],
                            parent_message_id=row[9]
                        )
                        # Calculate simple relevance score
                        score = row[6].lower().count(query.lower()) / max(len(row[6]), 1)
                        results.append((msg, score))
        except Exception as e:
            logger.error(f"[ConversationDB] Error searching messages: {e}")

        return results

    async def search_decisions(
        self,
        query: str,
        session_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Tuple[StoredMessage, float]]:
        """
        Search for decision-related messages.

        Looks for patterns like "decided", "agreed", "will use", etc.

        Args:
            query: Topic to search for
            session_id: Limit to specific session
            limit: Max results

        Returns:
            List of (message, relevance_score) tuples
        """
        decision_patterns = [
            "decided", "decision", "agreed", "will use", "going with",
            "chosen", "selected", "approved", "confirmed", "final"
        ]

        results = []

        # Search with decision context
        for pattern in decision_patterns[:3]:  # Limit patterns for efficiency
            search_query = f"{query} {pattern}"
            pattern_results = await self.search_messages(
                query=search_query,
                session_id=session_id,
                limit=limit // 3
            )
            results.extend(pattern_results)

        # Deduplicate and sort by score
        seen_ids = set()
        unique_results = []
        for msg, score in sorted(results, key=lambda x: x[1], reverse=True):
            if msg.id not in seen_ids:
                seen_ids.add(msg.id)
                unique_results.append((msg, score))

        return unique_results[:limit]

    # ===== Session Summary Operations =====

    async def update_session_summary(
        self,
        session_id: str,
        workspace_id: Optional[str] = None,
        key_topics: Optional[List[str]] = None,
        decisions: Optional[List[str]] = None,
        context_snapshot: Optional[str] = None
    ) -> bool:
        """
        Update or create session summary.

        Called periodically to maintain searchable summaries.
        """
        try:
            # Get current stats
            if self.db_type == DatabaseType.POSTGRESQL:
                async with self._pool.acquire() as conn:
                    stats = await conn.fetchrow('''
                        SELECT COUNT(*) as msg_count,
                               array_agg(DISTINCT user_id) as participants,
                               array_agg(DISTINCT agent_id) FILTER (WHERE agent_id IS NOT NULL) as agents
                        FROM messages
                        WHERE session_id = $1
                    ''', session_id)

                    await conn.execute('''
                        INSERT INTO session_summaries
                        (session_id, workspace_id, created_at, last_activity,
                         message_count, participants, agents_used, key_topics,
                         decisions, context_snapshot, updated_at)
                        VALUES ($1, $2, NOW(), NOW(), $3, $4, $5, $6, $7, $8, NOW())
                        ON CONFLICT (session_id) DO UPDATE SET
                            last_activity = NOW(),
                            message_count = EXCLUDED.message_count,
                            participants = EXCLUDED.participants,
                            agents_used = EXCLUDED.agents_used,
                            key_topics = COALESCE(EXCLUDED.key_topics, session_summaries.key_topics),
                            decisions = COALESCE(EXCLUDED.decisions, session_summaries.decisions),
                            context_snapshot = COALESCE(EXCLUDED.context_snapshot, session_summaries.context_snapshot),
                            updated_at = NOW()
                    ''', session_id, workspace_id,
                        stats['msg_count'] if stats else 0,
                        json.dumps(list(stats['participants'] or [])),
                        json.dumps(list(filter(None, stats['agents'] or []))),
                        json.dumps(key_topics or []),
                        json.dumps(decisions or []),
                        context_snapshot)
            else:
                async with self._sqlite_conn.execute('''
                    SELECT COUNT(*) as msg_count,
                           GROUP_CONCAT(DISTINCT user_id) as participants,
                           GROUP_CONCAT(DISTINCT agent_id) as agents
                    FROM messages
                    WHERE session_id = ?
                ''', (session_id,)) as cursor:
                    row = await cursor.fetchone()
                    msg_count = row[0] if row else 0
                    participants = row[1].split(',') if row and row[1] else []
                    agents = [a for a in (row[2].split(',') if row and row[2] else []) if a]

                now = datetime.utcnow().isoformat()
                await self._sqlite_conn.execute('''
                    INSERT OR REPLACE INTO session_summaries
                    (session_id, workspace_id, created_at, last_activity,
                     message_count, participants, agents_used, key_topics,
                     decisions, context_snapshot, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (session_id, workspace_id, now, now,
                      msg_count, json.dumps(participants), json.dumps(agents),
                      json.dumps(key_topics or []), json.dumps(decisions or []),
                      context_snapshot, now))
                await self._sqlite_conn.commit()

            return True
        except Exception as e:
            logger.error(f"[ConversationDB] Error updating summary: {e}")
            return False

    async def get_session_summary(self, session_id: str) -> Optional[SessionSummary]:
        """Get summary for a session."""
        try:
            if self.db_type == DatabaseType.POSTGRESQL:
                async with self._pool.acquire() as conn:
                    row = await conn.fetchrow('''
                        SELECT * FROM session_summaries WHERE session_id = $1
                    ''', session_id)

                    if row:
                        return SessionSummary(
                            session_id=row['session_id'],
                            workspace_id=row['workspace_id'],
                            created_at=row['created_at'].isoformat(),
                            last_activity=row['last_activity'].isoformat(),
                            message_count=row['message_count'],
                            participants=json.loads(row['participants']),
                            agents_used=json.loads(row['agents_used']),
                            key_topics=json.loads(row['key_topics']),
                            decisions=json.loads(row['decisions'])
                        )
            else:
                async with self._sqlite_conn.execute('''
                    SELECT * FROM session_summaries WHERE session_id = ?
                ''', (session_id,)) as cursor:
                    row = await cursor.fetchone()

                    if row:
                        return SessionSummary(
                            session_id=row[0],
                            workspace_id=row[1],
                            created_at=row[2],
                            last_activity=row[3],
                            message_count=row[4],
                            participants=json.loads(row[5]),
                            agents_used=json.loads(row[6]),
                            key_topics=json.loads(row[7]),
                            decisions=json.loads(row[8])
                        )
        except Exception as e:
            logger.error(f"[ConversationDB] Error getting summary: {e}")

        return None

    # ===== Context Recovery =====

    async def get_context_for_prax(
        self,
        session_id: str,
        max_messages: int = 50,
        include_summary: bool = True
    ) -> Dict[str, Any]:
        """
        Get context for a new Prax instance to resume work.

        Args:
            session_id: Session to recover context from
            max_messages: Max recent messages to include
            include_summary: Include session summary

        Returns:
            Context dict with messages, summary, and recovery instructions
        """
        context = {
            'session_id': session_id,
            'recovered_at': datetime.utcnow().isoformat(),
            'messages': [],
            'summary': None,
            'recovery_instructions': []
        }

        # Get session summary
        if include_summary:
            summary = await self.get_session_summary(session_id)
            if summary:
                context['summary'] = summary.to_dict()

        # Get recent messages
        messages = await self.get_session_messages(
            session_id=session_id,
            limit=max_messages
        )
        context['messages'] = [m.to_dict() for m in reversed(messages)]  # Chronological order

        # Search for important decisions
        decisions = await self.search_decisions(
            query="",  # Empty query gets general decisions
            session_id=session_id,
            limit=10
        )

        if decisions:
            context['key_decisions'] = [m.to_dict() for m, _ in decisions]

        # Generate recovery instructions
        if context['summary']:
            s = context['summary']
            context['recovery_instructions'] = [
                f"Session started: {s.get('created_at', 'unknown')}",
                f"Last activity: {s.get('last_activity', 'unknown')}",
                f"Messages exchanged: {s.get('message_count', 0)}",
                f"Agents involved: {', '.join(s.get('agents_used', []))}",
                f"Key topics: {', '.join(s.get('key_topics', [])[:5])}"
            ]

        return context

    async def get_agent_history(
        self,
        agent_id: str,
        session_id: Optional[str] = None,
        limit: int = 20
    ) -> List[StoredMessage]:
        """
        Get recent messages from a specific agent.

        Useful for understanding what an agent has been doing.
        """
        return await self.get_session_messages(
            session_id=session_id or "",
            agent_id=agent_id,
            limit=limit
        ) if session_id else []

    # ===== Statistics =====

    async def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        stats = {
            'db_type': self.db_type.value,
            'total_messages': 0,
            'total_sessions': 0,
            'messages_today': 0,
            'active_agents': []
        }

        try:
            if self.db_type == DatabaseType.POSTGRESQL:
                async with self._pool.acquire() as conn:
                    row = await conn.fetchrow('SELECT COUNT(*) FROM messages')
                    stats['total_messages'] = row[0]

                    row = await conn.fetchrow('SELECT COUNT(DISTINCT session_id) FROM messages')
                    stats['total_sessions'] = row[0]

                    row = await conn.fetchrow('''
                        SELECT COUNT(*) FROM messages
                        WHERE timestamp > NOW() - INTERVAL '1 day'
                    ''')
                    stats['messages_today'] = row[0]

                    rows = await conn.fetch('''
                        SELECT DISTINCT agent_id FROM messages
                        WHERE agent_id IS NOT NULL
                    ''')
                    stats['active_agents'] = [r[0] for r in rows]
            else:
                async with self._sqlite_conn.execute('SELECT COUNT(*) FROM messages') as cursor:
                    row = await cursor.fetchone()
                    stats['total_messages'] = row[0]

                async with self._sqlite_conn.execute(
                    'SELECT COUNT(DISTINCT session_id) FROM messages'
                ) as cursor:
                    row = await cursor.fetchone()
                    stats['total_sessions'] = row[0]

                # SQLite date handling
                today = datetime.utcnow().date().isoformat()
                async with self._sqlite_conn.execute(
                    'SELECT COUNT(*) FROM messages WHERE timestamp >= ?',
                    (today,)
                ) as cursor:
                    row = await cursor.fetchone()
                    stats['messages_today'] = row[0]

                async with self._sqlite_conn.execute(
                    'SELECT DISTINCT agent_id FROM messages WHERE agent_id IS NOT NULL'
                ) as cursor:
                    rows = await cursor.fetchall()
                    stats['active_agents'] = [r[0] for r in rows]
        except Exception as e:
            logger.error(f"[ConversationDB] Error getting stats: {e}")

        return stats


# ===== Global Instance =====

_conversation_db: Optional[ConversationDatabase] = None


async def get_conversation_db(
    database_url: Optional[str] = None,
    sqlite_path: str = "conversations.db"
) -> ConversationDatabase:
    """Get or create global ConversationDatabase instance."""
    global _conversation_db

    if _conversation_db is None:
        _conversation_db = ConversationDatabase(
            database_url=database_url,
            sqlite_path=sqlite_path
        )
        await _conversation_db.initialize()

    return _conversation_db


# ===== CLI Testing =====

async def test_database():
    """Test database functionality."""
    print("=" * 60)
    print("  ConversationDatabase Test")
    print("=" * 60)

    # Initialize with SQLite for testing
    db = ConversationDatabase(sqlite_path=":memory:")
    await db.initialize()

    # Test 1: Save messages
    print("\n[Test 1] Saving messages...")
    test_messages = [
        StoredMessage(
            id="msg1",
            session_id="test_session",
            user_id="user1",
            agent_id="cairn",
            role="assistant",
            content="I've decided we should use PostgreSQL for the database layer.",
            timestamp=datetime.utcnow().isoformat(),
            mentions=[]
        ),
        StoredMessage(
            id="msg2",
            session_id="test_session",
            user_id="user1",
            agent_id="koda",
            role="assistant",
            content="Implementing the database connection now. Using asyncpg for async support.",
            timestamp=datetime.utcnow().isoformat(),
            mentions=[]
        ),
        StoredMessage(
            id="msg3",
            session_id="test_session",
            user_id="user1",
            agent_id=None,
            role="user",
            content="What did we decide about the database?",
            timestamp=datetime.utcnow().isoformat(),
            mentions=[]
        ),
    ]

    saved = await db.save_messages_batch(test_messages)
    assert saved == 3, f"Expected 3 saved, got {saved}"
    print(f"  ✓ Saved {saved} messages")

    # Test 2: Retrieve messages
    print("\n[Test 2] Retrieving messages...")
    messages = await db.get_session_messages("test_session")
    assert len(messages) == 3, f"Expected 3 messages, got {len(messages)}"
    print(f"  ✓ Retrieved {len(messages)} messages")

    # Test 3: Search messages
    print("\n[Test 3] Searching messages...")
    results = await db.search_messages("PostgreSQL")
    assert len(results) >= 1, f"Expected at least 1 result, got {len(results)}"
    print(f"  ✓ Found {len(results)} results for 'PostgreSQL'")

    # Test 4: Search decisions
    print("\n[Test 4] Searching decisions...")
    decisions = await db.search_decisions("database")
    print(f"  ✓ Found {len(decisions)} decision-related messages")

    # Test 5: Update session summary
    print("\n[Test 5] Updating session summary...")
    success = await db.update_session_summary(
        session_id="test_session",
        key_topics=["database", "PostgreSQL", "async"],
        decisions=["Use PostgreSQL with asyncpg"]
    )
    assert success, "Failed to update summary"
    print(f"  ✓ Session summary updated")

    # Test 6: Get session summary
    print("\n[Test 6] Getting session summary...")
    summary = await db.get_session_summary("test_session")
    assert summary is not None, "Summary should exist"
    assert summary.message_count == 3, f"Expected 3 messages, got {summary.message_count}"
    print(f"  ✓ Summary: {summary.message_count} messages, topics: {summary.key_topics}")

    # Test 7: Context recovery
    print("\n[Test 7] Context recovery for Prax...")
    context = await db.get_context_for_prax("test_session")
    assert 'messages' in context, "Context should have messages"
    assert 'summary' in context, "Context should have summary"
    print(f"  ✓ Context recovered: {len(context['messages'])} messages")
    print(f"  ✓ Recovery instructions: {len(context.get('recovery_instructions', []))} items")

    # Test 8: Statistics
    print("\n[Test 8] Getting statistics...")
    stats = await db.get_statistics()
    assert stats['total_messages'] == 3, f"Expected 3 total, got {stats['total_messages']}"
    print(f"  ✓ Stats: {stats['total_messages']} messages, {stats['total_sessions']} sessions")

    await db.close()

    print("\n" + "=" * 60)
    print("  All tests passed! ✅")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_database())
