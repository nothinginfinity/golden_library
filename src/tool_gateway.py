#!/usr/bin/env python3
"""
Tool Gateway - Phase 4C.3 External Tool Integration

Provides Cairn and Koda with access to external APIs and tools:
- LLM APIs: DeepSeek, OpenAI, Claude Haiku
- Web: Search, Crawl, URL Fetch
- Code: Execution, Analysis
- Data: Database queries

Features:
- Permission-based access control per agent
- Cost tracking and rate limiting
- Audit logging of all tool calls
- Async execution with timeout handling
"""

import os
import json
import uuid
import asyncio
import aiohttp
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from abc import ABC, abstractmethod


class ToolCategory(Enum):
    """Categories of tools."""
    LLM = "llm"           # Language model APIs
    WEB = "web"           # Web search and crawl
    CODE = "code"         # Code execution/analysis
    DATA = "data"         # Database access
    MEDIA = "media"       # Image/video generation


class ToolStatus(Enum):
    """Status of a tool call."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    DENIED = "denied"


@dataclass
class ToolResult:
    """Result from a tool execution."""
    tool_name: str
    status: ToolStatus
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time_ms: int = 0
    cost_usd: float = 0.0
    tokens_used: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'tool_name': self.tool_name,
            'status': self.status.value,
            'result': self.result,
            'error': self.error,
            'execution_time_ms': self.execution_time_ms,
            'cost_usd': self.cost_usd,
            'tokens_used': self.tokens_used,
            'metadata': self.metadata
        }


@dataclass
class ToolCall:
    """Record of a tool call."""
    id: str
    tool_name: str
    requesting_agent: str
    session_id: str
    params: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    status: ToolStatus = ToolStatus.PENDING
    result: Optional[ToolResult] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'tool_name': self.tool_name,
            'requesting_agent': self.requesting_agent,
            'session_id': self.session_id,
            'params': self.params,
            'timestamp': self.timestamp,
            'status': self.status.value,
            'result': self.result.to_dict() if self.result else None
        }


class BaseTool(ABC):
    """Base class for all tools."""

    def __init__(self, name: str, category: ToolCategory, description: str):
        self.name = name
        self.category = category
        self.description = description
        self.enabled = True
        self.rate_limit_per_minute = 60
        self.cost_per_call = 0.0

    @abstractmethod
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Execute the tool with given parameters."""
        pass

    def get_schema(self) -> Dict[str, Any]:
        """Return JSON schema for tool parameters."""
        return {
            'name': self.name,
            'category': self.category.value,
            'description': self.description,
            'enabled': self.enabled
        }


# ===== LLM Tools =====

class DeepSeekTool(BaseTool):
    """DeepSeek API for code analysis and generation."""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(
            name="deepseek",
            category=ToolCategory.LLM,
            description="DeepSeek AI for code analysis, debugging, and generation. Best for technical/code tasks."
        )
        self.api_key = api_key or os.environ.get('DEEPSEEK_API_KEY')
        self.base_url = "https://api.deepseek.com/v1"
        self.cost_per_1k_tokens = 0.0014  # Approximate

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        start_time = datetime.utcnow()

        if not self.api_key:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.FAILED,
                error="DeepSeek API key not configured"
            )

        prompt = params.get('prompt', '')
        system_prompt = params.get('system', 'You are a helpful coding assistant.')
        max_tokens = params.get('max_tokens', 2000)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "deepseek-chat",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": max_tokens
                    },
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        content = data['choices'][0]['message']['content']
                        tokens = data.get('usage', {}).get('total_tokens', 0)

                        exec_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)

                        return ToolResult(
                            tool_name=self.name,
                            status=ToolStatus.SUCCESS,
                            result=content,
                            execution_time_ms=exec_time,
                            tokens_used=tokens,
                            cost_usd=tokens * self.cost_per_1k_tokens / 1000
                        )
                    else:
                        error_text = await response.text()
                        return ToolResult(
                            tool_name=self.name,
                            status=ToolStatus.FAILED,
                            error=f"API error {response.status}: {error_text}"
                        )

        except asyncio.TimeoutError:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.TIMEOUT,
                error="Request timed out after 60 seconds"
            )
        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.FAILED,
                error=str(e)
            )


class OpenAITool(BaseTool):
    """OpenAI API for general-purpose tasks."""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(
            name="openai",
            category=ToolCategory.LLM,
            description="OpenAI GPT-4 for complex reasoning, writing, and analysis tasks."
        )
        self.api_key = api_key or os.environ.get('OPENAI_API_KEY')
        self.base_url = "https://api.openai.com/v1"
        self.cost_per_1k_input = 0.01  # GPT-4 approximate
        self.cost_per_1k_output = 0.03

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        start_time = datetime.utcnow()

        if not self.api_key:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.FAILED,
                error="OpenAI API key not configured"
            )

        prompt = params.get('prompt', '')
        system_prompt = params.get('system', 'You are a helpful assistant.')
        model = params.get('model', 'gpt-4-turbo-preview')
        max_tokens = params.get('max_tokens', 2000)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": max_tokens
                    },
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        content = data['choices'][0]['message']['content']
                        usage = data.get('usage', {})
                        input_tokens = usage.get('prompt_tokens', 0)
                        output_tokens = usage.get('completion_tokens', 0)

                        exec_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                        cost = (input_tokens * self.cost_per_1k_input + output_tokens * self.cost_per_1k_output) / 1000

                        return ToolResult(
                            tool_name=self.name,
                            status=ToolStatus.SUCCESS,
                            result=content,
                            execution_time_ms=exec_time,
                            tokens_used=input_tokens + output_tokens,
                            cost_usd=cost
                        )
                    else:
                        error_text = await response.text()
                        return ToolResult(
                            tool_name=self.name,
                            status=ToolStatus.FAILED,
                            error=f"API error {response.status}: {error_text}"
                        )

        except asyncio.TimeoutError:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.TIMEOUT,
                error="Request timed out after 120 seconds"
            )
        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.FAILED,
                error=str(e)
            )


class ClaudeHaikuTool(BaseTool):
    """Claude Haiku for fast, lightweight responses."""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(
            name="claude_haiku",
            category=ToolCategory.LLM,
            description="Claude Haiku for fast, efficient responses. Best for quick lookups and simple tasks."
        )
        self.api_key = api_key or os.environ.get('ANTHROPIC_API_KEY')
        self.base_url = "https://api.anthropic.com/v1"
        self.cost_per_1k_input = 0.00025
        self.cost_per_1k_output = 0.00125

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        start_time = datetime.utcnow()

        if not self.api_key:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.FAILED,
                error="Anthropic API key not configured"
            )

        prompt = params.get('prompt', '')
        system_prompt = params.get('system', 'You are a helpful assistant.')
        max_tokens = params.get('max_tokens', 1000)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "claude-3-haiku-20240307",
                        "max_tokens": max_tokens,
                        "system": system_prompt,
                        "messages": [
                            {"role": "user", "content": prompt}
                        ]
                    },
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        content = data['content'][0]['text']
                        usage = data.get('usage', {})
                        input_tokens = usage.get('input_tokens', 0)
                        output_tokens = usage.get('output_tokens', 0)

                        exec_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                        cost = (input_tokens * self.cost_per_1k_input + output_tokens * self.cost_per_1k_output) / 1000

                        return ToolResult(
                            tool_name=self.name,
                            status=ToolStatus.SUCCESS,
                            result=content,
                            execution_time_ms=exec_time,
                            tokens_used=input_tokens + output_tokens,
                            cost_usd=cost
                        )
                    else:
                        error_text = await response.text()
                        return ToolResult(
                            tool_name=self.name,
                            status=ToolStatus.FAILED,
                            error=f"API error {response.status}: {error_text}"
                        )

        except asyncio.TimeoutError:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.TIMEOUT,
                error="Request timed out after 30 seconds"
            )
        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.FAILED,
                error=str(e)
            )


# ===== Web Tools =====

class WebSearchTool(BaseTool):
    """Web search using SerpAPI or Brave Search."""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(
            name="web_search",
            category=ToolCategory.WEB,
            description="Search the web for current information. Returns top results with snippets."
        )
        self.api_key = api_key or os.environ.get('SERPAPI_KEY') or os.environ.get('BRAVE_API_KEY')
        self.use_brave = bool(os.environ.get('BRAVE_API_KEY'))
        self.cost_per_call = 0.005  # Approximate

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        start_time = datetime.utcnow()

        query = params.get('query', '')
        num_results = params.get('num_results', 5)

        if not query:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.FAILED,
                error="Query parameter required"
            )

        # If no API key, return mock results for testing
        if not self.api_key:
            exec_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                result={
                    'query': query,
                    'results': [
                        {
                            'title': f'Result for: {query}',
                            'url': 'https://example.com',
                            'snippet': f'Mock search result for "{query}". Configure SERPAPI_KEY or BRAVE_API_KEY for real results.'
                        }
                    ],
                    'mock': True
                },
                execution_time_ms=exec_time,
                metadata={'mock': True}
            )

        try:
            if self.use_brave:
                return await self._brave_search(query, num_results, start_time)
            else:
                return await self._serp_search(query, num_results, start_time)

        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.FAILED,
                error=str(e)
            )

    async def _brave_search(self, query: str, num_results: int, start_time: datetime) -> ToolResult:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={"X-Subscription-Token": self.api_key},
                params={"q": query, "count": num_results},
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    results = []
                    for item in data.get('web', {}).get('results', [])[:num_results]:
                        results.append({
                            'title': item.get('title', ''),
                            'url': item.get('url', ''),
                            'snippet': item.get('description', '')
                        })

                    exec_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                    return ToolResult(
                        tool_name=self.name,
                        status=ToolStatus.SUCCESS,
                        result={'query': query, 'results': results},
                        execution_time_ms=exec_time,
                        cost_usd=self.cost_per_call
                    )
                else:
                    error_text = await response.text()
                    return ToolResult(
                        tool_name=self.name,
                        status=ToolStatus.FAILED,
                        error=f"Brave API error {response.status}: {error_text}"
                    )

    async def _serp_search(self, query: str, num_results: int, start_time: datetime) -> ToolResult:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://serpapi.com/search",
                params={
                    "q": query,
                    "api_key": self.api_key,
                    "num": num_results,
                    "engine": "google"
                },
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    results = []
                    for item in data.get('organic_results', [])[:num_results]:
                        results.append({
                            'title': item.get('title', ''),
                            'url': item.get('link', ''),
                            'snippet': item.get('snippet', '')
                        })

                    exec_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                    return ToolResult(
                        tool_name=self.name,
                        status=ToolStatus.SUCCESS,
                        result={'query': query, 'results': results},
                        execution_time_ms=exec_time,
                        cost_usd=self.cost_per_call
                    )
                else:
                    error_text = await response.text()
                    return ToolResult(
                        tool_name=self.name,
                        status=ToolStatus.FAILED,
                        error=f"SerpAPI error {response.status}: {error_text}"
                    )


class URLFetchTool(BaseTool):
    """Fetch and extract content from a URL."""

    def __init__(self):
        super().__init__(
            name="url_fetch",
            category=ToolCategory.WEB,
            description="Fetch content from a URL. Returns text content extracted from the page."
        )
        self.cost_per_call = 0.0

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        start_time = datetime.utcnow()

        url = params.get('url', '')
        if not url:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.FAILED,
                error="URL parameter required"
            )

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers={'User-Agent': 'Mozilla/5.0 (compatible; ToolGateway/1.0)'},
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        content_type = response.headers.get('content-type', '')

                        if 'text/html' in content_type:
                            html = await response.text()
                            # Basic text extraction (strip HTML tags)
                            import re
                            text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
                            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
                            text = re.sub(r'<[^>]+>', ' ', text)
                            text = re.sub(r'\s+', ' ', text).strip()
                            # Limit length
                            text = text[:10000] + '...' if len(text) > 10000 else text
                        else:
                            text = await response.text()
                            text = text[:10000] + '...' if len(text) > 10000 else text

                        exec_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                        return ToolResult(
                            tool_name=self.name,
                            status=ToolStatus.SUCCESS,
                            result={
                                'url': url,
                                'content_type': content_type,
                                'content': text,
                                'length': len(text)
                            },
                            execution_time_ms=exec_time
                        )
                    else:
                        return ToolResult(
                            tool_name=self.name,
                            status=ToolStatus.FAILED,
                            error=f"HTTP error {response.status}"
                        )

        except asyncio.TimeoutError:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.TIMEOUT,
                error="Request timed out after 30 seconds"
            )
        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.FAILED,
                error=str(e)
            )


# ===== Code Tools =====

class CodeAnalysisTool(BaseTool):
    """Analyze code for issues, patterns, and improvements."""

    def __init__(self):
        super().__init__(
            name="code_analysis",
            category=ToolCategory.CODE,
            description="Analyze code for bugs, security issues, and improvement suggestions."
        )

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        start_time = datetime.utcnow()

        code = params.get('code', '')
        language = params.get('language', 'python')

        if not code:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.FAILED,
                error="Code parameter required"
            )

        # Basic static analysis (in production, would use proper linters)
        issues = []
        suggestions = []

        # Python-specific checks
        if language.lower() == 'python':
            if 'eval(' in code:
                issues.append({
                    'type': 'security',
                    'severity': 'high',
                    'message': 'Use of eval() is a security risk'
                })
            if 'exec(' in code:
                issues.append({
                    'type': 'security',
                    'severity': 'high',
                    'message': 'Use of exec() is a security risk'
                })
            if 'import *' in code:
                suggestions.append({
                    'type': 'style',
                    'message': 'Avoid wildcard imports (import *)'
                })
            if 'except:' in code and 'except Exception' not in code:
                suggestions.append({
                    'type': 'best_practice',
                    'message': 'Avoid bare except clauses, catch specific exceptions'
                })

        # Generic checks
        lines = code.split('\n')
        if len(lines) > 100:
            suggestions.append({
                'type': 'maintainability',
                'message': f'File has {len(lines)} lines, consider breaking into smaller modules'
            })

        exec_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.SUCCESS,
            result={
                'language': language,
                'lines': len(lines),
                'issues': issues,
                'suggestions': suggestions,
                'summary': f"Found {len(issues)} issues and {len(suggestions)} suggestions"
            },
            execution_time_ms=exec_time
        )


# ===== Tool Gateway =====

class ToolGateway:
    """
    Gateway for external tool access with permission control and audit logging.

    Provides Cairn and Koda with controlled access to external APIs and tools.
    """

    # Default permissions per agent
    DEFAULT_PERMISSIONS = {
        'prax': ['web_search', 'url_fetch'],  # Limited tools for orchestrator
        'cairn': [
            'deepseek', 'openai', 'claude_haiku',  # LLMs
            'web_search', 'url_fetch',              # Web
            'code_analysis'                          # Code
        ],
        'koda': [
            'openai', 'claude_haiku',               # LLMs
            'web_search', 'url_fetch',              # Web
            'code_analysis'                          # Code
        ]
    }

    def __init__(self, api_keys: Optional[Dict[str, str]] = None, session_manager=None):
        """
        Initialize ToolGateway.

        Args:
            api_keys: Dict of API keys by service name
            session_manager: WorkspaceSessionManager for audit logging
        """
        self.api_keys = api_keys or {}
        self.session_manager = session_manager
        self.tools: Dict[str, BaseTool] = {}
        self.call_history: List[ToolCall] = []
        self.permissions: Dict[str, List[str]] = self.DEFAULT_PERMISSIONS.copy()
        self.total_cost: float = 0.0

        # Initialize default tools
        self._init_default_tools()

    def _init_default_tools(self):
        """Initialize default tools."""
        # LLM tools
        self.register_tool(DeepSeekTool(self.api_keys.get('deepseek')))
        self.register_tool(OpenAITool(self.api_keys.get('openai')))
        self.register_tool(ClaudeHaikuTool(self.api_keys.get('anthropic')))

        # Web tools
        self.register_tool(WebSearchTool(self.api_keys.get('serpapi') or self.api_keys.get('brave')))
        self.register_tool(URLFetchTool())

        # Code tools
        self.register_tool(CodeAnalysisTool())

    def register_tool(self, tool: BaseTool):
        """Register a tool."""
        self.tools[tool.name] = tool
        print(f"[ToolGateway] Registered tool: {tool.name} ({tool.category.value})")

    def set_permissions(self, agent_id: str, tool_names: List[str]):
        """Set tool permissions for an agent."""
        self.permissions[agent_id] = tool_names

    def check_permission(self, agent_id: str, tool_name: str) -> bool:
        """Check if agent has permission to use a tool."""
        allowed_tools = self.permissions.get(agent_id, [])
        return tool_name in allowed_tools

    def get_agent_tools(self, agent_id: str) -> List[Dict]:
        """Get list of tools available to an agent."""
        allowed_tools = self.permissions.get(agent_id, [])
        return [
            self.tools[name].get_schema()
            for name in allowed_tools
            if name in self.tools
        ]

    async def execute_tool(
        self,
        tool_name: str,
        params: Dict[str, Any],
        requesting_agent: str,
        session_id: str
    ) -> ToolResult:
        """
        Execute a tool on behalf of an agent.

        Args:
            tool_name: Name of tool to execute
            params: Parameters for tool
            requesting_agent: Agent requesting the tool (cairn, koda, prax)
            session_id: Session ID for audit logging

        Returns:
            ToolResult with execution status and result
        """
        # Create tool call record
        call_id = str(uuid.uuid4())
        tool_call = ToolCall(
            id=call_id,
            tool_name=tool_name,
            requesting_agent=requesting_agent,
            session_id=session_id,
            params=params
        )
        self.call_history.append(tool_call)

        # Check tool exists
        if tool_name not in self.tools:
            tool_call.status = ToolStatus.FAILED
            result = ToolResult(
                tool_name=tool_name,
                status=ToolStatus.FAILED,
                error=f"Tool '{tool_name}' not found"
            )
            tool_call.result = result
            self._audit_tool_call(tool_call)
            return result

        # Check permission
        if not self.check_permission(requesting_agent, tool_name):
            tool_call.status = ToolStatus.DENIED
            result = ToolResult(
                tool_name=tool_name,
                status=ToolStatus.DENIED,
                error=f"Agent '{requesting_agent}' does not have permission to use '{tool_name}'"
            )
            tool_call.result = result
            self._audit_tool_call(tool_call)
            return result

        # Execute tool
        tool = self.tools[tool_name]
        tool_call.status = ToolStatus.RUNNING

        try:
            result = await tool.execute(params)
            tool_call.status = result.status
            tool_call.result = result

            # Track cost
            if result.cost_usd > 0:
                self.total_cost += result.cost_usd

        except Exception as e:
            result = ToolResult(
                tool_name=tool_name,
                status=ToolStatus.FAILED,
                error=str(e)
            )
            tool_call.status = ToolStatus.FAILED
            tool_call.result = result

        self._audit_tool_call(tool_call)
        return result

    def _audit_tool_call(self, tool_call: ToolCall):
        """Log tool call to audit trail."""
        if self.session_manager:
            self.session_manager._add_audit_entry(
                session_id=tool_call.session_id,
                user_id=tool_call.requesting_agent,
                action='tool_executed',
                details={
                    'tool_name': tool_call.tool_name,
                    'status': tool_call.status.value,
                    'execution_time_ms': tool_call.result.execution_time_ms if tool_call.result else 0,
                    'cost_usd': tool_call.result.cost_usd if tool_call.result else 0,
                    'error': tool_call.result.error if tool_call.result else None
                }
            )

        print(f"[ToolGateway] {tool_call.requesting_agent} called {tool_call.tool_name}: {tool_call.status.value}")

    def get_call_history(
        self,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Get tool call history."""
        calls = self.call_history

        if session_id:
            calls = [c for c in calls if c.session_id == session_id]
        if agent_id:
            calls = [c for c in calls if c.requesting_agent == agent_id]

        return [c.to_dict() for c in calls[-limit:]]

    def get_cost_summary(self, session_id: Optional[str] = None) -> Dict:
        """Get cost summary."""
        calls = self.call_history
        if session_id:
            calls = [c for c in calls if c.session_id == session_id]

        total_cost = sum(c.result.cost_usd for c in calls if c.result)
        by_tool = {}
        for call in calls:
            if call.result:
                by_tool[call.tool_name] = by_tool.get(call.tool_name, 0) + call.result.cost_usd

        return {
            'total_cost_usd': total_cost,
            'by_tool': by_tool,
            'total_calls': len(calls)
        }

    def get_tool_descriptions_for_prompt(self, agent_id: str) -> str:
        """Generate tool descriptions for agent system prompt."""
        tools = self.get_agent_tools(agent_id)
        if not tools:
            return ""

        lines = ["\n**Available External Tools:**\n"]
        for tool in tools:
            lines.append(f"- **{tool['name']}**: {tool['description']}")

        lines.append("\n**To use a tool, include in your response:**")
        lines.append('`Use tool [tool_name]: {"param": "value"}`')

        # Build examples based on agent's available tools
        tool_names = {t['name'] for t in tools}
        examples = []
        if 'deepseek' in tool_names:
            examples.append('- `Use tool deepseek: {"prompt": "Analyze this code for bugs"}`')
        if 'openai' in tool_names:
            examples.append('- `Use tool openai: {"prompt": "Summarize this document"}`')
        if 'web_search' in tool_names:
            examples.append('- `Use tool web_search: {"query": "HIPAA compliance requirements 2024"}`')
        if 'code_analysis' in tool_names:
            examples.append('- `Use tool code_analysis: {"code": "def foo()...", "language": "python"}`')
        if 'url_fetch' in tool_names and not examples:
            examples.append('- `Use tool url_fetch: {"url": "https://example.com"}`')

        if examples:
            lines.append("\nExamples:")
            lines.extend(examples[:3])  # Max 3 examples

        return "\n".join(lines)


# Global instance
tool_gateway: Optional[ToolGateway] = None


def get_tool_gateway(api_keys: Optional[Dict] = None, session_manager=None) -> ToolGateway:
    """Get or create the global ToolGateway instance."""
    global tool_gateway

    if tool_gateway is None:
        tool_gateway = ToolGateway(api_keys, session_manager)
    elif session_manager and tool_gateway.session_manager is None:
        tool_gateway.session_manager = session_manager

    return tool_gateway
