#!/usr/bin/env python3
"""
Simple HTTP server to serve Claude compression data to the dashboard.
Provides JSON API for dashboard to load real compressed data.
"""

import json
import os
import glob
import sys
import uuid
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta
import subprocess
import hashlib
import asyncio
import websockets
import threading
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# aiohttp for unified HTTP + WebSocket on single port
try:
    from aiohttp import web
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    print("Warning: aiohttp not installed. Using separate ports for HTTP/WS.")

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Load .env file if exists
env_file = Path(__file__).parent / '.env'
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                os.environ[key] = val
    print(f"[Server] Loaded environment from {env_file}")

# Import agent orchestrator for collaborative workspace
try:
    from agent_orchestrator import AgentOrchestrator
    AGENT_ORCHESTRATOR = None  # Will be initialized on first use
except ImportError:
    AGENT_ORCHESTRATOR = None
    print("Warning: agent_orchestrator not found. Collaborative workspace features disabled.")

# Import workspace session manager for Phase 2
try:
    from workspace_session_manager import session_manager
except ImportError:
    session_manager = None
    print("Warning: workspace_session_manager not found. Multiplayer features disabled.")

# Import demo session store for shareable demos
try:
    from demo_session_store import get_demo_store, create_demo, join_demo, get_demo
    demo_store = get_demo_store()
except ImportError:
    demo_store = None
    print("Warning: demo_session_store not found. Demo sharing features disabled.")

# Redis for persistent API key storage
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None
    print("Warning: redis not installed. API keys will use file storage.")

# Initialize Redis connection for API keys
REDIS_CLIENT = None
REDIS_API_KEYS_KEY = "golden_library:api_keys"

def init_redis():
    """Initialize Redis connection."""
    global REDIS_CLIENT
    if not REDIS_AVAILABLE:
        return None

    # Support both Railway naming (REDISHOST) and standard (REDIS_HOST)
    redis_host = os.environ.get('REDISHOST') or os.environ.get('REDIS_HOST', 'localhost')
    redis_port = int(os.environ.get('REDISPORT') or os.environ.get('REDIS_PORT', '6379'))
    redis_user = os.environ.get('REDISUSER') or os.environ.get('REDIS_USER', '')
    redis_password = os.environ.get('REDISPASSWORD') or os.environ.get('REDIS_PASSWORD', '')

    try:
        if redis_password:
            REDIS_CLIENT = redis.Redis(
                host=redis_host,
                port=redis_port,
                username=redis_user or 'default',
                password=redis_password,
                decode_responses=True,
                socket_timeout=5
            )
        else:
            REDIS_CLIENT = redis.Redis(
                host=redis_host,
                port=redis_port,
                decode_responses=True,
                socket_timeout=5
            )
        REDIS_CLIENT.ping()
        print(f"[Server] Redis connected at {redis_host}:{redis_port}")
        return REDIS_CLIENT
    except Exception as e:
        print(f"[Server] Redis connection failed: {e}")
        return None

def get_api_keys_from_redis():
    """Load API keys from Redis."""
    global REDIS_CLIENT
    if REDIS_CLIENT is None:
        init_redis()
    if REDIS_CLIENT:
        try:
            data = REDIS_CLIENT.get(REDIS_API_KEYS_KEY)
            if data:
                return json.loads(data)
        except Exception as e:
            print(f"[Server] Redis get failed: {e}")
    return None

def save_api_keys_to_redis(keys: dict):
    """Save API keys to Redis."""
    global REDIS_CLIENT
    if REDIS_CLIENT is None:
        init_redis()
    if REDIS_CLIENT:
        try:
            REDIS_CLIENT.set(REDIS_API_KEYS_KEY, json.dumps(keys))
            return True
        except Exception as e:
            print(f"[Server] Redis set failed: {e}")
    return False

# Initialize Redis on startup
init_redis()

# Paths
HOME = Path.home()
LIBRARY_DIR = HOME / ".claude" / "conversation_library"
INDEX_FILE = LIBRARY_DIR / "index.json"
COMPRESSED_DIR = LIBRARY_DIR / "compressed"
DAEMON_PID_FILE = HOME / ".claude" / "auto_compress_daemon.pid"
ARSENAL_DIR = HOME / ".claude" / "arsenal"
ARSENAL_LIBRARY = ARSENAL_DIR / "library"
ARSENAL_PRESETS = ARSENAL_DIR / "presets"
GOLDEN_LIBRARY_DIR = HOME / "ztgi" / "golden_library" / ".golden_library"
GOLDEN_INDEX_FILE = GOLDEN_LIBRARY_DIR / "index.json"
API_KEYS_FILE = HOME / ".claude" / "api_keys.json"
UPLOADS_DIR = HOME / "ztgi" / "uploads"
UPLOADS_INDEX_FILE = UPLOADS_DIR / "index.json"
UNIFIED_HISTORY_INDEX = HOME / ".claude" / "unified_history_index.json"

class DashboardHandler(SimpleHTTPRequestHandler):
    """Custom handler to serve API endpoints and static files."""

    def do_GET(self):
        """Handle GET requests."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        # API Endpoints
        if path == '/api/stats':
            self.serve_stats()
            return
        elif path == '/api/search':
            self.serve_search(parsed_path.query)
            return
        elif path == '/api/daemon-status':
            self.serve_daemon_status()
            return
        elif path == '/api/conversation':
            self.serve_conversation(parsed_path.query)
            return
        elif path == '/api/config':
            self.serve_config(parsed_path.query)
            return
        elif path == '/api/config/list':
            self.serve_config_list()
            return
        elif path == '/api/mcp/list':
            self.serve_mcp_list()
            return
        elif path == '/api/daemons/list':
            self.serve_daemons_list()
            return
        elif path == '/api/universal-watcher/stats':
            self.serve_universal_watcher_stats()
            return
        elif path == '/api/arsenal/list':
            self.serve_arsenal_list()
            return
        elif path == '/api/arsenal/save':
            params = parse_qs(parsed_path.query)
            self.serve_arsenal_save(params)
            return
        elif path == '/api/hooks/list':
            self.serve_hooks_list()
            return
        elif path == '/api/templates/list':
            self.serve_templates_list()
            return
        elif path == '/api/model/current':
            self.serve_current_model()
            return
        elif path == '/api/3d/handoffs':
            self.serve_3d_handoffs()
            return
        elif path == '/api/3d/stats':
            self.serve_3d_stats()
            return
        elif path == '/api/patterns/search':
            self.serve_pattern_search(parsed_path.query)
            return
        elif path == '/api/patterns/categories':
            self.serve_pattern_categories()
            return
        elif path == '/api/patterns/by-category':
            self.serve_patterns_by_category(parsed_path.query)
            return
        elif path == '/api/compare':
            self.serve_compare(parsed_path.query)
            return
        elif path == '/api/golden/handoffs':
            self.serve_golden_handoffs()
            return
        elif path == '/api/storage/stats':
            self.serve_storage_stats()
            return
        elif path.startswith('/api/storage/list/'):
            location_key = path.split('/')[-1]
            self.serve_storage_list(location_key)
            return
        elif path == '/api/history/list':
            self.serve_history_list(parsed_path.query)
            return
        elif path == '/api/history/search':
            self.serve_history_search(parsed_path.query)
            return
        elif path == '/api/unified/list':
            self.serve_unified_list(parsed_path.query)
            return
        elif path == '/api/unified/search':
            self.serve_unified_search(parsed_path.query)
            return
        elif path == '/api/unified/tags':
            self.serve_unified_tags()
            return
        elif path == '/api/unified/timeline':
            self.serve_unified_timeline(parsed_path.query)
            return
        elif path == '/api/unified/related':
            self.serve_unified_related(parsed_path.query)
            return
        elif path == '/api/keys/list':
            self.serve_api_keys_list()
            return
        elif path == '/api/workspace/sessions/stats':
            self.serve_session_stats()
            return
        elif path.startswith('/api/workspace/sessions/'):
            # GET /api/workspace/sessions/{session_id}
            session_id = path.split('/')[-1]
            self.serve_session_info(session_id)
            return
        # Workspace Storage API (exported sessions)
        elif path == '/api/workspace/storage/list':
            self.serve_workspace_storage_list(parsed_path.query)
            return
        elif path == '/api/workspace/storage/stats':
            self.serve_workspace_storage_stats()
            return
        elif path == '/api/workspace/timeline':
            self.serve_workspace_timeline()
            return
        elif path == '/api/workspace/search':
            self.serve_workspace_search(parsed_path.query)
            return
        elif path.startswith('/api/workspace/storage/'):
            # GET /api/workspace/storage/{session_id}
            session_id = path.split('/')[-1]
            self.serve_workspace_session_detail(session_id)
            return
        # Webhook & Triggers GET endpoints
        elif path == '/api/webhooks/list':
            self.serve_webhooks_list()
            return
        elif path == '/api/triggers/pending':
            self.serve_pending_triggers()
            return
        # TODO System API
        elif path == '/api/todos/unified':
            self.serve_todos_unified(parsed_path.query)
            return
        elif path == '/api/todos/stats':
            self.serve_todos_stats()
            return
        elif path.startswith('/api/todos/'):
            parts = path.split('/')
            if len(parts) >= 4:
                agent_id = parts[3]  # koda, cairn, prax
                self.serve_todos(agent_id, parsed_path.query)
            return
        # Phase 4C.2: Canvas Collaboration GET endpoints
        # Calendar API
        elif path == '/api/calendar/combined':
            self.serve_calendar_combined(parsed_path.query)
            return
        elif path.startswith('/api/calendar/'):
            parts = path.split('/')
            if len(parts) >= 4:
                agent_id = parts[3]  # koda, cairn, prax, user
                self.serve_calendar(agent_id, parsed_path.query)
            return
        # Inbox Collab API
        elif path.startswith('/api/inbox/'):
            parts = path.split('/')
            if len(parts) >= 4:
                agent_id = parts[3]  # koda, cairn, prax
                self.serve_inbox(agent_id, parsed_path.query)
            return
        elif path.startswith('/api/canvas/') and '/export' in path:
            parts = path.split('/')
            session_id = parts[3]
            self.serve_canvas_export(session_id, parsed_path.query)
            return
        elif path.startswith('/api/canvas/'):
            # GET /api/canvas/{session_id}
            session_id = path.split('/')[-1]
            self.serve_canvas_document(session_id)
            return
        elif path == '/' or path == '/index.html':
            self.serve_dashboard()
            return
        elif path == '/chat_test.html':
            self.serve_chat_test()
            return
        elif path == '/test_tabs.html':
            self.serve_test_tabs()
            return
        # Demo sharing endpoints
        elif path == '/demo':
            self.serve_demo_page(parsed_path.query)
            return
        elif path == '/api/demo/create':
            self.serve_demo_create(parsed_path.query)
            return
        elif path == '/api/demo/join':
            self.serve_demo_join(parsed_path.query)
            return
        elif path == '/api/demo/info':
            self.serve_demo_info(parsed_path.query)
            return
        elif path == '/api/demo/link':
            self.serve_demo_link(parsed_path.query)
            return
        elif path == '/api/demo/list':
            self.serve_demo_list()
            return
        # File Upload API
        elif path == '/api/files/list':
            self.serve_files_list(parsed_path.query)
            return
        elif path.startswith('/api/files/') and '/thumbnail' in path:
            file_id = path.split('/')[3]
            self.serve_file_thumbnail(file_id)
            return
        elif path.startswith('/api/files/') and '/content' in path:
            file_id = path.split('/')[3]
            self.serve_file_content(file_id)
            return
        elif path.startswith('/api/files/') and path.count('/') == 3:
            file_id = path.split('/')[-1]
            self.serve_file_info(file_id)
            return
        else:
            # Return 404 for other paths
            self.send_error(404, "Not found")

    def do_OPTIONS(self):
        """Handle OPTIONS requests for CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        """Handle POST requests."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        # Handle file upload FIRST (before reading body as JSON)
        if path == '/api/files/upload':
            self.handle_file_upload()
            return

        # Get content length and read body for JSON endpoints
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')

        try:
            data = json.loads(body) if body else {}
        except:
            data = {}

        # API Endpoints
        if path == '/api/config/save':
            self.save_config(data)
            return
        elif path == '/api/mcp/toggle':
            self.toggle_mcp_server(data)
            return
        elif path == '/api/mcp/add':
            self.add_mcp_server(data)
            return
        elif path == '/api/mcp/remove':
            self.remove_mcp_server(data)
            return
        elif path == '/api/daemon/start':
            self.start_daemon(data)
            return
        elif path == '/api/daemon/stop':
            self.stop_daemon(data)
            return
        elif path == '/api/daemon/restart':
            self.restart_daemon(data)
            return
        elif path == '/api/arsenal/activate':
            self.activate_arsenal_config(data)
            return
        elif path == '/api/arsenal/create':
            self.create_arsenal_preset(data)
            return
        elif path == '/api/hooks/toggle':
            self.toggle_hook(data)
            return
        elif path == '/api/templates/load':
            self.load_template(data)
            return
        elif path == '/api/model/set':
            self.set_model(data)
            return
        elif path == '/api/3d/search':
            self.search_3d_handoffs(data)
            return
        elif path == '/api/3d/handoff/decompress':
            self.decompress_3d_handoff(data)
            return
        elif path == '/api/unified/rebuild-index':
            self.rebuild_unified_index()
            return
        elif path == '/api/assistant/chat':
            self.serve_assistant_chat(data)
            return
        elif path == '/api/golden/restore':
            self.restore_golden_plan(data)
            return
        elif path == '/api/agent/chat':
            self.agent_chat(data)
            return
        elif path == '/api/agent/load-document':
            self.agent_load_document(data)
            return
        elif path.startswith('/api/storage/open/'):
            location_key = path.split('/')[-1]
            self.open_storage_location(location_key)
            return
        elif path.startswith('/api/workspace/storage/delete/'):
            filename = path.split('/')[-1]
            self.delete_workspace_export(filename)
            return
        elif path == '/api/keys/save':
            self.save_api_keys(data)
            return
        elif path == '/api/workspace/sessions/create':
            self.create_workspace_session(data)
            return
        elif path == '/api/workspace/sessions/join':
            self.join_workspace_session(data)
            return
        # Phase 4C.2: Canvas Collaboration API
        elif path.startswith('/api/canvas/') and '/create' in path:
            session_id = path.split('/')[3]
            self.create_canvas_document(session_id, data)
            return
        elif path.startswith('/api/canvas/') and '/section' in path:
            session_id = path.split('/')[3]
            self.add_canvas_section(session_id, data)
            return
        elif path.startswith('/api/canvas/') and '/edit' in path:
            session_id = path.split('/')[3]
            self.edit_canvas_section(session_id, data)
            return
        # Inbox Collab API - Send message
        elif path == '/api/inbox/send':
            self.send_inbox_message(data)
            return
        elif path == '/api/inbox/mark-read':
            self.mark_inbox_read(data)
            return
        # Calendar API - Create/Update event
        elif path == '/api/calendar/event':
            self.create_calendar_event(data)
            return
        elif path == '/api/calendar/delete':
            self.delete_calendar_event(data)
            return
        # Task Assignment API (Prax -> Koda/Cairn)
        elif path == '/api/tasks/assign':
            self.assign_task(data)
            return
        # Webhook Configuration API
        elif path == '/api/webhooks/save':
            self.save_webhook(data)
            return
        elif path == '/api/webhooks/delete':
            self.delete_webhook(data)
            return
        elif path == '/api/webhooks/test':
            self.test_webhook(data)
            return
        # Calendar Triggers API
        elif path == '/api/triggers/process':
            self.process_calendar_triggers(data)
            return
        # TODO System API
        elif path == '/api/todos/create':
            self.create_todo(data)
            return
        elif path == '/api/todos/update':
            self.update_todo(data)
            return
        elif path == '/api/todos/delete':
            self.delete_todo(data)
            return
        elif path == '/api/todos/split-prd':
            self.split_prd_to_todos(data)
            return
        elif path == '/api/todos/sync-calendar':
            self.sync_todo_to_calendar(data)
            return
        elif path == '/api/todos/sync-inbox':
            self.sync_todo_to_inbox(data)
            return
        elif path == '/api/todos/bulk-update':
            self.bulk_update_todos(data)
            return
        # File API (upload handled before body read)
        elif path.startswith('/api/files/') and '/extract' in path:
            file_id = path.split('/')[3]
            self.extract_file_to_memory(file_id)
            return
        elif path.startswith('/api/files/') and '/to-canvas' in path:
            file_id = path.split('/')[3]
            self.convert_file_to_canvas(file_id, data)
            return
        elif path.startswith('/api/files/') and '/delete' in path:
            file_id = path.split('/')[3]
            self.delete_file(file_id)
            return
        # Video Editing API (FFmpeg)
        elif path == '/api/video/trim':
            self.video_trim(data)
            return
        elif path == '/api/video/concat':
            self.video_concat(data)
            return
        elif path == '/api/video/extract-audio':
            self.video_extract_audio(data)
            return
        elif path == '/api/video/add-text':
            self.video_add_text(data)
            return
        elif path == '/api/video/resize':
            self.video_resize(data)
            return
        # Agent File API
        elif path == '/api/files/for-agent':
            self.serve_files_for_agent(data)
            return
        elif path == '/api/files/agent-request':
            self.agent_file_request(data)
            return
        else:
            self.send_error(404, "Not found")

    def serve_json(self, data, status=200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())

    def serve_dashboard(self):
        """Serve the main dashboard HTML."""
        dashboard_path = Path(__file__).parent / "claude_dashboard.html"
        if not dashboard_path.exists():
            # Try alternative path
            dashboard_path = Path.cwd() / "claude_dashboard.html"

        if dashboard_path.exists():
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            with open(dashboard_path, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_error(404, f"Dashboard not found. Looked in: {Path(__file__).parent}, {Path.cwd()}")

    def serve_chat_test(self):
        """Serve the chat test page."""
        test_path = Path(__file__).parent / "chat_test.html"
        if test_path.exists():
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            with open(test_path, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_error(404, "Chat test page not found")

    def serve_test_tabs(self):
        """Serve the tabs test page."""
        test_path = Path(__file__).parent / "test_tabs.html"
        if test_path.exists():
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            with open(test_path, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_error(404, "Tabs test page not found")

    # =========================================================================
    # FILE UPLOAD & MANAGEMENT API
    # =========================================================================

    def get_file_type_category(self, filename):
        """Determine file type category from filename."""
        ext = Path(filename).suffix.lower()

        doc_exts = {'.pdf', '.docx', '.doc', '.txt', '.md', '.rtf', '.odt'}
        code_exts = {'.py', '.js', '.ts', '.jsx', '.tsx', '.go', '.rs', '.java',
                     '.c', '.cpp', '.h', '.hpp', '.cs', '.rb', '.php', '.swift',
                     '.kt', '.scala', '.r', '.sql', '.sh', '.bash', '.zsh',
                     '.json', '.yaml', '.yml', '.toml', '.xml', '.html', '.css'}
        image_exts = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.bmp', '.ico'}
        video_exts = {'.mp4', '.mov', '.avi', '.webm', '.mkv', '.m4v', '.wmv'}
        spec_exts = {'.prd', '.spec', '.req', '.feature'}

        if ext in doc_exts:
            return 'documents'
        elif ext in code_exts:
            return 'code'
        elif ext in image_exts:
            return 'images'
        elif ext in video_exts:
            return 'videos'
        elif ext in spec_exts:
            return 'specs'
        else:
            return 'documents'  # Default to documents

    def load_uploads_index(self):
        """Load the uploads index."""
        try:
            if UPLOADS_INDEX_FILE.exists():
                with open(UPLOADS_INDEX_FILE, 'r') as f:
                    return json.load(f)
            return {'files': [], 'version': '1.0'}
        except Exception as e:
            print(f"[Files] Error loading index: {e}")
            return {'files': [], 'version': '1.0'}

    def save_uploads_index(self, index_data):
        """Save the uploads index."""
        try:
            UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
            with open(UPLOADS_INDEX_FILE, 'w') as f:
                json.dump(index_data, f, indent=2)
        except Exception as e:
            print(f"[Files] Error saving index: {e}")

    def handle_file_upload(self):
        """Handle multipart file upload."""
        try:
            content_type = self.headers.get('Content-Type', '')

            if 'multipart/form-data' not in content_type:
                self.serve_json({'error': 'Expected multipart/form-data'}, status=400)
                return

            # Get boundary from content type
            boundary = None
            for part in content_type.split(';'):
                part = part.strip()
                if part.startswith('boundary='):
                    boundary = part[9:].strip('"\'')
                    break

            if not boundary:
                self.serve_json({'error': 'No boundary in content-type'}, status=400)
                return

            content_length = int(self.headers.get('Content-Length', 0))
            print(f"[Files] Upload: length={content_length}, boundary={boundary[:20]}...", flush=True)

            # Read body in chunks
            body = b''
            remaining = content_length
            while remaining > 0:
                chunk_size = min(remaining, 65536)
                chunk = self.rfile.read(chunk_size)
                if not chunk:
                    break
                body += chunk
                remaining -= len(chunk)

            print(f"[Files] Read {len(body)} bytes", flush=True)

            # Parse multipart manually
            boundary_bytes = f'--{boundary}'.encode()
            parts = body.split(boundary_bytes)

            uploaded_files = []

            for part in parts:
                # Skip empty parts and closing boundary
                if not part.strip() or part.strip() == b'--':
                    continue

                # Find header/body separator
                header_end = part.find(b'\r\n\r\n')
                if header_end == -1:
                    continue

                headers_raw = part[:header_end].decode('utf-8', errors='ignore')
                file_content = part[header_end + 4:]

                # Remove trailing \r\n
                if file_content.endswith(b'\r\n'):
                    file_content = file_content[:-2]

                # Check for filename in Content-Disposition
                filename_match = None
                for line in headers_raw.split('\r\n'):
                    if 'filename="' in line:
                        start = line.find('filename="') + 10
                        end = line.find('"', start)
                        if end > start:
                            filename_match = line[start:end]
                            break

                if not filename_match:
                    continue

                print(f"[Files] Found file: {filename_match}, size={len(file_content)}", flush=True)

                # Determine category and save
                category = self.get_file_type_category(filename_match)
                file_id = str(uuid.uuid4())[:8]
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                safe_filename = f"{timestamp}_{filename_match.replace(' ', '_')}"

                save_dir = UPLOADS_DIR / category
                save_dir.mkdir(parents=True, exist_ok=True)
                save_path = save_dir / safe_filename

                with open(save_path, 'wb') as f:
                    f.write(file_content)

                # Generate thumbnail for images/videos
                thumbnail_path = None
                if category == 'images':
                    thumbnail_path = self.generate_image_thumbnail(save_path)
                elif category == 'videos':
                    thumbnail_path = self.generate_video_thumbnail(save_path)

                # Extract text content for documents/code
                extracted_text = None
                if category in ['documents', 'code', 'specs']:
                    extracted_text = self.extract_text_content(save_path, category)

                # Create file metadata
                file_meta = {
                    'id': file_id,
                    'filename': filename_match,
                    'saved_as': safe_filename,
                    'category': category,
                    'path': str(save_path),
                    'size': len(file_content),
                    'uploaded': datetime.now().isoformat(),
                    'thumbnail': str(thumbnail_path) if thumbnail_path else None,
                    'extracted_preview': extracted_text[:500] if extracted_text else None,
                    'indexed_to_memory': False
                }

                # Update index
                index = self.load_uploads_index()
                index['files'].append(file_meta)
                self.save_uploads_index(index)

                uploaded_files.append(file_meta)
                print(f"[Files] Uploaded: {filename_match} -> {save_path}")

            if uploaded_files:
                self.serve_json({
                    'ok': True,
                    'files': uploaded_files,
                    'count': len(uploaded_files)
                })
            else:
                self.serve_json({'error': 'No files found in request'}, status=400)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.serve_json({'error': str(e)}, status=500)

    def generate_image_thumbnail(self, image_path):
        """Generate thumbnail for an image."""
        try:
            from PIL import Image

            thumb_dir = UPLOADS_DIR / 'thumbnails'
            thumb_dir.mkdir(parents=True, exist_ok=True)

            img = Image.open(image_path)
            img.thumbnail((200, 200), Image.Resampling.LANCZOS)

            thumb_name = f"thumb_{Path(image_path).stem}.jpg"
            thumb_path = thumb_dir / thumb_name

            # Convert to RGB if necessary (for PNG with alpha)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')

            img.save(thumb_path, 'JPEG', quality=85)
            return thumb_path

        except ImportError:
            print("[Files] PIL not installed, skipping thumbnail")
            return None
        except Exception as e:
            print(f"[Files] Thumbnail generation failed: {e}")
            return None

    def generate_video_thumbnail(self, video_path):
        """Generate thumbnail for a video using FFmpeg."""
        try:
            thumb_dir = UPLOADS_DIR / 'thumbnails'
            thumb_dir.mkdir(parents=True, exist_ok=True)

            thumb_name = f"thumb_{Path(video_path).stem}.jpg"
            thumb_path = thumb_dir / thumb_name

            # Get duration first
            probe_cmd = ['ffprobe', '-v', 'error', '-show_entries',
                        'format=duration', '-of', 'csv=p=0', str(video_path)]
            result = subprocess.run(probe_cmd, capture_output=True, text=True)

            duration = 10  # Default
            try:
                duration = float(result.stdout.strip())
            except:
                pass

            # Extract frame at 10% mark
            timestamp = duration * 0.1

            cmd = ['ffmpeg', '-y', '-ss', str(timestamp), '-i', str(video_path),
                   '-vframes', '1', '-vf', 'scale=200:-1', str(thumb_path)]

            subprocess.run(cmd, capture_output=True)

            if thumb_path.exists():
                return thumb_path
            return None

        except Exception as e:
            print(f"[Files] Video thumbnail failed: {e}")
            return None

    def extract_text_content(self, file_path, category):
        """Extract text content from a file."""
        try:
            file_path = Path(file_path)
            ext = file_path.suffix.lower()

            # Plain text and code files
            if ext in {'.txt', '.md', '.py', '.js', '.ts', '.jsx', '.tsx', '.go',
                      '.rs', '.java', '.c', '.cpp', '.h', '.cs', '.rb', '.php',
                      '.json', '.yaml', '.yml', '.toml', '.xml', '.html', '.css',
                      '.sh', '.bash', '.sql', '.prd', '.spec', '.req', '.feature'}:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()

            # PDF extraction
            elif ext == '.pdf':
                try:
                    import pypdf
                    reader = pypdf.PdfReader(str(file_path))
                    text = []
                    for page in reader.pages:
                        text.append(page.extract_text() or '')
                    return '\n'.join(text)
                except ImportError:
                    try:
                        import PyPDF2
                        reader = PyPDF2.PdfReader(str(file_path))
                        text = []
                        for page in reader.pages:
                            text.append(page.extract_text() or '')
                        return '\n'.join(text)
                    except ImportError:
                        print("[Files] PDF extraction requires pypdf or PyPDF2")
                        return None

            # DOCX extraction
            elif ext == '.docx':
                try:
                    from docx import Document
                    doc = Document(str(file_path))
                    paragraphs = [p.text for p in doc.paragraphs]
                    return '\n'.join(paragraphs)
                except ImportError:
                    print("[Files] DOCX extraction requires python-docx")
                    return None

            return None

        except Exception as e:
            print(f"[Files] Text extraction failed: {e}")
            return None

    def serve_files_list(self, query_string):
        """List uploaded files with optional filtering."""
        try:
            params = parse_qs(query_string) if query_string else {}
            category = params.get('category', [None])[0]
            limit = int(params.get('limit', ['100'])[0])
            offset = int(params.get('offset', ['0'])[0])

            index = self.load_uploads_index()
            files = index.get('files', [])

            # Apply category filter
            if category:
                files = [f for f in files if f.get('category') == category]

            # Sort by upload date (newest first)
            files.sort(key=lambda x: x.get('uploaded', ''), reverse=True)

            # Paginate
            total = len(files)
            files = files[offset:offset + limit]

            self.serve_json({
                'ok': True,
                'files': files,
                'total': total,
                'limit': limit,
                'offset': offset
            })

        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    def serve_file_info(self, file_id):
        """Get info for a specific file."""
        try:
            index = self.load_uploads_index()

            for f in index.get('files', []):
                if f.get('id') == file_id:
                    self.serve_json({'ok': True, 'file': f})
                    return

            self.serve_json({'error': 'File not found'}, status=404)

        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    def serve_file_thumbnail(self, file_id):
        """Serve thumbnail for a file."""
        try:
            index = self.load_uploads_index()

            for f in index.get('files', []):
                if f.get('id') == file_id:
                    thumb_path = f.get('thumbnail')
                    if thumb_path and Path(thumb_path).exists():
                        self.send_response(200)
                        self.send_header('Content-Type', 'image/jpeg')
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.end_headers()
                        with open(thumb_path, 'rb') as img:
                            self.wfile.write(img.read())
                        return
                    break

            self.send_error(404, "Thumbnail not found")

        except Exception as e:
            self.send_error(500, str(e))

    def serve_file_content(self, file_id):
        """Serve file content for download/preview."""
        try:
            index = self.load_uploads_index()

            for f in index.get('files', []):
                if f.get('id') == file_id:
                    file_path = Path(f.get('path', ''))
                    if file_path.exists():
                        # Determine content type
                        ext = file_path.suffix.lower()
                        content_types = {
                            '.pdf': 'application/pdf',
                            '.json': 'application/json',
                            '.txt': 'text/plain',
                            '.md': 'text/markdown',
                            '.html': 'text/html',
                            '.css': 'text/css',
                            '.js': 'application/javascript',
                            '.png': 'image/png',
                            '.jpg': 'image/jpeg',
                            '.jpeg': 'image/jpeg',
                            '.gif': 'image/gif',
                            '.svg': 'image/svg+xml',
                            '.mp4': 'video/mp4',
                            '.webm': 'video/webm',
                            '.mov': 'video/quicktime',
                        }
                        content_type = content_types.get(ext, 'application/octet-stream')

                        self.send_response(200)
                        self.send_header('Content-Type', content_type)
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.send_header('Content-Disposition',
                                        f'inline; filename="{f.get("filename", "file")}"')
                        self.end_headers()

                        with open(file_path, 'rb') as content:
                            self.wfile.write(content.read())
                        return
                    break

            self.send_error(404, "File not found")

        except Exception as e:
            self.send_error(500, str(e))

    def extract_file_to_memory(self, file_id):
        """Extract file content and add to memory browser index."""
        try:
            index = self.load_uploads_index()
            file_meta = None
            file_idx = None

            for i, f in enumerate(index.get('files', [])):
                if f.get('id') == file_id:
                    file_meta = f
                    file_idx = i
                    break

            if not file_meta:
                self.serve_json({'error': 'File not found'}, status=404)
                return

            file_path = Path(file_meta.get('path', ''))
            if not file_path.exists():
                self.serve_json({'error': 'File path not found'}, status=404)
                return

            # Extract full text content
            extracted_text = self.extract_text_content(file_path, file_meta.get('category', ''))

            if not extracted_text:
                self.serve_json({'error': 'Could not extract text from file'}, status=400)
                return

            # Create unified history entry
            memory_entry = {
                'type': 'uploaded_file',
                'id': f'file-{file_id}',
                'timestamp': int(datetime.now().timestamp() * 1000),
                'timeFormatted': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'file_type': file_meta.get('category', 'document'),
                'filename': file_meta.get('filename', 'unknown'),
                'path': str(file_path),
                'preview': extracted_text[:500] if extracted_text else '',
                'display': f"[File] {file_meta.get('filename', 'unknown')}",
                'tags': ['uploaded', file_meta.get('category', 'file')],
                'searchable_content': extracted_text,
                'category': 'uploaded_file'
            }

            # Load and update unified history index
            try:
                unified_index = {'items': [], 'counts': {}}
                if UNIFIED_HISTORY_INDEX.exists():
                    with open(UNIFIED_HISTORY_INDEX, 'r') as f:
                        unified_index = json.load(f)

                # Check if already indexed
                existing_ids = {item.get('id') for item in unified_index.get('items', [])}
                if memory_entry['id'] not in existing_ids:
                    unified_index['items'].append(memory_entry)

                    # Update counts
                    counts = unified_index.get('counts', {})
                    counts['uploaded_file'] = counts.get('uploaded_file', 0) + 1
                    unified_index['counts'] = counts

                    with open(UNIFIED_HISTORY_INDEX, 'w') as f:
                        json.dump(unified_index, f, indent=2)

                    print(f"[Files] Indexed to memory: {file_meta.get('filename')}")
            except Exception as e:
                print(f"[Files] Failed to update unified index: {e}")

            # Mark as indexed in uploads index
            index['files'][file_idx]['indexed_to_memory'] = True
            index['files'][file_idx]['extracted_preview'] = extracted_text[:500]
            self.save_uploads_index(index)

            self.serve_json({
                'ok': True,
                'message': 'File extracted and indexed to memory',
                'entry': memory_entry
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.serve_json({'error': str(e)}, status=500)

    def delete_file(self, file_id):
        """Delete an uploaded file."""
        try:
            index = self.load_uploads_index()

            new_files = []
            deleted = None

            for f in index.get('files', []):
                if f.get('id') == file_id:
                    deleted = f
                    # Delete actual file
                    file_path = Path(f.get('path', ''))
                    if file_path.exists():
                        file_path.unlink()
                    # Delete thumbnail
                    thumb_path = f.get('thumbnail')
                    if thumb_path and Path(thumb_path).exists():
                        Path(thumb_path).unlink()
                else:
                    new_files.append(f)

            if deleted:
                index['files'] = new_files
                self.save_uploads_index(index)

                # Remove from unified index if exists
                try:
                    if UNIFIED_HISTORY_INDEX.exists():
                        with open(UNIFIED_HISTORY_INDEX, 'r') as f:
                            unified_index = json.load(f)

                        unified_index['items'] = [
                            item for item in unified_index.get('items', [])
                            if item.get('id') != f'file-{file_id}'
                        ]

                        with open(UNIFIED_HISTORY_INDEX, 'w') as f:
                            json.dump(unified_index, f, indent=2)
                except Exception as e:
                    print(f"[Files] Failed to remove from unified index: {e}")

                self.serve_json({'ok': True, 'deleted': deleted})
            else:
                self.serve_json({'error': 'File not found'}, status=404)

        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    def convert_file_to_canvas(self, file_id, data):
        """Convert an uploaded file to a canvas document section."""
        try:
            # Get file metadata
            index = self.load_uploads_index()
            file_meta = None
            for f in index.get('files', []):
                if f.get('id') == file_id:
                    file_meta = f
                    break

            if not file_meta:
                self.serve_json({'error': 'File not found'}, status=404)
                return

            file_path = Path(file_meta.get('path', ''))
            if not file_path.exists():
                self.serve_json({'error': 'File path not found'}, status=404)
                return

            category = file_meta.get('category', 'document')
            filename = file_meta.get('filename', 'untitled')
            ext = file_path.suffix.lower()

            # Extract content based on file type
            content = ''
            section_type = 'markdown'

            # Text-based files
            text_extensions = ['.txt', '.md', '.json', '.xml', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf', '.log', '.csv', '.tsv']
            code_extensions = ['.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.c', '.cpp', '.h', '.hpp', '.cs', '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.scala', '.r', '.sql', '.sh', '.bash', '.zsh', '.ps1', '.html', '.css', '.scss', '.less', '.vue', '.svelte']

            if ext in text_extensions:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                section_type = 'markdown'

            elif ext in code_extensions:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                section_type = 'code'
                # Wrap in code fence with language hint
                lang = ext[1:]  # Remove the dot
                lang_map = {'js': 'javascript', 'ts': 'typescript', 'py': 'python', 'rb': 'ruby', 'rs': 'rust', 'kt': 'kotlin'}
                lang = lang_map.get(lang, lang)
                content = f"```{lang}\n{content}\n```"

            elif ext == '.pdf':
                # Try to extract text from PDF
                content = self._extract_pdf_text(file_path)
                if not content:
                    content = f"[PDF file: {filename} - Text extraction failed. View original file.]"
                section_type = 'markdown'

            elif category == 'images':
                # For images, create a reference
                content = f"![{filename}](/api/files/{file_id}/content)\n\n*Image file: {filename}*"
                section_type = 'markdown'

            elif category == 'videos':
                content = f"[Video: {filename}](/api/files/{file_id}/content)\n\n*Video file: {filename}*"
                section_type = 'markdown'

            else:
                # Try to read as text
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                except:
                    content = f"[Binary file: {filename} - Cannot display content]"
                section_type = 'markdown'

            # Get session_id from request data if provided
            session_id = data.get('session_id')

            # Return the extracted content for client-side handling
            self.serve_json({
                'ok': True,
                'file_id': file_id,
                'filename': filename,
                'content': content,
                'section_type': section_type,
                'suggested_name': file_path.stem  # Filename without extension
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.serve_json({'error': str(e)}, status=500)

    def _extract_pdf_text(self, file_path):
        """Extract text from PDF file."""
        try:
            # Try pdfplumber first (better quality)
            try:
                import pdfplumber
                text_parts = []
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages[:20]:  # Limit to first 20 pages
                        page_text = page.extract_text()
                        if page_text:
                            text_parts.append(page_text)
                if text_parts:
                    return '\n\n---\n\n'.join(text_parts)
            except ImportError:
                pass

            # Fallback to PyPDF2
            try:
                from PyPDF2 import PdfReader
                reader = PdfReader(file_path)
                text_parts = []
                for page in reader.pages[:20]:  # Limit to first 20 pages
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                if text_parts:
                    return '\n\n---\n\n'.join(text_parts)
            except ImportError:
                pass

            return None
        except Exception as e:
            print(f"[PDF] Text extraction failed: {e}")
            return None

    # =========================================================================
    # VIDEO EDITING API (FFmpeg)
    # =========================================================================

    def video_trim(self, data):
        """Trim a video to start/end time."""
        try:
            file_id = data.get('file_id')
            start_time = data.get('start_time', 0)
            end_time = data.get('end_time')

            if not file_id or not end_time:
                self.serve_json({'error': 'Missing file_id or end_time'}, status=400)
                return

            # Get file path
            index = self.load_uploads_index()
            file_meta = None
            for f in index.get('files', []):
                if f.get('id') == file_id:
                    file_meta = f
                    break

            if not file_meta:
                self.serve_json({'error': 'File not found'}, status=404)
                return

            input_path = Path(file_meta.get('path', ''))
            if not input_path.exists():
                self.serve_json({'error': 'Source file not found'}, status=404)
                return

            # Create output filename
            output_name = f"trimmed_{input_path.stem}_{int(start_time)}_{int(end_time)}{input_path.suffix}"
            output_path = UPLOADS_DIR / 'videos' / output_name

            # Run FFmpeg
            cmd = ['ffmpeg', '-y', '-i', str(input_path),
                   '-ss', str(start_time), '-to', str(end_time),
                   '-c', 'copy', str(output_path)]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if output_path.exists():
                # Add to index
                new_id = str(uuid.uuid4())[:8]
                new_meta = {
                    'id': new_id,
                    'filename': output_name,
                    'saved_as': output_name,
                    'category': 'videos',
                    'path': str(output_path),
                    'size': output_path.stat().st_size,
                    'uploaded': datetime.now().isoformat(),
                    'source_file': file_id,
                    'operation': 'trim'
                }

                # Generate thumbnail
                thumb = self.generate_video_thumbnail(output_path)
                if thumb:
                    new_meta['thumbnail'] = str(thumb)

                index['files'].append(new_meta)
                self.save_uploads_index(index)

                self.serve_json({'ok': True, 'file': new_meta})
            else:
                self.serve_json({
                    'error': 'FFmpeg failed',
                    'stderr': result.stderr
                }, status=500)

        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    def video_concat(self, data):
        """Concatenate multiple videos."""
        try:
            file_ids = data.get('file_ids', [])

            if len(file_ids) < 2:
                self.serve_json({'error': 'Need at least 2 files'}, status=400)
                return

            index = self.load_uploads_index()
            input_files = []

            for fid in file_ids:
                for f in index.get('files', []):
                    if f.get('id') == fid:
                        path = Path(f.get('path', ''))
                        if path.exists():
                            input_files.append(path)
                        break

            if len(input_files) < 2:
                self.serve_json({'error': 'Not enough valid files found'}, status=400)
                return

            # Create concat file
            concat_file = UPLOADS_DIR / 'videos' / 'concat_list.txt'
            with open(concat_file, 'w') as f:
                for p in input_files:
                    f.write(f"file '{p}'\n")

            # Output filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_name = f"concat_{timestamp}.mp4"
            output_path = UPLOADS_DIR / 'videos' / output_name

            # Run FFmpeg concat
            cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0',
                   '-i', str(concat_file), '-c', 'copy', str(output_path)]

            result = subprocess.run(cmd, capture_output=True, text=True)

            # Clean up concat file
            concat_file.unlink()

            if output_path.exists():
                new_id = str(uuid.uuid4())[:8]
                new_meta = {
                    'id': new_id,
                    'filename': output_name,
                    'saved_as': output_name,
                    'category': 'videos',
                    'path': str(output_path),
                    'size': output_path.stat().st_size,
                    'uploaded': datetime.now().isoformat(),
                    'source_files': file_ids,
                    'operation': 'concat'
                }

                thumb = self.generate_video_thumbnail(output_path)
                if thumb:
                    new_meta['thumbnail'] = str(thumb)

                index['files'].append(new_meta)
                self.save_uploads_index(index)

                self.serve_json({'ok': True, 'file': new_meta})
            else:
                self.serve_json({
                    'error': 'FFmpeg concat failed',
                    'stderr': result.stderr
                }, status=500)

        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    def video_extract_audio(self, data):
        """Extract audio from video."""
        try:
            file_id = data.get('file_id')
            output_format = data.get('format', 'mp3')

            if not file_id:
                self.serve_json({'error': 'Missing file_id'}, status=400)
                return

            index = self.load_uploads_index()
            file_meta = None
            for f in index.get('files', []):
                if f.get('id') == file_id:
                    file_meta = f
                    break

            if not file_meta:
                self.serve_json({'error': 'File not found'}, status=404)
                return

            input_path = Path(file_meta.get('path', ''))
            output_name = f"{input_path.stem}_audio.{output_format}"
            output_path = UPLOADS_DIR / 'documents' / output_name

            cmd = ['ffmpeg', '-y', '-i', str(input_path),
                   '-vn', '-acodec', 'libmp3lame' if output_format == 'mp3' else 'copy',
                   str(output_path)]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if output_path.exists():
                new_id = str(uuid.uuid4())[:8]
                new_meta = {
                    'id': new_id,
                    'filename': output_name,
                    'saved_as': output_name,
                    'category': 'documents',
                    'path': str(output_path),
                    'size': output_path.stat().st_size,
                    'uploaded': datetime.now().isoformat(),
                    'source_file': file_id,
                    'operation': 'extract_audio'
                }

                index['files'].append(new_meta)
                self.save_uploads_index(index)

                self.serve_json({'ok': True, 'file': new_meta})
            else:
                self.serve_json({'error': 'FFmpeg failed', 'stderr': result.stderr}, status=500)

        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    def video_add_text(self, data):
        """Add text overlay to video."""
        try:
            file_id = data.get('file_id')
            text = data.get('text', '')
            position = data.get('position', 'bottom')  # top, center, bottom
            font_size = data.get('font_size', 24)

            if not file_id or not text:
                self.serve_json({'error': 'Missing file_id or text'}, status=400)
                return

            index = self.load_uploads_index()
            file_meta = None
            for f in index.get('files', []):
                if f.get('id') == file_id:
                    file_meta = f
                    break

            if not file_meta:
                self.serve_json({'error': 'File not found'}, status=404)
                return

            input_path = Path(file_meta.get('path', ''))
            output_name = f"text_{input_path.stem}{input_path.suffix}"
            output_path = UPLOADS_DIR / 'videos' / output_name

            # Position mapping
            y_pos = {'top': '10', 'center': '(h-text_h)/2', 'bottom': 'h-text_h-10'}

            drawtext = f"drawtext=text='{text}':fontsize={font_size}:fontcolor=white:x=(w-text_w)/2:y={y_pos.get(position, 'h-text_h-10')}"

            cmd = ['ffmpeg', '-y', '-i', str(input_path),
                   '-vf', drawtext, '-codec:a', 'copy', str(output_path)]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if output_path.exists():
                new_id = str(uuid.uuid4())[:8]
                new_meta = {
                    'id': new_id,
                    'filename': output_name,
                    'saved_as': output_name,
                    'category': 'videos',
                    'path': str(output_path),
                    'size': output_path.stat().st_size,
                    'uploaded': datetime.now().isoformat(),
                    'source_file': file_id,
                    'operation': 'add_text'
                }

                thumb = self.generate_video_thumbnail(output_path)
                if thumb:
                    new_meta['thumbnail'] = str(thumb)

                index['files'].append(new_meta)
                self.save_uploads_index(index)

                self.serve_json({'ok': True, 'file': new_meta})
            else:
                self.serve_json({'error': 'FFmpeg failed', 'stderr': result.stderr}, status=500)

        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    def video_resize(self, data):
        """Resize video."""
        try:
            file_id = data.get('file_id')
            width = data.get('width')
            height = data.get('height', -1)  # -1 maintains aspect ratio

            if not file_id or not width:
                self.serve_json({'error': 'Missing file_id or width'}, status=400)
                return

            index = self.load_uploads_index()
            file_meta = None
            for f in index.get('files', []):
                if f.get('id') == file_id:
                    file_meta = f
                    break

            if not file_meta:
                self.serve_json({'error': 'File not found'}, status=404)
                return

            input_path = Path(file_meta.get('path', ''))
            output_name = f"resized_{width}x{height}_{input_path.name}"
            output_path = UPLOADS_DIR / 'videos' / output_name

            scale_filter = f"scale={width}:{height}"

            cmd = ['ffmpeg', '-y', '-i', str(input_path),
                   '-vf', scale_filter, '-codec:a', 'copy', str(output_path)]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if output_path.exists():
                new_id = str(uuid.uuid4())[:8]
                new_meta = {
                    'id': new_id,
                    'filename': output_name,
                    'saved_as': output_name,
                    'category': 'videos',
                    'path': str(output_path),
                    'size': output_path.stat().st_size,
                    'uploaded': datetime.now().isoformat(),
                    'source_file': file_id,
                    'operation': 'resize'
                }

                thumb = self.generate_video_thumbnail(output_path)
                if thumb:
                    new_meta['thumbnail'] = str(thumb)

                index['files'].append(new_meta)
                self.save_uploads_index(index)

                self.serve_json({'ok': True, 'file': new_meta})
            else:
                self.serve_json({'error': 'FFmpeg failed', 'stderr': result.stderr}, status=500)

        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    # =========================================================================
    # AGENT FILE ACCESS API
    # =========================================================================

    def serve_files_for_agent(self, data):
        """List files available to an agent."""
        try:
            agent_id = data.get('agent_id', 'default')
            category = data.get('category')

            index = self.load_uploads_index()
            files = index.get('files', [])

            if category:
                files = [f for f in files if f.get('category') == category]

            # Return simplified file list for agents
            agent_files = [{
                'id': f.get('id'),
                'filename': f.get('filename'),
                'category': f.get('category'),
                'size': f.get('size'),
                'has_extracted_text': bool(f.get('extracted_preview')),
                'indexed_to_memory': f.get('indexed_to_memory', False)
            } for f in files]

            self.serve_json({
                'ok': True,
                'agent_id': agent_id,
                'files': agent_files,
                'count': len(agent_files)
            })

        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    def agent_file_request(self, data):
        """Handle agent file operation request."""
        try:
            agent_id = data.get('agent_id', 'default')
            file_id = data.get('file_id')
            operation = data.get('operation', 'read')

            if not file_id:
                self.serve_json({'error': 'Missing file_id'}, status=400)
                return

            index = self.load_uploads_index()
            file_meta = None

            for f in index.get('files', []):
                if f.get('id') == file_id:
                    file_meta = f
                    break

            if not file_meta:
                self.serve_json({'error': 'File not found'}, status=404)
                return

            if operation == 'read':
                # Return extracted text content
                extracted = file_meta.get('extracted_preview', '')

                # If no preview, try to extract now
                if not extracted:
                    file_path = Path(file_meta.get('path', ''))
                    if file_path.exists():
                        extracted = self.extract_text_content(file_path, file_meta.get('category', ''))

                self.serve_json({
                    'ok': True,
                    'agent_id': agent_id,
                    'file_id': file_id,
                    'operation': operation,
                    'content': extracted or '[No text content extracted]',
                    'metadata': file_meta
                })

            elif operation == 'analyze':
                # Return file for analysis
                file_path = Path(file_meta.get('path', ''))
                if file_path.exists():
                    # For code/text files, return full content
                    if file_meta.get('category') in ['code', 'documents', 'specs']:
                        content = self.extract_text_content(file_path, file_meta.get('category', ''))
                        self.serve_json({
                            'ok': True,
                            'agent_id': agent_id,
                            'file_id': file_id,
                            'operation': operation,
                            'content': content,
                            'metadata': file_meta
                        })
                    else:
                        self.serve_json({
                            'ok': True,
                            'agent_id': agent_id,
                            'file_id': file_id,
                            'operation': operation,
                            'content_url': f'/api/files/{file_id}/content',
                            'metadata': file_meta
                        })
                else:
                    self.serve_json({'error': 'File path not found'}, status=404)
            else:
                self.serve_json({'error': f'Unknown operation: {operation}'}, status=400)

        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    # =========================================================================
    # DEMO SHARING ENDPOINTS
    # =========================================================================

    def serve_demo_page(self, query_string):
        """Serve the demo join page with optional pre-filled code."""
        import random
        params = parse_qs(query_string)
        code = params.get('code', [''])[0]
        name = params.get('name', [''])[0]
        auto_join = params.get('auto', [''])[0] == '1'

        # Auto-generate guest name if code provided but no name
        if code and not name:
            name = f"Guest-{random.randint(1000, 9999)}"

        # Generate demo join HTML
        html = self._generate_demo_html(code, name, auto_join)

        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())

    def serve_demo_create(self, query_string):
        """Create a new demo session."""
        if not demo_store:
            self.serve_json({'error': 'Demo store not available'}, status=500)
            return

        params = parse_qs(query_string)
        code = params.get('code', [None])[0]
        owner_name = params.get('owner', ['Host'])[0]
        template_id = params.get('template', [None])[0]

        try:
            demo = demo_store.create_demo(
                code=code.upper() if code else None,
                owner_name=owner_name,
                template_id=template_id
            )

            # Generate shareable URL
            host = self.headers.get('Host', 'localhost:8080')
            share_url = f"http://{host}/demo?code={demo.code}"

            self.serve_json({
                'success': True,
                'code': demo.code,
                'share_url': share_url,
                'expires_at': demo.expires_at,
                'template_id': demo.template_id
            })
        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    def serve_demo_join(self, query_string):
        """Join an existing demo session."""
        if not demo_store:
            self.serve_json({'error': 'Demo store not available'}, status=500)
            return

        params = parse_qs(query_string)
        code = params.get('code', [''])[0]
        name = params.get('name', ['Guest'])[0]

        if not code:
            self.serve_json({'error': 'Demo code required'}, status=400)
            return

        try:
            demo = demo_store.join_demo(code.upper(), name)

            if not demo:
                self.serve_json({'error': 'Demo not found or expired'}, status=404)
                return

            self.serve_json({
                'success': True,
                'code': demo.code,
                'workspace_session_id': demo.workspace_session_id,
                'participants': demo.participants,
                'template_id': demo.template_id,
                'owner_name': demo.owner_name
            })
        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    def serve_demo_info(self, query_string):
        """Get demo session info."""
        if not demo_store:
            self.serve_json({'error': 'Demo store not available'}, status=500)
            return

        params = parse_qs(query_string)
        code = params.get('code', [''])[0]

        if not code:
            self.serve_json({'error': 'Demo code required'}, status=400)
            return

        try:
            demo = demo_store.get_demo(code.upper())

            if not demo:
                self.serve_json({'error': 'Demo not found'}, status=404)
                return

            self.serve_json({
                'code': demo.code,
                'owner_name': demo.owner_name,
                'template_id': demo.template_id,
                'participants': demo.participants,
                'workspace_session_id': demo.workspace_session_id,
                'created_at': demo.created_at,
                'expires_at': demo.expires_at,
                'is_active': demo.is_active,
                'is_expired': demo.is_expired()
            })
        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    def serve_demo_link(self, query_string):
        """Link a demo code to a workspace session."""
        if not demo_store:
            self.serve_json({'error': 'Demo store not available'}, status=500)
            return

        params = parse_qs(query_string)
        code = params.get('code', [''])[0]
        session_id = params.get('session', [''])[0]

        if not code or not session_id:
            self.serve_json({'error': 'Both code and session required'}, status=400)
            return

        try:
            success = demo_store.link_workspace_session(code.upper(), session_id)
            if success:
                self.serve_json({'success': True, 'code': code.upper(), 'session_id': session_id})
            else:
                self.serve_json({'error': 'Demo not found'}, status=404)
        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    def serve_demo_list(self):
        """List all active demos."""
        if not demo_store:
            self.serve_json({'error': 'Demo store not available'}, status=500)
            return

        try:
            demos = demo_store.list_active_demos()
            self.serve_json({
                'demos': [d.to_dict() for d in demos],
                'count': len(demos)
            })
        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    def _generate_demo_html(self, code: str = '', name: str = '', auto_join: bool = False) -> str:
        """Generate the demo join page HTML."""
        auto_join_js = 'true' if auto_join else 'false'
        has_code = 'true' if code else 'false'
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Join Demo - Golden Library</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #fff;
        }}
        .container {{
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 40px;
            width: 100%;
            max-width: 420px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        }}
        h1 {{
            font-size: 28px;
            margin-bottom: 8px;
            text-align: center;
        }}
        .subtitle {{
            text-align: center;
            color: #aaa;
            margin-bottom: 30px;
        }}
        .form-group {{
            margin-bottom: 20px;
        }}
        label {{
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
        }}
        input {{
            width: 100%;
            padding: 14px 16px;
            border: 2px solid rgba(255,255,255,0.2);
            border-radius: 10px;
            background: rgba(255,255,255,0.1);
            color: #fff;
            font-size: 16px;
            transition: border-color 0.3s;
        }}
        input:focus {{
            outline: none;
            border-color: #4a9eff;
        }}
        input::placeholder {{
            color: rgba(255,255,255,0.5);
        }}
        .code-input {{
            text-transform: uppercase;
            font-family: monospace;
            font-size: 20px;
            letter-spacing: 3px;
            text-align: center;
        }}
        button {{
            width: 100%;
            padding: 16px;
            border: none;
            border-radius: 10px;
            background: linear-gradient(135deg, #4a9eff 0%, #6c5ce7 100%);
            color: #fff;
            font-size: 18px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 20px rgba(74,158,255,0.4);
        }}
        button:disabled {{
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }}
        .status {{
            text-align: center;
            margin-top: 20px;
            padding: 12px;
            border-radius: 8px;
            display: none;
        }}
        .status.error {{
            display: block;
            background: rgba(255,71,87,0.2);
            color: #ff4757;
        }}
        .status.success {{
            display: block;
            background: rgba(46,213,115,0.2);
            color: #2ed573;
        }}
        .divider {{
            text-align: center;
            margin: 30px 0;
            color: #666;
        }}
        .divider::before, .divider::after {{
            content: '';
            display: inline-block;
            width: 60px;
            height: 1px;
            background: rgba(255,255,255,0.2);
            vertical-align: middle;
            margin: 0 15px;
        }}
        .create-link {{
            text-align: center;
            color: #4a9eff;
            cursor: pointer;
        }}
        .create-link:hover {{
            text-decoration: underline;
        }}
        .invite-info {{
            background: rgba(74,158,255,0.15);
            border-radius: 12px;
            padding: 20px;
            margin: 25px 0;
            text-align: center;
        }}
        .invite-code {{
            font-size: 14px;
            color: #888;
            margin-bottom: 8px;
        }}
        .invite-code strong {{
            color: #4a9eff;
            font-family: monospace;
            letter-spacing: 2px;
        }}
        .invite-name {{
            font-size: 18px;
        }}
        .invite-name strong {{
            color: #2ed573;
        }}
        .change-name {{
            text-align: center;
            color: #666;
            font-size: 14px;
            margin-top: 15px;
            cursor: pointer;
        }}
        .change-name:hover {{
            color: #4a9eff;
        }}
        #quickJoinBtn {{
            font-size: 20px;
            padding: 18px;
            background: linear-gradient(135deg, #2ed573 0%, #1abc9c 100%);
        }}
        #quickJoinBtn:hover {{
            box-shadow: 0 4px 20px rgba(46,213,115,0.4);
        }}
    </style>
</head>
<body>
    <div class="container">
        <div id="invite-view" style="display: {{'none' if not code else 'block'}};">
            <h1>🎉 You're Invited!</h1>
            <p class="subtitle">Join the collaborative workspace session</p>

            <div class="invite-info">
                <div class="invite-code">Session: <strong>{code}</strong></div>
                <div class="invite-name">Joining as: <strong id="guest-name">{name}</strong></div>
            </div>

            <button type="button" id="quickJoinBtn" onclick="quickJoin()">
                Join Now →
            </button>

            <p class="change-name" onclick="showFullForm()">Change your name</p>

            <div id="quick-status" class="status"></div>
        </div>

        <div id="full-form" style="display: {{'block' if not code else 'none'}};">
            <h1>Join Demo</h1>
            <p class="subtitle">Enter the demo code to join a live workspace session</p>

            <form id="joinForm">
                <div class="form-group">
                    <label for="code">Demo Code</label>
                    <input type="text" id="code" class="code-input" placeholder="DEMO123ABC"
                           value="{code}" maxlength="12" required>
                </div>

                <div class="form-group">
                    <label for="name">Your Name</label>
                    <input type="text" id="name" placeholder="Enter your name"
                           value="{name}" required>
                </div>

                <button type="submit" id="joinBtn">Join Demo</button>
            </form>

            <div id="status" class="status"></div>

            <div class="divider">or</div>

            <p class="create-link" onclick="createDemo()">Create a new demo session</p>
        </div>
    </div>

    <script>
        const WS_URL = 'ws://' + window.location.hostname + ':8081';
        const AUTO_JOIN = {auto_join_js};
        const HAS_CODE = {has_code};
        const PREFILLED_CODE = '{code}';
        const PREFILLED_NAME = '{name}';

        // Quick join function for invite links
        async function quickJoin() {{
            const code = PREFILLED_CODE;
            const name = PREFILLED_NAME;
            const btn = document.getElementById('quickJoinBtn');
            const status = document.getElementById('quick-status');

            btn.disabled = true;
            btn.textContent = 'Joining...';

            try {{
                const res = await fetch(`/api/demo/join?code=${{code}}&name=${{encodeURIComponent(name)}}`);
                const data = await res.json();

                if (!res.ok) {{
                    throw new Error(data.error || 'Failed to join demo');
                }}

                status.className = 'status success';
                status.textContent = 'Success! Redirecting...';
                status.style.display = 'block';

                const params = new URLSearchParams({{
                    demo: code,
                    name: name,
                    session: data.workspace_session_id || ''
                }});
                window.location.href = '/#workspace?' + params.toString();

            }} catch (err) {{
                status.className = 'status error';
                status.textContent = err.message;
                status.style.display = 'block';
                btn.disabled = false;
                btn.textContent = 'Join Now →';
            }}
        }}

        // Show full form for name change
        function showFullForm() {{
            document.getElementById('invite-view').style.display = 'none';
            document.getElementById('full-form').style.display = 'block';
            document.getElementById('name').focus();
        }}

        // Auto-join on page load if enabled
        if (AUTO_JOIN && HAS_CODE) {{
            window.addEventListener('load', () => {{
                setTimeout(quickJoin, 500);
            }});
        }}

        document.getElementById('joinForm').addEventListener('submit', async (e) => {{
            e.preventDefault();
            const code = document.getElementById('code').value.trim().toUpperCase();
            const name = document.getElementById('name').value.trim();
            const btn = document.getElementById('joinBtn');
            const status = document.getElementById('status');

            if (!code || !name) return;

            btn.disabled = true;
            btn.textContent = 'Joining...';
            status.className = 'status';
            status.style.display = 'none';

            try {{
                // Join demo via API
                const res = await fetch(`/api/demo/join?code=${{code}}&name=${{encodeURIComponent(name)}}`);
                const data = await res.json();

                if (!res.ok) {{
                    throw new Error(data.error || 'Failed to join demo');
                }}

                status.className = 'status success';
                status.textContent = 'Joining workspace...';
                status.style.display = 'block';

                // Redirect to dashboard with session info
                const params = new URLSearchParams({{
                    demo: code,
                    name: name,
                    session: data.workspace_session_id || ''
                }});
                window.location.href = '/#workspace?' + params.toString();

            }} catch (err) {{
                status.className = 'status error';
                status.textContent = err.message;
                status.style.display = 'block';
                btn.disabled = false;
                btn.textContent = 'Join Demo';
            }}
        }});

        async function createDemo() {{
            const name = prompt('Enter your name (host):');
            if (!name) return;

            try {{
                const res = await fetch(`/api/demo/create?owner=${{encodeURIComponent(name)}}`);
                const data = await res.json();

                if (!res.ok) throw new Error(data.error);

                alert(`Demo created!\\n\\nCode: ${{data.code}}\\n\\nShare this link:\\n${{data.share_url}}`);
                document.getElementById('code').value = data.code;
                document.getElementById('name').value = name;

            }} catch (err) {{
                alert('Failed to create demo: ' + err.message);
            }}
        }}

        // Auto-focus
        if (!document.getElementById('code').value) {{
            document.getElementById('code').focus();
        }} else if (!document.getElementById('name').value) {{
            document.getElementById('name').focus();
        }}
    </script>
</body>
</html>'''

    def serve_stats(self):
        """Serve statistics about compressed data."""
        try:
            stats = self.get_compression_stats()
            self.serve_json(stats)
        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    def serve_search(self, query_string):
        """Search compressed conversations."""
        try:
            params = parse_qs(query_string)
            query = params.get('q', [''])[0]
            category = params.get('category', ['all'])[0]

            results = self.search_conversations(query, category)
            self.serve_json(results)
        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    def serve_daemon_status(self):
        """Check if daemon is running."""
        try:
            status = self.check_daemon_status()
            self.serve_json(status)
        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    def serve_conversation(self, query_string):
        """Serve a specific conversation."""
        try:
            params = parse_qs(query_string)
            conv_id = params.get('id', [''])[0]

            conversation = self.get_conversation(conv_id)
            self.serve_json(conversation)
        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    # =========================================================================
    # Data Loading Methods
    # =========================================================================

    def get_compression_stats(self):
        """Load compression statistics from index."""
        if not INDEX_FILE.exists():
            return self.generate_sample_stats()

        with open(INDEX_FILE, 'r') as f:
            index = json.load(f)

        # Calculate stats
        conversations = index.get('conversations', [])
        total_conversations = len(conversations)
        total_original = sum(c.get('original_tokens', 0) for c in conversations)
        total_compressed = sum(c.get('compressed_tokens', 0) for c in conversations)
        total_saved = total_original - total_compressed
        reduction_percent = (total_saved / total_original * 100) if total_original > 0 else 0

        # Category breakdown
        category_stats = {}
        for conv in conversations:
            cat = conv.get('category', 'conversations')
            if cat not in category_stats:
                category_stats[cat] = {
                    'count': 0,
                    'original_tokens': 0,
                    'compressed_tokens': 0
                }
            category_stats[cat]['count'] += 1
            category_stats[cat]['original_tokens'] += conv.get('original_tokens', 0)
            category_stats[cat]['compressed_tokens'] += conv.get('compressed_tokens', 0)

        return {
            'total_conversations': total_conversations,
            'total_original_tokens': total_original,
            'total_compressed_tokens': total_compressed,
            'total_saved_tokens': total_saved,
            'reduction_percent': round(reduction_percent, 2),
            'disk_saved_mb': round((total_saved * 4) / (1024 * 1024), 2),
            'categories': category_stats,
            'conversations': conversations,
            'last_updated': index.get('last_updated', datetime.now().isoformat())
        }

    def generate_sample_stats(self):
        """Generate sample stats if no index exists."""
        # Check if compressed directory exists
        if COMPRESSED_DIR.exists():
            # Scan for compressed files in nested directories
            compressed_files = []

            # Scan root directory
            compressed_files.extend(COMPRESSED_DIR.glob('*.slim*'))

            # Scan nested directories (projects/, todos/, etc.)
            for subdir in COMPRESSED_DIR.iterdir():
                if subdir.is_dir():
                    compressed_files.extend(subdir.glob('*.slim*'))

            conversations = []

            for file_path in compressed_files:
                try:
                    file_size = file_path.stat().st_size
                    created = datetime.fromtimestamp(file_path.stat().st_mtime)

                    # Estimate tokens (rough: 1 byte ≈ 0.25 tokens for compressed)
                    compressed_tokens = int(file_size * 0.25)
                    original_tokens = int(compressed_tokens * 2.5)  # Assume 60% compression

                    # Determine category from subdirectory
                    if file_path.parent.name == 'projects':
                        category = 'projects'
                        project = 'Project Handoff'
                    elif file_path.parent.name == 'todos':
                        category = 'todos'
                        project = 'Todo Task'
                    else:
                        category = 'conversations'
                        project = 'General'

                    conversations.append({
                        'id': file_path.stem,
                        'title': file_path.stem.replace('_', ' ').replace('-', ' ').title()[:50],
                        'project': project,
                        'created': created.isoformat(),
                        'original_tokens': original_tokens,
                        'compressed_tokens': compressed_tokens,
                        'category': category,
                        'file_path': str(file_path)
                    })
                except Exception as e:
                    # Skip files that cause errors
                    print(f"Warning: Skipped {file_path}: {e}")
                    continue

            if not conversations:
                # No valid files found
                return {
                    'total_conversations': 0,
                    'total_original_tokens': 0,
                    'total_compressed_tokens': 0,
                    'total_saved_tokens': 0,
                    'reduction_percent': 0,
                    'disk_saved_mb': 0,
                    'categories': {},
                    'conversations': [],
                    'last_updated': datetime.now().isoformat(),
                    'note': 'No valid compressed files found.'
                }

            total_original = sum(c['original_tokens'] for c in conversations)
            total_compressed = sum(c['compressed_tokens'] for c in conversations)
            total_saved = total_original - total_compressed
            reduction = (total_saved / total_original * 100) if total_original > 0 else 0

            # Build category breakdown
            categories = {}
            for conv in conversations:
                cat = conv['category']
                if cat not in categories:
                    categories[cat] = {
                        'count': 0,
                        'original_tokens': 0,
                        'compressed_tokens': 0
                    }
                categories[cat]['count'] += 1
                categories[cat]['original_tokens'] += conv['original_tokens']
                categories[cat]['compressed_tokens'] += conv['compressed_tokens']

            return {
                'total_conversations': len(conversations),
                'total_original_tokens': total_original,
                'total_compressed_tokens': total_compressed,
                'total_saved_tokens': total_saved,
                'reduction_percent': round(reduction, 2),
                'disk_saved_mb': round((total_saved * 4) / (1024 * 1024), 2),
                'categories': categories,
                'conversations': conversations,
                'last_updated': datetime.now().isoformat(),
                'note': 'Generated from compressed files (index not found)'
            }

        # No data at all - return empty stats
        return {
            'total_conversations': 0,
            'total_original_tokens': 0,
            'total_compressed_tokens': 0,
            'total_saved_tokens': 0,
            'reduction_percent': 0,
            'disk_saved_mb': 0,
            'categories': {},
            'conversations': [],
            'last_updated': datetime.now().isoformat(),
            'note': 'No compressed data found. Start the daemon to begin compression.'
        }

    def search_conversations(self, query, category='all'):
        """Search conversations by query and category."""
        stats = self.get_compression_stats()
        conversations = stats.get('conversations', [])

        if not query:
            return {
                'query': query,
                'category': category,
                'results': conversations[:20],  # Return first 20 if no query
                'total_results': len(conversations)
            }

        # Filter by category
        if category != 'all':
            conversations = [c for c in conversations if c.get('category') == category]

        # Search in title, id, project
        query_lower = query.lower()
        results = [
            c for c in conversations
            if (query_lower in c.get('title', '').lower() or
                query_lower in c.get('id', '').lower() or
                query_lower in c.get('project', '').lower())
        ]

        return {
            'query': query,
            'category': category,
            'results': results,
            'total_results': len(results)
        }

    def check_daemon_status(self):
        """Check if compression daemon is running."""
        if not DAEMON_PID_FILE.exists():
            return {
                'running': False,
                'message': 'Daemon not running (PID file not found)',
                'pid': None
            }

        try:
            with open(DAEMON_PID_FILE, 'r') as f:
                pid = int(f.read().strip())

            # Check if process is running
            try:
                os.kill(pid, 0)  # Signal 0 checks if process exists
                return {
                    'running': True,
                    'message': 'Daemon running',
                    'pid': pid
                }
            except OSError:
                return {
                    'running': False,
                    'message': 'Daemon stopped (PID exists but process not found)',
                    'pid': pid
                }
        except Exception as e:
            return {
                'running': False,
                'message': f'Error checking daemon: {str(e)}',
                'pid': None
            }

    def get_conversation(self, conv_id):
        """Get details of a specific conversation."""
        stats = self.get_compression_stats()
        conversations = stats.get('conversations', [])

        for conv in conversations:
            if conv.get('id') == conv_id:
                # Try to load the compressed file
                file_path = conv.get('file_path')
                if file_path and Path(file_path).exists():
                    with open(file_path, 'r') as f:
                        content = f.read()
                    conv['content_preview'] = content[:1000] + '...' if len(content) > 1000 else content

                return conv

        return {'error': 'Conversation not found'}

    # =========================================================================
    # Configuration Methods
    # =========================================================================

    def serve_config_list(self):
        """List all available configuration files."""
        config_files = self.get_config_files()
        self.serve_json(config_files)

    def serve_config(self, query_string):
        """Serve a specific configuration file."""
        try:
            params = parse_qs(query_string)
            file_type = params.get('type', [''])[0]

            content = self.get_config_content(file_type)
            self.serve_json(content)
        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    def get_config_files(self):
        """Get list of all Claude configuration files."""
        claude_dir = HOME / ".claude"

        config_files = {
            'markdown': [],
            'json': [],
            'hooks': [],
            'skills': [],
            'mcp_servers': []
        }

        # Markdown configs
        for md_file in ['CLAUDE.md', 'agents.md']:
            path = HOME / md_file
            if not path.exists():
                path = claude_dir / md_file
            if path.exists():
                config_files['markdown'].append({
                    'name': md_file,
                    'path': str(path),
                    'size': path.stat().st_size,
                    'modified': datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                    'type': 'markdown'
                })

        # JSON configs
        for json_file in ['settings.json', 'settings.local.json']:
            path = claude_dir / json_file
            if path.exists():
                config_files['json'].append({
                    'name': json_file,
                    'path': str(path),
                    'size': path.stat().st_size,
                    'modified': datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                    'type': 'json'
                })

        # Hooks
        hooks_dir = claude_dir / 'hooks'
        if hooks_dir.exists():
            for hook_file in hooks_dir.iterdir():
                if hook_file.is_file():
                    config_files['hooks'].append({
                        'name': hook_file.name,
                        'path': str(hook_file),
                        'size': hook_file.stat().st_size,
                        'modified': datetime.fromtimestamp(hook_file.stat().st_mtime).isoformat(),
                        'type': 'hook'
                    })

        # Skills from settings
        settings_path = claude_dir / 'settings.json'
        if settings_path.exists():
            try:
                with open(settings_path, 'r') as f:
                    settings = json.load(f)

                # Extract skills
                skills = settings.get('skills', {})
                for skill_name, skill_data in skills.items():
                    config_files['skills'].append({
                        'name': skill_name,
                        'enabled': skill_data.get('enabled', True),
                        'path': skill_data.get('path', ''),
                        'type': 'skill'
                    })

                # Extract MCP servers
                mcp_servers = settings.get('mcpServers', {})
                for server_name, server_data in mcp_servers.items():
                    config_files['mcp_servers'].append({
                        'name': server_name,
                        'command': server_data.get('command', ''),
                        'args': server_data.get('args', []),
                        'type': 'mcp_server'
                    })
            except Exception as e:
                config_files['error'] = f'Error reading settings: {str(e)}'

        return config_files

    def get_config_content(self, file_type):
        """Get content of a specific configuration file."""
        claude_dir = HOME / ".claude"

        # Map file types to paths
        file_map = {
            'claude.md': HOME / 'CLAUDE.md' if (HOME / 'CLAUDE.md').exists() else claude_dir / 'CLAUDE.md',
            'agents.md': HOME / 'agents.md' if (HOME / 'agents.md').exists() else claude_dir / 'agents.md',
            'settings': claude_dir / 'settings.json',
            'settings.local': claude_dir / 'settings.local.json',
        }

        # Handle hooks
        if file_type.startswith('hook:'):
            hook_name = file_type.split(':', 1)[1]
            hook_path = claude_dir / 'hooks' / hook_name
            if hook_path.exists():
                with open(hook_path, 'r') as f:
                    return {
                        'name': hook_name,
                        'type': 'hook',
                        'content': f.read(),
                        'path': str(hook_path)
                    }

        # Handle regular config files
        if file_type in file_map:
            path = file_map[file_type]
            if path.exists():
                with open(path, 'r') as f:
                    content = f.read()

                return {
                    'name': file_type,
                    'type': 'text' if file_type.endswith('.md') else 'json',
                    'content': content,
                    'path': str(path),
                    'size': path.stat().st_size,
                    'modified': datetime.fromtimestamp(path.stat().st_mtime).isoformat()
                }

        return {'error': f'Configuration file not found: {file_type}'}

    # =========================================================================
    # Config Editing Methods
    # =========================================================================

    def save_config(self, data):
        """Save edited configuration file."""
        try:
            file_type = data.get('type')
            content = data.get('content')

            if not file_type or content is None:
                self.serve_json({'error': 'Missing type or content'}, status=400)
                return

            # Get file path
            claude_dir = HOME / ".claude"
            file_map = {
                'claude.md': HOME / 'CLAUDE.md' if (HOME / 'CLAUDE.md').exists() else claude_dir / 'CLAUDE.md',
                'agents.md': HOME / 'agents.md' if (HOME / 'agents.md').exists() else claude_dir / 'agents.md',
                'settings': claude_dir / 'settings.json',
                'settings.local': claude_dir / 'settings.local.json',
            }

            # Handle hooks
            if file_type.startswith('hook:'):
                hook_name = file_type.split(':', 1)[1]
                path = claude_dir / 'hooks' / hook_name
            elif file_type in file_map:
                path = file_map[file_type]
            else:
                self.serve_json({'error': f'Unknown file type: {file_type}'}, status=400)
                return

            # Backup original
            if path.exists():
                backup_dir = claude_dir / 'backups'
                backup_dir.mkdir(exist_ok=True)
                backup_path = backup_dir / f"{path.name}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
                import shutil
                shutil.copy2(path, backup_path)

            # Write new content
            with open(path, 'w') as f:
                f.write(content)

            self.serve_json({
                'success': True,
                'message': f'Saved {file_type}',
                'path': str(path)
            })
        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    # =========================================================================
    # MCP Server Management
    # =========================================================================

    def serve_mcp_list(self):
        """List all MCP servers."""
        try:
            settings_path = HOME / ".claude" / "settings.json"
            if not settings_path.exists():
                self.serve_json({'servers': []})
                return

            with open(settings_path, 'r') as f:
                settings = json.load(f)

            mcp_servers = settings.get('mcpServers', {})
            servers = []
            for name, config in mcp_servers.items():
                servers.append({
                    'name': name,
                    'command': config.get('command', ''),
                    'args': config.get('args', []),
                    'env': config.get('env', {}),
                    'enabled': config.get('enabled', True)
                })

            self.serve_json({'servers': servers})
        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    def toggle_mcp_server(self, data):
        """Toggle MCP server enabled/disabled."""
        try:
            server_name = data.get('name')
            enabled = data.get('enabled')

            settings_path = HOME / ".claude" / "settings.json"
            with open(settings_path, 'r') as f:
                settings = json.load(f)

            if server_name in settings.get('mcpServers', {}):
                settings['mcpServers'][server_name]['enabled'] = enabled

                with open(settings_path, 'w') as f:
                    json.dump(settings, f, indent=2)

                self.serve_json({'success': True, 'message': f'Server {server_name} {"enabled" if enabled else "disabled"}'})
            else:
                self.serve_json({'error': f'Server {server_name} not found'}, status=404)
        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    def add_mcp_server(self, data):
        """Add new MCP server."""
        try:
            name = data.get('name')
            command = data.get('command')
            args = data.get('args', [])
            env = data.get('env', {})

            settings_path = HOME / ".claude" / "settings.json"
            with open(settings_path, 'r') as f:
                settings = json.load(f)

            if 'mcpServers' not in settings:
                settings['mcpServers'] = {}

            settings['mcpServers'][name] = {
                'command': command,
                'args': args,
                'env': env,
                'enabled': True
            }

            with open(settings_path, 'w') as f:
                json.dump(settings, f, indent=2)

            self.serve_json({'success': True, 'message': f'Added server {name}'})
        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    def remove_mcp_server(self, data):
        """Remove MCP server."""
        try:
            name = data.get('name')

            settings_path = HOME / ".claude" / "settings.json"
            with open(settings_path, 'r') as f:
                settings = json.load(f)

            if name in settings.get('mcpServers', {}):
                del settings['mcpServers'][name]

                with open(settings_path, 'w') as f:
                    json.dump(settings, f, indent=2)

                self.serve_json({'success': True, 'message': f'Removed server {name}'})
            else:
                self.serve_json({'error': f'Server {name} not found'}, status=404)
        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    # =========================================================================
    # Daemon Management
    # =========================================================================

    def serve_daemons_list(self):
        """List all known daemons."""
        try:
            daemons = []

            # Auto-compress daemon
            daemon_pid_file = HOME / ".claude" / "auto_compress_daemon.pid"
            if daemon_pid_file.exists():
                with open(daemon_pid_file, 'r') as f:
                    pid = int(f.read().strip())
                try:
                    os.kill(pid, 0)
                    running = True
                except:
                    running = False
            else:
                pid = None
                running = False

            daemons.append({
                'id': 'auto_compress',
                'name': 'Auto-Compress Daemon',
                'description': 'Compresses Claude conversations automatically',
                'pid': pid,
                'running': running,
                'pid_file': str(daemon_pid_file),
                'script': str(HOME / 'ztgi' / 'golden_library' / 'daemons' / 'auto_compress_daemon.py')
            })

            # Dashboard server (this server)
            dashboard_pid_file = HOME / ".claude" / "dashboard_server.pid"
            if dashboard_pid_file.exists():
                with open(dashboard_pid_file, 'r') as f:
                    pid = int(f.read().strip())
                running = True  # We're running if this code executes
            else:
                pid = os.getpid()
                running = True

            daemons.append({
                'id': 'dashboard_server',
                'name': 'Dashboard Server',
                'description': 'Claude Control Center web interface',
                'pid': pid,
                'running': running,
                'pid_file': str(dashboard_pid_file),
                'script': str(HOME / 'ztgi' / 'golden_library' / 'dashboard_server.py')
            })

            # Universal watcher daemon
            universal_watcher_pid_file = HOME / ".claude" / "universal_watcher.pid"
            if universal_watcher_pid_file.exists():
                with open(universal_watcher_pid_file, 'r') as f:
                    pid = int(f.read().strip())
                try:
                    os.kill(pid, 0)
                    running = True
                except:
                    running = False
            else:
                pid = None
                running = False

            daemons.append({
                'id': 'universal_watcher',
                'name': 'Universal Watcher',
                'description': 'Watches all 15+ Claude storage locations for compression',
                'pid': pid,
                'running': running,
                'pid_file': str(universal_watcher_pid_file),
                'script': str(HOME / 'ztgi' / 'golden_library' / 'daemons' / 'universal_watcher.py')
            })

            self.serve_json({'daemons': daemons})
        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    def start_daemon(self, data):
        """Start a daemon."""
        try:
            daemon_id = data.get('id')

            if daemon_id == 'auto_compress':
                script_path = HOME / 'ztgi' / 'golden_library' / 'daemons' / 'auto_compress_daemon.py'
                subprocess.Popen(['python3', str(script_path)],
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
                self.serve_json({'success': True, 'message': 'Started auto-compress daemon'})
            else:
                self.serve_json({'error': f'Unknown daemon: {daemon_id}'}, status=400)
        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    def stop_daemon(self, data):
        """Stop a daemon."""
        try:
            daemon_id = data.get('id')

            if daemon_id == 'auto_compress':
                pid_file = HOME / ".claude" / "auto_compress_daemon.pid"
                if pid_file.exists():
                    with open(pid_file, 'r') as f:
                        pid = int(f.read().strip())
                    os.kill(pid, 15)  # SIGTERM
                    self.serve_json({'success': True, 'message': 'Stopped auto-compress daemon'})
                else:
                    self.serve_json({'error': 'Daemon not running'}, status=400)
            elif daemon_id == 'dashboard_server':
                self.serve_json({'error': 'Cannot stop dashboard from within dashboard'}, status=400)
            else:
                self.serve_json({'error': f'Unknown daemon: {daemon_id}'}, status=400)
        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    def restart_daemon(self, data):
        """Restart a daemon."""
        try:
            self.stop_daemon(data)
            import time
            time.sleep(1)
            self.start_daemon(data)
        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    # =========================================================================
    # Universal Watcher Stats
    # =========================================================================

    def serve_universal_watcher_stats(self):
        """Get detailed stats from universal watcher."""
        try:
            # Check if universal watcher config exists
            config_path = HOME / ".claude" / "universal_watcher_config.json"

            if not config_path.exists():
                self.serve_json({
                    'enabled': False,
                    'message': 'Universal watcher not configured'
                })
                return

            # Load config
            with open(config_path, 'r') as f:
                config = json.load(f)

            locations = config.get('locations', [])

            # Check if stats file exists (would be created by running watcher)
            stats_file = LIBRARY_DIR / "stats" / "location_stats.json"
            location_stats = {}

            if stats_file.exists():
                with open(stats_file, 'r') as f:
                    location_stats = json.load(f)

            # Build response
            response = {
                'enabled': True,
                'total_locations': len(locations),
                'active_locations': sum(1 for loc in locations if loc.get('enabled', True)),
                'locations': []
            }

            for loc in locations:
                loc_id = loc.get('id')
                stats = location_stats.get(loc_id, {
                    'processed': 0,
                    'failed': 0,
                    'original_tokens': 0,
                    'compressed_tokens': 0,
                    'bytes_saved': 0
                })

                response['locations'].append({
                    'id': loc_id,
                    'name': loc.get('id').replace('_', ' ').title(),
                    'path': loc.get('path'),
                    'enabled': loc.get('enabled', True),
                    'priority': loc.get('priority', 1),
                    'strategy': loc.get('strategy', 'real-time-incremental'),
                    'processed': stats.get('processed', 0),
                    'failed': stats.get('failed', 0),
                    'original_tokens': stats.get('original_tokens', 0),
                    'compressed_tokens': stats.get('compressed_tokens', 0),
                    'tokens_saved': stats.get('original_tokens', 0) - stats.get('compressed_tokens', 0),
                    'bytes_saved': stats.get('bytes_saved', 0),
                    'last_compression': stats.get('last_compression')
                })

            self.serve_json(response)
        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    # =========================================================================
    # Arsenal Management
    # =========================================================================

    def serve_arsenal_list(self):
        """List available config presets."""
        try:
            # Get current active config
            claude_md_path = HOME / 'CLAUDE.md'
            current_name = 'Custom'
            if claude_md_path.exists():
                with open(claude_md_path, 'r') as f:
                    first_line = f.readline()
                    if 'KODA' in first_line.upper() or 'BUILDER' in first_line.upper():
                        current_name = 'Koda Builder'
                    elif 'CAIRN' in first_line.upper() or 'ARCHITECT' in first_line.upper():
                        current_name = 'Cairn Architect'
                    elif 'PRAX' in first_line.upper() or 'STRATEGIST' in first_line.upper():
                        current_name = 'Prax Strategist'

            # Scan library for saved presets
            library_dir = ARSENAL_LIBRARY / 'claude_md'
            library_dir.mkdir(parents=True, exist_ok=True)

            saved_presets = []
            for file in library_dir.glob('*.md'):
                saved_presets.append({
                    'id': file.stem,
                    'name': file.stem.replace('_', ' ').title(),
                    'path': str(file),
                    'size': file.stat().st_size,
                    'modified': datetime.fromtimestamp(file.stat().st_mtime).isoformat()
                })

            arsenal = {
                'current': {
                    'name': current_name,
                    'claude_md': str(claude_md_path),
                    'agents_md': str(HOME / 'agents.md')
                },
                'saved_presets': saved_presets
            }

            self.serve_json(arsenal)
        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    def serve_arsenal_save(self, params):
        """Save current config as preset."""
        try:
            name = params.get('name', [''])[0]
            if not name:
                self.serve_json({'error': 'Name required'}, status=400)
                return

            # Save current CLAUDE.md
            claude_md_src = HOME / 'CLAUDE.md'
            if claude_md_src.exists():
                library_dir = ARSENAL_LIBRARY / 'claude_md'
                library_dir.mkdir(parents=True, exist_ok=True)

                dest = library_dir / f"{name.replace(' ', '_').lower()}.md"
                import shutil
                shutil.copy2(claude_md_src, dest)

                self.serve_json({'success': True, 'message': f'Saved as {name}', 'path': str(dest)})
            else:
                self.serve_json({'error': 'CLAUDE.md not found'}, status=404)
        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    def create_arsenal_preset(self, data):
        """Create new preset from template or empty."""
        try:
            name = data.get('name')
            template = data.get('template', 'current')

            if not name:
                self.serve_json({'error': 'Name required'}, status=400)
                return

            library_dir = ARSENAL_LIBRARY / 'claude_md'
            library_dir.mkdir(parents=True, exist_ok=True)

            dest = library_dir / f"{name.replace(' ', '_').lower()}.md"

            if template == 'current':
                # Copy current CLAUDE.md
                src = HOME / 'CLAUDE.md'
                if src.exists():
                    import shutil
                    shutil.copy2(src, dest)
            else:
                # Create empty template
                with open(dest, 'w') as f:
                    f.write(f"# {name}\n\nYour custom Claude configuration.\n")

            self.serve_json({'success': True, 'message': f'Created {name}', 'path': str(dest)})
        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    def activate_arsenal_config(self, data):
        """Switch to a different config preset."""
        try:
            preset_name = data.get('name')

            if not preset_name:
                self.serve_json({'error': 'Preset name required'}, status=400)
                return

            # Find preset file
            library_dir = ARSENAL_LIBRARY / 'claude_md'
            preset_file = library_dir / f"{preset_name.replace(' ', '_').lower()}.md"

            if not preset_file.exists():
                self.serve_json({'error': f'Preset {preset_name} not found'}, status=404)
                return

            # Backup current CLAUDE.md
            claude_md = HOME / 'CLAUDE.md'
            if claude_md.exists():
                backup_dir = HOME / '.claude' / 'backups'
                backup_dir.mkdir(exist_ok=True)
                backup_path = backup_dir / f"CLAUDE.md.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
                import shutil
                shutil.copy2(claude_md, backup_path)

            # Copy preset to CLAUDE.md
            import shutil
            shutil.copy2(preset_file, claude_md)

            self.serve_json({
                'success': True,
                'message': f'✅ Activated {preset_name}! Restart Claude Code to apply changes.'
            })
        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    # =========================================================================
    # Hook Management
    # =========================================================================

    def serve_hooks_list(self):
        """List all hooks and their status."""
        try:
            hooks_dir = HOME / ".claude" / "hooks"
            hooks = []

            if hooks_dir.exists():
                for hook_file in sorted(hooks_dir.iterdir()):
                    if hook_file.is_file():
                        # Check if hook is executable
                        is_executable = os.access(hook_file, os.X_OK)

                        hooks.append({
                            'name': hook_file.name,
                            'path': str(hook_file),
                            'enabled': is_executable,
                            'size': hook_file.stat().st_size,
                            'modified': datetime.fromtimestamp(hook_file.stat().st_mtime).isoformat()
                        })

            self.serve_json({'hooks': hooks})
        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    def toggle_hook(self, data):
        """Enable or disable a hook by changing permissions."""
        try:
            hook_name = data.get('name')
            enabled = data.get('enabled')

            if not hook_name:
                self.serve_json({'error': 'Hook name required'}, status=400)
                return

            hook_path = HOME / ".claude" / "hooks" / hook_name

            if not hook_path.exists():
                self.serve_json({'error': f'Hook {hook_name} not found'}, status=404)
                return

            if enabled:
                # Make executable (chmod +x)
                current_mode = hook_path.stat().st_mode
                hook_path.chmod(current_mode | 0o111)  # Add execute permission
                message = f'✅ Enabled {hook_name}'
            else:
                # Remove executable (chmod -x)
                current_mode = hook_path.stat().st_mode
                hook_path.chmod(current_mode & ~0o111)  # Remove execute permission
                message = f'⏸️ Disabled {hook_name}'

            self.serve_json({'success': True, 'message': message})
        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    # =========================================================================
    # Config Templates Management
    # =========================================================================

    def serve_templates_list(self):
        """List available config templates."""
        try:
            templates_dir = ARSENAL_LIBRARY / "claude_md"
            templates = []

            if templates_dir.exists():
                for template_file in templates_dir.glob("*.md"):
                    # Skip files that aren't templates
                    name = template_file.stem

                    # Read first line for description
                    description = ""
                    try:
                        with open(template_file, 'r') as f:
                            first_line = f.readline().strip()
                            if first_line.startswith('#'):
                                description = first_line.lstrip('# ').strip()
                    except:
                        pass

                    templates.append({
                        'id': name,
                        'name': name.replace('_', ' ').title(),
                        'file': template_file.name,
                        'description': description,
                        'path': str(template_file),
                        'size': template_file.stat().st_size
                    })

            self.serve_json({'templates': templates})
        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    def load_template(self, data):
        """Load a template as the active CLAUDE.md."""
        try:
            template_id = data.get('template_id')
            if not template_id:
                self.serve_json({'error': 'Template ID required'}, status=400)
                return

            template_path = ARSENAL_LIBRARY / "claude_md" / f"{template_id}.md"

            if not template_path.exists():
                self.serve_json({'error': f'Template {template_id} not found'}, status=404)
                return

            # Backup current CLAUDE.md
            claude_md_path = HOME / "CLAUDE.md"
            if claude_md_path.exists():
                backup_dir = HOME / ".claude" / "backups"
                backup_dir.mkdir(exist_ok=True)
                backup_path = backup_dir / f"CLAUDE.md.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
                import shutil
                shutil.copy2(claude_md_path, backup_path)

            # Copy template to CLAUDE.md
            import shutil
            shutil.copy2(template_path, claude_md_path)

            self.serve_json({
                'success': True,
                'message': f'Loaded template: {template_id}',
                'template': template_id
            })
        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    # =========================================================================
    # Model Selection Management
    # =========================================================================

    def serve_current_model(self):
        """Get the current Claude model selection."""
        try:
            settings_path = HOME / ".claude" / "settings.local.json"

            # Default model
            current_model = "claude-sonnet-4.5"

            if settings_path.exists():
                with open(settings_path, 'r') as f:
                    settings = json.load(f)
                    current_model = settings.get('defaultModel', current_model)

            available_models = [
                {
                    'id': 'claude-opus-4.5',
                    'name': 'Claude Opus 4.5',
                    'description': 'Most capable model - best for complex reasoning, architecture, and analysis',
                    'speed': 'Slower',
                    'cost': 'Highest',
                    'recommended_for': ['Architecture', 'Code Review', 'Strategy']
                },
                {
                    'id': 'claude-sonnet-4.5',
                    'name': 'Claude Sonnet 4.5',
                    'description': 'Balanced model - great for most tasks with good speed and capability',
                    'speed': 'Medium',
                    'cost': 'Medium',
                    'recommended_for': ['Building', 'Debugging', 'General Use']
                },
                {
                    'id': 'claude-haiku-4',
                    'name': 'Claude Haiku 4',
                    'description': 'Fastest model - ideal for quick tasks and high-volume operations',
                    'speed': 'Fastest',
                    'cost': 'Lowest',
                    'recommended_for': ['Quick fixes', 'Simple tasks', 'Batch operations']
                }
            ]

            self.serve_json({
                'current_model': current_model,
                'available_models': available_models
            })
        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    def set_model(self, data):
        """Set the default Claude model."""
        try:
            model_id = data.get('model_id')
            if not model_id:
                self.serve_json({'error': 'Model ID required'}, status=400)
                return

            valid_models = ['claude-opus-4.5', 'claude-sonnet-4.5', 'claude-haiku-4']
            if model_id not in valid_models:
                self.serve_json({'error': f'Invalid model: {model_id}'}, status=400)
                return

            settings_path = HOME / ".claude" / "settings.local.json"

            # Load existing settings or create new
            settings = {}
            if settings_path.exists():
                with open(settings_path, 'r') as f:
                    settings = json.load(f)

            # Update model
            settings['defaultModel'] = model_id

            # Save settings
            with open(settings_path, 'w') as f:
                json.dump(settings, f, indent=2)

            self.serve_json({
                'success': True,
                'message': f'Set default model to {model_id}',
                'model': model_id
            })
        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    # =========================================================================
    # 3D Viewer Endpoints
    # =========================================================================

    def serve_3d_handoffs(self):
        """List all compressed handoffs for 3D visualization."""
        try:
            stats = self.get_compression_stats()
            conversations = stats.get('conversations', [])

            # Transform conversation library handoffs to 3D viewer format
            handoffs = []
            skipped = 0

            for conv in conversations:
                try:
                    # Verify file still exists
                    file_path = conv.get('file_path')
                    if file_path and not Path(file_path).exists():
                        skipped += 1
                        continue

                    # Infer compression format
                    comp_format = self.infer_compression_format(conv)

                    # Calculate reduction percentage safely
                    original = conv.get('original_tokens', 0)
                    compressed = conv.get('compressed_tokens', 0)
                    reduction = ((original - compressed) / original * 100) if original > 0 else 0

                    handoffs.append({
                        'id': conv.get('id', 'unknown'),
                        'filename': Path(file_path).name if file_path else 'unknown',
                        'compression_format': comp_format,
                        'original_size': original * 4,  # Approx bytes
                        'final_size': compressed * 4,
                        'reduction_percent': round(reduction, 1),
                        'created': conv.get('created', datetime.now().isoformat()),
                        'project_id': conv.get('project', 'unknown'),
                        'session_id': conv.get('id', 'unknown'),
                        'category': 'conversation'  # Blue nodes
                    })
                except Exception as e:
                    # Skip individual files that cause errors
                    print(f"Warning: Skipped conversation {conv.get('id', 'unknown')}: {e}")
                    skipped += 1
                    continue

            # Load golden library handoffs
            if GOLDEN_INDEX_FILE.exists():
                try:
                    with open(GOLDEN_INDEX_FILE, 'r') as f:
                        golden_index = json.load(f)

                    golden_handoffs = golden_index.get('handoffs', [])

                    for gh in golden_handoffs:
                        try:
                            # Verify compressed file exists
                            compressed_file = gh.get('compressed_file')
                            if compressed_file:
                                full_path = GOLDEN_LIBRARY_DIR.parent / compressed_file
                                if not full_path.exists():
                                    skipped += 1
                                    continue

                            # Get sizes (prefer bytes, fallback to tokens)
                            original_bytes = gh.get('original_size_bytes', gh.get('original_size', 0))
                            compressed_bytes = gh.get('compressed_size_bytes', gh.get('compressed_size', 0))

                            # Calculate reduction
                            reduction = gh.get('reduction_percent', 0)
                            if reduction == 0 and original_bytes > 0:
                                reduction = ((original_bytes - compressed_bytes) / original_bytes * 100)

                            # Get format
                            comp_format = gh.get('format', gh.get('compression_format', 'v4z'))

                            handoffs.append({
                                'id': gh.get('handoff_id', 'unknown'),
                                'filename': gh.get('original_file', gh.get('source_file', 'unknown')),
                                'compression_format': comp_format,
                                'original_size': original_bytes,
                                'final_size': compressed_bytes,
                                'reduction_percent': round(reduction, 1),
                                'created': gh.get('created', datetime.now().isoformat()),
                                'project_id': gh.get('project', 'golden_library'),
                                'session_id': gh.get('handoff_id', 'unknown'),
                                'category': gh.get('category', 'plan'),  # Use category from index
                                'phase': gh.get('phase', 'unknown'),
                                'phase_name': gh.get('phase_name', '')
                            })
                        except Exception as e:
                            print(f"Warning: Skipped golden handoff {gh.get('handoff_id', 'unknown')}: {e}")
                            skipped += 1
                            continue

                except Exception as e:
                    print(f"Warning: Failed to load golden library index: {e}")

            # Check if we have any handoffs
            if not handoffs:
                self.serve_json({
                    'ok': True,
                    'count': 0,
                    'handoffs': [],
                    'message': 'No handoffs found. Both libraries are empty.'
                })
                return

            response = {
                'ok': True,
                'count': len(handoffs),
                'handoffs': handoffs
            }

            # Add warning if some files were skipped
            if skipped > 0:
                response['warning'] = f'{skipped} handoff(s) skipped due to errors'

            self.serve_json(response)
        except Exception as e:
            self.serve_json({
                'ok': False,
                'error': str(e),
                'message': 'Failed to load handoffs. Check server logs for details.'
            }, status=500)

    def serve_3d_stats(self):
        """Overall compression statistics for 3D viewer."""
        try:
            stats = self.get_compression_stats()
            conversations = stats.get('conversations', [])

            # Check for empty data
            if not conversations:
                self.serve_json({
                    'ok': True,
                    'total_handoffs': 0,
                    'total_original_bytes': 0,
                    'total_compressed_bytes': 0,
                    'avg_reduction_percent': 0,
                    'formats': {},
                    'categories': {},
                    'message': 'No data available yet'
                })
                return

            # Calculate format breakdown
            formats = {
                'slim_only': 0,
                'slim_v4z': 0,
                'slim_fsl': 0,
                'slim_ztpcf': 0,
                'unknown': 0,
                'json': 0
            }

            # Calculate category breakdown
            categories = stats.get('categories', {})

            for conv in conversations:
                try:
                    comp_format = self.infer_compression_format(conv)
                    if comp_format in formats:
                        formats[comp_format] += 1
                    else:
                        formats['unknown'] += 1
                except Exception as e:
                    formats['unknown'] += 1
                    continue

            total_original = sum(c.get('original_tokens', 0) for c in conversations) * 4
            total_compressed = sum(c.get('compressed_tokens', 0) for c in conversations) * 4
            avg_reduction = ((total_original - total_compressed) / total_original * 100) if total_original > 0 else 0

            self.serve_json({
                'ok': True,
                'total_handoffs': len(conversations),
                'total_original_bytes': total_original,
                'total_compressed_bytes': total_compressed,
                'bytes_saved': total_original - total_compressed,
                'avg_reduction_percent': round(avg_reduction, 1),
                'formats': formats,
                'categories': categories
            })
        except Exception as e:
            self.serve_json({
                'ok': False,
                'error': str(e),
                'message': 'Failed to calculate statistics'
            }, status=500)

    # =========================================================================
    # Comparison API
    # =========================================================================

    def serve_golden_handoffs(self):
        """List all golden library handoffs for comparison."""
        try:
            if not GOLDEN_INDEX_FILE.exists():
                self.serve_json({'ok': True, 'handoffs': []})
                return

            with open(GOLDEN_INDEX_FILE, 'r') as f:
                golden_index = json.load(f)

            handoffs = []
            for h in golden_index.get('handoffs', []):
                handoffs.append({
                    'id': h.get('handoff_id'),
                    'filename': h.get('filename', h.get('original_file', 'unknown')),
                    'title': h.get('title', 'Unknown'),
                    'compression_format': h.get('compression_format', 'unknown'),
                    'created': h.get('created', ''),
                    'original_size': h.get('original_size', 0),
                    'compressed_size': h.get('compressed_size', 0),
                    'final_size': h.get('compressed_size', 0),
                    'reduction_percent': h.get('reduction_percent', 0),
                    'category': 'golden_library'
                })

            self.serve_json({
                'ok': True,
                'handoffs': handoffs,
                'count': len(handoffs)
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.serve_json({'ok': False, 'error': str(e)}, status=500)

    def serve_compare(self, query_string):
        """Compare two handoffs and return diff."""
        try:
            from urllib.parse import parse_qs
            import difflib

            params = parse_qs(query_string)
            handoff_a = params.get('handoff_a', [None])[0]
            handoff_b = params.get('handoff_b', [None])[0]

            if not handoff_a or not handoff_b:
                self.serve_json({
                    'ok': False,
                    'error': 'Missing handoff_a or handoff_b parameter'
                }, status=400)
                return

            # Decompress both handoffs
            content_a = self._decompress_handoff(handoff_a)
            content_b = self._decompress_handoff(handoff_b)

            if not content_a:
                self.serve_json({
                    'ok': False,
                    'error': f'Failed to decompress handoff_a: {handoff_a}'
                }, status=404)
                return

            if not content_b:
                self.serve_json({
                    'ok': False,
                    'error': f'Failed to decompress handoff_b: {handoff_b}'
                }, status=404)
                return

            # Split into lines for diff
            lines_a = content_a.splitlines(keepends=True)
            lines_b = content_b.splitlines(keepends=True)

            # Generate unified diff
            unified_diff = list(difflib.unified_diff(
                lines_a,
                lines_b,
                fromfile=f'Handoff A ({handoff_a})',
                tofile=f'Handoff B ({handoff_b})',
                lineterm=''
            ))

            # Generate side-by-side diff data
            differ = difflib.Differ()
            diff_result = list(differ.compare(lines_a, lines_b))

            # Process diff for side-by-side view
            side_by_side = []
            for line in diff_result:
                prefix = line[0]
                content = line[2:] if len(line) > 2 else ''

                if prefix == ' ':  # unchanged
                    side_by_side.append({
                        'type': 'unchanged',
                        'left': content,
                        'right': content
                    })
                elif prefix == '-':  # removed
                    side_by_side.append({
                        'type': 'removed',
                        'left': content,
                        'right': ''
                    })
                elif prefix == '+':  # added
                    side_by_side.append({
                        'type': 'added',
                        'left': '',
                        'right': content
                    })

            # Calculate stats
            added = sum(1 for item in side_by_side if item['type'] == 'added')
            removed = sum(1 for item in side_by_side if item['type'] == 'removed')
            changed = added + removed

            self.serve_json({
                'ok': True,
                'handoff_a': handoff_a,
                'handoff_b': handoff_b,
                'unified_diff': ''.join(unified_diff),
                'side_by_side': side_by_side,
                'stats': {
                    'added': added,
                    'removed': removed,
                    'changed': changed,
                    'unchanged': len([x for x in side_by_side if x['type'] == 'unchanged'])
                }
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.serve_json({
                'ok': False,
                'error': f'Comparison failed: {str(e)}'
            }, status=500)

    def _decompress_handoff(self, handoff_id):
        """Decompress a single handoff and return content."""
        try:
            print(f"[_decompress_handoff] Attempting to decompress: {handoff_id}")
            # First check golden library
            if GOLDEN_INDEX_FILE.exists():
                try:
                    with open(GOLDEN_INDEX_FILE, 'r') as f:
                        golden_index = json.load(f)

                    for handoff in golden_index.get('handoffs', []):
                        if handoff.get('handoff_id') == handoff_id:
                            # Found in golden library
                            compressed_file = handoff.get('compressed_file')

                            # Try new format first (V4Z with compressed_file field)
                            if compressed_file:
                                full_path = GOLDEN_LIBRARY_DIR.parent / compressed_file
                                if full_path.exists():
                                    try:
                                        from v4z_compressor import V4ZCompressor
                                        compressor = V4ZCompressor()

                                        with open(full_path, 'r') as f:
                                            compressed_content = f.read()

                                        return compressor.decompress(compressed_content)
                                    except Exception as e:
                                        print(f"V4Z decompression failed: {e}")

                            # Try old format (plain .md files)
                            old_format_path = GOLDEN_LIBRARY_DIR / 'compressed' / f'{handoff_id}.md'
                            if old_format_path.exists():
                                with open(old_format_path, 'r') as f:
                                    return f.read()

                except Exception as e:
                    print(f"Warning: Failed to check golden library: {e}")

            # Check conversation library
            conv_compressed_dirs = [
                COMPRESSED_DIR / 'projects',
                COMPRESSED_DIR / 'todos'
            ]

            for conv_dir in conv_compressed_dirs:
                if not conv_dir.exists():
                    continue

                print(f"[_decompress_handoff] Searching in: {conv_dir}")

                # Try exact match
                slim_path = conv_dir / handoff_id
                print(f"[_decompress_handoff] Trying exact: {slim_path}")
                if slim_path.exists():
                    print(f"[_decompress_handoff] Found exact match!")
                    try:
                        from slim_converter import SlimConverter
                        converter = SlimConverter()
                        print(f"[_decompress_handoff] SlimConverter loaded")

                        with open(slim_path, 'r', encoding='utf-8') as f:
                            slim_content = f.read()
                        print(f"[_decompress_handoff] Read {len(slim_content)} bytes")

                        # Convert SLIM to JSONL
                        result = converter.slim_to_jsonl(slim_content)
                        print(f"[_decompress_handoff] Conversion successful, {len(result)} bytes")
                        return result
                    except Exception as e:
                        import traceback
                        print(f"SLIM decompression failed: {e}")
                        traceback.print_exc()

                # Try with common extensions (V4Z first, then old SLIM formats)
                for ext in ['.v4z', '', '.indexed', '.slim', '.slim.indexed']:
                    test_path = conv_dir / f'{handoff_id}{ext}'
                    print(f"[_decompress_handoff] Trying with extension '{ext}': {test_path}")
                    if test_path.exists():
                        print(f"[_decompress_handoff] Found with extension '{ext}'!")
                        try:
                            # V4Z format
                            if ext == '.v4z':
                                from v4z_compressor import V4ZCompressor
                                compressor = V4ZCompressor()
                                print(f"[_decompress_handoff] V4ZCompressor loaded")

                                with open(test_path, 'r', encoding='utf-8') as f:
                                    compressed_content = f.read()
                                print(f"[_decompress_handoff] Read {len(compressed_content)} bytes")

                                result = compressor.decompress(compressed_content)
                                print(f"[_decompress_handoff] Decompression successful, {len(result)} bytes")
                                return result
                            # SLIM format
                            else:
                                from slim_converter import SlimConverter
                                converter = SlimConverter()
                                print(f"[_decompress_handoff] SlimConverter loaded")

                                with open(test_path, 'r', encoding='utf-8') as f:
                                    slim_content = f.read()
                                print(f"[_decompress_handoff] Read {len(slim_content)} bytes")

                                result = converter.slim_to_jsonl(slim_content)
                                print(f"[_decompress_handoff] Conversion successful, {len(result)} bytes")
                                return result
                        except Exception as e:
                            import traceback
                            print(f"Decompression failed: {e}")
                            traceback.print_exc()

            print(f"[_decompress_handoff] Failed to find handoff: {handoff_id}")
            return None

        except Exception as e:
            print(f"Decompression error: {e}")
            return None

    # =========================================================================
    # Pattern Library API
    # =========================================================================

    def load_pattern_index(self):
        """Load the cross-repo pattern index."""
        pattern_index_file = GOLDEN_LIBRARY_DIR / "cross_repo_index.json"
        if not pattern_index_file.exists():
            return {"version": "1.0", "patterns": [], "categories": []}

        with open(pattern_index_file, 'r') as f:
            return json.load(f)

    def serve_pattern_search(self, query_string):
        """Search patterns by query string."""
        try:
            params = parse_qs(query_string)
            query = params.get('q', [''])[0].lower()
            category = params.get('category', [None])[0]
            limit = int(params.get('limit', ['50'])[0])

            # Load pattern index
            pattern_index = self.load_pattern_index()
            all_patterns = pattern_index.get('patterns', [])

            if not all_patterns:
                self.serve_json({
                    'ok': True,
                    'count': 0,
                    'patterns': [],
                    'message': 'No patterns indexed yet. Run scripts/scan-repos.py to build the index.'
                })
                return

            # Filter patterns
            results = []

            for pattern in all_patterns:
                # Category filter
                if category and pattern.get('category') != category:
                    continue

                # Query filter (search in title, description, tags, category)
                if query:
                    searchable_text = ' '.join([
                        pattern.get('title', ''),
                        pattern.get('description', ''),
                        pattern.get('category', ''),
                        ' '.join(pattern.get('tags', [])),
                        pattern.get('repo', ''),
                        pattern.get('file_path', '')
                    ]).lower()

                    if query not in searchable_text:
                        continue

                results.append(pattern)

            # Limit results
            results = results[:limit]

            self.serve_json({
                'ok': True,
                'count': len(results),
                'total_patterns': len(all_patterns),
                'query': query,
                'category': category,
                'patterns': results
            })

        except Exception as e:
            self.serve_json({
                'ok': False,
                'error': str(e),
                'message': 'Pattern search failed'
            }, status=500)

    def serve_pattern_categories(self):
        """List all pattern categories with counts."""
        try:
            pattern_index = self.load_pattern_index()
            all_patterns = pattern_index.get('patterns', [])

            # Count patterns by category
            category_counts = {}
            tag_counts = {}

            for pattern in all_patterns:
                category = pattern.get('category', 'unknown')
                category_counts[category] = category_counts.get(category, 0) + 1

                # Count tags
                for tag in pattern.get('tags', []):
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1

            # Sort by count
            categories = [
                {'name': cat, 'count': count}
                for cat, count in sorted(category_counts.items(), key=lambda x: -x[1])
            ]

            # Top tags
            top_tags = [
                {'name': tag, 'count': count}
                for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1])[:50]
            ]

            self.serve_json({
                'ok': True,
                'total_patterns': len(all_patterns),
                'categories': categories,
                'top_tags': top_tags,
                'category_definitions': pattern_index.get('categories', [])
            })

        except Exception as e:
            self.serve_json({
                'ok': False,
                'error': str(e),
                'message': 'Failed to load categories'
            }, status=500)

    def serve_patterns_by_category(self, query_string):
        """Get all patterns for a specific category."""
        try:
            params = parse_qs(query_string)
            category = params.get('category', [''])[0]
            limit = int(params.get('limit', ['100'])[0])

            if not category:
                self.serve_json({'error': 'Category parameter required'}, status=400)
                return

            pattern_index = self.load_pattern_index()
            all_patterns = pattern_index.get('patterns', [])

            # Filter by category
            category_patterns = [
                p for p in all_patterns
                if p.get('category') == category
            ][:limit]

            self.serve_json({
                'ok': True,
                'category': category,
                'count': len(category_patterns),
                'total_in_category': len([p for p in all_patterns if p.get('category') == category]),
                'patterns': category_patterns
            })

        except Exception as e:
            self.serve_json({
                'ok': False,
                'error': str(e),
                'message': 'Failed to get patterns by category'
            }, status=500)

    def search_3d_handoffs(self, data):
        """Search handoffs for 3D viewer."""
        try:
            query = data.get('query', '').lower()
            search_local = data.get('search_local', True)
            search_metadata = data.get('search_metadata', True)

            stats = self.get_compression_stats()
            conversations = stats.get('conversations', [])

            if not query:
                # Return all
                results = conversations[:50]  # Limit to 50
            else:
                # Simple search in title, id, project
                results = []
                for conv in conversations:
                    if search_metadata:
                        if (query in conv.get('title', '').lower() or
                            query in conv.get('id', '').lower() or
                            query in conv.get('project', '').lower()):
                            results.append(conv)

            # Transform to 3D format
            handoffs = []
            for conv in results:
                comp_format = self.infer_compression_format(conv)
                handoffs.append({
                    'id': conv.get('id', 'unknown'),
                    'filename': Path(conv.get('file_path', '')).name if conv.get('file_path') else 'unknown',
                    'match_score': 0.95  # Placeholder
                })

            self.serve_json({
                'ok': True,
                'results': handoffs
            })
        except Exception as e:
            self.serve_json({'ok': False, 'error': str(e)}, status=500)

    def decompress_3d_handoff(self, data):
        """Decompress a handoff."""
        try:
            handoff_id = data.get('handoff_id')

            if not handoff_id:
                self.serve_json({'ok': False, 'error': 'Missing handoff_id'}, status=400)
                return

            # First check golden library
            if GOLDEN_INDEX_FILE.exists():
                try:
                    with open(GOLDEN_INDEX_FILE, 'r') as f:
                        golden_index = json.load(f)

                    for handoff in golden_index.get('handoffs', []):
                        if handoff.get('handoff_id') == handoff_id:
                            # Found in golden library
                            compressed_file = handoff.get('compressed_file')

                            # Try new format first (V4Z with compressed_file field)
                            if compressed_file:
                                full_path = GOLDEN_LIBRARY_DIR.parent / compressed_file
                                if full_path.exists():
                                    try:
                                        from v4z_compressor import V4ZCompressor
                                        compressor = V4ZCompressor()

                                        with open(full_path, 'r') as f:
                                            compressed_content = f.read()

                                        decompressed_content = compressor.decompress(compressed_content)

                                        self.serve_json({
                                            'ok': True,
                                            'content': decompressed_content,
                                            'handoff_id': handoff_id,
                                            'source': 'golden_library'
                                        })
                                        return
                                    except Exception as e:
                                        self.serve_json({'ok': False, 'error': f'Decompression failed: {str(e)}'}, status=500)
                                        return

                            # Try old format (plain .md files)
                            old_format_path = GOLDEN_LIBRARY_DIR / 'compressed' / f'{handoff_id}.md'
                            if old_format_path.exists():
                                try:
                                    with open(old_format_path, 'r') as f:
                                        content = f.read()

                                    self.serve_json({
                                        'ok': True,
                                        'content': content,
                                        'handoff_id': handoff_id,
                                        'source': 'golden_library',
                                        'format': 'legacy_markdown'
                                    })
                                    return
                                except Exception as e:
                                    self.serve_json({'ok': False, 'error': f'Failed to read legacy file: {str(e)}'}, status=500)
                                    return

                except Exception as e:
                    print(f"Warning: Failed to check golden library: {e}")

            # Check conversation library
            # Try projects and todos subdirectories
            conv_compressed_dirs = [
                COMPRESSED_DIR / 'projects',
                COMPRESSED_DIR / 'todos'
            ]

            for conv_dir in conv_compressed_dirs:
                if not conv_dir.exists():
                    continue

                # Try exact match
                slim_path = conv_dir / handoff_id
                if slim_path.exists():
                    try:
                        from slim_converter import SlimConverter
                        converter = SlimConverter()

                        with open(slim_path, 'r', encoding='utf-8') as f:
                            slim_content = f.read()

                        # Convert SLIM to JSONL
                        jsonl_content = converter.slim_to_jsonl(slim_content)

                        self.serve_json({
                            'ok': True,
                            'content': jsonl_content,
                            'handoff_id': handoff_id,
                            'source': 'conversation_library',
                            'format': 'slim'
                        })
                        return
                    except Exception as e:
                        self.serve_json({'ok': False, 'error': f'SLIM decompression failed: {str(e)}'}, status=500)
                        return

                # Try with common extensions (V4Z first, then old SLIM formats)
                for ext in ['.v4z', '', '.indexed', '.slim', '.slim.indexed']:
                    test_path = conv_dir / f'{handoff_id}{ext}'
                    if test_path.exists():
                        try:
                            # V4Z format
                            if ext == '.v4z':
                                from v4z_compressor import V4ZCompressor
                                compressor = V4ZCompressor()

                                with open(test_path, 'r', encoding='utf-8') as f:
                                    compressed_content = f.read()

                                jsonl_content = compressor.decompress(compressed_content)

                                self.serve_json({
                                    'ok': True,
                                    'content': jsonl_content,
                                    'handoff_id': handoff_id,
                                    'source': 'conversation_library',
                                    'format': 'v4z'
                                })
                                return
                            # SLIM format
                            else:
                                from slim_converter import SlimConverter
                                converter = SlimConverter()

                                with open(test_path, 'r', encoding='utf-8') as f:
                                    slim_content = f.read()

                                jsonl_content = converter.slim_to_jsonl(slim_content)

                                self.serve_json({
                                    'ok': True,
                                    'content': jsonl_content,
                                    'handoff_id': handoff_id,
                                    'source': 'conversation_library',
                                    'format': 'slim'
                                })
                                return
                        except Exception as e:
                            self.serve_json({'ok': False, 'error': f'Decompression failed: {str(e)}'}, status=500)
                            return

            self.serve_json({'ok': False, 'error': 'Handoff not found'}, status=404)
        except Exception as e:
            self.serve_json({'ok': False, 'error': str(e)}, status=500)

    def restore_golden_plan(self, data):
        """Restore a golden library plan to CURRENT_PLAN.md."""
        try:
            handoff_id = data.get('handoff_id')

            if not handoff_id:
                self.serve_json({'ok': False, 'error': 'Missing handoff_id'}, status=400)
                return

            # Use the unarchive-phase.sh script
            script_path = GOLDEN_LIBRARY_DIR.parent / 'scripts' / 'unarchive-phase.sh'

            if not script_path.exists():
                self.serve_json({'ok': False, 'error': 'unarchive-phase.sh not found'}, status=500)
                return

            # Run the unarchive script
            result = subprocess.run(
                [str(script_path), handoff_id],
                cwd=GOLDEN_LIBRARY_DIR.parent,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                self.serve_json({
                    'ok': True,
                    'message': f'Restored handoff {handoff_id} to CURRENT_PLAN.md',
                    'handoff_id': handoff_id
                })
            else:
                error_msg = result.stderr if result.stderr else result.stdout
                self.serve_json({
                    'ok': False,
                    'error': f'Restore failed: {error_msg}'
                }, status=500)

        except subprocess.TimeoutExpired:
            self.serve_json({'ok': False, 'error': 'Restore operation timed out'}, status=500)
        except Exception as e:
            self.serve_json({'ok': False, 'error': str(e)}, status=500)

    def infer_compression_format(self, conv):
        """Infer compression format from conversation data by reading file header."""
        file_path = conv.get('file_path', '')

        # First try filename/title heuristics
        filename = file_path.lower()
        title = conv.get('title', '').lower()

        # If file_path exists, read the file to detect format
        if file_path and Path(file_path).exists():
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    # Read first 500 bytes to detect format
                    header = f.read(500)

                    # Check for SLIM format variations
                    if '§SLIM§' in header:
                        # Check for secondary compression layers
                        if 'v4z' in header.lower() or 'V4Z' in header:
                            return 'slim_v4z'
                        elif 'fsl' in header.lower() or 'FSL' in header:
                            return 'slim_fsl'
                        elif 'ztpcf' in header.lower() or 'ZTPCF' in header:
                            return 'slim_ztpcf'
                        else:
                            return 'slim_only'

                    # Check for other formats
                    if header.strip().startswith('{') or header.strip().startswith('['):
                        return 'json'

            except Exception as e:
                # If file read fails, fall back to filename heuristics
                pass

        # Fallback to filename heuristics
        if 'v4z' in filename or 'v4z' in title:
            return 'slim_v4z'
        elif 'fsl' in filename or 'fsl' in title:
            return 'slim_fsl'
        elif 'ztpcf' in filename or 'ztpcf' in title:
            return 'slim_ztpcf'
        elif 'slim' in filename or '.slim' in filename:
            return 'slim_only'
        else:
            return 'unknown'

    # =========================================================================
    # Collaborative Workspace Methods (Agent Chat)
    # =========================================================================

    def agent_chat(self, data):
        """Stream agent response from collaborative workspace."""
        global AGENT_ORCHESTRATOR

        agent_id = data.get('agent_id')
        message = data.get('message')
        document = data.get('document')  # Optional

        if not agent_id or not message:
            self.serve_json({'error': 'Missing agent_id or message'}, status=400)
            return

        # Initialize orchestrator on first use
        if AGENT_ORCHESTRATOR is None:
            try:
                AGENT_ORCHESTRATOR = AgentOrchestrator()
            except ValueError as e:
                self.serve_json({'error': str(e)}, status=500)
                return

        # Load document if provided and not already loaded
        if document and AGENT_ORCHESTRATOR.agents[agent_id].get('document') is None:
            AGENT_ORCHESTRATOR.load_document(agent_id, document)

        # Set headers for Server-Sent Events (SSE) streaming
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        try:
            # Stream response chunks
            for chunk in AGENT_ORCHESTRATOR.send_message(agent_id, message):
                # Send as SSE format: data: <content>\n\n
                self.wfile.write(f'data: {json.dumps({"chunk": chunk})}\n\n'.encode())
                self.wfile.flush()

            # Send completion marker
            self.wfile.write(f'data: {json.dumps({"done": True})}\n\n'.encode())
            self.wfile.flush()

        except Exception as e:
            error_msg = f'data: {json.dumps({"error": str(e)})}\n\n'
            self.wfile.write(error_msg.encode())
            self.wfile.flush()

    def agent_load_document(self, data):
        """Load a document into an agent's context."""
        global AGENT_ORCHESTRATOR

        agent_id = data.get('agent_id')
        document = data.get('document')
        handoff_id = data.get('handoff_id')  # Optional: load from V4Z handoff

        if not agent_id:
            self.serve_json({'error': 'Missing agent_id'}, status=400)
            return

        # Initialize orchestrator if needed
        if AGENT_ORCHESTRATOR is None:
            try:
                AGENT_ORCHESTRATOR = AgentOrchestrator()
            except ValueError as e:
                self.serve_json({'error': str(e)}, status=500)
                return

        # Load document from handoff if specified
        if handoff_id:
            try:
                # Decompress handoff to get content
                handoff_path = GOLDEN_LIBRARY_DIR / f"{handoff_id}.v4z"
                if not handoff_path.exists():
                    self.serve_json({'error': f'Handoff not found: {handoff_id}'}, status=404)
                    return

                # Use decompress script to get content
                import decompress
                with open(handoff_path, 'r') as f:
                    compressed = f.read()

                decompressed = decompress.decompress_v4z(compressed)
                document = decompressed

            except Exception as e:
                self.serve_json({'error': f'Failed to load handoff: {str(e)}'}, status=500)
                return

        if not document:
            self.serve_json({'error': 'Missing document or handoff_id'}, status=400)
            return

        try:
            AGENT_ORCHESTRATOR.load_document(agent_id, document)
            self.serve_json({
                'success': True,
                'agent_id': agent_id,
                'document_length': len(document)
            })
        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    # =========================================================================
    # API Keys Management
    # =========================================================================

    def serve_api_keys_list(self):
        """Load and return API keys from storage."""
        print(f"[DEBUG] serve_api_keys_list called, API_KEYS_FILE={API_KEYS_FILE}")
        try:
            if API_KEYS_FILE.exists():
                print(f"[DEBUG] API keys file exists, loading...")
                with open(API_KEYS_FILE, 'r') as f:
                    keys = json.load(f)
                print(f"[DEBUG] Loaded {len(keys)} keys")
                self.serve_json({'keys': keys})
            else:
                print(f"[DEBUG] API keys file does not exist, returning empty")
                self.serve_json({'keys': {}})
        except Exception as e:
            print(f"[DEBUG] Error in serve_api_keys_list: {e}")
            import traceback
            traceback.print_exc()
            self.serve_json({'error': str(e)}, status=500)

    def save_api_keys(self, data):
        """Save API keys to secure storage."""
        try:
            keys = data.get('keys', {})

            if not keys:
                self.serve_json({'error': 'No keys provided'}, status=400)
                return

            # Ensure .claude directory exists
            API_KEYS_FILE.parent.mkdir(parents=True, exist_ok=True)

            # Save keys to file
            with open(API_KEYS_FILE, 'w') as f:
                json.dump(keys, f, indent=2)

            # Set restrictive permissions (owner read/write only)
            os.chmod(API_KEYS_FILE, 0o600)

            self.serve_json({
                'success': True,
                'message': f'Saved {len(keys)} API key(s)',
                'count': len(keys)
            })

        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    # =========================================================================
    # Workspace Session Management (Phase 2)
    # =========================================================================

    def create_workspace_session(self, data):
        """Create a new workspace session."""
        if not session_manager:
            self.serve_json({'error': 'Session manager not available'}, status=500)
            return

        try:
            user_name = data.get('user_name', 'Anonymous')
            user_id = data.get('user_id') or str(uuid.uuid4())

            # Note: WebSocket connection will be added when user connects via WS
            # For now, create session without WS (will be added in WS handler)
            session_id = session_manager._generate_session_id()

            self.serve_json({
                'success': True,
                'session_id': session_id,
                'user_id': user_id,
                'invite_url': f'http://localhost:8080/?session={session_id}'
            })

        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    def join_workspace_session(self, data):
        """Join an existing workspace session."""
        if not session_manager:
            self.serve_json({'error': 'Session manager not available'}, status=500)
            return

        try:
            session_id = data.get('session_id')
            user_name = data.get('user_name', 'Anonymous')

            if not session_id:
                self.serve_json({'error': 'session_id required'}, status=400)
                return

            session = session_manager.get_session(session_id)

            if not session:
                self.serve_json({'error': 'Session not found'}, status=404)
                return

            if session.is_expired():
                self.serve_json({'error': 'Session expired'}, status=410)
                return

            user_id = str(uuid.uuid4())

            self.serve_json({
                'success': True,
                'session_id': session_id,
                'user_id': user_id,
                'session': session.to_dict()
            })

        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    # ===== Phase 4C.2: Canvas Collaboration API =====

    def serve_canvas_document(self, session_id):
        """Get canvas document for a session."""
        try:
            from src.canvas_sync_manager import get_canvas_sync_manager

            canvas_manager = get_canvas_sync_manager(session_manager)

            # Sync from session canvas_sections if exists
            doc = canvas_manager.sync_from_session_canvas(session_id)

            if not doc:
                # Get any existing documents
                docs = canvas_manager.get_session_documents(session_id)
                doc = docs[0] if docs else None

            if doc:
                self.serve_json({
                    'success': True,
                    'document': doc.to_dict()
                })
            else:
                self.serve_json({
                    'success': True,
                    'document': None,
                    'message': 'No canvas document found. Create one to start.'
                })

        except Exception as e:
            print(f"[Canvas] Error serving document: {e}")
            self.serve_json({'error': str(e)}, status=500)

    def create_canvas_document(self, session_id, data):
        """Create a new canvas document."""
        try:
            from src.canvas_sync_manager import get_canvas_sync_manager

            canvas_manager = get_canvas_sync_manager(session_manager)

            name = data.get('name', 'Shared Document')
            initial_sections = data.get('sections', [])

            doc = canvas_manager.create_document(
                session_id=session_id,
                name=name,
                initial_sections=initial_sections
            )

            self.serve_json({
                'success': True,
                'document': doc.to_dict()
            })

        except Exception as e:
            print(f"[Canvas] Error creating document: {e}")
            self.serve_json({'error': str(e)}, status=500)

    def add_canvas_section(self, session_id, data):
        """Add a section to a canvas document."""
        try:
            from src.canvas_sync_manager import get_canvas_sync_manager

            canvas_manager = get_canvas_sync_manager(session_manager)

            doc_id = data.get('document_id')
            section_name = data.get('section_name')
            section_type = data.get('section_type', 'markdown')
            content = data.get('content', '')
            owner = data.get('owner')

            if not doc_id or not section_name:
                self.serve_json({'error': 'document_id and section_name required'}, status=400)
                return

            section = canvas_manager.add_section(
                doc_id=doc_id,
                section_name=section_name,
                section_type=section_type,
                content=content,
                owner=owner
            )

            if section:
                self.serve_json({
                    'success': True,
                    'section': section.to_dict()
                })
            else:
                self.serve_json({'error': 'Failed to add section'}, status=400)

        except Exception as e:
            print(f"[Canvas] Error adding section: {e}")
            self.serve_json({'error': str(e)}, status=500)

    def edit_canvas_section(self, session_id, data):
        """Edit a canvas section."""
        try:
            from src.canvas_sync_manager import get_canvas_sync_manager

            canvas_manager = get_canvas_sync_manager(session_manager)

            doc_id = data.get('document_id')
            section_name = data.get('section_name')
            content = data.get('content', '')
            author_id = data.get('author_id', 'unknown')
            author_name = data.get('author_name', 'Unknown')

            if not doc_id or not section_name:
                self.serve_json({'error': 'document_id and section_name required'}, status=400)
                return

            success, edit = canvas_manager.apply_edit(
                doc_id=doc_id,
                section_name=section_name,
                author_id=author_id,
                author_name=author_name,
                content=content,
                operation='replace'
            )

            if success:
                section = canvas_manager.get_section(doc_id, section_name)
                self.serve_json({
                    'success': True,
                    'version': section.version if section else 1,
                    'edit_id': edit.id if edit else None
                })
            else:
                self.serve_json({'error': 'Edit failed (permission denied or section not found)'}, status=403)

        except Exception as e:
            print(f"[Canvas] Error editing section: {e}")
            self.serve_json({'error': str(e)}, status=500)

    def serve_canvas_export(self, session_id, query_string):
        """Export canvas document."""
        try:
            from src.canvas_sync_manager import get_canvas_sync_manager
            from urllib.parse import parse_qs

            params = parse_qs(query_string)
            doc_id = params.get('document_id', [''])[0]
            format_type = params.get('format', ['markdown'])[0]

            canvas_manager = get_canvas_sync_manager(session_manager)

            # Get document
            if doc_id:
                doc = canvas_manager.get_document(doc_id)
            else:
                docs = canvas_manager.get_session_documents(session_id)
                doc = docs[0] if docs else None

            if not doc:
                self.serve_json({'error': 'Document not found'}, status=404)
                return

            if format_type == 'markdown':
                content = canvas_manager.export_markdown(doc.id)
            elif format_type == 'html':
                content = canvas_manager.export_html(doc.id)
            elif format_type == 'json':
                content = canvas_manager.export_json(doc.id)
            else:
                content = canvas_manager.export_markdown(doc.id)

            self.serve_json({
                'success': True,
                'content': content,
                'format': format_type,
                'document_name': doc.name
            })

        except Exception as e:
            print(f"[Canvas] Error exporting: {e}")
            self.serve_json({'error': str(e)}, status=500)

    # ===== End Canvas Collaboration API =====

    def serve_session_info(self, session_id):
        """Get information about a session."""
        if not session_manager:
            self.serve_json({'error': 'Session manager not available'}, status=500)
            return

        try:
            session = session_manager.get_session(session_id)

            if not session:
                self.serve_json({'success': False, 'error': 'Session not found'}, status=404)
                return

            self.serve_json({'success': True, 'session': session.to_dict()})

        except Exception as e:
            self.serve_json({'success': False, 'error': str(e)}, status=500)

    def serve_session_stats(self):
        """Get statistics about all sessions."""
        if not session_manager:
            self.serve_json({'error': 'Session manager not available'}, status=500)
            return

        try:
            stats = session_manager.get_session_stats()
            self.serve_json(stats)

        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)

    # =========================================================================
    # INBOX COLLAB API
    # =========================================================================

    def _get_inbox_path(self, agent_id):
        """Get the FSL inbox file path for an agent."""
        inbox_dir = Path.home() / ".fsl" / "collab"
        agent_map = {
            'koda': 'inbox_b.fsl',
            'cairn': 'inbox_a.fsl',
            'prax': 'inbox_d.fsl',
            'moderator': 'inbox_d.fsl',
            'all': 'inbox_all.fsl'
        }
        filename = agent_map.get(agent_id.lower(), f'inbox_{agent_id}.fsl')
        return inbox_dir / filename

    def _parse_fsl_messages(self, content, limit=50):
        """Parse FSL inbox messages into structured format."""
        import re
        import hashlib

        messages = []
        # Pattern for §MSG§{FROM}→{TO}§{TYPE}§§{CONTENT}§{TIMESTAMP}§{HASH}§
        msg_pattern = re.compile(
            r'§MSG§([A-Z]+)→([A-Z]+)§([a-z]?)§§(.+?)§(\d{10,})§([a-f0-9]+)§',
            re.DOTALL
        )

        # Pattern for stone format §T:{TARGET}§o:{objective}§p:{PRIORITY}§...
        stone_pattern = re.compile(
            r'§T:([A-Z]+)§o:([^§]+)§p:([HML])§(?:stone:([a-f0-9]+)§)?(?:c:([^§]*)§)?from:([A-Z]+)§',
            re.DOTALL
        )

        sender_names = {
            'D': 'Prax', 'K': 'Koda', 'B': 'Koda',
            'A': 'Cairn', 'C': 'Cairn', 'H': 'Helper',
            'O': 'Operator', 'PHI': 'Phi'
        }

        priority_map = {'H': 'high', 'M': 'normal', 'L': 'low', 'h': 'high', 'n': 'normal'}

        lines = content.strip().split('\n')
        for line in reversed(lines):
            if len(messages) >= limit:
                break

            line = line.strip()
            if not line:
                continue

            # Try MSG format
            match = msg_pattern.search(line)
            if match:
                from_id, to_id, msg_type, content_text, timestamp, msg_hash = match.groups()
                messages.append({
                    'id': msg_hash,
                    'from_agent': sender_names.get(from_id, from_id),
                    'from_id': from_id,
                    'to_id': to_id,
                    'content': content_text[:500],
                    'timestamp': int(timestamp) * 1000,  # Convert to ms
                    'priority': priority_map.get(msg_type, 'normal'),
                    'read': False,
                    'type': 'message'
                })
                continue

            # Try stone format
            match = stone_pattern.search(line)
            if match:
                target, objective, priority, stone_hash, context, sender = match.groups()
                msg_hash = hashlib.md5(line.encode()).hexdigest()[:12]
                messages.append({
                    'id': msg_hash,
                    'from_agent': sender_names.get(sender, sender),
                    'from_id': sender,
                    'to_id': target,
                    'content': f"Task: {objective}" + (f" (context: {context})" if context else ""),
                    'timestamp': int(datetime.now().timestamp() * 1000),
                    'priority': priority_map.get(priority, 'normal'),
                    'read': False,
                    'type': 'task',
                    'metadata': {
                        'stone_hash': stone_hash,
                        'objective': objective
                    }
                })

        return messages

    def serve_inbox(self, agent_id, query_string):
        """Get inbox messages for an agent."""
        try:
            inbox_path = self._get_inbox_path(agent_id)

            if not inbox_path.exists():
                # Create empty inbox if it doesn't exist
                inbox_path.parent.mkdir(parents=True, exist_ok=True)
                inbox_path.write_text('')
                self.serve_json({
                    'success': True,
                    'agent': agent_id,
                    'messages': [],
                    'count': 0
                })
                return

            content = inbox_path.read_text()
            messages = self._parse_fsl_messages(content)

            # Also check inbox_all.fsl for broadcast messages
            all_inbox = self._get_inbox_path('all')
            if all_inbox.exists():
                all_content = all_inbox.read_text()
                all_messages = self._parse_fsl_messages(all_content, limit=20)
                messages.extend(all_messages)

            # Sort by timestamp descending
            messages.sort(key=lambda m: m['timestamp'], reverse=True)

            self.serve_json({
                'success': True,
                'agent': agent_id,
                'messages': messages[:50],
                'count': len(messages)
            })

        except Exception as e:
            self.serve_json({'success': False, 'error': str(e)}, status=500)

    def send_inbox_message(self, data):
        """Send a message to an agent's inbox."""
        import hashlib
        import time

        try:
            target = data.get('target', '').lower()
            message = data.get('message', '')
            sender = data.get('from', 'D')  # Default to Prax/Desktop
            priority = data.get('priority', 'n')
            msg_type = data.get('type', 'message')

            if not target or not message:
                self.serve_json({'success': False, 'error': 'Missing target or message'}, status=400)
                return

            # Map agent names to IDs
            target_map = {
                'koda': 'B', 'cairn': 'A', 'prax': 'D',
                'moderator': 'D', 'all': 'ALL'
            }
            sender_map = {
                'koda': 'K', 'cairn': 'C', 'prax': 'D',
                'moderator': 'D', 'operator': 'O'
            }

            target_id = target_map.get(target, target.upper())
            sender_id = sender_map.get(sender.lower(), sender.upper())

            timestamp = int(time.time())
            msg_hash = hashlib.md5(f"{timestamp}{message[:50]}".encode()).hexdigest()[:12]

            # Format: §MSG§{FROM}→{TO}§{TYPE}§§{CONTENT}§{TIMESTAMP}§{HASH}§
            priority_char = 'h' if priority in ['high', 'H'] else 'n'
            fsl_msg = f"§MSG§{sender_id}→{target_id}§{priority_char}§§{message}§{timestamp}§{msg_hash}§\n"

            # Write to target inbox
            inbox_path = self._get_inbox_path(target)
            inbox_path.parent.mkdir(parents=True, exist_ok=True)

            with open(inbox_path, 'a') as f:
                f.write(fsl_msg)

            self.serve_json({
                'success': True,
                'message_id': msg_hash,
                'target': target,
                'timestamp': timestamp
            })

        except Exception as e:
            self.serve_json({'success': False, 'error': str(e)}, status=500)

    def mark_inbox_read(self, data):
        """Mark inbox messages as read (stored in separate tracking file)."""
        try:
            agent_id = data.get('agent', '')
            message_ids = data.get('message_ids', [])

            if not agent_id or not message_ids:
                self.serve_json({'success': False, 'error': 'Missing agent or message_ids'}, status=400)
                return

            # Store read status in a separate file
            read_file = Path.home() / ".fsl" / "collab" / f"read_{agent_id}.json"
            read_file.parent.mkdir(parents=True, exist_ok=True)

            existing = {}
            if read_file.exists():
                try:
                    existing = json.loads(read_file.read_text())
                except:
                    pass

            for msg_id in message_ids:
                existing[msg_id] = int(datetime.now().timestamp() * 1000)

            read_file.write_text(json.dumps(existing, indent=2))

            self.serve_json({'success': True, 'marked': len(message_ids)})

        except Exception as e:
            self.serve_json({'success': False, 'error': str(e)}, status=500)

    # ==================== CALENDAR API ====================

    def _get_calendar_path(self, agent_id):
        """Get the calendar JSON file path for an agent."""
        calendar_dir = Path.home() / ".fsl" / "collab" / "calendars"
        calendar_dir.mkdir(parents=True, exist_ok=True)
        agent_map = {
            'koda': 'calendar_koda.json',
            'cairn': 'calendar_cairn.json',
            'prax': 'calendar_prax.json',
            'user': 'calendar_user.json'
        }
        filename = agent_map.get(agent_id.lower(), f'calendar_{agent_id}.json')
        return calendar_dir / filename

    def _get_calendar_events(self, agent_id):
        """Load calendar events for an agent."""
        calendar_path = self._get_calendar_path(agent_id)
        if not calendar_path.exists():
            return []
        try:
            return json.loads(calendar_path.read_text())
        except:
            return []

    def _save_calendar_events(self, agent_id, events):
        """Save calendar events for an agent."""
        calendar_path = self._get_calendar_path(agent_id)
        calendar_path.write_text(json.dumps(events, indent=2))

    def serve_calendar(self, agent_id, query_string):
        """Get calendar events for an agent."""
        try:
            params = parse_qs(query_string)
            start_date = params.get('start', [None])[0]
            end_date = params.get('end', [None])[0]

            events = self._get_calendar_events(agent_id)

            # Filter by date range if provided
            if start_date or end_date:
                filtered = []
                for event in events:
                    event_start = event.get('start', '')
                    event_end = event.get('end', event_start)
                    # Simple string comparison works for ISO dates
                    if start_date and event_end < start_date:
                        continue
                    if end_date and event_start > end_date:
                        continue
                    filtered.append(event)
                events = filtered

            # Add agent color to events
            agent_colors = {
                'koda': '#3b82f6',    # Blue
                'cairn': '#a855f7',   # Purple
                'prax': '#eab308',    # Yellow/Gold
                'user': '#22c55e'     # Green
            }
            for event in events:
                if 'color' not in event:
                    event['color'] = agent_colors.get(agent_id.lower(), '#6b7280')
                event['agent'] = agent_id

            self.serve_json({
                'success': True,
                'agent': agent_id,
                'events': events,
                'count': len(events)
            })

        except Exception as e:
            self.serve_json({'success': False, 'error': str(e)}, status=500)

    def serve_calendar_combined(self, query_string):
        """Get combined calendar events from multiple agents."""
        try:
            params = parse_qs(query_string)
            agents = params.get('agents', ['koda,cairn,prax,user'])[0].split(',')
            start_date = params.get('start', [None])[0]
            end_date = params.get('end', [None])[0]

            agent_colors = {
                'koda': '#3b82f6',    # Blue
                'cairn': '#a855f7',   # Purple
                'prax': '#eab308',    # Yellow/Gold
                'user': '#22c55e'     # Green
            }

            all_events = []
            for agent_id in agents:
                agent_id = agent_id.strip().lower()
                events = self._get_calendar_events(agent_id)

                for event in events:
                    # Filter by date range
                    if start_date or end_date:
                        event_start = event.get('start', '')
                        event_end = event.get('end', event_start)
                        if start_date and event_end < start_date:
                            continue
                        if end_date and event_start > end_date:
                            continue

                    # Add agent info
                    event['agent'] = agent_id
                    if 'color' not in event:
                        event['color'] = agent_colors.get(agent_id, '#6b7280')
                    all_events.append(event)

            # Sort by start date
            all_events.sort(key=lambda e: e.get('start', ''))

            self.serve_json({
                'success': True,
                'agents': agents,
                'events': all_events,
                'count': len(all_events)
            })

        except Exception as e:
            self.serve_json({'success': False, 'error': str(e)}, status=500)

    def create_calendar_event(self, data):
        """Create or update a calendar event."""
        import hashlib

        try:
            agent_id = data.get('agent', 'user').lower()
            event_id = data.get('id')
            title = data.get('title', 'Untitled Event')
            start = data.get('start')  # ISO date string: 2024-01-17T10:00
            end = data.get('end', start)
            event_type = data.get('type', 'event')  # event, meeting, task, deadline
            description = data.get('description', '')
            color = data.get('color')

            if not start:
                self.serve_json({'success': False, 'error': 'Missing start date'}, status=400)
                return

            events = self._get_calendar_events(agent_id)

            # Generate ID if not provided (new event)
            if not event_id:
                event_id = hashlib.md5(f"{agent_id}{start}{title}{datetime.now().timestamp()}".encode()).hexdigest()[:12]
                is_new = True
            else:
                is_new = not any(e.get('id') == event_id for e in events)

            event = {
                'id': event_id,
                'title': title,
                'start': start,
                'end': end,
                'type': event_type,
                'description': description,
                'created': datetime.now().isoformat() if is_new else data.get('created', datetime.now().isoformat()),
                'updated': datetime.now().isoformat()
            }

            if color:
                event['color'] = color

            if is_new:
                events.append(event)
            else:
                # Update existing event
                events = [e if e.get('id') != event_id else event for e in events]

            self._save_calendar_events(agent_id, events)

            self.serve_json({
                'success': True,
                'event': event,
                'is_new': is_new
            })

        except Exception as e:
            self.serve_json({'success': False, 'error': str(e)}, status=500)

    def delete_calendar_event(self, data):
        """Delete a calendar event."""
        try:
            agent_id = data.get('agent', 'user').lower()
            event_id = data.get('id')

            if not event_id:
                self.serve_json({'success': False, 'error': 'Missing event id'}, status=400)
                return

            events = self._get_calendar_events(agent_id)
            original_count = len(events)
            events = [e for e in events if e.get('id') != event_id]

            if len(events) == original_count:
                self.serve_json({'success': False, 'error': 'Event not found'}, status=404)
                return

            self._save_calendar_events(agent_id, events)

            self.serve_json({
                'success': True,
                'deleted': event_id
            })

        except Exception as e:
            self.serve_json({'success': False, 'error': str(e)}, status=500)

    # ==================== END CALENDAR API ====================

    # ==================== TASK ASSIGNMENT & WEBHOOKS ====================

    def _get_webhooks_path(self):
        """Get the webhooks configuration file path."""
        webhooks_dir = Path.home() / ".fsl" / "collab"
        webhooks_dir.mkdir(parents=True, exist_ok=True)
        return webhooks_dir / "webhooks.json"

    def _get_triggers_log_path(self):
        """Get the triggers log file path."""
        triggers_dir = Path.home() / ".fsl" / "collab"
        triggers_dir.mkdir(parents=True, exist_ok=True)
        return triggers_dir / "triggers_log.json"

    def _load_webhooks(self):
        """Load webhook configurations."""
        path = self._get_webhooks_path()
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text())
        except:
            return []

    def _save_webhooks(self, webhooks):
        """Save webhook configurations."""
        path = self._get_webhooks_path()
        path.write_text(json.dumps(webhooks, indent=2))

    def _load_triggers_log(self):
        """Load triggers log (tracks what's been fired)."""
        path = self._get_triggers_log_path()
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text())
        except:
            return {}

    def _save_triggers_log(self, log):
        """Save triggers log."""
        path = self._get_triggers_log_path()
        path.write_text(json.dumps(log, indent=2))

    def assign_task(self, data):
        """Assign a task from Prax to Koda/Cairn - creates inbox message + calendar event."""
        import hashlib
        import time

        try:
            target_agent = data.get('target', '').lower()  # koda, cairn
            title = data.get('title', 'Untitled Task')
            description = data.get('description', '')
            due_date = data.get('due_date')  # ISO datetime string
            priority = data.get('priority', 'normal')  # high, normal, low
            from_agent = data.get('from', 'prax').lower()

            if not target_agent or target_agent not in ['koda', 'cairn']:
                self.serve_json({'success': False, 'error': 'Invalid target agent'}, status=400)
                return

            if not due_date:
                self.serve_json({'success': False, 'error': 'Due date required'}, status=400)
                return

            timestamp = int(time.time())
            task_id = hashlib.md5(f"{target_agent}{title}{timestamp}".encode()).hexdigest()[:12]

            # 1. Create calendar event (deadline)
            calendar_event = {
                'id': task_id,
                'title': f"[TASK] {title}",
                'start': due_date,
                'end': due_date,
                'type': 'deadline',
                'description': description,
                'assigned_by': from_agent,
                'priority': priority,
                'status': 'pending',
                'created': datetime.now().isoformat(),
                'updated': datetime.now().isoformat()
            }

            events = self._get_calendar_events(target_agent)
            events.append(calendar_event)
            self._save_calendar_events(target_agent, events)

            # 2. Create inbox message
            sender_map = {'prax': 'D', 'koda': 'K', 'cairn': 'C'}
            target_map = {'koda': 'B', 'cairn': 'A'}
            sender_id = sender_map.get(from_agent, 'D')
            target_id = target_map.get(target_agent, 'B')

            priority_char = 'h' if priority == 'high' else 'n'
            msg_content = f"TASK: {title}"
            if description:
                msg_content += f" | {description[:100]}"
            msg_content += f" | Due: {due_date}"

            fsl_msg = f"§MSG§{sender_id}→{target_id}§{priority_char}§§{msg_content}§{timestamp}§{task_id}§\n"

            inbox_path = self._get_inbox_path(target_agent)
            inbox_path.parent.mkdir(parents=True, exist_ok=True)
            with open(inbox_path, 'a') as f:
                f.write(fsl_msg)

            # 3. Schedule triggers (24h and 1h reminders)
            triggers_log = self._load_triggers_log()
            due_dt = datetime.fromisoformat(due_date.replace('Z', '+00:00') if due_date.endswith('Z') else due_date)

            # Calculate reminder times
            reminder_24h = (due_dt - timedelta(hours=24)).isoformat()
            reminder_1h = (due_dt - timedelta(hours=1)).isoformat()

            triggers_log[task_id] = {
                'task_id': task_id,
                'title': title,
                'target_agent': target_agent,
                'due_date': due_date,
                'reminders': {
                    '24h': {'time': reminder_24h, 'fired': False},
                    '1h': {'time': reminder_1h, 'fired': False},
                    'due': {'time': due_date, 'fired': False}
                },
                'webhooks_fired': []
            }
            self._save_triggers_log(triggers_log)

            self.serve_json({
                'success': True,
                'task_id': task_id,
                'calendar_event': calendar_event,
                'inbox_sent': True,
                'triggers_scheduled': ['24h', '1h', 'due']
            })

        except Exception as e:
            self.serve_json({'success': False, 'error': str(e)}, status=500)

    def serve_webhooks_list(self):
        """List all configured webhooks."""
        try:
            webhooks = self._load_webhooks()
            self.serve_json({
                'success': True,
                'webhooks': webhooks,
                'count': len(webhooks)
            })
        except Exception as e:
            self.serve_json({'success': False, 'error': str(e)}, status=500)

    def save_webhook(self, data):
        """Save a webhook configuration."""
        import hashlib

        try:
            webhook_id = data.get('id')
            name = data.get('name', 'Unnamed Webhook')
            url = data.get('url')
            trigger_type = data.get('trigger_type', 'event_start')  # event_start, reminder_24h, reminder_1h, task_due
            agent_filter = data.get('agent_filter', [])  # empty = all agents
            event_type_filter = data.get('event_type_filter', [])  # empty = all types
            enabled = data.get('enabled', True)
            headers = data.get('headers', {})
            payload_template = data.get('payload_template', None)

            if not url:
                self.serve_json({'success': False, 'error': 'URL required'}, status=400)
                return

            webhooks = self._load_webhooks()

            if not webhook_id:
                webhook_id = hashlib.md5(f"{url}{name}{datetime.now().timestamp()}".encode()).hexdigest()[:12]
                is_new = True
            else:
                is_new = not any(w.get('id') == webhook_id for w in webhooks)

            webhook = {
                'id': webhook_id,
                'name': name,
                'url': url,
                'trigger_type': trigger_type,
                'agent_filter': agent_filter,
                'event_type_filter': event_type_filter,
                'enabled': enabled,
                'headers': headers,
                'payload_template': payload_template,
                'created': datetime.now().isoformat() if is_new else data.get('created'),
                'updated': datetime.now().isoformat()
            }

            if is_new:
                webhooks.append(webhook)
            else:
                webhooks = [w if w.get('id') != webhook_id else webhook for w in webhooks]

            self._save_webhooks(webhooks)

            self.serve_json({
                'success': True,
                'webhook': webhook,
                'is_new': is_new
            })

        except Exception as e:
            self.serve_json({'success': False, 'error': str(e)}, status=500)

    def delete_webhook(self, data):
        """Delete a webhook configuration."""
        try:
            webhook_id = data.get('id')
            if not webhook_id:
                self.serve_json({'success': False, 'error': 'Webhook ID required'}, status=400)
                return

            webhooks = self._load_webhooks()
            original_count = len(webhooks)
            webhooks = [w for w in webhooks if w.get('id') != webhook_id]

            if len(webhooks) == original_count:
                self.serve_json({'success': False, 'error': 'Webhook not found'}, status=404)
                return

            self._save_webhooks(webhooks)
            self.serve_json({'success': True, 'deleted': webhook_id})

        except Exception as e:
            self.serve_json({'success': False, 'error': str(e)}, status=500)

    def test_webhook(self, data):
        """Test a webhook by sending a test payload."""
        import urllib.request
        import urllib.error

        try:
            url = data.get('url')
            headers = data.get('headers', {})

            if not url:
                self.serve_json({'success': False, 'error': 'URL required'}, status=400)
                return

            # Build test payload
            test_payload = {
                'type': 'test',
                'message': 'Webhook test from Trinity Calendar',
                'timestamp': datetime.now().isoformat(),
                'source': 'trinity_dashboard'
            }

            payload_bytes = json.dumps(test_payload).encode('utf-8')

            req = urllib.request.Request(url, data=payload_bytes, method='POST')
            req.add_header('Content-Type', 'application/json')
            for key, value in headers.items():
                req.add_header(key, value)

            try:
                with urllib.request.urlopen(req, timeout=10) as response:
                    status = response.status
                    response_body = response.read().decode('utf-8')[:500]
                    self.serve_json({
                        'success': True,
                        'status_code': status,
                        'response': response_body
                    })
            except urllib.error.HTTPError as e:
                self.serve_json({
                    'success': False,
                    'status_code': e.code,
                    'error': str(e.reason)
                })
            except urllib.error.URLError as e:
                self.serve_json({
                    'success': False,
                    'error': f'Connection failed: {str(e.reason)}'
                })

        except Exception as e:
            self.serve_json({'success': False, 'error': str(e)}, status=500)

    def serve_pending_triggers(self):
        """Get pending triggers that need to fire."""
        try:
            triggers_log = self._load_triggers_log()
            now = datetime.now()
            pending = []

            for task_id, trigger_info in triggers_log.items():
                for reminder_type, reminder_data in trigger_info.get('reminders', {}).items():
                    if not reminder_data.get('fired', False):
                        reminder_time = datetime.fromisoformat(reminder_data['time'].replace('Z', '+00:00') if reminder_data['time'].endswith('Z') else reminder_data['time'])
                        if reminder_time <= now:
                            pending.append({
                                'task_id': task_id,
                                'title': trigger_info.get('title'),
                                'target_agent': trigger_info.get('target_agent'),
                                'reminder_type': reminder_type,
                                'reminder_time': reminder_data['time'],
                                'due_date': trigger_info.get('due_date')
                            })

            self.serve_json({
                'success': True,
                'pending': pending,
                'count': len(pending)
            })

        except Exception as e:
            self.serve_json({'success': False, 'error': str(e)}, status=500)

    def process_calendar_triggers(self, data):
        """Process pending calendar triggers - send reminders and fire webhooks."""
        import urllib.request
        import urllib.error
        import time

        try:
            triggers_log = self._load_triggers_log()
            webhooks = self._load_webhooks()
            now = datetime.now()
            processed = []
            errors = []

            for task_id, trigger_info in list(triggers_log.items()):
                target_agent = trigger_info.get('target_agent')
                title = trigger_info.get('title')

                for reminder_type, reminder_data in trigger_info.get('reminders', {}).items():
                    if reminder_data.get('fired', False):
                        continue

                    try:
                        reminder_time = datetime.fromisoformat(
                            reminder_data['time'].replace('Z', '+00:00') if reminder_data['time'].endswith('Z') else reminder_data['time']
                        )
                    except:
                        continue

                    if reminder_time <= now:
                        # 1. Send inbox reminder
                        reminder_msgs = {
                            '24h': f"REMINDER: Task '{title}' is due in 24 hours!",
                            '1h': f"URGENT: Task '{title}' is due in 1 hour!",
                            'due': f"DEADLINE NOW: Task '{title}' is due!"
                        }

                        msg = reminder_msgs.get(reminder_type, f"Reminder for: {title}")
                        timestamp = int(time.time())
                        msg_hash = hashlib.md5(f"{timestamp}{msg[:20]}".encode()).hexdigest()[:12]
                        priority_char = 'h' if reminder_type in ['1h', 'due'] else 'n'
                        target_map = {'koda': 'B', 'cairn': 'A'}
                        target_id = target_map.get(target_agent, 'B')

                        fsl_msg = f"§MSG§SYS→{target_id}§{priority_char}§§{msg}§{timestamp}§{msg_hash}§\n"

                        inbox_path = self._get_inbox_path(target_agent)
                        with open(inbox_path, 'a') as f:
                            f.write(fsl_msg)

                        # 2. Fire matching webhooks
                        trigger_type_map = {
                            '24h': 'reminder_24h',
                            '1h': 'reminder_1h',
                            'due': 'task_due'
                        }
                        webhook_trigger = trigger_type_map.get(reminder_type)

                        for webhook in webhooks:
                            if not webhook.get('enabled', True):
                                continue
                            if webhook.get('trigger_type') != webhook_trigger:
                                continue
                            if webhook.get('agent_filter') and target_agent not in webhook.get('agent_filter'):
                                continue

                            # Fire webhook
                            webhook_payload = {
                                'type': webhook_trigger,
                                'task_id': task_id,
                                'title': title,
                                'target_agent': target_agent,
                                'due_date': trigger_info.get('due_date'),
                                'timestamp': datetime.now().isoformat()
                            }

                            try:
                                payload_bytes = json.dumps(webhook_payload).encode('utf-8')
                                req = urllib.request.Request(webhook['url'], data=payload_bytes, method='POST')
                                req.add_header('Content-Type', 'application/json')
                                for key, value in webhook.get('headers', {}).items():
                                    req.add_header(key, value)

                                with urllib.request.urlopen(req, timeout=10) as response:
                                    trigger_info.setdefault('webhooks_fired', []).append({
                                        'webhook_id': webhook['id'],
                                        'trigger_type': webhook_trigger,
                                        'fired_at': datetime.now().isoformat(),
                                        'status': response.status
                                    })
                            except Exception as webhook_error:
                                errors.append({
                                    'webhook_id': webhook['id'],
                                    'error': str(webhook_error)
                                })

                        # Mark as fired
                        reminder_data['fired'] = True
                        reminder_data['fired_at'] = datetime.now().isoformat()

                        processed.append({
                            'task_id': task_id,
                            'reminder_type': reminder_type,
                            'target_agent': target_agent
                        })

            self._save_triggers_log(triggers_log)

            self.serve_json({
                'success': True,
                'processed': processed,
                'processed_count': len(processed),
                'errors': errors
            })

        except Exception as e:
            import traceback
            self.serve_json({'success': False, 'error': str(e), 'traceback': traceback.format_exc()}, status=500)

    # ==================== END TASK ASSIGNMENT & WEBHOOKS ====================

    # ==================== TODO SYSTEM ====================

    def _get_todos_path(self, agent_id):
        """Get the todos JSON file path for an agent."""
        todos_dir = Path.home() / ".fsl" / "collab" / "todos"
        todos_dir.mkdir(parents=True, exist_ok=True)
        return todos_dir / f"todos_{agent_id}.json"

    def _get_prds_path(self):
        """Get the PRDs storage path."""
        prds_dir = Path.home() / ".fsl" / "collab" / "prds"
        prds_dir.mkdir(parents=True, exist_ok=True)
        return prds_dir

    def _load_todos(self, agent_id):
        """Load todos for an agent."""
        path = self._get_todos_path(agent_id)
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text())
        except:
            return []

    def _save_todos(self, agent_id, todos):
        """Save todos for an agent."""
        path = self._get_todos_path(agent_id)
        path.write_text(json.dumps(todos, indent=2))

    def _load_all_todos(self):
        """Load todos from all agents."""
        all_todos = []
        for agent in ['koda', 'cairn', 'prax']:
            todos = self._load_todos(agent)
            for todo in todos:
                todo['agent'] = agent
            all_todos.extend(todos)
        return all_todos

    def serve_todos(self, agent_id, query_string):
        """Get todos for an agent."""
        try:
            params = parse_qs(query_string)
            status_filter = params.get('status', [None])[0]
            priority_filter = params.get('priority', [None])[0]
            include_subtasks = params.get('subtasks', ['true'])[0] == 'true'

            todos = self._load_todos(agent_id)

            # Apply filters
            if status_filter:
                todos = [t for t in todos if t.get('status') == status_filter]
            if priority_filter:
                todos = [t for t in todos if t.get('priority') == priority_filter]

            # Sort by priority then due date
            priority_order = {'high': 0, 'normal': 1, 'low': 2}
            todos.sort(key=lambda t: (
                priority_order.get(t.get('priority', 'normal'), 1),
                t.get('due_date', '9999')
            ))

            # Count by status
            all_todos = self._load_todos(agent_id)
            stats = {
                'total': len(all_todos),
                'pending': len([t for t in all_todos if t.get('status') == 'pending']),
                'in_progress': len([t for t in all_todos if t.get('status') == 'in_progress']),
                'completed': len([t for t in all_todos if t.get('status') == 'completed']),
                'blocked': len([t for t in all_todos if t.get('status') == 'blocked'])
            }

            self.serve_json({
                'success': True,
                'agent': agent_id,
                'todos': todos,
                'stats': stats,
                'count': len(todos)
            })

        except Exception as e:
            self.serve_json({'success': False, 'error': str(e)}, status=500)

    def serve_todos_unified(self, query_string):
        """Get unified todos from all agents."""
        try:
            params = parse_qs(query_string)
            status_filter = params.get('status', [None])[0]
            agents_filter = params.get('agents', [None])[0]

            all_todos = []
            agents_list = agents_filter.split(',') if agents_filter else ['koda', 'cairn', 'prax']

            for agent in agents_list:
                agent = agent.strip()
                todos = self._load_todos(agent)
                for todo in todos:
                    todo['agent'] = agent
                    if status_filter and todo.get('status') != status_filter:
                        continue
                    all_todos.append(todo)

            # Sort by priority then due date
            priority_order = {'high': 0, 'normal': 1, 'low': 2}
            all_todos.sort(key=lambda t: (
                priority_order.get(t.get('priority', 'normal'), 1),
                t.get('due_date', '9999')
            ))

            # Aggregate stats
            stats = {
                'total': len(all_todos),
                'by_agent': {},
                'by_status': {
                    'pending': 0, 'in_progress': 0, 'completed': 0, 'blocked': 0
                }
            }
            for todo in all_todos:
                agent = todo.get('agent', 'unknown')
                status = todo.get('status', 'pending')
                stats['by_agent'][agent] = stats['by_agent'].get(agent, 0) + 1
                stats['by_status'][status] = stats['by_status'].get(status, 0) + 1

            self.serve_json({
                'success': True,
                'todos': all_todos,
                'stats': stats,
                'count': len(all_todos)
            })

        except Exception as e:
            self.serve_json({'success': False, 'error': str(e)}, status=500)

    def serve_todos_stats(self):
        """Get aggregated stats for all todos."""
        try:
            stats = {
                'total': 0,
                'by_agent': {},
                'by_status': {'pending': 0, 'in_progress': 0, 'completed': 0, 'blocked': 0},
                'by_priority': {'high': 0, 'normal': 0, 'low': 0},
                'overdue': 0,
                'due_today': 0,
                'due_this_week': 0
            }

            now = datetime.now()
            today = now.strftime('%Y-%m-%d')
            week_end = (now + timedelta(days=7)).strftime('%Y-%m-%d')

            for agent in ['koda', 'cairn', 'prax']:
                todos = self._load_todos(agent)
                stats['by_agent'][agent] = {
                    'total': len(todos),
                    'pending': 0, 'in_progress': 0, 'completed': 0
                }

                for todo in todos:
                    stats['total'] += 1
                    status = todo.get('status', 'pending')
                    priority = todo.get('priority', 'normal')
                    due = todo.get('due_date', '')[:10] if todo.get('due_date') else ''

                    stats['by_status'][status] = stats['by_status'].get(status, 0) + 1
                    stats['by_priority'][priority] = stats['by_priority'].get(priority, 0) + 1
                    stats['by_agent'][agent][status] = stats['by_agent'][agent].get(status, 0) + 1

                    if due and status not in ['completed']:
                        if due < today:
                            stats['overdue'] += 1
                        elif due == today:
                            stats['due_today'] += 1
                        elif due <= week_end:
                            stats['due_this_week'] += 1

            self.serve_json({'success': True, 'stats': stats})

        except Exception as e:
            self.serve_json({'success': False, 'error': str(e)}, status=500)

    def create_todo(self, data):
        """Create a new todo."""
        try:
            agent_id = data.get('agent', 'koda').lower()
            title = data.get('title', 'Untitled Task')
            description = data.get('description', '')
            status = data.get('status', 'pending')
            priority = data.get('priority', 'normal')
            due_date = data.get('due_date')
            parent_id = data.get('parent_id')  # For subtasks
            prd_id = data.get('prd_id')  # Link to PRD
            tags = data.get('tags', [])
            created_by = data.get('created_by', 'user')
            sync_calendar = data.get('sync_calendar', False)
            sync_inbox = data.get('sync_inbox', False)

            todo_id = hashlib.md5(f"{agent_id}{title}{datetime.now().timestamp()}".encode()).hexdigest()[:12]

            todo = {
                'id': todo_id,
                'title': title,
                'description': description,
                'status': status,
                'priority': priority,
                'due_date': due_date,
                'parent_id': parent_id,
                'prd_id': prd_id,
                'tags': tags,
                'created_by': created_by,
                'created': datetime.now().isoformat(),
                'updated': datetime.now().isoformat(),
                'calendar_event_id': None,
                'inbox_message_id': None,
                'subtasks': []
            }

            todos = self._load_todos(agent_id)
            todos.append(todo)
            self._save_todos(agent_id, todos)

            # Sync to calendar if requested
            if sync_calendar and due_date:
                self._sync_todo_to_calendar_internal(todo, agent_id)

            # Sync to inbox if requested
            if sync_inbox:
                self._sync_todo_to_inbox_internal(todo, agent_id, created_by)

            self.serve_json({
                'success': True,
                'todo': todo,
                'agent': agent_id
            })

        except Exception as e:
            self.serve_json({'success': False, 'error': str(e)}, status=500)

    def update_todo(self, data):
        """Update an existing todo."""
        try:
            agent_id = data.get('agent', '').lower()
            todo_id = data.get('id')

            if not agent_id or not todo_id:
                self.serve_json({'success': False, 'error': 'Agent and todo ID required'}, status=400)
                return

            todos = self._load_todos(agent_id)
            todo_index = next((i for i, t in enumerate(todos) if t.get('id') == todo_id), None)

            if todo_index is None:
                self.serve_json({'success': False, 'error': 'Todo not found'}, status=404)
                return

            todo = todos[todo_index]

            # Update fields
            updateable_fields = ['title', 'description', 'status', 'priority', 'due_date', 'tags', 'parent_id']
            for field in updateable_fields:
                if field in data:
                    todo[field] = data[field]

            todo['updated'] = datetime.now().isoformat()

            todos[todo_index] = todo
            self._save_todos(agent_id, todos)

            # Re-sync calendar if due date changed
            if 'due_date' in data and todo.get('calendar_event_id'):
                self._sync_todo_to_calendar_internal(todo, agent_id)

            self.serve_json({
                'success': True,
                'todo': todo
            })

        except Exception as e:
            self.serve_json({'success': False, 'error': str(e)}, status=500)

    def delete_todo(self, data):
        """Delete a todo."""
        try:
            agent_id = data.get('agent', '').lower()
            todo_id = data.get('id')

            if not agent_id or not todo_id:
                self.serve_json({'success': False, 'error': 'Agent and todo ID required'}, status=400)
                return

            todos = self._load_todos(agent_id)
            original_count = len(todos)
            todos = [t for t in todos if t.get('id') != todo_id]

            if len(todos) == original_count:
                self.serve_json({'success': False, 'error': 'Todo not found'}, status=404)
                return

            self._save_todos(agent_id, todos)

            self.serve_json({
                'success': True,
                'deleted': todo_id
            })

        except Exception as e:
            self.serve_json({'success': False, 'error': str(e)}, status=500)

    def split_prd_to_todos(self, data):
        """Split a PRD into multiple todos for different agents (Prax feature)."""
        try:
            prd_title = data.get('title', 'Untitled PRD')
            prd_content = data.get('content', '')
            tasks = data.get('tasks', [])  # Pre-split tasks from UI
            auto_sync_calendar = data.get('sync_calendar', True)
            auto_sync_inbox = data.get('sync_inbox', True)

            if not tasks:
                self.serve_json({'success': False, 'error': 'No tasks provided'}, status=400)
                return

            # Generate PRD ID
            prd_id = hashlib.md5(f"{prd_title}{datetime.now().timestamp()}".encode()).hexdigest()[:12]

            # Save PRD for reference
            prd = {
                'id': prd_id,
                'title': prd_title,
                'content': prd_content,
                'created': datetime.now().isoformat(),
                'task_count': len(tasks)
            }

            prd_path = self._get_prds_path() / f"{prd_id}.json"
            prd_path.write_text(json.dumps(prd, indent=2))

            created_todos = []

            for task in tasks:
                agent_id = task.get('agent', 'koda').lower()
                title = task.get('title', 'Untitled Task')
                description = task.get('description', '')
                priority = task.get('priority', 'normal')
                due_date = task.get('due_date')

                todo_id = hashlib.md5(f"{agent_id}{title}{datetime.now().timestamp()}{len(created_todos)}".encode()).hexdigest()[:12]

                todo = {
                    'id': todo_id,
                    'title': title,
                    'description': description,
                    'status': 'pending',
                    'priority': priority,
                    'due_date': due_date,
                    'parent_id': None,
                    'prd_id': prd_id,
                    'prd_title': prd_title,
                    'tags': ['prd', prd_id[:6]],
                    'created_by': 'prax',
                    'created': datetime.now().isoformat(),
                    'updated': datetime.now().isoformat(),
                    'calendar_event_id': None,
                    'inbox_message_id': None,
                    'subtasks': []
                }

                # Save to agent's todos
                todos = self._load_todos(agent_id)
                todos.append(todo)
                self._save_todos(agent_id, todos)

                # Sync to calendar
                if auto_sync_calendar and due_date:
                    self._sync_todo_to_calendar_internal(todo, agent_id)

                # Sync to inbox
                if auto_sync_inbox:
                    self._sync_todo_to_inbox_internal(todo, agent_id, 'prax')

                created_todos.append({
                    'id': todo_id,
                    'agent': agent_id,
                    'title': title
                })

            self.serve_json({
                'success': True,
                'prd_id': prd_id,
                'created_todos': created_todos,
                'count': len(created_todos)
            })

        except Exception as e:
            self.serve_json({'success': False, 'error': str(e)}, status=500)

    def _sync_todo_to_calendar_internal(self, todo, agent_id):
        """Internal helper to sync a todo to calendar."""
        try:
            if not todo.get('due_date'):
                return None

            event = {
                'id': f"todo_{todo['id']}",
                'title': f"[TODO] {todo['title']}",
                'start': todo['due_date'],
                'end': todo['due_date'],
                'type': 'deadline',
                'description': todo.get('description', ''),
                'todo_id': todo['id'],
                'priority': todo.get('priority', 'normal'),
                'created': datetime.now().isoformat(),
                'updated': datetime.now().isoformat()
            }

            events = self._get_calendar_events(agent_id)
            # Remove existing event if any
            events = [e for e in events if e.get('id') != event['id']]
            events.append(event)
            self._save_calendar_events(agent_id, events)

            # Update todo with calendar link
            todos = self._load_todos(agent_id)
            for t in todos:
                if t.get('id') == todo['id']:
                    t['calendar_event_id'] = event['id']
                    break
            self._save_todos(agent_id, todos)

            return event['id']

        except Exception as e:
            print(f"Error syncing todo to calendar: {e}")
            return None

    def _sync_todo_to_inbox_internal(self, todo, target_agent, from_agent='prax'):
        """Internal helper to sync a todo to inbox."""
        import time

        try:
            sender_map = {'prax': 'D', 'koda': 'K', 'cairn': 'C', 'user': 'O'}
            target_map = {'koda': 'B', 'cairn': 'A', 'prax': 'D'}

            sender_id = sender_map.get(from_agent, 'D')
            target_id = target_map.get(target_agent, 'B')

            timestamp = int(time.time())
            msg_hash = hashlib.md5(f"{timestamp}{todo['id']}".encode()).hexdigest()[:12]

            priority_char = 'h' if todo.get('priority') == 'high' else 'n'
            msg_content = f"TODO: {todo['title']}"
            if todo.get('due_date'):
                msg_content += f" | Due: {todo['due_date']}"
            if todo.get('prd_title'):
                msg_content += f" | PRD: {todo['prd_title']}"

            fsl_msg = f"§MSG§{sender_id}→{target_id}§{priority_char}§§{msg_content}§{timestamp}§{msg_hash}§\n"

            inbox_path = self._get_inbox_path(target_agent)
            with open(inbox_path, 'a') as f:
                f.write(fsl_msg)

            # Update todo with inbox link
            todos = self._load_todos(target_agent)
            for t in todos:
                if t.get('id') == todo['id']:
                    t['inbox_message_id'] = msg_hash
                    break
            self._save_todos(target_agent, todos)

            return msg_hash

        except Exception as e:
            print(f"Error syncing todo to inbox: {e}")
            return None

    def sync_todo_to_calendar(self, data):
        """Sync a todo to calendar (API endpoint)."""
        try:
            agent_id = data.get('agent', '').lower()
            todo_id = data.get('id')

            if not agent_id or not todo_id:
                self.serve_json({'success': False, 'error': 'Agent and todo ID required'}, status=400)
                return

            todos = self._load_todos(agent_id)
            todo = next((t for t in todos if t.get('id') == todo_id), None)

            if not todo:
                self.serve_json({'success': False, 'error': 'Todo not found'}, status=404)
                return

            event_id = self._sync_todo_to_calendar_internal(todo, agent_id)

            self.serve_json({
                'success': True,
                'calendar_event_id': event_id
            })

        except Exception as e:
            self.serve_json({'success': False, 'error': str(e)}, status=500)

    def sync_todo_to_inbox(self, data):
        """Sync a todo to inbox (API endpoint)."""
        try:
            agent_id = data.get('agent', '').lower()
            todo_id = data.get('id')
            from_agent = data.get('from', 'prax')

            if not agent_id or not todo_id:
                self.serve_json({'success': False, 'error': 'Agent and todo ID required'}, status=400)
                return

            todos = self._load_todos(agent_id)
            todo = next((t for t in todos if t.get('id') == todo_id), None)

            if not todo:
                self.serve_json({'success': False, 'error': 'Todo not found'}, status=404)
                return

            msg_id = self._sync_todo_to_inbox_internal(todo, agent_id, from_agent)

            self.serve_json({
                'success': True,
                'inbox_message_id': msg_id
            })

        except Exception as e:
            self.serve_json({'success': False, 'error': str(e)}, status=500)

    def bulk_update_todos(self, data):
        """Bulk update multiple todos (for drag-drop reordering, status changes, etc.)."""
        try:
            updates = data.get('updates', [])
            results = []

            for update in updates:
                agent_id = update.get('agent', '').lower()
                todo_id = update.get('id')

                if not agent_id or not todo_id:
                    continue

                todos = self._load_todos(agent_id)
                todo_index = next((i for i, t in enumerate(todos) if t.get('id') == todo_id), None)

                if todo_index is not None:
                    for field in ['status', 'priority', 'order']:
                        if field in update:
                            todos[todo_index][field] = update[field]
                    todos[todo_index]['updated'] = datetime.now().isoformat()
                    self._save_todos(agent_id, todos)
                    results.append({'id': todo_id, 'success': True})
                else:
                    results.append({'id': todo_id, 'success': False, 'error': 'Not found'})

            self.serve_json({
                'success': True,
                'results': results,
                'updated_count': len([r for r in results if r.get('success')])
            })

        except Exception as e:
            self.serve_json({'success': False, 'error': str(e)}, status=500)

    # ==================== END TODO SYSTEM ====================

    def serve_storage_stats(self):
        """Get stats for all Claude storage locations."""
        import os
        from pathlib import Path

        # Define storage locations
        home = Path.home()
        locations = {
            'historyJsonl': home / '.claude' / 'history.jsonl',
            'projects': home / '.claude' / 'projects',
            'sessions': home / 'Library' / 'Application Support' / 'Claude' / 'claude-code-sessions',
            'debug': home / '.claude' / 'debug',
            'todos': home / '.claude' / 'todos',
            'fileHistory': home / '.claude' / 'file-history',
            'shellSnapshots': home / '.claude' / 'shell-snapshots',
            'mcpCache': home / 'Library' / 'Caches' / 'claude-cli-nodejs',
            'appSupportCache': home / 'Library' / 'Application Support' / 'Claude' / 'Cache',
            'codeCache': home / 'Library' / 'Application Support' / 'Claude' / 'Code Cache',
            'telemetry': home / '.claude' / 'telemetry',
            'plans': home / '.claude' / 'plans',
            'logs': home / 'Library' / 'Logs' / 'Claude',
            'settings': home / '.claude' / 'settings.json',
            'settingsLocal': home / '.claude' / 'settings.local.json'
        }

        def format_bytes(bytes):
            """Format bytes to human readable."""
            if bytes == 0:
                return '0 B'
            k = 1024
            sizes = ['B', 'KB', 'MB', 'GB', 'TB']
            i = 0
            while bytes >= k and i < len(sizes) - 1:
                bytes /= k
                i += 1
            return f'{bytes:.2f} {sizes[i]}'

        def get_dir_stats(path):
            """Get directory size and file count."""
            if not path.exists():
                return {'exists': False, 'size': 0, 'files': 0}

            total_size = 0
            file_count = 0

            try:
                for item in path.rglob('*'):
                    if item.is_file():
                        try:
                            total_size += item.stat().st_size
                            file_count += 1
                        except:
                            pass
            except Exception as e:
                print(f'Error scanning {path}: {e}')

            return {
                'exists': True,
                'path': str(path),
                'size': total_size,
                'files': file_count,
                'sizeFormatted': format_bytes(total_size)
            }

        def get_file_stats(path):
            """Get file size."""
            if not path.exists():
                return {'exists': False, 'size': 0}

            try:
                stat = path.stat()
                return {
                    'exists': True,
                    'path': str(path),
                    'size': stat.st_size,
                    'modified': stat.st_mtime,
                    'sizeFormatted': format_bytes(stat.st_size)
                }
            except Exception as e:
                return {'exists': False, 'size': 0, 'error': str(e)}

        try:
            stats = {}
            total = 0

            for key, path in locations.items():
                if path.is_file() or (path.exists() and not path.is_dir()):
                    stats[key] = get_file_stats(path)
                else:
                    stats[key] = get_dir_stats(path)

                total += stats[key].get('size', 0)

            self.serve_json({
                'ok': True,
                'locations': stats,
                'total': total,
                'totalFormatted': format_bytes(total)
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.serve_json({'ok': False, 'error': str(e)}, status=500)

    def serve_storage_list(self, location_key):
        """List files in a storage location."""
        import os
        from pathlib import Path

        home = Path.home()
        locations = {
            'historyJsonl': home / '.claude' / 'history.jsonl',
            'projects': home / '.claude' / 'projects',
            'sessions': home / 'Library' / 'Application Support' / 'Claude' / 'claude-code-sessions',
            'debug': home / '.claude' / 'debug',
            'todos': home / '.claude' / 'todos',
            'fileHistory': home / '.claude' / 'file-history',
            'shellSnapshots': home / '.claude' / 'shell-snapshots',
            'mcpCache': home / 'Library' / 'Caches' / 'claude-cli-nodejs',
            'appSupportCache': home / 'Library' / 'Application Support' / 'Claude' / 'Cache',
            'codeCache': home / 'Library' / 'Application Support' / 'Claude' / 'Code Cache',
            'telemetry': home / '.claude' / 'telemetry',
            'plans': home / '.claude' / 'plans',
            'logs': home / 'Library' / 'Logs' / 'Claude',
            'settings': home / '.claude' / 'settings.json',
            'settingsLocal': home / '.claude' / 'settings.local.json'
        }

        if location_key not in locations:
            self.serve_json({'ok': False, 'error': 'Invalid location key'}, status=400)
            return

        path = locations[location_key]

        if not path.exists():
            self.serve_json({'ok': True, 'files': []})
            return

        def format_bytes(bytes):
            if bytes == 0:
                return '0 B'
            k = 1024
            sizes = ['B', 'KB', 'MB', 'GB', 'TB']
            i = 0
            while bytes >= k and i < len(sizes) - 1:
                bytes /= k
                i += 1
            return f'{bytes:.2f} {sizes[i]}'

        try:
            files = []

            if path.is_file():
                stat = path.stat()
                files.append({
                    'name': path.name,
                    'path': str(path),
                    'size': stat.st_size,
                    'sizeFormatted': format_bytes(stat.st_size),
                    'modified': stat.st_mtime,
                    'isDirectory': False
                })
            else:
                # List directory contents
                for item in sorted(path.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
                    try:
                        stat = item.stat()
                        files.append({
                            'name': item.name,
                            'path': str(item),
                            'size': stat.st_size if item.is_file() else 0,
                            'sizeFormatted': format_bytes(stat.st_size) if item.is_file() else '-',
                            'modified': stat.st_mtime,
                            'isDirectory': item.is_dir()
                        })
                    except:
                        pass

            self.serve_json({
                'ok': True,
                'files': files[:200],  # Limit to 200 files
                'total': len(files)
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.serve_json({'ok': False, 'error': str(e)}, status=500)

    def open_storage_location(self, location_key):
        """Open a storage location in Finder."""
        import subprocess
        from pathlib import Path

        home = Path.home()
        locations = {
            'historyJsonl': home / '.claude' / 'history.jsonl',
            'projects': home / '.claude' / 'projects',
            'sessions': home / 'Library' / 'Application Support' / 'Claude' / 'claude-code-sessions',
            'debug': home / '.claude' / 'debug',
            'todos': home / '.claude' / 'todos',
            'fileHistory': home / '.claude' / 'file-history',
            'shellSnapshots': home / '.claude' / 'shell-snapshots',
            'mcpCache': home / 'Library' / 'Caches' / 'claude-cli-nodejs',
            'appSupportCache': home / 'Library' / 'Application Support' / 'Claude' / 'Cache',
            'codeCache': home / 'Library' / 'Application Support' / 'Claude' / 'Code Cache',
            'telemetry': home / '.claude' / 'telemetry',
            'plans': home / '.claude' / 'plans',
            'logs': home / 'Library' / 'Logs' / 'Claude',
            'settings': home / '.claude' / 'settings.json',
            'settingsLocal': home / '.claude' / 'settings.local.json'
        }

        if location_key not in locations:
            self.serve_json({'ok': False, 'error': 'Invalid location key'}, status=400)
            return

        path = locations[location_key]

        if not path.exists():
            self.serve_json({'ok': False, 'error': 'Location does not exist'}, status=404)
            return

        try:
            # Use 'open' command on macOS to open in Finder
            # If it's a file, open the parent directory
            target = path.parent if path.is_file() else path
            subprocess.run(['open', str(target)], check=True)

            self.serve_json({
                'ok': True,
                'location': str(target)
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.serve_json({'ok': False, 'error': str(e)}, status=500)

    # ===== Workspace Storage API (Exported Sessions) =====

    def serve_workspace_storage_list(self, query_string):
        """List all exported workspace sessions."""
        from urllib.parse import parse_qs

        try:
            params = parse_qs(query_string) if query_string else {}
            limit = int(params.get('limit', ['50'])[0])

            sessions = session_manager.list_exported_sessions(limit=limit)

            self.serve_json({
                'ok': True,
                'sessions': sessions,
                'count': len(sessions)
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.serve_json({'ok': False, 'error': str(e)}, status=500)

    def serve_workspace_storage_stats(self):
        """Get workspace storage statistics."""
        try:
            stats = session_manager.get_workspace_storage_stats()

            # Format size for display
            def format_bytes(bytes):
                if bytes == 0:
                    return '0 B'
                k = 1024
                sizes = ['B', 'KB', 'MB', 'GB', 'TB']
                i = 0
                while bytes >= k and i < len(sizes) - 1:
                    bytes /= k
                    i += 1
                return f'{bytes:.2f} {sizes[i]}'

            stats['total_size_formatted'] = format_bytes(stats['total_size_bytes'])

            self.serve_json({
                'ok': True,
                **stats
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.serve_json({'ok': False, 'error': str(e)}, status=500)

    def serve_workspace_session_detail(self, session_id):
        """Get full detail for an exported workspace session."""
        try:
            session_data = session_manager.get_exported_session(session_id)

            if not session_data:
                self.serve_json({'ok': False, 'error': 'Session not found'}, status=404)
                return

            self.serve_json({
                'ok': True,
                'session': session_data
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.serve_json({'ok': False, 'error': str(e)}, status=500)

    def serve_workspace_timeline(self):
        """Get workspace sessions formatted for timeline display."""
        try:
            items = session_manager.get_workspace_timeline_items(limit=100)

            self.serve_json({
                'ok': True,
                'items': items,
                'count': len(items)
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.serve_json({'ok': False, 'error': str(e)}, status=500)

    def serve_workspace_search(self, query_string):
        """Search across exported workspace sessions."""
        from urllib.parse import parse_qs

        try:
            params = parse_qs(query_string) if query_string else {}
            query = params.get('q', [''])[0]
            limit = int(params.get('limit', ['20'])[0])

            if not query:
                self.serve_json({'ok': False, 'error': 'Query parameter required'}, status=400)
                return

            results = session_manager.search_exported_sessions(query=query, limit=limit)

            self.serve_json({
                'ok': True,
                'results': results,
                'count': len(results),
                'query': query
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.serve_json({'ok': False, 'error': str(e)}, status=500)

    def delete_workspace_export(self, filename):
        """Delete an exported workspace session file."""
        try:
            # Security validation (already done in session_manager method)
            success = session_manager.delete_exported_session(filename)

            if success:
                self.serve_json({
                    'ok': True,
                    'message': f'Deleted {filename}'
                })
            else:
                self.serve_json({
                    'ok': False,
                    'error': 'File not found or could not be deleted'
                }, status=404)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.serve_json({'ok': False, 'error': str(e)}, status=500)

    def serve_history_list(self, query_string):
        """List conversation history with pagination and filters."""
        from urllib.parse import parse_qs
        from pathlib import Path

        try:
            params = parse_qs(query_string) if query_string else {}
            limit = int(params.get('limit', ['100'])[0])
            offset = int(params.get('offset', ['0'])[0])
            project_filter = params.get('project', [None])[0]

            history_file = Path.home() / '.claude' / 'history.jsonl'
            if not history_file.exists():
                self.serve_json({'ok': True, 'conversations': [], 'total': 0})
                return

            conversations = []
            with open(history_file, 'r') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                        # Apply project filter if specified
                        if project_filter and project_filter not in entry.get('project', ''):
                            continue

                        conversations.append({
                            'sessionId': entry.get('sessionId', ''),
                            'timestamp': entry.get('timestamp', 0),
                            'timeFormatted': datetime.fromtimestamp(entry.get('timestamp', 0) / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                            'project': entry.get('project', '').replace(str(Path.home()), '~'),
                            'display': entry.get('display', ''),
                            'preview': entry.get('display', '')[:200],
                            'hasPaste': len(entry.get('pastedContents', {})) > 0
                        })
                    except json.JSONDecodeError:
                        continue

            # Sort by timestamp descending (newest first)
            conversations.sort(key=lambda x: x['timestamp'], reverse=True)

            total = len(conversations)
            paginated = conversations[offset:offset + limit]

            self.serve_json({
                'ok': True,
                'conversations': paginated,
                'total': total,
                'limit': limit,
                'offset': offset
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.serve_json({'ok': False, 'error': str(e)}, status=500)

    def serve_history_search(self, query_string):
        """Search conversation history."""
        from urllib.parse import parse_qs
        from pathlib import Path

        try:
            params = parse_qs(query_string) if query_string else {}
            search_query = params.get('q', [''])[0].lower()
            limit = int(params.get('limit', ['100'])[0])

            if not search_query:
                self.serve_json({'ok': False, 'error': 'Missing search query'}, status=400)
                return

            history_file = Path.home() / '.claude' / 'history.jsonl'
            if not history_file.exists():
                self.serve_json({'ok': True, 'conversations': [], 'total': 0})
                return

            results = []
            with open(history_file, 'r') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                        display = entry.get('display', '').lower()
                        project = entry.get('project', '').lower()

                        # Search in display text or project path
                        if search_query in display or search_query in project:
                            results.append({
                                'sessionId': entry.get('sessionId', ''),
                                'timestamp': entry.get('timestamp', 0),
                                'timeFormatted': datetime.fromtimestamp(entry.get('timestamp', 0) / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                                'project': entry.get('project', '').replace(str(Path.home()), '~'),
                                'display': entry.get('display', ''),
                                'preview': entry.get('display', '')[:200],
                                'hasPaste': len(entry.get('pastedContents', {})) > 0,
                                'matchScore': display.count(search_query) + project.count(search_query)
                            })
                    except json.JSONDecodeError:
                        continue

            # Sort by match score then timestamp
            results.sort(key=lambda x: (x['matchScore'], x['timestamp']), reverse=True)
            results = results[:limit]

            self.serve_json({
                'ok': True,
                'conversations': results,
                'total': len(results),
                'query': search_query
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.serve_json({'ok': False, 'error': str(e)}, status=500)

    # =========================================================================
    # UNIFIED HISTORY BROWSER - INDEXING FUNCTIONS
    # =========================================================================

    def index_projects(self):
        """Index all project sessions from ~/.claude/projects/"""
        from pathlib import Path
        import re

        projects_dir = Path.home() / '.claude' / 'projects'
        if not projects_dir.exists():
            return []

        items = []

        try:
            # Scan all project directories
            for project_dir in projects_dir.iterdir():
                if not project_dir.is_dir():
                    continue

                # Decode project path: -Users-kanelawaccount-foo -> /Users/kanelawaccount/foo
                project_path = project_dir.name.replace('-', '/')
                if not project_path.startswith('/'):
                    project_path = '/' + project_path

                # Scan session directories within project
                for session_dir in project_dir.iterdir():
                    if not session_dir.is_dir():
                        continue

                    session_uuid = session_dir.name

                    # Get session timestamp from directory mtime
                    try:
                        stat = session_dir.stat()
                        timestamp = int(stat.st_mtime * 1000)
                    except:
                        timestamp = 0

                    # Count tool files
                    tool_results_dir = session_dir / 'tool-results'
                    tool_count = 0
                    tools_used = set()

                    if tool_results_dir.exists():
                        for tool_file in tool_results_dir.iterdir():
                            if tool_file.name.startswith('toolu_'):
                                tool_count += 1
                                # Try to extract tool name from file content or name
                                try:
                                    content = tool_file.read_text(errors='ignore')[:500]
                                    # Common tool patterns
                                    for tool in ['Bash', 'Read', 'Write', 'Edit', 'Grep', 'Glob', 'Task']:
                                        if tool in content:
                                            tools_used.add(tool)
                                except:
                                    pass

                    # Read session jsonl for preview
                    session_jsonl = session_dir / f'{session_uuid}.jsonl'
                    preview = f'Session with {tool_count} tool executions'
                    if session_jsonl.exists():
                        try:
                            with open(session_jsonl, 'r') as f:
                                lines = f.readlines()
                                if len(lines) > 0:
                                    first_entry = json.loads(lines[0])
                                    if 'content' in first_entry:
                                        preview = first_entry['content'][:500]
                        except:
                            pass

                    items.append({
                        'type': 'project_session',
                        'id': f'project-{session_uuid}',
                        'project': project_path.replace(str(Path.home()), '~'),
                        'sessionId': session_uuid,
                        'timestamp': timestamp,
                        'toolCount': tool_count,
                        'tools': list(tools_used) if tools_used else ['Unknown'],
                        'preview': preview,
                        'path': str(session_dir).replace(str(Path.home()), '~')
                    })

        except Exception as e:
            print(f"[Unified Index] Error indexing projects: {e}")
            import traceback
            traceback.print_exc()

        return items

    def index_file_history(self):
        """Index file edit history from ~/.claude/file-history/"""
        from pathlib import Path

        file_history_dir = Path.home() / '.claude' / 'file-history'
        if not file_history_dir.exists():
            return []

        items = []

        try:
            # Group files by session and file hash
            file_map = {}  # session_uuid -> {file_hash: [versions]}

            for session_dir in file_history_dir.iterdir():
                if not session_dir.is_dir():
                    continue

                session_uuid = session_dir.name

                for file_path in session_dir.iterdir():
                    if not file_path.is_file():
                        continue

                    # Parse filename: hash@vN
                    parts = file_path.name.split('@v')
                    if len(parts) != 2:
                        continue

                    file_hash = parts[0]
                    try:
                        version = int(parts[1])
                    except:
                        continue

                    key = f'{session_uuid}:{file_hash}'
                    if key not in file_map:
                        file_map[key] = {
                            'session_uuid': session_uuid,
                            'file_hash': file_hash,
                            'versions': [],
                            'files': []
                        }

                    file_map[key]['versions'].append(version)
                    file_map[key]['files'].append(file_path)

            # Create items from grouped files
            for key, data in file_map.items():
                versions = sorted(data['versions'])
                latest_version = max(versions)

                # Get latest file for preview
                latest_file = None
                for fp in data['files']:
                    if fp.name.endswith(f'@v{latest_version}'):
                        latest_file = fp
                        break

                if not latest_file:
                    continue

                # Get timestamp from first version
                first_file = None
                for fp in data['files']:
                    if fp.name.endswith(f'@v{versions[0]}'):
                        first_file = fp
                        break

                timestamp = 0
                if first_file:
                    try:
                        stat = first_file.stat()
                        timestamp = int(stat.st_mtime * 1000)
                    except:
                        pass

                # Get preview and size
                preview = ''
                size_growth = ''
                try:
                    content = latest_file.read_text(errors='ignore')
                    preview = content[:500]

                    if first_file and len(versions) > 1:
                        first_size = first_file.stat().st_size
                        latest_size = latest_file.stat().st_size
                        growth = latest_size - first_size
                        if growth > 0:
                            size_growth = f'+{growth} bytes'
                        elif growth < 0:
                            size_growth = f'{growth} bytes'
                        else:
                            size_growth = 'No change'
                except:
                    pass

                items.append({
                    'type': 'file_edit',
                    'id': f'file-{data["session_uuid"]}-{data["file_hash"]}',
                    'sessionId': data['session_uuid'],
                    'fileHash': data['file_hash'],
                    'versions': versions,
                    'latestVersion': latest_version,
                    'timestamp': timestamp,
                    'preview': preview,
                    'sizeGrowth': size_growth,
                    'path': str(latest_file).replace(str(Path.home()), '~')
                })

        except Exception as e:
            print(f"[Unified Index] Error indexing file history: {e}")
            import traceback
            traceback.print_exc()

        return items

    def index_todos(self):
        """Index todo lists from ~/.claude/todos/"""
        from pathlib import Path

        todos_dir = Path.home() / '.claude' / 'todos'
        if not todos_dir.exists():
            return []

        items = []

        try:
            for todo_file in todos_dir.glob('*.json'):
                try:
                    with open(todo_file, 'r') as f:
                        tasks = json.load(f)

                    if not isinstance(tasks, list):
                        continue

                    # Extract session UUID from filename
                    session_uuid = todo_file.stem.split('-agent-')[0] if '-agent-' in todo_file.stem else todo_file.stem

                    # Count task statuses
                    total_tasks = len(tasks)
                    completed = sum(1 for t in tasks if t.get('status') == 'completed')
                    in_progress = sum(1 for t in tasks if t.get('status') == 'in_progress')
                    pending = sum(1 for t in tasks if t.get('status') == 'pending')

                    # Build preview
                    task_previews = []
                    for task in tasks[:5]:  # First 5 tasks
                        status = task.get('status', 'pending')
                        icon = '✓' if status == 'completed' else '⏳' if status == 'in_progress' else '○'
                        task_previews.append(f"{icon} {task.get('content', '')[:50]}")
                    preview = ', '.join(task_previews)

                    # Get timestamp
                    stat = todo_file.stat()
                    timestamp = int(stat.st_mtime * 1000)

                    items.append({
                        'type': 'todo_list',
                        'id': f'todo-{session_uuid}',
                        'sessionId': session_uuid,
                        'timestamp': timestamp,
                        'totalTasks': total_tasks,
                        'completed': completed,
                        'inProgress': in_progress,
                        'pending': pending,
                        'preview': preview,
                        'tasks': tasks,
                        'path': str(todo_file).replace(str(Path.home()), '~')
                    })

                except Exception as e:
                    print(f"[Unified Index] Error reading todo file {todo_file}: {e}")
                    continue

        except Exception as e:
            print(f"[Unified Index] Error indexing todos: {e}")
            import traceback
            traceback.print_exc()

        return items

    def index_plans(self):
        """Index plan files from ~/.claude/plans/"""
        from pathlib import Path

        plans_dir = Path.home() / '.claude' / 'plans'
        if not plans_dir.exists():
            return []

        items = []

        try:
            for plan_file in plans_dir.glob('*.md'):
                try:
                    content = plan_file.read_text(errors='ignore')

                    # Extract title from first H1 heading
                    title = plan_file.stem
                    lines = content.split('\n')
                    for line in lines[:10]:
                        if line.startswith('# '):
                            title = line[2:].strip()
                            break

                    # Get preview (first 300 chars)
                    preview = content[:300].replace('\n', ' ')

                    # Word count
                    word_count = len(content.split())

                    # Get timestamp
                    stat = plan_file.stat()
                    timestamp = int(stat.st_mtime * 1000)

                    items.append({
                        'type': 'plan',
                        'id': f'plan-{plan_file.stem}',
                        'filename': plan_file.name,
                        'title': title,
                        'timestamp': timestamp,
                        'preview': preview,
                        'wordCount': word_count,
                        'path': str(plan_file).replace(str(Path.home()), '~')
                    })

                except Exception as e:
                    print(f"[Unified Index] Error reading plan file {plan_file}: {e}")
                    continue

        except Exception as e:
            print(f"[Unified Index] Error indexing plans: {e}")
            import traceback
            traceback.print_exc()

        return items

    def extract_tags_and_category(self, item):
        """Extract category and tags from item text."""
        # Category definitions
        HISTORY_CATEGORIES = {
            "debugging": ["error", "bug", "fix", "debug", "traceback", "exception", "failed", "crash"],
            "feature": ["add", "implement", "create", "new feature", "build", "develop", "added"],
            "refactor": ["refactor", "cleanup", "reorganize", "restructure", "rename", "clean"],
            "documentation": ["docs", "readme", "documentation", "comment", "explain", "document"],
            "testing": ["test", "pytest", "unittest", "assert", "mock", "coverage", "spec"],
            "configuration": ["config", "settings", "setup", "install", "environment", "configure"],
            "api": ["api", "endpoint", "route", "rest", "fetch", "/api/", "http"],
            "database": ["database", "query", "sql", "schema", "index", "migration", "db"],
            "ui": ["ui", "dashboard", "component", "style", "css", "html", "react", "frontend"],
            "git": ["commit", "push", "merge", "branch", "pull request", "github", "git"],
            "optimization": ["optimize", "performance", "speed", "cache", "benchmark", "fast"],
            "learning": ["how to", "what is", "explain", "understand", "learn", "tutorial", "help"]
        }

        # Combine searchable fields
        text_parts = []
        if 'display' in item:
            text_parts.append(item['display'])
        if 'preview' in item:
            text_parts.append(item['preview'])
        if 'project' in item:
            text_parts.append(item['project'])
        if 'title' in item:
            text_parts.append(item['title'])

        text = ' '.join(text_parts).lower()

        # Find category
        category = 'general'
        for cat, keywords in HISTORY_CATEGORIES.items():
            for keyword in keywords:
                if keyword in text:
                    category = cat
                    break
            if category != 'general':
                break

        # Extract tags (frequent words, excluding common ones)
        common_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'in', 'on', 'at', 'to', 'for',
                       'of', 'with', 'by', 'from', 'this', 'that', 'these', 'those', 'and', 'or',
                       'but', 'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
                       'could', 'should', 'may', 'might', 'can', 'it', 'its', 'as', 'if', 'then'}

        import re
        words = re.findall(r'\b\w{3,}\b', text.lower())
        word_freq = {}
        for word in words:
            if word not in common_words and not word.isdigit():
                word_freq[word] = word_freq.get(word, 0) + 1

        # Get top 5 words as tags
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        tags = [word for word, count in sorted_words[:5]]

        item['category'] = category
        item['tags'] = tags

        return item

    def build_unified_index(self):
        """Build unified index from all sources."""
        from pathlib import Path

        cache_file = Path.home() / '.claude' / 'unified_history_index.json'

        print("[Unified Index] Building index from all sources...")

        # Index all sources
        conversations = self.index_conversations()
        projects = self.index_projects()
        file_history = self.index_file_history()
        todos = self.index_todos()
        plans = self.index_plans()
        workspace_sessions = self.index_workspace_sessions()

        # Combine all items
        all_items = conversations + projects + file_history + todos + plans + workspace_sessions

        print(f"[Unified Index] Found {len(conversations)} conversations, {len(projects)} projects, "
              f"{len(file_history)} file edits, {len(todos)} todo lists, {len(plans)} plans, "
              f"{len(workspace_sessions)} workspace sessions")

        # Extract tags and categories for all items
        for item in all_items:
            self.extract_tags_and_category(item)

        # Sort by timestamp descending
        all_items.sort(key=lambda x: x.get('timestamp', 0), reverse=True)

        # Build cache
        cache_data = {
            'items': all_items,
            'total': len(all_items),
            'lastUpdated': int(time.time() * 1000),
            'counts': {
                'conversation': len(conversations),
                'project_session': len(projects),
                'file_edit': len(file_history),
                'todo_list': len(todos),
                'plan': len(plans),
                'workspace_session': len(workspace_sessions)
            }
        }

        # Write cache
        try:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
            print(f"[Unified Index] Cache written to {cache_file}")
        except Exception as e:
            print(f"[Unified Index] Error writing cache: {e}")

        return cache_data

    def index_conversations(self):
        """Index conversations from history.jsonl."""
        from pathlib import Path

        history_file = Path.home() / '.claude' / 'history.jsonl'
        if not history_file.exists():
            return []

        items = []

        try:
            with open(history_file, 'r') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                        items.append({
                            'type': 'conversation',
                            'id': f'conversation-{entry.get("sessionId", "")}',
                            'sessionId': entry.get('sessionId', ''),
                            'timestamp': entry.get('timestamp', 0),
                            'timeFormatted': datetime.fromtimestamp(entry.get('timestamp', 0) / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                            'project': entry.get('project', '').replace(str(Path.home()), '~'),
                            'display': entry.get('display', ''),
                            'preview': entry.get('display', '')[:200],
                            'hasPaste': len(entry.get('pastedContents', {})) > 0
                        })
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"[Unified Index] Error indexing conversations: {e}")

        return items

    def index_workspace_sessions(self):
        """Index workspace sessions from exported files."""
        from pathlib import Path

        export_dir = Path.home() / '.claude' / 'workspace_sessions'
        if not export_dir.exists():
            return []

        items = []

        try:
            for filepath in export_dir.glob('session_*.json'):
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)

                    # Parse timestamp from created_at
                    created_at = data.get('created_at', '')
                    try:
                        dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        timestamp = int(dt.timestamp() * 1000)
                    except:
                        timestamp = int(filepath.stat().st_mtime * 1000)

                    participants = [p.get('name', 'Unknown') for p in data.get('participants', [])]
                    message_count = data.get('message_count', 0)

                    items.append({
                        'type': 'workspace_session',
                        'id': f'workspace-{data.get("session_id", "")}',
                        'sessionId': data.get('session_id', ''),
                        'timestamp': timestamp,
                        'timeFormatted': datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                        'display': f'Workspace Session - {", ".join(participants[:3])}',
                        'preview': f'{message_count} messages with {len(participants)} participants',
                        'participants': participants,
                        'messageCount': message_count,
                        'filename': filepath.name,
                        'source': 'workspaceSessions'
                    })
                except Exception as e:
                    print(f"[Unified Index] Error indexing workspace {filepath}: {e}")
                    continue

        except Exception as e:
            print(f"[Unified Index] Error indexing workspace sessions: {e}")

        return items

    def get_unified_index(self, force_rebuild=False):
        """Get unified index from cache or rebuild if needed."""
        from pathlib import Path

        cache_file = Path.home() / '.claude' / 'unified_history_index.json'

        # Check if cache exists and is recent (< 5 minutes old)
        if not force_rebuild and cache_file.exists():
            try:
                stat = cache_file.stat()
                age_seconds = time.time() - stat.st_mtime
                if age_seconds < 300:  # 5 minutes
                    with open(cache_file, 'r') as f:
                        return json.load(f)
            except:
                pass

        # Rebuild index
        return self.build_unified_index()

    def aggregate_tags(self, items):
        """Aggregate tags and categories across all items."""
        tag_counts = {}
        category_counts = {}

        for item in items:
            # Count category
            category = item.get('category', 'general')
            category_counts[category] = category_counts.get(category, 0) + 1

            # Count tags
            for tag in item.get('tags', []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        # Sort and format
        tags = [{'tag': tag, 'count': count} for tag, count in tag_counts.items()]
        tags.sort(key=lambda x: x['count'], reverse=True)

        categories = [{'category': cat, 'count': count} for cat, count in category_counts.items()]
        categories.sort(key=lambda x: x['count'], reverse=True)

        return {
            'tags': tags,
            'categories': categories
        }

    # =========================================================================
    # UNIFIED HISTORY BROWSER - API ENDPOINTS
    # =========================================================================

    def serve_unified_list(self, query_string):
        """List unified history with pagination and filters."""
        from urllib.parse import parse_qs

        try:
            params = parse_qs(query_string) if query_string else {}
            limit = int(params.get('limit', ['100'])[0])
            offset = int(params.get('offset', ['0'])[0])
            type_filter = params.get('type', ['all'])[0]
            category_filter = params.get('category', [None])[0]
            project_filter = params.get('project', [None])[0]

            # Get index
            index_data = self.get_unified_index()
            items = index_data['items']

            # Apply filters
            filtered = items
            if type_filter != 'all':
                filtered = [i for i in filtered if i.get('type') == type_filter]
            if category_filter:
                filtered = [i for i in filtered if i.get('category') == category_filter]
            if project_filter:
                filtered = [i for i in filtered if project_filter in i.get('project', '')]

            # Add formatted time
            for item in filtered:
                if 'timeFormatted' not in item and 'timestamp' in item:
                    item['timeFormatted'] = datetime.fromtimestamp(item['timestamp'] / 1000).strftime('%Y-%m-%d %H:%M:%S')

            total = len(filtered)
            paginated = filtered[offset:offset + limit]

            self.serve_json({
                'ok': True,
                'items': paginated,
                'total': total,
                'limit': limit,
                'offset': offset,
                'counts': index_data['counts']
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.serve_json({'ok': False, 'error': str(e)}, status=500)

    def serve_unified_search(self, query_string):
        """Search unified history."""
        from urllib.parse import parse_qs

        try:
            params = parse_qs(query_string) if query_string else {}
            search_query = params.get('q', [''])[0].lower()
            limit = int(params.get('limit', ['100'])[0])
            type_filter = params.get('type', ['all'])[0]
            category_filter = params.get('category', [None])[0]

            if not search_query:
                self.serve_json({'ok': False, 'error': 'Missing search query'}, status=400)
                return

            # Get index
            index_data = self.get_unified_index()
            items = index_data['items']

            # Apply type filter first
            if type_filter != 'all':
                items = [i for i in items if i.get('type') == type_filter]

            # Apply category filter
            if category_filter:
                items = [i for i in items if i.get('category') == category_filter]

            # Search
            results = []
            for item in items:
                # Build searchable text
                search_fields = []
                for field in ['display', 'preview', 'project', 'title', 'category']:
                    if field in item:
                        search_fields.append(str(item[field]).lower())

                search_text = ' '.join(search_fields)

                if search_query in search_text:
                    # Calculate match score
                    match_score = search_text.count(search_query)
                    item['matchScore'] = match_score
                    results.append(item)

            # Sort by match score then timestamp
            results.sort(key=lambda x: (x.get('matchScore', 0), x.get('timestamp', 0)), reverse=True)
            results = results[:limit]

            # Add formatted time
            for item in results:
                if 'timeFormatted' not in item and 'timestamp' in item:
                    item['timeFormatted'] = datetime.fromtimestamp(item['timestamp'] / 1000).strftime('%Y-%m-%d %H:%M:%S')

            self.serve_json({
                'ok': True,
                'items': results,
                'total': len(results),
                'query': search_query
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.serve_json({'ok': False, 'error': str(e)}, status=500)

    def serve_unified_tags(self):
        """Get tags and categories with counts."""
        try:
            # Get index
            index_data = self.get_unified_index()
            items = index_data['items']

            # Aggregate tags
            aggregated = self.aggregate_tags(items)

            self.serve_json({
                'ok': True,
                'tags': aggregated['tags'][:50],  # Top 50 tags
                'categories': aggregated['categories']
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.serve_json({'ok': False, 'error': str(e)}, status=500)

    def serve_unified_timeline(self, query_string):
        """Get timeline data grouped by time period."""
        from urllib.parse import parse_qs
        from datetime import datetime, timedelta

        try:
            params = parse_qs(query_string) if query_string else {}
            group_by = params.get('group', ['month'])[0]

            # Get index
            index_data = self.get_unified_index()
            items = index_data['items']

            # Group by time period
            timeline = {}
            for item in items:
                timestamp = item.get('timestamp', 0)
                if timestamp == 0:
                    continue

                dt = datetime.fromtimestamp(timestamp / 1000)

                if group_by == 'day':
                    key = dt.strftime('%Y-%m-%d')
                elif group_by == 'week':
                    # Get week start (Monday)
                    week_start = dt - timedelta(days=dt.weekday())
                    key = week_start.strftime('%Y-%m-%d')
                else:  # month
                    key = dt.strftime('%Y-%m')

                if key not in timeline:
                    timeline[key] = {
                        'period': key,
                        'total': 0,
                        'byType': {}
                    }

                timeline[key]['total'] += 1

                item_type = item.get('type', 'unknown')
                timeline[key]['byType'][item_type] = timeline[key]['byType'].get(item_type, 0) + 1

            # Convert to list and sort
            timeline_list = list(timeline.values())
            timeline_list.sort(key=lambda x: x['period'], reverse=True)

            self.serve_json({
                'ok': True,
                'timeline': timeline_list,
                'groupBy': group_by
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.serve_json({'ok': False, 'error': str(e)}, status=500)

    def serve_unified_related(self, query_string):
        """Find related items based on similarity."""
        from urllib.parse import parse_qs

        try:
            params = parse_qs(query_string) if query_string else {}
            item_id = params.get('id', [''])[0]
            limit = int(params.get('limit', ['10'])[0])

            if not item_id:
                self.serve_json({'ok': False, 'error': 'Missing item id'}, status=400)
                return

            # Get index
            index_data = self.get_unified_index()
            items = index_data['items']

            # Find the source item
            source_item = None
            for item in items:
                if item.get('id') == item_id:
                    source_item = item
                    break

            if not source_item:
                self.serve_json({'ok': False, 'error': 'Item not found'}, status=404)
                return

            # Calculate similarity scores
            related = []
            source_tags = set(source_item.get('tags', []))
            source_session = source_item.get('sessionId', '')
            source_project = source_item.get('project', '')
            source_timestamp = source_item.get('timestamp', 0)

            for item in items:
                if item.get('id') == item_id:
                    continue  # Skip self

                score = 0

                # Same session = high relevance
                if item.get('sessionId') == source_session and source_session:
                    score += 5

                # Same project
                if item.get('project') == source_project and source_project:
                    score += 2

                # Shared tags
                item_tags = set(item.get('tags', []))
                shared_tags = source_tags & item_tags
                score += len(shared_tags) * 3

                # Similar timestamp (within 7 days)
                if source_timestamp > 0 and item.get('timestamp', 0) > 0:
                    time_diff_days = abs(source_timestamp - item.get('timestamp', 0)) / 1000 / 86400
                    if time_diff_days <= 7:
                        score += 1

                if score > 0:
                    item['relevanceScore'] = score
                    related.append(item)

            # Sort by relevance
            related.sort(key=lambda x: x.get('relevanceScore', 0), reverse=True)
            related = related[:limit]

            # Add formatted time
            for item in related:
                if 'timeFormatted' not in item and 'timestamp' in item:
                    item['timeFormatted'] = datetime.fromtimestamp(item['timestamp'] / 1000).strftime('%Y-%m-%d %H:%M:%S')

            self.serve_json({
                'ok': True,
                'related': related,
                'sourceId': item_id
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.serve_json({'ok': False, 'error': str(e)}, status=500)

    def rebuild_unified_index(self):
        """Rebuild unified index (POST endpoint)."""
        try:
            print("[Unified Index] Rebuild requested")
            index_data = self.build_unified_index()

            self.serve_json({
                'ok': True,
                'total': index_data['total'],
                'counts': index_data['counts'],
                'message': 'Index rebuilt successfully'
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.serve_json({'ok': False, 'error': str(e)}, status=500)

    # =========================================================================
    # AI ASSISTANT - LLM PROXY WITH TOOL CALLING
    # =========================================================================

    def serve_assistant_chat(self, data):
        """Handle assistant chat with streaming and tool calling."""
        try:
            message = data.get('message')
            model = data.get('model', 'claude')
            conversation_history = data.get('history', [])

            if not message:
                self.serve_json({'ok': False, 'error': 'Missing message'}, status=400)
                return

            # Load API keys
            api_keys = self.load_api_keys()

            # Set headers for Server-Sent Events (SSE) streaming
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            # Define tools available to the assistant
            tools = [
                {
                    "name": "search_history",
                    "description": "Search across all Claude history (conversations, projects, file edits, todos, plans)",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query to find in history"
                            },
                            "type": {
                                "type": "string",
                                "enum": ["all", "conversation", "project_session", "file_edit", "todo_list", "plan"],
                                "description": "Type of items to search"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results to return"
                            }
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "get_related_items",
                    "description": "Find items related to a specific history item",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "item_id": {
                                "type": "string",
                                "description": "ID of the item to find related items for"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of related items to return"
                            }
                        },
                        "required": ["item_id"]
                    }
                },
                {
                    "name": "get_timeline",
                    "description": "Get activity timeline grouped by time period",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "group_by": {
                                "type": "string",
                                "enum": ["day", "week", "month"],
                                "description": "How to group timeline data"
                            }
                        },
                        "required": []
                    }
                },
                {
                    "name": "create_artifact",
                    "description": "Create a visual artifact (chart, checklist, table) from data",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["checklist", "table", "chart", "timeline"],
                                "description": "Type of artifact to create"
                            },
                            "title": {
                                "type": "string",
                                "description": "Title for the artifact"
                            },
                            "data": {
                                "type": "object",
                                "description": "Data for the artifact (structure depends on type)"
                            }
                        },
                        "required": ["type", "title", "data"]
                    }
                }
            ]

            # Call LLM based on model choice
            if model == 'claude':
                self.call_claude_with_tools(message, conversation_history, tools, api_keys)
            elif model == 'deepseek':
                self.call_deepseek_with_tools(message, conversation_history, tools, api_keys)
            else:
                self.wfile.write(f'data: {json.dumps({"error": "Unknown model"})}\n\n'.encode())

            # Send completion marker
            self.wfile.write(f'data: {json.dumps({"done": True})}\n\n'.encode())
            self.wfile.flush()

        except Exception as e:
            import traceback
            traceback.print_exc()
            error_msg = f'data: {json.dumps({"error": str(e)})}\n\n'
            self.wfile.write(error_msg.encode())
            self.wfile.flush()

    def call_claude_with_tools(self, message, history, tools, api_keys):
        """Call Claude API with streaming and tool support."""
        import anthropic

        # Support both 'anthropic' and 'claude' key names
        api_key = api_keys.get('anthropic') or api_keys.get('claude')
        if not api_key:
            self.wfile.write(f'data: {json.dumps({"error": "Claude API key not configured"})}\n\n'.encode())
            return

        client = anthropic.Anthropic(api_key=api_key)

        # Build messages
        messages = history + [{"role": "user", "content": message}]

        # System prompt
        system = """You are a helpful AI assistant integrated into the Claude History Browser. You can help users search, analyze, and organize their Claude conversation history.

# CAPABILITIES & FAQ

## What You Can Search
- **Conversations** (6,987+): All Claude Code terminal sessions with timestamps, projects, and full text
- **Project Sessions** (138+): Claude Code work sessions organized by project directory
- **File Edits** (2,666+): Every file version edited by Claude with diff previews
- **Todo Lists** (727+): Task lists from Claude sessions with status tracking
- **Plans** (103+): Implementation plans and architecture documents

## Available Tools

### 1. search_history(query, type, limit)
**What it does:** Search across all history sources with filters
**Parameters:**
- `query` (required): Search terms (e.g., "websocket", "api debug", "login feature")
- `type` (optional): Filter by type - "all" | "conversation" | "project_session" | "file_edit" | "todo_list" | "plan"
- `limit` (optional): Max results (default 20)

**Example queries:**
- "Find all conversations about websockets from last week"
- "Search for file edits related to API development"
- "Show me plans about authentication"

### 2. get_related_items(item_id, limit)
**What it does:** Find items related to a specific session/file/conversation
**How it works:** Matches by session ID, shared tags, project, and time proximity
**Use cases:**
- "What files were edited in this session?"
- "Show conversations related to this project"
- "Find todos from the same work session"

### 3. get_timeline(group_by)
**What it does:** Show activity patterns over time
**Parameters:**
- `group_by`: "day" | "week" | "month"

**Example queries:**
- "Show my activity timeline for January"
- "What did I work on last week?"
- "Create a monthly breakdown of my sessions"

### 4. create_artifact(type, title, data)
**What it does:** Create visual artifacts from data
**Types:**
- **checklist**: Interactive todo lists - `{items: [{text: "...", checked: false}]}`
- **table**: Data tables - `{columns: ["Name", "Value"], rows: [["foo", "bar"]]}`
- **chart**: Visualization data (JSON preview)
- **timeline**: Temporal data visualizations

**Example queries:**
- "Create a checklist of all debugging patterns I used"
- "Make a table of API endpoints I worked on"
- "Show a timeline of my December activity"

## Search Tips

### Natural Language Queries
You understand natural language! Try:
- "Find all work I did on the login feature"
- "What was I debugging yesterday?"
- "Show me everything related to websockets"
- "List all my incomplete todos"
- "When did I last work on the API?"

### Time-Based Searches
- "Show my work from January 14th"
- "What did I do yesterday?"
- "Find sessions from last week"
- "Activity from December 2025"

### Project-Based Searches
- "Find all sessions in the phi_proxy project"
- "What did I build in golden_library?"
- "Show file edits in the dashboard project"

### Category Filters
Available categories: debugging, feature, refactor, documentation, testing, configuration, api, database, ui, git, optimization, learning

Example: "Show all debugging sessions from last month"

### Tag-Based Searches
Search by auto-extracted tags like: websocket, api, mcp, test, config, error, implement, etc.

## Common Workflows

### Research & Analysis
1. "Find all conversations about [topic]"
2. "Show related files and sessions"
3. "Create a summary table of findings"

### Progress Tracking
1. "Show my timeline for this week"
2. "List all completed todos"
3. "What features did I build this month?"

### Debugging History
1. "Find all error-related sessions"
2. "Show debugging patterns I used"
3. "When did I fix [specific bug]?"

### Project Overview
1. "Show all work in [project_name]"
2. "Create a timeline of project activity"
3. "List all files edited in this project"

## Tips for Best Results

1. **Be specific with time ranges**: "last week" > "recently"
2. **Use project names**: They're indexed and searchable
3. **Combine filters**: "debugging sessions in phi_proxy from yesterday"
4. **Ask for visualizations**: I can create checklists, tables, timelines
5. **Follow up questions**: I remember our conversation context

## Data Sources & Counts
- Total indexed items: 10,621+
- Time range: October 2025 - Present
- Updates: Real-time as you work
- Storage: All in ~/.claude/ directories

## If Something's Not Found
- Try broader search terms
- Check time range
- Try searching by project name
- Ask me to search related items

Remember: All your Claude work is saved and searchable. Nothing is lost when you close terminals!"""

        # Call Claude with streaming
        try:
            with client.messages.stream(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                tools=tools,
                system=system,
                messages=messages
            ) as stream:
                for text in stream.text_stream:
                    self.wfile.write(f'data: {json.dumps({"chunk": text})}\n\n'.encode())
                    self.wfile.flush()

                # Handle tool calls
                message_obj = stream.get_final_message()
                if message_obj.stop_reason == "tool_use":
                    for block in message_obj.content:
                        if block.type == "tool_use":
                            # Execute tool
                            tool_result = self.execute_tool(block.name, block.input)

                            # Send tool call info to client
                            self.wfile.write(f'data: {json.dumps({"tool_call": {"name": block.name, "input": block.input}})}\n\n'.encode())
                            self.wfile.flush()

                            # Continue conversation with tool result
                            new_messages = messages + [
                                {"role": "assistant", "content": message_obj.content},
                                {
                                    "role": "user",
                                    "content": [
                                        {
                                            "type": "tool_result",
                                            "tool_use_id": block.id,
                                            "content": json.dumps(tool_result)
                                        }
                                    ]
                                }
                            ]

                            # Stream the follow-up response
                            with client.messages.stream(
                                model="claude-sonnet-4-20250514",
                                max_tokens=4096,
                                tools=tools,
                                system=system,
                                messages=new_messages
                            ) as follow_up_stream:
                                for text in follow_up_stream.text_stream:
                                    self.wfile.write(f'data: {json.dumps({"chunk": text})}\n\n'.encode())
                                    self.wfile.flush()

        except Exception as e:
            self.wfile.write(f'data: {json.dumps({"error": str(e)})}\n\n'.encode())
            self.wfile.flush()

    def call_deepseek_with_tools(self, message, history, tools, api_keys):
        """Call DeepSeek API (compatible with OpenAI format)."""
        import requests

        if 'deepseek' not in api_keys:
            self.wfile.write(f'data: {json.dumps({"error": "DeepSeek API key not configured"})}\n\n'.encode())
            return

        # DeepSeek uses OpenAI-compatible API
        url = "https://api.deepseek.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_keys['deepseek']}",
            "Content-Type": "application/json"
        }

        # Build messages
        messages = [
            {"role": "system", "content": "You are a helpful AI assistant integrated into the Claude History Browser."}
        ] + history + [{"role": "user", "content": message}]

        payload = {
            "model": "deepseek-chat",
            "messages": messages,
            "stream": True,
            "tools": tools
        }

        try:
            response = requests.post(url, headers=headers, json=payload, stream=True)

            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data = line[6:]
                        if data == '[DONE]':
                            break
                        try:
                            chunk = json.loads(data)
                            if 'choices' in chunk and len(chunk['choices']) > 0:
                                delta = chunk['choices'][0].get('delta', {})
                                if 'content' in delta:
                                    self.wfile.write(f'data: {json.dumps({"chunk": delta["content"]})}\n\n'.encode())
                                    self.wfile.flush()
                        except json.JSONDecodeError:
                            pass

        except Exception as e:
            self.wfile.write(f'data: {json.dumps({"error": str(e)})}\n\n'.encode())
            self.wfile.flush()

    def execute_tool(self, tool_name, tool_input):
        """Execute a tool call and return the result."""
        try:
            if tool_name == "search_history":
                # Use existing unified search
                query = tool_input.get('query', '')
                type_filter = tool_input.get('type', 'all')
                limit = tool_input.get('limit', 20)

                index_data = self.get_unified_index()
                items = index_data['items']

                # Apply type filter
                if type_filter != 'all':
                    items = [i for i in items if i.get('type') == type_filter]

                # Search
                search_query = query.lower()
                results = []
                for item in items:
                    search_fields = []
                    for field in ['display', 'preview', 'project', 'title', 'category']:
                        if field in item:
                            search_fields.append(str(item[field]).lower())
                    search_text = ' '.join(search_fields)

                    if search_query in search_text:
                        match_score = search_text.count(search_query)
                        item['matchScore'] = match_score
                        results.append(item)

                results.sort(key=lambda x: x.get('matchScore', 0), reverse=True)
                results = results[:limit]

                return {
                    "success": True,
                    "results": results,
                    "total": len(results),
                    "query": query
                }

            elif tool_name == "get_related_items":
                item_id = tool_input.get('item_id')
                limit = tool_input.get('limit', 10)

                index_data = self.get_unified_index()
                items = index_data['items']

                # Find source item
                source_item = None
                for item in items:
                    if item.get('id') == item_id:
                        source_item = item
                        break

                if not source_item:
                    return {"success": False, "error": "Item not found"}

                # Calculate similarity (simplified version of serve_unified_related)
                related = []
                source_tags = set(source_item.get('tags', []))
                source_session = source_item.get('sessionId', '')

                for item in items:
                    if item.get('id') == item_id:
                        continue
                    score = 0
                    if item.get('sessionId') == source_session and source_session:
                        score += 5
                    item_tags = set(item.get('tags', []))
                    shared_tags = source_tags & item_tags
                    score += len(shared_tags) * 3
                    if score > 0:
                        item['relevanceScore'] = score
                        related.append(item)

                related.sort(key=lambda x: x.get('relevanceScore', 0), reverse=True)
                return {"success": True, "related": related[:limit]}

            elif tool_name == "get_timeline":
                group_by = tool_input.get('group_by', 'month')

                index_data = self.get_unified_index()
                items = index_data['items']

                timeline = {}
                for item in items:
                    timestamp = item.get('timestamp', 0)
                    if timestamp == 0:
                        continue

                    dt = datetime.fromtimestamp(timestamp / 1000)
                    if group_by == 'day':
                        key = dt.strftime('%Y-%m-%d')
                    elif group_by == 'week':
                        from datetime import timedelta
                        week_start = dt - timedelta(days=dt.weekday())
                        key = week_start.strftime('%Y-%m-%d')
                    else:
                        key = dt.strftime('%Y-%m')

                    if key not in timeline:
                        timeline[key] = {"period": key, "total": 0, "byType": {}}

                    timeline[key]['total'] += 1
                    item_type = item.get('type', 'unknown')
                    timeline[key]['byType'][item_type] = timeline[key]['byType'].get(item_type, 0) + 1

                timeline_list = list(timeline.values())
                timeline_list.sort(key=lambda x: x['period'], reverse=True)

                return {"success": True, "timeline": timeline_list[:30]}

            elif tool_name == "create_artifact":
                # Just return the artifact data for frontend rendering
                return {
                    "success": True,
                    "artifact": {
                        "type": tool_input.get('type'),
                        "title": tool_input.get('title'),
                        "data": tool_input.get('data')
                    }
                }

            else:
                return {"success": False, "error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def load_api_keys(self):
        """Load API keys from file."""
        try:
            with open(API_KEYS_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}

    def log_message(self, format, *args):
        """Override to customize logging."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] {format % args}")


# WebSocket Support
connected_clients = set()
pending_notifications = []


class HandoffWatcher(FileSystemEventHandler):
    """Watch for new handoff files in the conversation library."""

    def __init__(self):
        super().__init__()
        self.last_seen_files = set()
        # Initialize with existing files
        self._scan_existing_files()

    def _scan_existing_files(self):
        """Scan and remember existing files to avoid notifying on startup."""
        if COMPRESSED_DIR.exists():
            for file_path in COMPRESSED_DIR.rglob('*.indexed'):
                self.last_seen_files.add(str(file_path))

    def on_created(self, event):
        """Handle new file creation."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # Only process .indexed files (completed compressions)
        if not file_path.name.endswith('.indexed'):
            return

        # Avoid duplicate notifications
        if str(file_path) in self.last_seen_files:
            return

        self.last_seen_files.add(str(file_path))

        # Extract handoff info
        try:
            handoff_id = file_path.stem.replace('.slim.indexed', '.slim').replace('.indexed', '')
            category = file_path.parent.name if file_path.parent != COMPRESSED_DIR else 'unknown'

            # Read file stats
            stats = file_path.stat()

            notification = {
                'event': 'new_handoff',
                'data': {
                    'id': handoff_id,
                    'filename': file_path.name,
                    'category': category,
                    'created': datetime.fromtimestamp(stats.st_mtime).isoformat(),
                    'size': stats.st_size
                }
            }

            # Queue notification for WebSocket broadcast
            pending_notifications.append(notification)
            print(f"[HandoffWatcher] New handoff detected: {handoff_id}")

        except Exception as e:
            print(f"[HandoffWatcher] Error processing {file_path}: {e}")


class HistoryWatcher(FileSystemEventHandler):
    """Watch for new entries in history.jsonl."""

    def __init__(self):
        super().__init__()
        self.history_file = Path.home() / '.claude' / 'history.jsonl'
        self.file_position = 0
        # Initialize position to end of file to avoid broadcasting existing entries
        if self.history_file.exists():
            self.file_position = self.history_file.stat().st_size

    def on_modified(self, event):
        """Handle file modifications."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # Only process history.jsonl
        if file_path != self.history_file:
            return

        # Read new lines
        try:
            with open(self.history_file, 'r') as f:
                f.seek(self.file_position)
                new_lines = f.read()
                self.file_position = f.tell()

            if not new_lines.strip():
                return

            # Parse each new line as JSON
            for line in new_lines.strip().split('\n'):
                if not line.strip():
                    continue

                try:
                    entry = json.loads(line)

                    # Extract conversation info
                    display = entry.get('display', '')
                    timestamp = entry.get('timestamp', 0)
                    project = entry.get('project', '')
                    session_id = entry.get('sessionId', '')
                    pasted = entry.get('pastedContents', {})

                    # Truncate display for preview
                    preview = display[:200] + '...' if len(display) > 200 else display

                    notification = {
                        'event': 'new_conversation',
                        'data': {
                            'sessionId': session_id,
                            'timestamp': timestamp,
                            'timeFormatted': datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                            'project': project.replace(str(Path.home()), '~'),
                            'display': display,
                            'preview': preview,
                            'hasPaste': len(pasted) > 0
                        }
                    }

                    # Queue notification for WebSocket broadcast
                    pending_notifications.append(notification)
                    print(f"[HistoryWatcher] New conversation entry: {preview[:50]}...")

                except json.JSONDecodeError as e:
                    print(f"[HistoryWatcher] Error parsing JSON line: {e}")
                    continue

        except Exception as e:
            print(f"[HistoryWatcher] Error reading history file: {e}")


async def handle_join_workspace_session(websocket, data):
    """Handle user joining a workspace session."""
    if not session_manager:
        return None

    session_id = data.get('session_id')
    user_name = data.get('user_name', 'Anonymous')
    user_id = data.get('user_id') or str(uuid.uuid4())

    try:
        # Try to join existing session
        session = session_manager.get_session(session_id)

        if not session:
            # Create new session if it doesn't exist
            session = session_manager.create_session(user_id, user_name, websocket)
            session_id = session.id
        else:
            # Join existing session
            session = session_manager.join_session(session_id, user_id, user_name, websocket)

            if not session:
                return None

        # Broadcast to other users that someone joined
        await session_manager.broadcast_to_session(
            session_id,
            'user_joined',
            {
                'user_id': user_id,
                'user_name': user_name,
                'users': [u.to_dict() for u in session.users.values()]
            },
            exclude_user=user_id
        )

        return (session_id, user_id)

    except Exception as e:
        print(f"[WebSocket] Error joining session: {e}")
        import traceback
        traceback.print_exc()
        return None


async def handle_workspace_message(session_id, user_id, data, websocket):
    """Handle a workspace message (user prompt to agent)."""
    if not session_manager:
        return

    try:
        agent_id = data.get('agent_id')
        message_content = data.get('message')

        if not agent_id or not message_content:
            return

        # Add user message to session
        msg = session_manager.add_message(
            session_id, user_id, agent_id, 'user', message_content
        )

        # Broadcast user message to all users in session
        await session_manager.broadcast_to_session(
            session_id,
            'user_message',
            {
                'message_id': msg.id,
                'user_id': user_id,
                'agent_id': agent_id,
                'content': message_content,
                'timestamp': msg.timestamp,
                'mentions': msg.mentions
            }
        )

        # Send mention notifications if any
        if msg.mentions:
            session = session_manager.get_session(session_id)
            user = session.users.get(user_id) if session else None
            user_name = user.name if user else 'Unknown'

            for mentioned_user_id in msg.mentions:
                if mentioned_user_id != user_id:
                    await session_manager.broadcast_to_session(
                        session_id,
                        'mention_notification',
                        {
                            'mentioned_user_id': mentioned_user_id,
                            'from_user_id': user_id,
                            'from_user_name': user_name,
                            'message_preview': message_content[:100],
                            'agent_id': agent_id,
                            'timestamp': msg.timestamp
                        }
                    )

        # Get session and orchestrator
        session = session_manager.get_session(session_id)
        if not session:
            print(f"[WebSocket] Session {session_id} not found!")
            return
        if not session.orchestrator:
            print(f"[WebSocket] No orchestrator for session {session_id}. Users: {list(session.users.keys())}")
            # Try to reinitialize orchestrator if missing
            from workspace_session_manager import get_api_key
            api_key = get_api_key()
            if api_key and AgentOrchestrator:
                try:
                    session.orchestrator = AgentOrchestrator(
                        api_key=api_key,
                        session_users=session.users,
                        session_manager=session_manager,
                        session_id=session_id
                    )
                    print(f"[WebSocket] Re-initialized orchestrator for session {session_id}")
                except Exception as e:
                    print(f"[WebSocket] Failed to re-init orchestrator: {e}")
                    return
            else:
                print(f"[WebSocket] Cannot init orchestrator - no API key or AgentOrchestrator")
                return

        # Start streaming indicator
        await session_manager.broadcast_to_session(
            session_id,
            'agent_thinking',
            {'agent_id': agent_id}
        )

        # Stream agent response
        full_response = []
        try:
            # Map friendly agent names to orchestrator IDs
            AGENT_ID_MAP = {
                'prax': 'moderator',
                'cairn': 'b',
                'koda': 'a'
            }
            orchestrator_agent_id = AGENT_ID_MAP.get(agent_id, agent_id)

            # orchestrator.send_message() is a sync iterator with sender_user_id for collaborative context
            loop = asyncio.get_event_loop()

            # Collect chunks from sync iterator (orchestrator builds collaborative context in system prompt)
            for chunk in session.orchestrator.send_message(orchestrator_agent_id, message_content, sender_user_id=user_id):
                full_response.append(chunk)

                # Broadcast chunk to all users in session
                await session_manager.broadcast_to_session(
                    session_id,
                    'agent_response_chunk',
                    {
                        'agent_id': agent_id,
                        'chunk': chunk
                    }
                )

            # After streaming complete, store full response
            complete_response = ''.join(full_response)
            response_msg = session_manager.add_message(
                session_id, user_id, agent_id, 'assistant', complete_response
            )

            # Broadcast completion
            await session_manager.broadcast_to_session(
                session_id,
                'agent_response_complete',
                {
                    'agent_id': agent_id,
                    'message_id': response_msg.id
                }
            )

            # Sync agent context back to session storage
            session.agent_contexts[agent_id] = session.orchestrator.get_context(agent_id)

        except Exception as e:
            print(f"[WebSocket] Error streaming agent response: {e}")
            await session_manager.broadcast_to_session(
                session_id,
                'agent_error',
                {
                    'agent_id': agent_id,
                    'error': str(e)
                }
            )

    except Exception as e:
        print(f"[WebSocket] Error handling workspace message: {e}")
        import traceback
        traceback.print_exc()


async def websocket_handler(websocket):
    """Handle WebSocket connections from dashboard clients."""
    print(f"[WebSocket] Client connected from {websocket.remote_address}")
    connected_clients.add(websocket)

    # Track session info for this connection
    session_id = None
    user_id = None

    try:
        # Send initial connection confirmation
        await websocket.send(json.dumps({
            'event': 'connected',
            'message': 'WebSocket connected - listening for updates'
        }))

        # Keep connection alive and handle incoming messages
        async for message in websocket:
            # Handle ping/pong or other client messages
            try:
                data = json.loads(message)
                msg_type = data.get('type')

                if msg_type == 'ping':
                    await websocket.send(json.dumps({'type': 'pong'}))

                # Workspace session events
                elif msg_type == 'join_workspace_session':
                    result = await handle_join_workspace_session(websocket, data)
                    if result:
                        session_id, user_id = result
                        await websocket.send(json.dumps({
                            'event': 'session_joined',
                            'session_id': session_id,
                            'user_id': user_id
                        }))

                elif msg_type == 'workspace_message':
                    if session_id and session_manager:
                        # Check permission to send messages
                        if not session_manager.can_send_messages(session_id, user_id):
                            await websocket.send(json.dumps({
                                'event': 'permission_denied',
                                'message': 'You do not have permission to send messages (viewer role)'
                            }))
                        else:
                            await handle_workspace_message(session_id, user_id, data, websocket)

                elif msg_type == 'user_typing':
                    if session_id and session_manager:
                        session_manager.update_user_presence(
                            session_id, user_id, is_typing=data.get('is_typing', False)
                        )
                        await session_manager.broadcast_to_session(
                            session_id,
                            'user_typing',
                            {'user_id': user_id, 'is_typing': data.get('is_typing')},
                            exclude_user=user_id
                        )

                elif msg_type == 'cursor_move':
                    if session_id and session_manager:
                        session_manager.update_user_presence(
                            session_id, user_id, cursor_position=data.get('position')
                        )
                        await session_manager.broadcast_to_session(
                            session_id,
                            'cursor_move',
                            {'user_id': user_id, 'position': data.get('position')},
                            exclude_user=user_id
                        )

                elif msg_type == 'claim_agent_control':
                    if session_id and session_manager:
                        agent_id = data.get('agent_id')
                        success = session_manager.claim_agent_control(session_id, user_id, agent_id)
                        if success:
                            session = session_manager.get_session(session_id)
                            await session_manager.broadcast_to_session(
                                session_id,
                                'agent_control_updated',
                                {'agent_control': session.agent_control}
                            )

                elif msg_type == 'release_agent_control':
                    if session_id and session_manager:
                        agent_id = data.get('agent_id')
                        success = session_manager.release_agent_control(session_id, user_id, agent_id)
                        if success:
                            session = session_manager.get_session(session_id)
                            await session_manager.broadcast_to_session(
                                session_id,
                                'agent_control_updated',
                                {'agent_control': session.agent_control}
                            )

                elif msg_type == 'handoff_agent_control':
                    if session_id and session_manager:
                        agent_id = data.get('agent_id')
                        to_user_id = data.get('to_user_id')
                        if agent_id and to_user_id:
                            success = session_manager.handoff_agent_control(
                                session_id, user_id, to_user_id, agent_id
                            )
                            if success:
                                session = session_manager.get_session(session_id)
                                await session_manager.broadcast_to_session(
                                    session_id,
                                    'agent_control_updated',
                                    {'agent_control': session.agent_control}
                                )
                                # Notify both users
                                to_user = session.users.get(to_user_id)
                                from_user = session.users.get(user_id)
                                if to_user and from_user:
                                    await session_manager.broadcast_to_session(
                                        session_id,
                                        'control_handoff_notification',
                                        {
                                            'agent_id': agent_id,
                                            'from_user_name': from_user.name,
                                            'to_user_name': to_user.name,
                                            'to_user_id': to_user_id
                                        }
                                    )
                            else:
                                await websocket.send(json.dumps({
                                    'event': 'handoff_failed',
                                    'message': 'Failed to hand off control'
                                }))

                elif msg_type == 'human_message':
                    if session_id and session_manager:
                        # Check permission to send messages
                        if not session_manager.can_send_messages(session_id, user_id):
                            await websocket.send(json.dumps({
                                'event': 'permission_denied',
                                'message': 'You do not have permission to send messages (viewer role)'
                            }))
                        else:
                            message_content = data.get('message')
                            if message_content:
                                session = session_manager.get_session(session_id)
                                user = session.users.get(user_id) if session else None
                                user_name = user.name if user else 'Unknown'

                                # Parse mentions
                                mentions = session_manager._parse_mentions(message_content, session_id)

                                # Broadcast human message to all users in session
                                await session_manager.broadcast_to_session(
                                    session_id,
                                    'human_message',
                                    {
                                        'user_id': user_id,
                                        'user_name': user_name,
                                        'message': message_content,
                                        'timestamp': datetime.utcnow().isoformat(),
                                        'mentions': mentions
                                    }
                                )

                                # Send mention notifications to mentioned users
                                if mentions:
                                    for mentioned_user_id in mentions:
                                        if mentioned_user_id != user_id:  # Don't notify yourself
                                            await session_manager.broadcast_to_session(
                                                session_id,
                                                'mention_notification',
                                                {
                                                    'mentioned_user_id': mentioned_user_id,
                                                    'from_user_id': user_id,
                                                    'from_user_name': user_name,
                                                    'message_preview': message_content[:100],
                                                    'timestamp': datetime.utcnow().isoformat()
                                                }
                                            )

                elif msg_type == 'change_user_role':
                    if session_id and session_manager:
                        target_user_id = data.get('target_user_id')
                        new_role = data.get('new_role')

                        if target_user_id and new_role:
                            success = session_manager.change_user_role(
                                session_id, user_id, target_user_id, new_role
                            )

                            if success:
                                # Broadcast role change to all users
                                session = session_manager.get_session(session_id)
                                await session_manager.broadcast_to_session(
                                    session_id,
                                    'user_role_changed',
                                    {
                                        'user_id': target_user_id,
                                        'new_role': new_role,
                                        'users': {uid: u.to_dict() for uid, u in session.users.items()}
                                    }
                                )
                            else:
                                await websocket.send(json.dumps({
                                    'event': 'permission_denied',
                                    'message': 'Failed to change role (insufficient permissions or invalid target)'
                                }))

                elif msg_type == 'acquire_document_lock':
                    if session_id and session_manager:
                        agent_id = data.get('agent_id')
                        if agent_id:
                            success = session_manager.acquire_document_lock(session_id, user_id, agent_id)
                            if success:
                                session = session_manager.get_session(session_id)
                                await session_manager.broadcast_to_session(
                                    session_id,
                                    'document_lock_updated',
                                    {'document_locks': session.document_locks}
                                )
                            else:
                                await websocket.send(json.dumps({
                                    'event': 'document_lock_failed',
                                    'agent_id': agent_id,
                                    'message': 'Document is locked by another user'
                                }))

                elif msg_type == 'release_document_lock':
                    if session_id and session_manager:
                        agent_id = data.get('agent_id')
                        if agent_id:
                            success = session_manager.release_document_lock(session_id, user_id, agent_id)
                            if success:
                                session = session_manager.get_session(session_id)
                                await session_manager.broadcast_to_session(
                                    session_id,
                                    'document_lock_updated',
                                    {'document_locks': session.document_locks}
                                )

                # Phase 4C.4: Conversation Search
                elif msg_type == 'conversation:search':
                    if session_manager:
                        query = data.get('query', '')
                        search_type = data.get('search_type', 'all')  # 'all', 'decisions', 'agent'
                        target_session = data.get('target_session', session_id)
                        agent_filter = data.get('agent_id')
                        limit = data.get('limit', 20)

                        try:
                            if search_type == 'decisions':
                                results = await session_manager.search_decisions(
                                    query=query,
                                    session_id=target_session,
                                    limit=limit
                                )
                            else:
                                results = await session_manager.search_conversation_history(
                                    query=query,
                                    session_id=target_session,
                                    agent_id=agent_filter,
                                    limit=limit
                                )

                            await websocket.send(json.dumps({
                                'event': 'search_results',
                                'query': query,
                                'search_type': search_type,
                                'results': results,
                                'total': len(results)
                            }))
                        except Exception as e:
                            await websocket.send(json.dumps({
                                'event': 'search_error',
                                'error': str(e)
                            }))

                elif msg_type == 'conversation:get_context':
                    # Get context for Prax recovery
                    if session_manager and session_id:
                        try:
                            context = await session_manager.get_context_for_prax(session_id)
                            await websocket.send(json.dumps({
                                'event': 'prax_context',
                                'context': context
                            }))
                        except Exception as e:
                            await websocket.send(json.dumps({
                                'event': 'context_error',
                                'error': str(e)
                            }))

                # Phase 4C.5: Demo Mode Controls
                elif msg_type == 'demo:start':
                    if session_manager and session_id:
                        result = session_manager.start_demo_mode(
                            session_id=session_id,
                            title=data.get('title', 'Demo Recording'),
                            description=data.get('description', ''),
                            branding=data.get('branding')
                        )
                        await websocket.send(json.dumps({
                            'event': 'demo_started',
                            **result
                        }))
                        # Broadcast to all session users
                        await session_manager.broadcast_to_session(
                            session_id,
                            'demo_mode_changed',
                            {'demo_mode': True, 'title': data.get('title')}
                        )

                elif msg_type == 'demo:stop':
                    if session_manager and session_id:
                        result = session_manager.stop_demo_mode(session_id)
                        await websocket.send(json.dumps({
                            'event': 'demo_stopped',
                            **result
                        }))
                        await session_manager.broadcast_to_session(
                            session_id,
                            'demo_mode_changed',
                            {'demo_mode': False}
                        )

                elif msg_type == 'demo:highlight':
                    if session_manager and session_id:
                        success = session_manager.add_demo_highlight(
                            session_id=session_id,
                            label=data.get('label', 'Highlight'),
                            description=data.get('description')
                        )
                        await websocket.send(json.dumps({
                            'event': 'highlight_added',
                            'success': success
                        }))

                elif msg_type == 'demo:list':
                    if session_manager:
                        recordings = session_manager.get_demo_recordings()
                        await websocket.send(json.dumps({
                            'event': 'demo_recordings',
                            'recordings': recordings
                        }))

                elif msg_type == 'demo:export':
                    if session_manager:
                        recording_id = data.get('recording_id')
                        format_type = data.get('format', 'html')

                        if format_type == 'json':
                            content = session_manager.export_demo_json(recording_id)
                        else:
                            content = session_manager.export_demo_html(recording_id)

                        await websocket.send(json.dumps({
                            'event': 'demo_export',
                            'recording_id': recording_id,
                            'format': format_type,
                            'content': content
                        }))

                # Phase 4C.6: Configuration & Preferences
                elif msg_type == 'config:get':
                    if session_manager:
                        settings = session_manager.get_workspace_settings()
                        await websocket.send(json.dumps({
                            'event': 'workspace_settings',
                            'settings': settings
                        }))

                elif msg_type == 'preferences:get':
                    if session_manager and user_id:
                        prefs = session_manager.get_user_preferences(user_id)
                        await websocket.send(json.dumps({
                            'event': 'user_preferences',
                            'preferences': prefs
                        }))

                elif msg_type == 'preferences:update':
                    if session_manager and user_id:
                        updates = data.get('preferences', {})
                        prefs = session_manager.update_user_preferences(user_id, **updates)
                        await websocket.send(json.dumps({
                            'event': 'preferences_updated',
                            'preferences': prefs
                        }))

                elif msg_type == 'config:reload':
                    if session_manager:
                        session_manager.reload_config()
                        settings = session_manager.get_workspace_settings()
                        await websocket.send(json.dumps({
                            'event': 'config_reloaded',
                            'settings': settings
                        }))

                elif msg_type == 'config:agent':
                    if session_manager:
                        agent_id = data.get('agent_id', 'prax')
                        config = session_manager.get_agent_config(agent_id)
                        await websocket.send(json.dumps({
                            'event': 'agent_config',
                            'agent_id': agent_id,
                            'config': config
                        }))

            except json.JSONDecodeError:
                pass
            except Exception as e:
                print(f"[WebSocket] Error handling message: {e}")
                import traceback
                traceback.print_exc()

    except websockets.exceptions.ConnectionClosed:
        print(f"[WebSocket] Client disconnected from {websocket.remote_address}")
    finally:
        connected_clients.discard(websocket)
        # Clean up session if user was in one
        if session_id and user_id and session_manager:
            # Get user name before removing from session
            session = session_manager.get_session(session_id)
            user_name = None
            if session and user_id in session.users:
                user_name = session.users[user_id].name

            session_manager.leave_session(session_id, user_id)
            await session_manager.broadcast_to_session(
                session_id,
                'user_left',
                {'user_id': user_id, 'user_name': user_name}
            )


    # =========================================================================
    # Collaborative Workspace Methods (Agent Chat)
    # =========================================================================

    def agent_chat(self, data):
        """Stream agent response from collaborative workspace."""
        global AGENT_ORCHESTRATOR

        agent_id = data.get('agent_id')
        message = data.get('message')
        document = data.get('document')  # Optional

        if not agent_id or not message:
            self.serve_json({'error': 'Missing agent_id or message'}, status=400)
            return

        # Initialize orchestrator on first use
        if AGENT_ORCHESTRATOR is None:
            try:
                AGENT_ORCHESTRATOR = AgentOrchestrator()
            except ValueError as e:
                self.serve_json({'error': str(e)}, status=500)
                return

        # Load document if provided and not already loaded
        if document and AGENT_ORCHESTRATOR.agents[agent_id].get('document') is None:
            AGENT_ORCHESTRATOR.load_document(agent_id, document)

        # Set headers for Server-Sent Events (SSE) streaming
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        try:
            # Stream response chunks
            for chunk in AGENT_ORCHESTRATOR.send_message(agent_id, message):
                # Send as SSE format: data: <content>\n\n
                self.wfile.write(f'data: {json.dumps({"chunk": chunk})}\n\n'.encode())
                self.wfile.flush()

            # Send completion marker
            self.wfile.write(f'data: {json.dumps({"done": True})}\n\n'.encode())
            self.wfile.flush()

        except Exception as e:
            error_msg = f'data: {json.dumps({"error": str(e)})}\n\n'
            self.wfile.write(error_msg.encode())
            self.wfile.flush()

    def agent_load_document(self, data):
        """Load a document into an agent's context."""
        global AGENT_ORCHESTRATOR

        agent_id = data.get('agent_id')
        document = data.get('document')
        handoff_id = data.get('handoff_id')  # Optional: load from V4Z handoff

        if not agent_id:
            self.serve_json({'error': 'Missing agent_id'}, status=400)
            return

        # Initialize orchestrator if needed
        if AGENT_ORCHESTRATOR is None:
            try:
                AGENT_ORCHESTRATOR = AgentOrchestrator()
            except ValueError as e:
                self.serve_json({'error': str(e)}, status=500)
                return

        # Load document from handoff if specified
        if handoff_id:
            try:
                # Decompress handoff to get content
                handoff_path = GOLDEN_LIBRARY_DIR / f"{handoff_id}.v4z"
                if not handoff_path.exists():
                    self.serve_json({'error': f'Handoff not found: {handoff_id}'}, status=404)
                    return

                # Use decompress script to get content
                import decompress
                with open(handoff_path, 'r') as f:
                    compressed = f.read()

                decompressed = decompress.decompress_v4z(compressed)
                document = decompressed

            except Exception as e:
                self.serve_json({'error': f'Failed to load handoff: {str(e)}'}, status=500)
                return

        if not document:
            self.serve_json({'error': 'Missing document or handoff_id'}, status=400)
            return

        try:
            AGENT_ORCHESTRATOR.load_document(agent_id, document)
            self.serve_json({
                'success': True,
                'agent_id': agent_id,
                'document_length': len(document)
            })
        except Exception as e:
            self.serve_json({'error': str(e)}, status=500)


async def broadcast_notifications():
    """Broadcast pending notifications to all connected clients."""
    while True:
        # Broadcast general pending notifications
        if pending_notifications and connected_clients:
            notification = pending_notifications.pop(0)
            disconnected = set()

            for client in connected_clients:
                try:
                    await client.send(json.dumps(notification))
                except Exception as e:
                    print(f"[WebSocket] Error sending to client: {e}")
                    disconnected.add(client)

            # Remove disconnected clients
            for client in disconnected:
                connected_clients.discard(client)

        # Broadcast Phase 4B workspace events (agent messages, workflows, blockers)
        if session_manager:
            ws_events = session_manager.get_and_clear_ws_events()
            for event in ws_events:
                session_id = event.get('session_id')
                event_type = event.get('event')
                event_data = event.get('data', {})

                # Broadcast to specific session
                await session_manager.broadcast_to_session(
                    session_id,
                    event_type,
                    event_data
                )

        await asyncio.sleep(0.1)


async def run_websocket_server(port=8081):
    """Run the WebSocket server."""
    print(f"[WebSocket] Server starting on ws://localhost:{port}")

    # Start file watcher
    observer = Observer()

    # Watch for new handoffs
    handoff_handler = HandoffWatcher()
    if COMPRESSED_DIR.exists():
        observer.schedule(handoff_handler, str(COMPRESSED_DIR), recursive=True)
        print(f"[WebSocket] Watching {COMPRESSED_DIR} for new handoffs")
    else:
        print(f"[WebSocket] Warning: {COMPRESSED_DIR} does not exist")

    # Watch for new conversation history entries
    history_handler = HistoryWatcher()
    history_dir = Path.home() / '.claude'
    if history_dir.exists():
        observer.schedule(history_handler, str(history_dir), recursive=False)
        print(f"[WebSocket] Watching {history_dir / 'history.jsonl'} for new conversations")
    else:
        print(f"[WebSocket] Warning: {history_dir} does not exist")

    observer.start()

    # Start broadcast task
    broadcast_task = asyncio.create_task(broadcast_notifications())

    # Start WebSocket server
    async with websockets.serve(websocket_handler, "localhost", port):
        await asyncio.Future()  # Run forever


def run_http_server(port=8080):
    """Run the HTTP server in a separate thread."""
    server_address = ('', port)
    httpd = HTTPServer(server_address, DashboardHandler)
    httpd.serve_forever()


def run_server(port=8080, ws_port=8081):
    """Run both HTTP and WebSocket servers."""
    print(f"""
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║           🎛️  Claude Control Center Dashboard 🎛️               ║
║                                                                ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║  HTTP Server:       http://localhost:{port}                     ║
║  WebSocket Server:  ws://localhost:{ws_port}                     ║
║                                                                ║
║  Features:                                                     ║
║    📊 Dashboard UI with 3D visualization                       ║
║    📡 Real-time handoff notifications via WebSocket            ║
║    🔍 Compression statistics & search                          ║
║                                                                ║
║  Endpoints:                                                    ║
║    GET /                    - Dashboard UI                     ║
║    GET /api/stats           - Compression statistics           ║
║    GET /api/search?q=...    - Search conversations             ║
║    GET /api/daemon-status   - Check daemon status              ║
║    GET /api/3d/handoffs     - 3D visualization data            ║
║                                                                ║
║  Press Ctrl+C to stop                                          ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
    """)

    # Start HTTP server in background thread
    http_thread = threading.Thread(target=run_http_server, args=(port,), daemon=True)
    http_thread.start()
    print(f"✅ HTTP server started on port {port}")

    # Run WebSocket server in main thread with asyncio
    try:
        asyncio.run(run_websocket_server(ws_port))
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down dashboard server...")
    except Exception as e:
        print(f"\n❌ Server error: {e}")


# =============================================================================
# UNIFIED AIOHTTP SERVER (Single Port for HTTP + WebSocket)
# =============================================================================

# Track aiohttp WebSocket clients by session
aiohttp_session_clients = {}  # {session_id: {user_id: (ws, user_name)}}

async def aiohttp_broadcast_to_session(session_id, event, data, exclude_user=None):
    """Broadcast message to all clients in a session."""
    if session_id not in aiohttp_session_clients:
        return

    message = json.dumps({'event': event, 'data': data})
    for uid, (client_ws, _) in list(aiohttp_session_clients[session_id].items()):
        if uid != exclude_user and not client_ws.closed:
            try:
                await client_ws.send_str(message)
            except Exception as e:
                print(f"[Broadcast] Error sending to {uid}: {e}")


async def aiohttp_websocket_handler(request):
    """Handle WebSocket connections via aiohttp."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    print(f"[WebSocket] Client connected via aiohttp")
    connected_clients.add(ws)

    session_id = None
    user_id = None
    user_name = None

    try:
        await ws.send_json({
            'event': 'connected',
            'message': 'WebSocket connected - listening for updates'
        })

        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    msg_type = data.get('type')

                    if msg_type == 'ping':
                        await ws.send_json({'type': 'pong'})

                    elif msg_type == 'join_workspace_session':
                        session_id = data.get('session_id')
                        user_id = data.get('user_id') or str(uuid.uuid4())[:8]
                        user_name = data.get('user_name', 'Anonymous')

                        # Track this client in the session
                        if session_id not in aiohttp_session_clients:
                            aiohttp_session_clients[session_id] = {}
                        aiohttp_session_clients[session_id][user_id] = (ws, user_name)

                        # CRITICAL: Also register with session_manager for orchestrator support
                        if session_manager:
                            existing_session = session_manager.get_session(session_id)
                            if existing_session:
                                # Join existing session
                                session_manager.join_session(session_id, user_id, user_name, ws)
                                print(f"[WebSocket/aiohttp] User {user_name} joined existing session {session_id}")
                            else:
                                # Create new session with orchestrator
                                new_session = session_manager.create_session(user_id, user_name, ws)
                                # Override the auto-generated session_id with the requested one
                                if new_session and session_id:
                                    session_manager.sessions[session_id] = new_session
                                    if new_session.id != session_id:
                                        session_manager.sessions.pop(new_session.id, None)
                                    new_session.id = session_id
                                print(f"[WebSocket/aiohttp] Created new session {session_id} with orchestrator")

                        print(f"[WebSocket] User {user_name} ({user_id}) joined session {session_id}")

                        # Notify the joining user
                        await ws.send_json({
                            'event': 'session_joined',
                            'session_id': session_id,
                            'user_id': user_id
                        })

                        # Notify others in the session
                        await aiohttp_broadcast_to_session(
                            session_id, 'user_joined',
                            {'user_id': user_id, 'user_name': user_name,
                             'users': {uid: {'name': un} for uid, (_, un) in aiohttp_session_clients[session_id].items()}},
                            exclude_user=user_id
                        )

                    elif msg_type == 'workspace_message':
                        if session_id:
                            # Broadcast message to all users in session
                            msg_content = data.get('content', data.get('message', ''))
                            agent_id = data.get('agent_id', 'chat')

                            print(f"[WebSocket] Message from {user_name} in {session_id}: {msg_content[:50]}...")

                            await aiohttp_broadcast_to_session(
                                session_id, 'user_message',
                                {
                                    'user_id': user_id,
                                    'user_name': user_name,
                                    'content': msg_content,
                                    'agent_id': agent_id,
                                    'timestamp': datetime.utcnow().isoformat()
                                },
                                exclude_user=None  # Send to everyone including sender for confirmation
                            )

                            # Process agent message through orchestrator if this is an agent panel
                            if agent_id in ['prax', 'koda', 'cairn', 'moderator', 'a', 'b'] and session_manager:
                                print(f"[WebSocket/aiohttp] Processing agent message for {agent_id} in session {session_id}")

                                # Get session and orchestrator
                                session = session_manager.get_session(session_id)
                                if session:
                                    # Initialize orchestrator if missing
                                    if not session.orchestrator:
                                        print(f"[WebSocket/aiohttp] No orchestrator, attempting init for {session_id}")
                                        from workspace_session_manager import get_api_key
                                        api_key = get_api_key()
                                        if api_key and AgentOrchestrator:
                                            try:
                                                session.orchestrator = AgentOrchestrator(
                                                    api_key=api_key,
                                                    session_users=session.users,
                                                    session_manager=session_manager,
                                                    session_id=session_id
                                                )
                                                print(f"[WebSocket/aiohttp] Orchestrator initialized for {session_id}")
                                            except Exception as e:
                                                print(f"[WebSocket/aiohttp] Failed to init orchestrator: {e}")

                                    if session.orchestrator:
                                        # Broadcast thinking indicator
                                        await aiohttp_broadcast_to_session(
                                            session_id, 'agent_thinking',
                                            {'agent_id': agent_id}
                                        )

                                        # Map agent names to orchestrator IDs
                                        AGENT_ID_MAP = {'prax': 'moderator', 'cairn': 'b', 'koda': 'a'}
                                        orchestrator_agent_id = AGENT_ID_MAP.get(agent_id, agent_id)

                                        # Stream response from orchestrator
                                        try:
                                            full_response = []
                                            for chunk in session.orchestrator.send_message(
                                                orchestrator_agent_id, msg_content, sender_user_id=user_id
                                            ):
                                                full_response.append(chunk)
                                                await aiohttp_broadcast_to_session(
                                                    session_id, 'agent_response_chunk',
                                                    {'agent_id': agent_id, 'chunk': chunk}
                                                )

                                            # Broadcast completion
                                            await aiohttp_broadcast_to_session(
                                                session_id, 'agent_response_complete',
                                                {'agent_id': agent_id, 'response': ''.join(full_response)}
                                            )
                                            print(f"[WebSocket/aiohttp] Agent {agent_id} response complete")
                                        except Exception as e:
                                            print(f"[WebSocket/aiohttp] Agent error: {e}")
                                            await aiohttp_broadcast_to_session(
                                                session_id, 'agent_error',
                                                {'agent_id': agent_id, 'error': str(e)}
                                            )
                                    else:
                                        print(f"[WebSocket/aiohttp] No orchestrator available for {session_id}")
                                else:
                                    print(f"[WebSocket/aiohttp] Session {session_id} not found")

                    elif msg_type == 'user_typing':
                        if session_id:
                            await aiohttp_broadcast_to_session(
                                session_id, 'user_typing',
                                {'user_id': user_id, 'user_name': user_name, 'is_typing': data.get('is_typing')},
                                exclude_user=user_id
                            )

                    elif msg_type == 'cursor_move':
                        if session_id:
                            await aiohttp_broadcast_to_session(
                                session_id, 'cursor_move',
                                {'user_id': user_id, 'position': data.get('position')},
                                exclude_user=user_id
                            )

                    elif msg_type == 'human_message':
                        if session_id:
                            message_content = data.get('message', '')
                            print(f"[WebSocket] Human chat from {user_name} in {session_id}: {message_content[:50]}...")

                            await aiohttp_broadcast_to_session(
                                session_id, 'human_message',
                                {
                                    'user_id': user_id,
                                    'user_name': user_name,
                                    'message': message_content,
                                    'timestamp': datetime.utcnow().isoformat()
                                },
                                exclude_user=user_id  # Don't send back to sender (they already added locally)
                            )

                except json.JSONDecodeError:
                    pass

            elif msg.type == web.WSMsgType.ERROR:
                print(f'[WebSocket] Error: {ws.exception()}')

    finally:
        connected_clients.discard(ws)
        # Remove from session tracking
        if session_id and user_id and session_id in aiohttp_session_clients:
            aiohttp_session_clients[session_id].pop(user_id, None)
            print(f"[WebSocket] User {user_name} ({user_id}) left session {session_id}")
            # Notify others
            await aiohttp_broadcast_to_session(
                session_id, 'user_left',
                {'user_id': user_id, 'user_name': user_name}
            )
        print(f"[WebSocket] Client disconnected")

    return ws


class AiohttpHandler:
    """Wraps DashboardHandler methods for aiohttp."""

    def __init__(self):
        self.handler = DashboardHandler

    async def handle_request(self, request):
        """Route HTTP requests to appropriate handler."""
        path = request.path
        query = request.query_string

        # Create a mock handler instance to use its methods
        handler = MockHandler(path, query, request)

        # Route based on path
        try:
            if path == '/' or path == '':
                return await self._serve_dashboard(handler)
            elif path == '/api/stats':
                return await self._serve_json(handler.get_compression_stats())
            elif path == '/api/daemon-status':
                return await self._serve_json(handler.get_daemon_status())
            elif path.startswith('/api/demo/'):
                return await self._handle_demo_api(path, query, handler)
            elif path == '/demo':
                return await self._serve_demo_page(query)
            elif path.startswith('/api/'):
                return await self._handle_api(path, query, handler, request)
            else:
                # Serve static files
                return await self._serve_static(path)
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)

    async def _serve_dashboard(self, handler):
        """Serve the main dashboard HTML."""
        dashboard_html = handler.get_dashboard_html()
        return web.Response(text=dashboard_html, content_type='text/html')

    async def _serve_json(self, data):
        """Serve JSON response."""
        return web.json_response(data)

    async def _serve_demo_page(self, query):
        """Serve demo join page."""
        import random
        params = parse_qs(query)
        code = params.get('code', [''])[0] if params.get('code') else ''
        name = params.get('name', [''])[0] if params.get('name') else ''
        auto_join = params.get('auto', [''])[0] == '1' if params.get('auto') else False

        if code and not name:
            name = f"Guest-{random.randint(1000, 9999)}"

        handler = MockHandler('/demo', query, None)
        html = handler._generate_demo_html(code, name, auto_join)
        return web.Response(text=html, content_type='text/html')

    async def _handle_demo_api(self, path, query, handler):
        """Handle demo API endpoints."""
        params = parse_qs(query)

        if path == '/api/demo/create':
            if not demo_store:
                return web.json_response({'error': 'Demo store not available'}, status=500)
            code = params.get('code', [None])[0]
            owner = params.get('owner', ['Host'])[0]
            demo = demo_store.create_demo(
                code=code.upper() if code else None,
                owner_name=owner
            )
            host = os.environ.get('RAILWAY_PUBLIC_DOMAIN', 'localhost:8080')
            protocol = 'https' if 'RAILWAY' in os.environ.get('RAILWAY_ENVIRONMENT', '') else 'http'
            share_url = f"{protocol}://{host}/demo?code={demo.code}"
            return web.json_response({
                'success': True, 'code': demo.code,
                'share_url': share_url, 'expires_at': demo.expires_at
            })

        elif path == '/api/demo/join':
            if not demo_store:
                return web.json_response({'error': 'Demo store not available'}, status=500)
            code = params.get('code', [''])[0]
            name = params.get('name', ['Guest'])[0]
            if not code:
                return web.json_response({'error': 'Code required'}, status=400)
            demo = demo_store.join_demo(code.upper(), name)
            if not demo:
                return web.json_response({'error': 'Demo not found or expired'}, status=404)
            return web.json_response({
                'success': True, 'code': demo.code,
                'workspace_session_id': demo.workspace_session_id,
                'participants': demo.participants
            })

        elif path == '/api/demo/link':
            if not demo_store:
                return web.json_response({'error': 'Demo store not available'}, status=500)
            code = params.get('code', [''])[0]
            session_id = params.get('session', [''])[0]
            if not code or not session_id:
                return web.json_response({'error': 'Code and session required'}, status=400)
            success = demo_store.link_workspace_session(code.upper(), session_id)
            if success:
                return web.json_response({'success': True})
            return web.json_response({'error': 'Demo not found'}, status=404)

        elif path == '/api/demo/list':
            if not demo_store:
                return web.json_response({'error': 'Demo store not available'}, status=500)
            demos = demo_store.list_active_demos()
            return web.json_response({'demos': [d.to_dict() for d in demos], 'count': len(demos)})

        elif path == '/api/demo/info':
            if not demo_store:
                return web.json_response({'error': 'Demo store not available'}, status=500)
            code = params.get('code', [''])[0]
            if not code:
                return web.json_response({'error': 'Code required'}, status=400)
            demo = demo_store.get_demo(code.upper())
            if not demo:
                return web.json_response({'error': 'Demo not found'}, status=404)
            return web.json_response(demo.to_dict())

        return web.json_response({'error': 'Not found'}, status=404)

    async def _handle_api(self, path, query, handler, request):
        """Handle other API endpoints."""
        params = parse_qs(query)

        # Session management
        if path == '/api/session/create':
            if not session_manager:
                return web.json_response({'error': 'Session manager not available'}, status=500)
            name = params.get('name', ['Anonymous'])[0]
            session = session_manager.create_session(name)
            return web.json_response({
                'session_id': session.session_id,
                'created_at': session.created_at
            })

        elif path == '/api/session/list':
            if not session_manager:
                return web.json_response({'error': 'Session manager not available'}, status=500)
            sessions = session_manager.list_sessions()
            return web.json_response({'sessions': sessions})

        elif path.startswith('/api/session/') and path.endswith('/info'):
            session_id = path.split('/')[3]
            if not session_manager:
                return web.json_response({'error': 'Session manager not available'}, status=500)
            session = session_manager.get_session(session_id)
            if not session:
                return web.json_response({'error': 'Session not found'}, status=404)
            return web.json_response(session.to_dict())

        # Search and other endpoints
        elif path == '/api/search':
            q = params.get('q', [''])[0]
            result = handler.search_conversations(q)
            return web.json_response(result)

        # API keys - load from Redis first, then file
        elif path == '/api/keys/list':
            keys = get_api_keys_from_redis()
            if keys is None:
                # Fall back to file
                keys = {}
                if API_KEYS_FILE.exists():
                    try:
                        with open(API_KEYS_FILE, 'r') as f:
                            keys = json.load(f)
                    except:
                        pass
            return web.json_response({'keys': keys, 'ok': True, 'source': 'redis' if REDIS_CLIENT else 'file'})

        # Model selection
        elif path == '/api/model/current':
            current_model = 'claude-opus-4.5'
            available_models = [
                {
                    'id': 'claude-opus-4.5',
                    'name': 'Claude Opus 4.5',
                    'description': 'Most capable model for complex tasks',
                    'speed': 'Slower',
                    'cost': 'Highest',
                    'recommended_for': ['Complex analysis', 'Code architecture', 'Research']
                },
                {
                    'id': 'claude-sonnet-4',
                    'name': 'Claude Sonnet 4',
                    'description': 'Balanced performance and speed',
                    'speed': 'Medium',
                    'cost': 'Medium',
                    'recommended_for': ['General coding', 'Documentation', 'Debugging']
                },
                {
                    'id': 'claude-3.5-haiku',
                    'name': 'Claude 3.5 Haiku',
                    'description': 'Fast and efficient for simple tasks',
                    'speed': 'Fastest',
                    'cost': 'Lowest',
                    'recommended_for': ['Quick questions', 'Simple edits', 'Formatting']
                }
            ]
            return web.json_response({
                'current_model': current_model,
                'available_models': available_models
            })

        # Todos (stub)
        elif path.startswith('/api/todos/'):
            return web.json_response({'todos': [], 'ok': True})

        # Conversations (stub to prevent errors)
        elif path == '/api/conversations/list':
            return web.json_response({'conversations': [], 'ok': True})

        # Agents list
        elif path == '/api/agents/list':
            return web.json_response({'agents': [], 'ok': True})

        # Default - return empty ok response for unknown API paths
        return web.json_response({'ok': True, 'data': None})

    async def _serve_static(self, path):
        """Serve static files."""
        # For now, return 404 for unknown paths
        return web.Response(text='Not found', status=404)

    async def handle_post_request(self, request):
        """Handle POST requests."""
        path = request.path

        # Handle file upload (multipart/form-data) BEFORE trying JSON parse
        if path == '/api/files/upload':
            return await self._handle_file_upload_async(request)

        # Handle file to-canvas conversion
        if path.startswith('/api/files/') and '/to-canvas' in path:
            file_id = path.split('/')[3]
            try:
                body = await request.json()
            except:
                body = {}
            return await self._convert_file_to_canvas_async(file_id, body)

        try:
            body = await request.json()
        except:
            body = {}

        # Session creation - generate session ID for WebSocket to use
        if path == '/api/workspace/sessions/create' or path == '/api/session/create':
            import uuid
            session_id = str(uuid.uuid4())[:8]
            user_id = body.get('user_id') or str(uuid.uuid4())[:8]
            user_name = body.get('user_name', body.get('name', 'Anonymous'))

            return web.json_response({
                'success': True,
                'ok': True,
                'session_id': session_id,
                'user_id': user_id,
                'user_name': user_name,
                'created_at': datetime.utcnow().isoformat()
            })

        # API keys save - to Redis first, then file as backup
        if path == '/api/keys/save':
            keys = body.get('keys', {})
            if not keys:
                return web.json_response({'error': 'No keys provided'}, status=400)
            try:
                saved_to_redis = save_api_keys_to_redis(keys)

                # Also save to file as backup
                try:
                    API_KEYS_FILE.parent.mkdir(parents=True, exist_ok=True)
                    with open(API_KEYS_FILE, 'w') as f:
                        json.dump(keys, f, indent=2)
                    os.chmod(API_KEYS_FILE, 0o600)
                except:
                    pass  # File save is optional on Railway

                return web.json_response({
                    'success': True,
                    'message': f'Saved {len(keys)} API key(s)' + (' to Redis' if saved_to_redis else ' to file'),
                    'count': len(keys),
                    'storage': 'redis' if saved_to_redis else 'file'
                })
            except Exception as e:
                return web.json_response({'error': str(e)}, status=500)

        # Agent chat with SSE streaming
        if path == '/api/agent/chat':
            return await self._handle_agent_chat(request, body)

        # Canvas endpoints
        if '/canvas/' in path:
            return web.json_response({'ok': True, 'success': True, 'message': 'Canvas endpoint'})

        # Default - allow unknown POST endpoints to succeed
        return web.json_response({'ok': True, 'success': True, 'path': path})

    async def _handle_agent_chat(self, request, body):
        """Handle agent chat with SSE streaming."""
        global AGENT_ORCHESTRATOR

        agent_id = body.get('agent_id')
        message = body.get('message')
        document = body.get('document')

        if not agent_id or not message:
            return web.json_response({'error': 'Missing agent_id or message'}, status=400)

        # Initialize orchestrator on first use
        if AGENT_ORCHESTRATOR is None:
            try:
                # Priority: 1. Environment variable, 2. Redis, 3. File
                api_key = os.environ.get('ANTHROPIC_API_KEY')

                if not api_key:
                    # Try Redis
                    redis_keys = get_api_keys_from_redis()
                    if redis_keys:
                        api_key = redis_keys.get('claude')

                if not api_key and API_KEYS_FILE.exists():
                    # Fall back to file
                    try:
                        with open(API_KEYS_FILE, 'r') as f:
                            keys = json.load(f)
                        api_key = keys.get('claude')
                    except:
                        pass

                if not api_key:
                    return web.json_response({
                        'error': 'ANTHROPIC_API_KEY not configured. Save your API key in the Config tab (it will persist in Redis).'
                    }, status=500)

                AGENT_ORCHESTRATOR = AgentOrchestrator(api_key=api_key)
            except Exception as e:
                return web.json_response({'error': str(e)}, status=500)

        # Load document if provided
        if document and AGENT_ORCHESTRATOR.agents.get(agent_id, {}).get('document') is None:
            AGENT_ORCHESTRATOR.load_document(agent_id, document)

        # Create SSE streaming response
        response = web.StreamResponse(
            status=200,
            headers={
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*'
            }
        )
        await response.prepare(request)

        try:
            # Stream response chunks
            for chunk in AGENT_ORCHESTRATOR.send_message(agent_id, message):
                data = f'data: {json.dumps({"chunk": chunk})}\n\n'
                await response.write(data.encode())

            # Send completion marker
            await response.write(f'data: {json.dumps({"done": True})}\n\n'.encode())

        except Exception as e:
            await response.write(f'data: {json.dumps({"error": str(e)})}\n\n'.encode())

        await response.write_eof()
        return response

    async def _handle_file_upload_async(self, request):
        """Handle multipart file upload for aiohttp."""
        import uuid
        import re

        try:
            reader = await request.multipart()
            uploaded_files = []

            while True:
                part = await reader.next()
                if part is None:
                    break

                if part.filename:
                    # Read file content
                    file_content = await part.read()
                    filename = part.filename

                    # Generate file ID
                    file_id = str(uuid.uuid4())[:8]

                    # Sanitize filename
                    safe_filename = re.sub(r'[^\w\-_\.]', '_', filename)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    safe_filename = f"{timestamp}_{safe_filename}"

                    # Determine category and extract text content
                    ext = Path(filename).suffix.lower()
                    doc_exts = {'.pdf', '.txt', '.md', '.doc', '.docx', '.rtf', '.odt', '.csv', '.json', '.xml', '.yaml', '.yml'}
                    code_exts = {'.py', '.js', '.ts', '.jsx', '.tsx', '.html', '.css', '.go', '.rs', '.java', '.c', '.cpp', '.h', '.sh', '.bash', '.sql', '.swift', '.kt', '.rb', '.php'}
                    image_exts = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.bmp', '.ico'}
                    text_exts = {'.txt', '.md', '.json', '.xml', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf', '.log', '.csv', '.tsv'}

                    if ext in doc_exts:
                        category = 'documents'
                    elif ext in code_exts:
                        category = 'code'
                    elif ext in image_exts:
                        category = 'images'
                    else:
                        category = 'documents'

                    # Extract text content immediately (before saving to disk)
                    extracted_content = ''
                    section_type = 'markdown'

                    try:
                        if ext in text_exts or ext in code_exts:
                            extracted_content = file_content.decode('utf-8', errors='ignore')
                            if ext in code_exts:
                                section_type = 'code'
                                lang = ext[1:]
                                lang_map = {'js': 'javascript', 'ts': 'typescript', 'py': 'python', 'rb': 'ruby', 'rs': 'rust', 'kt': 'kotlin'}
                                lang = lang_map.get(lang, lang)
                                extracted_content = f"```{lang}\n{extracted_content}\n```"
                        elif ext in image_exts:
                            extracted_content = f"![{filename}](/api/files/{file_id}/content)\n\n*Image file: {filename}*"
                        elif ext == '.pdf':
                            extracted_content = f"[PDF file: {filename} - Upload to local server for text extraction]"
                        else:
                            # Try to decode as text
                            try:
                                extracted_content = file_content.decode('utf-8', errors='ignore')
                            except:
                                extracted_content = f"[Binary file: {filename}]"
                    except Exception as e:
                        print(f"[Files] Content extraction error: {e}")
                        extracted_content = f"[Error extracting content: {str(e)}]"

                    # Save file (optional for Railway, but try anyway)
                    try:
                        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
                        save_path = UPLOADS_DIR / safe_filename
                        with open(save_path, 'wb') as f:
                            f.write(file_content)
                    except Exception as e:
                        print(f"[Files] File save failed (Railway ephemeral?): {e}")
                        save_path = Path(f"/tmp/{safe_filename}")

                    # Create metadata WITH extracted content
                    file_meta = {
                        'id': file_id,
                        'filename': filename,
                        'saved_as': safe_filename,
                        'category': category,
                        'path': str(save_path),
                        'size': len(file_content),
                        'uploaded': datetime.now().isoformat(),
                        'thumbnail': None,
                        'extracted_preview': extracted_content[:500] if extracted_content else None,
                        'indexed_to_memory': False,
                        # Include content for immediate canvas conversion
                        'content': extracted_content,
                        'section_type': section_type,
                        'suggested_name': Path(filename).stem
                    }

                    # Update index (try, but don't fail if it doesn't work)
                    try:
                        index = {'files': [], 'version': '1.0'}
                        if UPLOADS_INDEX_FILE.exists():
                            with open(UPLOADS_INDEX_FILE, 'r') as f:
                                index = json.load(f)
                        index['files'].append(file_meta)
                        with open(UPLOADS_INDEX_FILE, 'w') as f:
                            json.dump(index, f, indent=2)
                    except Exception as e:
                        print(f"[Files] Index update failed: {e}")

                    uploaded_files.append(file_meta)
                    print(f"[Files] Uploaded (async): {filename}, content length: {len(extracted_content)}")

            if uploaded_files:
                return web.json_response({
                    'ok': True,
                    'files': uploaded_files,
                    'count': len(uploaded_files)
                })
            else:
                return web.json_response({'error': 'No files found in request'}, status=400)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return web.json_response({'error': str(e)}, status=500)

    async def _convert_file_to_canvas_async(self, file_id, data):
        """Convert an uploaded file to canvas section content (async version)."""
        try:
            # Load uploads index
            index = {'files': [], 'version': '1.0'}
            if UPLOADS_INDEX_FILE.exists():
                with open(UPLOADS_INDEX_FILE, 'r') as f:
                    index = json.load(f)

            # Find file metadata
            file_meta = None
            for f in index.get('files', []):
                if f.get('id') == file_id:
                    file_meta = f
                    break

            if not file_meta:
                return web.json_response({'error': 'File not found'}, status=404)

            file_path = Path(file_meta.get('path', ''))
            if not file_path.exists():
                return web.json_response({'error': 'File path not found'}, status=404)

            category = file_meta.get('category', 'document')
            filename = file_meta.get('filename', 'untitled')
            ext = file_path.suffix.lower()

            # Extract content based on file type
            content = ''
            section_type = 'markdown'

            text_extensions = ['.txt', '.md', '.json', '.xml', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf', '.log', '.csv', '.tsv']
            code_extensions = ['.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.c', '.cpp', '.h', '.hpp', '.cs', '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.scala', '.r', '.sql', '.sh', '.bash', '.zsh', '.ps1', '.html', '.css', '.scss', '.less', '.vue', '.svelte']

            if ext in text_extensions:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                section_type = 'markdown'

            elif ext in code_extensions:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                section_type = 'code'
                lang = ext[1:]
                lang_map = {'js': 'javascript', 'ts': 'typescript', 'py': 'python', 'rb': 'ruby', 'rs': 'rust', 'kt': 'kotlin'}
                lang = lang_map.get(lang, lang)
                content = f"```{lang}\n{content}\n```"

            elif ext == '.pdf':
                content = f"[PDF file: {filename} - Text extraction not available in async mode. View original file.]"
                section_type = 'markdown'

            elif category == 'images':
                content = f"![{filename}](/api/files/{file_id}/content)\n\n*Image file: {filename}*"
                section_type = 'markdown'

            elif category == 'videos':
                content = f"[Video: {filename}](/api/files/{file_id}/content)\n\n*Video file: {filename}*"
                section_type = 'markdown'

            else:
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                except:
                    content = f"[Binary file: {filename} - Cannot display content]"
                section_type = 'markdown'

            print(f"[Files] Converted to canvas (async): {filename}, content length: {len(content)}")

            return web.json_response({
                'ok': True,
                'file_id': file_id,
                'filename': filename,
                'content': content,
                'section_type': section_type,
                'suggested_name': file_path.stem
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            return web.json_response({'error': str(e)}, status=500)


class MockHandler:
    """Mock handler to reuse DashboardHandler methods."""

    def __init__(self, path, query, request):
        self.path = path
        self.query = query
        self.request = request

    def get_compression_stats(self):
        """Get compression statistics."""
        conversations = []
        total_original = 0
        total_compressed = 0

        # Try to load from index file
        if INDEX_FILE.exists():
            try:
                with open(INDEX_FILE, 'r') as f:
                    index = json.load(f)
                conversations = index.get('conversations', [])
                total_original = sum(c.get('original_tokens', 0) for c in conversations)
                total_compressed = sum(c.get('compressed_tokens', 0) for c in conversations)
            except:
                pass

        # If no index, check compressed dir
        if not conversations and COMPRESSED_DIR.exists():
            files = list(COMPRESSED_DIR.glob('*.jsonl'))
            conversations = [{'id': f.stem, 'name': f.stem} for f in files[:20]]

        total_saved = total_original - total_compressed
        reduction_percent = (total_saved / total_original * 100) if total_original > 0 else 0

        return {
            'library_exists': LIBRARY_DIR.exists(),
            'compressed_count': len(conversations),
            'total_original_bytes': total_original,
            'total_compressed_bytes': total_compressed,
            'conversations': conversations,
            'total_conversations': len(conversations),
            'total_original_tokens': total_original,
            'total_compressed_tokens': total_compressed,
            'total_saved_tokens': total_saved,
            'reduction_percent': round(reduction_percent, 1),
            'recent_activity': []
        }

    def get_daemon_status(self):
        """Get daemon status."""
        running = False
        pid = None
        if DAEMON_PID_FILE.exists():
            try:
                pid = int(DAEMON_PID_FILE.read_text().strip())
                os.kill(pid, 0)
                running = True
            except (ValueError, OSError):
                running = False
        return {'running': running, 'pid': pid}

    def get_dashboard_html(self):
        """Get dashboard HTML from file."""
        dashboard_path = Path(__file__).parent / 'claude_dashboard.html'
        if dashboard_path.exists():
            return dashboard_path.read_text()
        return '<html><body>Dashboard not found</body></html>'

    def search_conversations(self, query):
        """Search conversations."""
        return {'results': [], 'query': query}

    def _generate_demo_html(self, code='', name='', auto_join=False):
        """Generate demo join HTML - delegating to DashboardHandler."""
        # This is a simplified version - the full HTML is in DashboardHandler
        handler = DashboardHandler.__new__(DashboardHandler)
        return handler._generate_demo_html(code, name, auto_join)


async def run_unified_server(port=8080):
    """Run unified HTTP + WebSocket server on single port."""
    print(f"""
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║      🎛️  Claude Control Center Dashboard (Unified) 🎛️          ║
║                                                                ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║  Server:    http://localhost:{port}                            ║
║  WebSocket: ws://localhost:{port}/ws                           ║
║                                                                ║
║  Single port mode - ready for Railway deployment!              ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
    """)

    # Start file watchers
    observer = Observer()
    handoff_handler = HandoffWatcher()
    if COMPRESSED_DIR.exists():
        observer.schedule(handoff_handler, str(COMPRESSED_DIR), recursive=True)
        print(f"[Server] Watching {COMPRESSED_DIR} for handoffs")

    history_handler = HistoryWatcher()
    history_dir = Path.home() / '.claude'
    if history_dir.exists():
        observer.schedule(history_handler, str(history_dir), recursive=False)

    observer.start()

    # Create aiohttp app
    app = web.Application()
    aio_handler = AiohttpHandler()

    # WebSocket route
    app.router.add_get('/ws', aiohttp_websocket_handler)

    # POST routes for session/workspace APIs
    app.router.add_post('/api/workspace/sessions/create', aio_handler.handle_post_request)
    app.router.add_post('/api/session/create', aio_handler.handle_post_request)
    app.router.add_post('/{path:.*}', aio_handler.handle_post_request)

    # HTTP GET routes
    app.router.add_get('/{path:.*}', aio_handler.handle_request)

    # Start broadcast notifications task
    asyncio.create_task(broadcast_notifications())

    # Run server
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"✅ Unified server started on port {port}")

    # Keep running
    await asyncio.Future()


if __name__ == '__main__':
    import sys

    # Railway/cloud deployment: use PORT env variable
    port = int(os.environ.get('PORT', 8080))
    ws_port = int(os.environ.get('WS_PORT', 8081))

    # Parse arguments (skip flags)
    for arg in sys.argv[1:]:
        if not arg.startswith('--'):
            try:
                port = int(arg)
            except ValueError:
                print(f"Invalid port: {arg}")
                sys.exit(1)

    # Use unified server if aiohttp available and on Railway or --unified flag
    use_unified = AIOHTTP_AVAILABLE and (
        os.environ.get('RAILWAY_ENVIRONMENT') or
        '--unified' in sys.argv or
        os.environ.get('UNIFIED_SERVER', '').lower() == 'true'
    )

    if use_unified:
        print("🚀 Starting unified single-port server...")
        asyncio.run(run_unified_server(port))
    else:
        # Fallback to separate ports
        run_server(port, ws_port)
