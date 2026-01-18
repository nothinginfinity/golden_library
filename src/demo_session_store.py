"""
Demo Session Store - Redis-backed persistent sessions for investor demos.

Simple demo system:
- Demo codes (e.g., "INVEST2026") create/join sessions
- Sessions persist in Redis (survive server restarts)
- Shareable URLs for remote demos
"""

import json
import os
import secrets
import string
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None


# Redis key patterns
KEY_DEMO_SESSION = "gl:demo:{code}"          # Demo session data
KEY_DEMO_CODES = "gl:demo:codes"              # Set of active demo codes
KEY_SESSION_MAPPING = "gl:session:{code}"     # Maps demo code -> workspace session ID

# TTL
TTL_DEMO_SESSION = 24 * 60 * 60  # 24 hours


@dataclass
class DemoSession:
    """A demo session that can be shared via URL."""
    code: str                          # Demo code (e.g., "INVEST2026")
    workspace_session_id: Optional[str] = None  # Linked workspace session
    owner_name: str = ""               # Who created it
    template_id: Optional[str] = None  # Which demo template to use
    created_at: str = ""
    expires_at: str = ""
    participants: List[str] = None     # List of participant names
    is_active: bool = True

    def __post_init__(self):
        if self.participants is None:
            self.participants = []
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()
        if not self.expires_at:
            expires = datetime.utcnow() + timedelta(hours=24)
            self.expires_at = expires.isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DemoSession":
        return cls(**data)

    def is_expired(self) -> bool:
        expires = datetime.fromisoformat(self.expires_at)
        return datetime.utcnow() > expires


class DemoSessionStore:
    """
    Redis-backed store for demo sessions.

    Usage:
        store = DemoSessionStore()

        # Create demo
        demo = store.create_demo("INVEST2026", owner_name="Kane")

        # Join demo
        demo = store.join_demo("INVEST2026", participant_name="Investor")

        # Get demo
        demo = store.get_demo("INVEST2026")
    """

    def __init__(self, redis_url: Optional[str] = None):
        """Initialize with Redis connection."""
        self.redis: Optional["redis.Redis"] = None
        self._connected = False

        if not REDIS_AVAILABLE:
            print("[DemoSessionStore] Redis not available - using in-memory fallback")
            self._memory_store: Dict[str, DemoSession] = {}
            return

        # Get Redis config from environment or use defaults
        redis_host = os.environ.get('REDIS_HOST', 'localhost')
        redis_port = int(os.environ.get('REDIS_PORT', 6379))
        redis_user = os.environ.get('REDIS_USER', '')
        redis_password = os.environ.get('REDIS_PASSWORD', '')

        try:
            if redis_url:
                self.redis = redis.from_url(redis_url, decode_responses=True)
            elif redis_password:
                # Cloud Redis with auth
                self.redis = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    username=redis_user or 'default',
                    password=redis_password,
                    decode_responses=True,
                    socket_timeout=5
                )
            else:
                # Local Redis
                self.redis = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    decode_responses=True,
                    socket_timeout=5
                )

            # Test connection
            self.redis.ping()
            self._connected = True
            print(f"[DemoSessionStore] Connected to Redis at {redis_host}:{redis_port}")

        except Exception as e:
            print(f"[DemoSessionStore] Redis connection failed: {e}")
            print("[DemoSessionStore] Using in-memory fallback")
            self._memory_store = {}

    @property
    def is_connected(self) -> bool:
        return self._connected

    def _generate_code(self, prefix: str = "DEMO") -> str:
        """Generate a unique demo code."""
        suffix = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
        return f"{prefix}{suffix}"

    def create_demo(
        self,
        code: Optional[str] = None,
        owner_name: str = "Host",
        template_id: Optional[str] = None,
        ttl_hours: int = 24
    ) -> DemoSession:
        """
        Create a new demo session.

        Args:
            code: Demo code (auto-generated if not provided)
            owner_name: Name of the demo host
            template_id: Optional template to use
            ttl_hours: How long the demo lasts

        Returns:
            DemoSession object
        """
        if not code:
            code = self._generate_code()

        # Check if code already exists
        existing = self.get_demo(code)
        if existing and not existing.is_expired():
            return existing

        expires = datetime.utcnow() + timedelta(hours=ttl_hours)

        demo = DemoSession(
            code=code,
            owner_name=owner_name,
            template_id=template_id,
            created_at=datetime.utcnow().isoformat(),
            expires_at=expires.isoformat(),
            participants=[owner_name],
            is_active=True
        )

        self._save_demo(demo, ttl_hours * 3600)
        return demo

    def get_demo(self, code: str) -> Optional[DemoSession]:
        """Get a demo session by code."""
        code = code.upper()

        if self._connected and self.redis:
            try:
                data = self.redis.get(KEY_DEMO_SESSION.format(code=code))
                if data:
                    return DemoSession.from_dict(json.loads(data))
            except Exception as e:
                print(f"[DemoSessionStore] Redis get error: {e}")
        else:
            # In-memory fallback
            return self._memory_store.get(code)

        return None

    def join_demo(self, code: str, participant_name: str) -> Optional[DemoSession]:
        """
        Join an existing demo session.

        Args:
            code: Demo code
            participant_name: Name of the participant

        Returns:
            DemoSession if found and active, None otherwise
        """
        code = code.upper()
        demo = self.get_demo(code)

        if not demo:
            return None

        if demo.is_expired():
            return None

        if not demo.is_active:
            return None

        # Add participant if not already in list
        if participant_name not in demo.participants:
            demo.participants.append(participant_name)
            self._save_demo(demo)

        return demo

    def link_workspace_session(self, code: str, workspace_session_id: str) -> bool:
        """Link a demo to a workspace session ID."""
        code = code.upper()
        demo = self.get_demo(code)

        if not demo:
            return False

        demo.workspace_session_id = workspace_session_id
        self._save_demo(demo)

        # Also store reverse mapping
        if self._connected and self.redis:
            try:
                self.redis.setex(
                    KEY_SESSION_MAPPING.format(code=code),
                    TTL_DEMO_SESSION,
                    workspace_session_id
                )
            except Exception:
                pass

        return True

    def get_workspace_session_id(self, code: str) -> Optional[str]:
        """Get the workspace session ID for a demo code."""
        code = code.upper()
        demo = self.get_demo(code)
        return demo.workspace_session_id if demo else None

    def list_active_demos(self) -> List[DemoSession]:
        """List all active demo sessions."""
        demos = []

        if self._connected and self.redis:
            try:
                codes = self.redis.smembers(KEY_DEMO_CODES)
                for code in codes:
                    demo = self.get_demo(code)
                    if demo and not demo.is_expired() and demo.is_active:
                        demos.append(demo)
            except Exception as e:
                print(f"[DemoSessionStore] List error: {e}")
        else:
            for demo in self._memory_store.values():
                if not demo.is_expired() and demo.is_active:
                    demos.append(demo)

        return demos

    def end_demo(self, code: str) -> bool:
        """End a demo session."""
        code = code.upper()
        demo = self.get_demo(code)

        if not demo:
            return False

        demo.is_active = False
        self._save_demo(demo)
        return True

    def _save_demo(self, demo: DemoSession, ttl: int = TTL_DEMO_SESSION):
        """Save demo to storage."""
        code = demo.code.upper()

        if self._connected and self.redis:
            try:
                self.redis.setex(
                    KEY_DEMO_SESSION.format(code=code),
                    ttl,
                    json.dumps(demo.to_dict())
                )
                self.redis.sadd(KEY_DEMO_CODES, code)
            except Exception as e:
                print(f"[DemoSessionStore] Save error: {e}")
        else:
            self._memory_store[code] = demo


# Singleton instance
_demo_store: Optional[DemoSessionStore] = None


def get_demo_store() -> DemoSessionStore:
    """Get the singleton demo store instance."""
    global _demo_store
    if _demo_store is None:
        _demo_store = DemoSessionStore()
    return _demo_store


# Convenience functions
def create_demo(code: str = None, owner_name: str = "Host", template_id: str = None) -> DemoSession:
    """Create a new demo session."""
    return get_demo_store().create_demo(code, owner_name, template_id)


def join_demo(code: str, participant_name: str) -> Optional[DemoSession]:
    """Join an existing demo session."""
    return get_demo_store().join_demo(code, participant_name)


def get_demo(code: str) -> Optional[DemoSession]:
    """Get a demo session by code."""
    return get_demo_store().get_demo(code)
