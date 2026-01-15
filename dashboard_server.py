#!/usr/bin/env python3
"""
Simple HTTP server to serve Claude compression data to the dashboard.
Provides JSON API for dashboard to load real compressed data.
"""

import json
import os
import glob
import sys
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import subprocess
import asyncio
import websockets
import threading
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / 'src'))

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
        elif path == '/' or path == '/index.html':
            self.serve_dashboard()
            return
        else:
            # Return 404 for other paths
            self.send_error(404, "Not found")

    def do_POST(self):
        """Handle POST requests."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        # Get content length and read body
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
        elif path == '/api/golden/restore':
            self.restore_golden_plan(data)
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


async def websocket_handler(websocket):
    """Handle WebSocket connections from dashboard clients."""
    print(f"[WebSocket] Client connected from {websocket.remote_address}")
    connected_clients.add(websocket)

    try:
        # Send initial connection confirmation
        await websocket.send(json.dumps({
            'event': 'connected',
            'message': 'WebSocket connected - listening for handoff updates'
        }))

        # Keep connection alive and handle incoming messages
        async for message in websocket:
            # Handle ping/pong or other client messages
            try:
                data = json.loads(message)
                if data.get('type') == 'ping':
                    await websocket.send(json.dumps({'type': 'pong'}))
            except json.JSONDecodeError:
                pass

    except websockets.exceptions.ConnectionClosed:
        print(f"[WebSocket] Client disconnected from {websocket.remote_address}")
    finally:
        connected_clients.discard(websocket)


async def broadcast_notifications():
    """Broadcast pending notifications to all connected clients."""
    while True:
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

        await asyncio.sleep(0.1)


async def run_websocket_server(port=8081):
    """Run the WebSocket server."""
    print(f"[WebSocket] Server starting on ws://localhost:{port}")

    # Start file watcher
    observer = Observer()
    event_handler = HandoffWatcher()

    if COMPRESSED_DIR.exists():
        observer.schedule(event_handler, str(COMPRESSED_DIR), recursive=True)
        observer.start()
        print(f"[WebSocket] Watching {COMPRESSED_DIR} for new handoffs")
    else:
        print(f"[WebSocket] Warning: {COMPRESSED_DIR} does not exist")

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


if __name__ == '__main__':
    import sys

    port = 8080
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Invalid port: {sys.argv[1]}")
            sys.exit(1)

    run_server(port)
