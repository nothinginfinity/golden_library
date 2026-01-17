#!/usr/bin/env python3
"""
Agent Orchestrator - Manages multiple Claude agents for collaborative workspace

Handles 3 concurrent agents:
- Agent A (Koda/Cairn) - Works on Document A
- Agent B (Koda/Cairn) - Works on Document B
- Moderator (Prax) - Coordinates both agents

Each agent maintains its own conversation context and can stream responses.
"""

import anthropic
from typing import Dict, List, Optional, Iterator, Any
import os
import json


class AgentOrchestrator:
    """Orchestrates multiple Claude agents for collaborative workspace."""

    def __init__(self, api_key: Optional[str] = None, session_users: Optional[Dict] = None):
        """
        Initialize orchestrator with API key.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var or ~/.claude/api_keys.json)
            session_users: Dict of users in the collaborative session (user_id -> User object)
        """
        # Try to get API key from multiple sources
        if api_key:
            self.api_key = api_key
        elif os.environ.get('ANTHROPIC_API_KEY'):
            self.api_key = os.environ.get('ANTHROPIC_API_KEY')
        else:
            # Try to load from api_keys.json
            api_keys_file = os.path.expanduser('~/.claude/api_keys.json')
            if os.path.exists(api_keys_file):
                try:
                    with open(api_keys_file, 'r') as f:
                        keys = json.load(f)
                    self.api_key = keys.get('claude')
                except Exception as e:
                    print(f"Warning: Could not load API keys from {api_keys_file}: {e}")
                    self.api_key = None
            else:
                self.api_key = None

        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not found. Please set it via:\n"
                "1. Environment variable: export ANTHROPIC_API_KEY='your-key'\n"
                "2. Dashboard Config tab: Save your API key there\n"
                "3. Pass directly to AgentOrchestrator(api_key='your-key')"
            )

        self.client = anthropic.Anthropic(api_key=self.api_key)

        # Store session users for collaborative context
        self.session_users = session_users or {}

        # Initialize 3 agents with separate contexts
        self.agents = {
            'a': {
                'role': 'koda',  # Default role, can be changed
                'context': [],
                'model': 'claude-sonnet-4-20250514',
                'status': 'idle',
                'document': None
            },
            'b': {
                'role': 'cairn',  # Default role, can be changed
                'context': [],
                'model': 'claude-sonnet-4-20250514',
                'status': 'idle',
                'document': None
            },
            'moderator': {
                'role': 'prax',
                'context': [],
                'model': 'claude-sonnet-4-20250514',
                'status': 'idle',
                'document': None
            }
        }

    def update_session_users(self, session_users: Dict):
        """
        Update the session users for collaborative context.

        Args:
            session_users: Dict of users in the session (user_id -> User object)
        """
        self.session_users = session_users

    def set_agent_role(self, agent_id: str, role: str):
        """
        Set the role for a specific agent.

        Args:
            agent_id: Agent identifier ('a', 'b', or 'moderator')
            role: Role name ('koda', 'cairn', 'prax', etc.)
        """
        if agent_id in self.agents:
            self.agents[agent_id]['role'] = role

    def load_document(self, agent_id: str, document: str):
        """
        Load a document into an agent's context.

        Args:
            agent_id: Agent identifier ('a', 'b', or 'moderator')
            document: Document content (markdown, code, etc.)
        """
        if agent_id not in self.agents:
            raise ValueError(f"Invalid agent_id: {agent_id}")

        agent = self.agents[agent_id]

        # Store document reference
        agent['document'] = document

        # Add document to context if context is empty
        # (only add once at the start)
        if len(agent['context']) == 0:
            agent['context'].append({
                'role': 'user',
                'content': f'[Document loaded]\n\n{document}'
            })

    def send_message(
        self,
        agent_id: str,
        message: str,
        max_tokens: int = 4000,
        sender_user_id: Optional[str] = None
    ) -> Iterator[str]:
        """
        Send a message to a specific agent and stream the response.

        Args:
            agent_id: Agent identifier ('a', 'b', or 'moderator')
            message: User message/prompt
            max_tokens: Maximum tokens for response
            sender_user_id: ID of user sending the message (for collaborative context)

        Yields:
            Response chunks as they arrive
        """
        if agent_id not in self.agents:
            raise ValueError(f"Invalid agent_id: {agent_id}")

        agent = self.agents[agent_id]
        agent['status'] = 'thinking'

        # Add user message to context
        agent['context'].append({
            'role': 'user',
            'content': message
        })

        # Build system prompt based on role (with collaborative context)
        system_prompt = self._build_system_prompt(agent['role'], sender_user_id)

        try:
            # Stream response from Claude
            with self.client.messages.stream(
                model=agent['model'],
                max_tokens=max_tokens,
                system=system_prompt,
                messages=agent['context']
            ) as stream:
                agent['status'] = 'responding'

                full_response = []
                for text in stream.text_stream:
                    full_response.append(text)
                    yield text

                # Save complete assistant response to context
                agent['context'].append({
                    'role': 'assistant',
                    'content': ''.join(full_response)
                })

                agent['status'] = 'idle'

        except Exception as e:
            agent['status'] = 'error'
            yield f"[ERROR] {str(e)}"

    def coordinate(
        self,
        instruction: str,
        max_tokens: int = 4000
    ) -> Dict[str, Any]:
        """
        Moderator coordinates both agents with a single instruction.

        Args:
            instruction: Coordination instruction from user
                Example: "Agent A: analyze X. Agent B: analyze Y. Then synthesize."
            max_tokens: Maximum tokens per response

        Returns:
            Dict with moderator response and any agent responses
        """
        # For Phase 1 (MVP), send instruction to moderator
        # Moderator will decide what to ask agents A and B

        moderator_response = list(self.send_message('moderator', instruction, max_tokens))

        # TODO: Parse moderator response and route to agents A/B
        # For now, just return moderator response

        return {
            'moderator': ''.join(moderator_response),
            'agent_a': None,  # Will implement in future
            'agent_b': None
        }

    def get_context(self, agent_id: str) -> List[Dict[str, str]]:
        """
        Get the full conversation context for an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            List of message dicts with 'role' and 'content'
        """
        if agent_id not in self.agents:
            raise ValueError(f"Invalid agent_id: {agent_id}")

        return self.agents[agent_id]['context']

    def get_status(self, agent_id: str) -> str:
        """
        Get current status of an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            Status string: 'idle', 'thinking', 'responding', or 'error'
        """
        if agent_id not in self.agents:
            raise ValueError(f"Invalid agent_id: {agent_id}")

        return self.agents[agent_id]['status']

    def clear_context(self, agent_id: str):
        """
        Clear an agent's conversation context.

        Args:
            agent_id: Agent identifier
        """
        if agent_id not in self.agents:
            raise ValueError(f"Invalid agent_id: {agent_id}")

        self.agents[agent_id]['context'] = []
        self.agents[agent_id]['status'] = 'idle'

        # Re-add document if it exists
        if self.agents[agent_id]['document']:
            doc = self.agents[agent_id]['document']
            self.agents[agent_id]['context'].append({
                'role': 'user',
                'content': f'[Document loaded]\n\n{doc}'
            })

    def _build_system_prompt(self, role: str, sender_user_id: Optional[str] = None) -> str:
        """
        Build system prompt based on agent role.

        Args:
            role: Agent role (koda, cairn, prax, etc.)
            sender_user_id: ID of user sending the current message

        Returns:
            System prompt string
        """
        base_prompt = "You are a helpful AI assistant working in a collaborative workspace."

        # Add collaborative session context if we have session users
        if self.session_users:
            user_list = []
            sender_name = None
            for uid, user in self.session_users.items():
                user_data = user if isinstance(user, dict) else user.to_dict()
                name = user_data.get('name', 'Unknown')
                user_role = user_data.get('role', 'unknown')

                if uid == sender_user_id:
                    sender_name = name
                    user_list.append(f"- {name} ({user_role}) ← sending the current message")
                else:
                    user_list.append(f"- {name} ({user_role})")

            users_context = "\n".join(user_list)

            collab_context = f"""
COLLABORATIVE SESSION CONTEXT:
You are in a collaborative workspace with {len(self.session_users)} user(s):
{users_context}

IMPORTANT: When responding to messages, you can distinguish between users by their names. Address them directly when appropriate. Be aware that multiple people may be working together in this session."""

            if sender_name:
                collab_context += f"\n\nThe current message is from {sender_name}."

            base_prompt += "\n\n" + collab_context

        role_prompts = {
            'koda': """

You are Koda, the Builder agent. Your focus is on implementation, coding, and building.
- Provide working code and practical solutions
- Be direct and results-oriented
- Test after building
- Report blockers clearly
""",
            'cairn': """

You are Cairn, the Architect agent. Your focus is on design, architecture, and specifications.
- Think systematically about structure and patterns
- Design before building
- Document decisions with rationale
- Review implementations for issues
""",
            'prax': """

You are Prax, the Orchestrator agent. Your focus is on coordination and strategy.
- Coordinate between multiple agents and users
- Make strategic decisions
- Think about the big picture
- Track progress across workstreams
- Help facilitate collaboration between different users
""",
        }

        return base_prompt + "\n\n" + role_prompts.get(role, base_prompt)

    def export_session(self) -> Dict[str, Any]:
        """
        Export full session state (all agent contexts).

        Returns:
            Dict with all agent contexts and metadata
        """
        return {
            'agents': {
                agent_id: {
                    'role': agent['role'],
                    'context': agent['context'],
                    'status': agent['status'],
                    'document': agent['document']
                }
                for agent_id, agent in self.agents.items()
            }
        }

    def import_session(self, session_data: Dict[str, Any]):
        """
        Import session state from exported data.

        Args:
            session_data: Session data from export_session()
        """
        if 'agents' in session_data:
            for agent_id, data in session_data['agents'].items():
                if agent_id in self.agents:
                    self.agents[agent_id].update(data)


# Example usage and testing
if __name__ == '__main__':
    """
    Test the orchestrator with a simple conversation.
    """
    import sys

    # Check for API key
    if not os.environ.get('ANTHROPIC_API_KEY'):
        print("Error: ANTHROPIC_API_KEY not set")
        print("Set it with: export ANTHROPIC_API_KEY='your-key-here'")
        sys.exit(1)

    # Create orchestrator
    print("Creating orchestrator...")
    orchestrator = AgentOrchestrator()

    # Test Agent A
    print("\n--- Testing Agent A (Koda) ---")
    print("Sending message: 'Hello, what's your role?'")

    for chunk in orchestrator.send_message('a', "Hello, what's your role?"):
        print(chunk, end='', flush=True)

    print("\n\n--- Agent A Status ---")
    print(f"Status: {orchestrator.get_status('a')}")
    print(f"Context length: {len(orchestrator.get_context('a'))} messages")

    # Test document loading
    print("\n--- Testing Document Loading ---")
    sample_doc = """
# Sample Document

This is a sample document for testing.

## Features
- Feature 1
- Feature 2
"""

    orchestrator.load_document('b', sample_doc)
    print("Document loaded into Agent B")

    print("\n--- Testing Agent B (Cairn) ---")
    print("Sending message: 'Summarize the document'")

    for chunk in orchestrator.send_message('b', "Summarize the document"):
        print(chunk, end='', flush=True)

    print("\n\n--- Session Export ---")
    session = orchestrator.export_session()
    print(f"Exported session with {len(session['agents'])} agents")
    print(json.dumps({k: {'context_length': len(v['context'])} for k, v in session['agents'].items()}, indent=2))
